"""Sequences for use by ABU."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from core_modules import measurement_config as limits
from utility_modules import background_checks as bg
from utility_modules import tc
from utility_modules.send_cmd import cmd_repeat as repeat

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")
_scan_quiet = threading.Event()


class _ScanLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _scan_quiet.is_set() or record.levelno >= logging.ERROR


_scan_log_filter = _ScanLogFilter()
event_log.addFilter(_scan_log_filter)
info_log.addFilter(_scan_log_filter)

# ----Constants Setup-------------------------------------------------------------------------------

# Binary chop parameters
SWIR_BINARY_CHOP_LOCATION = 9600
SWIR_BINARY_CHOP_TARGET = 5250
MWIR_BINARY_CHOP_LOCATION = 8000
MWIR_BINARY_CHOP_TARGET = 25300

# ----Helper Functions------------------------------------------------------------------------------


def _run_with_port_lock(port_lock: Any, func, *args, **kwargs):
    """Run an operation under the shared port lock when one is supplied.

    Kept transaction-scoped (never around a whole scan/movement loop) so the
    shared serial port stays available to other threads between operations.
    """
    if port_lock is None:
        return func(*args, **kwargs)
    with port_lock:
        return func(*args, **kwargs)


def _run_transaction(worker: Any, port_lock: Any, func, *args, **kwargs):
    bg.gate_script_control()
    if worker is not None:
        return worker.call(func, *args[1:], **kwargs)
    return _run_with_port_lock(port_lock, func, *args, **kwargs)


def _run_with_failure_popup(on_failure: Callable[..., bool] | None, failure_label: str, func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        if on_failure is not None and on_failure(failure_label, [str(exc)]):
            return None
        raise


def find_dac_offset(
    port: Any,
    sensor_name: str,
    target_output: int,
    fixed_offset: int,
    max_miss: int = 1600,
    port_lock: Any = None,
    worker: Any = None,
) -> int:
    """Perform binary chop on a DAC offset.

    This function tries to find a DAC offset which results in a high gain output close
    to the value or target_output. The sensor that's *not* being configured has its gain
    value set to fixed_offset, while binary chop is used to find a suitable offset for
    the sensor that *is* being configured.

    The offset is returned, and the instrument is left configured with that offset.

    :param port: The serial port for comms with the instrument
    :param sensor_name: "MWIR" or "SWIR" - which sensor we're calibrating
    :param target_output: The output value we're aiming for
    :param fixed_offset: The fixed value that the other sensor will take during the chop.
    :param max_miss: If the final value is more than this distance from the target output, report a problem.
    :return: The DAC offset that gives an output closest to the target value.
    """
    event_log.info(f"Running abu find_dac_offset for {sensor_name} with target value {target_output}")

    if sensor_name not in ("MWIR", "SWIR"):
        event_log.error(f"For DAC offsets, sensor name must be either MWIR or SWIR, not {sensor_name}")

    # Check detector powered, if not enable.
    hk = bg.request_hk(
        port,
        "find_dac_offset power check",
        port_lock=port_lock,
        transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
    )
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        _run_transaction(worker, port_lock, repeat, port, tc.power_control, hk.PWR_STAT | 0x02)

    dac_value = 0x0
    bit_value = 1 << 11
    reading = 0

    # Binary chop - work down through the bits, homing in on
    # the DAC offset value which gets closest to the target output.
    while bit_value != 0:
        # Make a test value with the current bit set.
        test_value = dac_value | bit_value

        event_log.info(f"Setting the {sensor_name} DAC offset value to: {test_value}")

        if sensor_name == "MWIR":
            swir_offset, mwir_offset = fixed_offset, test_value
        else:
            swir_offset, mwir_offset = test_value, fixed_offset

        _run_transaction(worker, port_lock, repeat, port, tc.sci_offset, swir_offset, mwir_offset)
        sci = bg.request_science(
            port,
            f"{sensor_name} DAC offset {test_value}",
            port_lock=port_lock,
            transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
        )

        if sensor_name == "MWIR":
            if sci.MWIR_OFFSET != test_value:
                event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {test_value}")
            reading = sci.MWIR_HIGH
        else:
            if sci.SWIR_OFFSET != test_value:
                event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}, Expected: {test_value}")
            reading = sci.SWIR_HIGH

        event_log.info(f"Got the following {sensor_name} high reading: {reading}")

        # If the HIGH reading is >= target_output, keep the bit, otherwise discard.
        if reading >= target_output:
            dac_value = test_value

        bit_value >>= 1

    if abs(reading - target_output) <= max_miss:
        event_log.info(f"Suitable {sensor_name} offset found for target {target_output}.")
    else:
        event_log.error(f"No in-range {sensor_name} offset found for target {target_output}.")

    event_log.info(f"Final {sensor_name} DAC offset value: {dac_value}")
    event_log.info(f"Final {sensor_name} high reading: {reading}")
    return dac_value


def choose_dac_offsets(
    port: Any,
    port_lock: Any = None,
    worker: Any = None,
    *,
    on_failure: Callable[..., bool] | None = None,
    notify_negative: Callable[[str], Any] | None = None,
    notify_positive: Callable[[str], Any] | None = None,
) -> tuple[int, int]:
    """Select SWIR and MWIR DAC offsets using the default locations and targets."""
    # Motor parameters are already nominal by the time this runs in the OB flow.
    checks = bg.CommandChecks(
        port,
        port_lock=port_lock,
        transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
        last_power=3,
        last_motor_params=limits.MOTOR_NOMINAL_PARAMS,
    )

    # SWIR binary chop
    checks.move_to_absolute_position(SWIR_BINARY_CHOP_LOCATION, label="SWIR DAC chop position")
    swir_offset = find_dac_offset(port, "SWIR", SWIR_BINARY_CHOP_TARGET, 1, port_lock=port_lock, worker=worker)
    event_log.info(f"SWIR offset = {swir_offset}")

    # MWIR binary chop.
    checks.move_to_absolute_position(MWIR_BINARY_CHOP_LOCATION, label="MWIR DAC chop position")
    mwir_offset = find_dac_offset(
        port, "MWIR", MWIR_BINARY_CHOP_TARGET, swir_offset, port_lock=port_lock, worker=worker
    )
    event_log.info(f"MWIR offset = {mwir_offset}")

    errors = []
    for sensor, value in (("SWIR", swir_offset), ("MWIR", mwir_offset)):
        low, high = limits.SCI_DAC_OFFSET_LIMITS[sensor]
        if not low <= value <= high:
            errors.append(f"{sensor} DAC offset {value} is outside the calibrated range {low}..{high}")
    bg.report_check(
        "SCI DAC offset selection",
        errors,
        on_failure=on_failure,
        notify_negative=notify_negative,
        notify_positive=notify_positive,
    )

    _run_transaction(worker, port_lock, repeat, port, tc.sci_offset, swir_offset, mwir_offset)
    verify_dac_offset(
        port,
        port_lock=port_lock,
        worker=worker,
        expected_swir_offset=swir_offset,
        expected_mwir_offset=mwir_offset,
        on_failure=on_failure,
        notify_negative=notify_negative,
        notify_positive=notify_positive,
    )
    return swir_offset, mwir_offset


def _scan_step(port: Any, steps: int, port_lock: Any, checks: bg.CommandChecks, worker: Any = None) -> None:
    """Move (if needed) and take a science + HK reading at the resulting position."""
    if steps != 0:
        command = tc.mtr_mov_neg if steps < 0 else tc.mtr_mov_pos
        _run_transaction(worker, port_lock, repeat, port, command, abs(steps))
        time.sleep(0.45)
    else:
        event_log.info("No need to move any steps, proceeding to measurement")

    runner = (lambda func, *args: worker.call(func, *args)) if worker is not None else None
    sci = bg.request_science(port, "measurement scan step science", port_lock=port_lock, transaction_runner=runner)
    hk_tm = bg.request_hk(port, "measurement scan step hk", port_lock=port_lock, transaction_runner=runner)
    event_log.debug(
        f"ABS_STEPS: {sci.MTR_ABS_STEPS:04d}" + f"   HK_ABS_STEPS: {hk_tm.MTR_ABS_STEPS:04d}"
        f"   SWIR_OFFSET: {sci.SWIR_OFFSET:04d}"
        + f"   MWIR_OFFSET: {sci.MWIR_OFFSET:04d}"
        + f"\t\t SW_L: {sci.SWIR_LOW:04d}"
        + f"   SW_M: {sci.SWIR_MED:04d}"
        + f"   SW_H: {sci.SWIR_HIGH:04d}"
        + f"\t MW_L: {sci.MWIR_LOW:04d}"
        + f"   MW_M: {sci.MWIR_MED:04d}"
        + f"   MW_HH: {sci.MWIR_HIGH:04d}"
        + f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}"
        + f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}"
    )


def measurement_scan(
    port: Any,
    step_spacing: int = 30,
    port_lock: Any = None,
    worker: Any = None,
    on_failure: Callable[..., bool] | None = None,
) -> None:
    """Perform a basic Enfys science measurement scan.

    Uses the same command primitives as the OB background checks (CommandChecks
    for homing/movement, request_hk/request_science for telemetry) so this scan
    is serialized against the shared port_lock the same way as the rest of the
    OB qualification flow, rather than issuing raw commands of its own.

    Homes and Calibrates to Base
    Goes to the Outer
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    Halts once Base Stop is reached
    """
    event_log.info("Running ABU Measurement Scan")
    event_level = event_log.level
    info_level = info_log.level
    _scan_quiet.set()
    event_log.setLevel(logging.WARNING)
    info_log.setLevel(logging.ERROR)
    try:
        # Motor parameters are already nominal by the time this runs in the OB flow.
        checks = bg.CommandChecks(
            port,
            port_lock=port_lock,
            transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
            last_power=3,
            last_motor_params=limits.MOTOR_NOMINAL_PARAMS,
        )

        # Cal to Base
        _run_with_failure_popup(
            on_failure,
            "measurement scan cal to base",
            checks.home,
            calibration=True,
            outer=False,
            label="measurement scan cal to base",
        )

        # Home to Outer
        _run_with_failure_popup(
            on_failure,
            "measurement scan home to outer",
            checks.home,
            calibration=False,
            outer=True,
            label="measurement scan home to outer",
        )

        # Measurement sequence
        event_log.warning("Starting Science Measurements")
        _run_with_failure_popup(on_failure, "measurement scan initial step", _scan_step, port, 0, port_lock, checks, worker)
        for _ in range(0, 8900, step_spacing):
            _run_with_failure_popup(
                on_failure,
                "measurement scan step",
                _scan_step,
                port,
                step_spacing,
                port_lock,
                checks,
                worker,
            )

        event_log.warning("Science Measurements Completed!!")
    finally:
        _scan_quiet.clear()
        event_log.setLevel(event_level)
        info_log.setLevel(info_level)


def measurement_scan_async(
    port: Any,
    *,
    step_spacing: int = 30,
    daemon: bool = True,
    port_lock: Any = None,
    worker: Any = None,
) -> threading.Thread:
    """Launch a science scan in a background thread while respecting the shared serial lock."""
    thread = threading.Thread(
        target=measurement_scan,
        args=(port,),
        kwargs={
            "step_spacing": step_spacing,
            "port_lock": port_lock,
            **({"worker": worker} if worker is not None else {}),
        },
        daemon=daemon,
    )
    thread.start()
    return thread

def _check_reported_dac_offsets(
    response: Any,
    source: str,
    errors: list[str],
    expected_swir_offset: int | None = None,
    expected_mwir_offset: int | None = None,
) -> None:
    for sensor, expected in (("SWIR", expected_swir_offset), ("MWIR", expected_mwir_offset)):
        field = f"{sensor}_OFFSET"
        raw_value = getattr(response, field, None)
        low, high = limits.SCI_DAC_OFFSET_LIMITS[sensor]
        if raw_value is None:
            errors.append(f"{source} {field} is missing or invalid: {raw_value!r}")
            continue
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            errors.append(f"{source} {field} is missing or invalid: {raw_value!r}")
            continue
        if not low <= value <= high:
            errors.append(f"{source} {field}={value} is outside the calibrated range {low}..{high}")
        if expected is not None and value != expected:
            errors.append(f"{source} {field}={value}, expected applied offset {expected}")


def verify_dac_offset(
    port: Any,
    port_lock: Any = None,
    worker: Any = None,
    *,
    expected_swir_offset: int | None = None,
    expected_mwir_offset: int | None = None,
    on_failure: Callable[..., bool] | None = None,
    notify_negative: Callable[[str], Any] | None = None,
    notify_positive: Callable[[str], Any] | None = None,
) -> Any:
    """Verify the applied calibration offsets in both SCI and HK telemetry."""
    runner = (lambda func, *args: worker.call(func, *args)) if worker is not None else None
    sci = bg.request_science(port, "SCI DAC offset verification", port_lock=port_lock, transaction_runner=runner)
    hk_tm = bg.request_hk(port, "SCI DAC offset HK verification", port_lock=port_lock, transaction_runner=runner)
    errors: list[str] = []
    for source, response in (("SCI", sci), ("HK", hk_tm)):
        _check_reported_dac_offsets(
            response,
            source,
            errors,
            expected_swir_offset,
            expected_mwir_offset,
        )
    bg.report_check(
        "SCI DAC offset",
        errors,
        on_failure=on_failure,
        notify_negative=notify_negative,
        notify_positive=notify_positive,
    )
    event_log.debug(
        "Verified SCI DAC offsets SWIR=%s MWIR=%s; HIGH channels SWIR=%s MWIR=%s",
        sci.SWIR_OFFSET,
        sci.MWIR_OFFSET,
        sci.SWIR_HIGH,
        sci.MWIR_HIGH,
    )
    return sci


def verify_sci_readings(
    port: Any,
    port_lock: Any = None,
    worker: Any = None,
    *,
    expected_swir_offset: int | None = None,
    expected_mwir_offset: int | None = None,
    on_failure: Callable[..., bool] | None = None,
    notify_negative: Callable[[str], Any] | None = None,
    notify_positive: Callable[[str], Any] | None = None,
) -> list[Any]:
    """Verify five SCI samples one second apart against offset and HIGH-DN limits."""
    runner = (lambda func, *args: worker.call(func, *args)) if worker is not None else None
    readings = []
    errors: list[str] = []
    swir_offset = expected_swir_offset
    mwir_offset = expected_mwir_offset

    for sample_number in range(1, 6):
        sci = bg.request_science(
            port,
            f"SCI gain verification sample {sample_number}/5",
            port_lock=port_lock,
            transaction_runner=runner,
        )
        if swir_offset is None:
            swir_offset = getattr(sci, "SWIR_OFFSET", None)
        if mwir_offset is None:
            mwir_offset = getattr(sci, "MWIR_OFFSET", None)
        _check_reported_dac_offsets(sci, f"SCI sample {sample_number}", errors, swir_offset, mwir_offset)

        for field, (low, high) in limits.SCI_HIGH_GAIN_DN_LIMITS.items():
            value = getattr(sci, field, None)
            if value is None:
                errors.append(f"SCI sample {sample_number} {field} is missing or invalid: {value!r}")
                continue
            try:
                numeric_value = int(value)
            except (TypeError, ValueError):
                errors.append(f"SCI sample {sample_number} {field} is missing or invalid: {value!r}")
                continue
            if not low <= numeric_value <= high:
                errors.append(f"SCI sample {sample_number} {field}={numeric_value} is outside {low}..{high} DN")
        readings.append(sci)
        if sample_number < 5:
            bg.gate_script_control()
            time.sleep(1.0)

    bg.report_check(
        "SCI gain-channel readings",
        errors,
        on_failure=on_failure,
        notify_negative=notify_negative,
        notify_positive=notify_positive,
    )
    return readings