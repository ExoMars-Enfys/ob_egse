"""Sequences for use by ABU."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from core_modules import config
from core_modules import measurement_config as limits
from scripts_modules import sequences as sq
from utility_modules import background_checks as bg
from utility_modules import tc
from utility_modules.send_cmd import cmd_repeat as repeat

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")

# ----Constants Setup-------------------------------------------------------------------------------

# Binary chop parameters
SWIR_BINARY_CHOP_LOCATION = 9600
MWIR_BINARY_CHOP_LOCATION = 8000

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


# Direct copies of abu_sequences.mwir_binary_chop / swir_binary_chop; only the serial access is
# routed through the OB FFT worker/port lock.
def _enable_detector(port: Any, port_lock: Any, worker: Any) -> None:
    # Check detector powered, if not enable.
    hk = _run_transaction(worker, port_lock, tc.hk_request, port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        _run_transaction(worker, port_lock, repeat, port, tc.power_control, hk.PWR_STAT | 0x02)


def mwir_binary_chop(port, swir_fixed=2048, sci_adc_samp=4, sci_adc_skip=2, port_lock: Any = None, worker: Any = None):
    """
    This fixes the SWIR DAC offset as per the functional call.
    It then itterates throgh the MWIR DAC offsets doing a binary search.
    The function aims for the science readings for the MWIR to be between the values set within the
    constants file.
    """
    event_log.info("Running abu mwir_binary_chop")

    _enable_detector(port, port_lock, worker)

    mwir_value = 0x0  # Seed value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        mwir_delta = 0x1 << (i - 1)
        event_log.info(f"Setting the MWIR Value to: {mwir_value + mwir_delta}")
        _run_transaction(worker, port_lock, repeat, port, tc.sci_offset, swir_fixed, mwir_value + mwir_delta)
        sci = _run_transaction(worker, port_lock, sq.check_sci, port, sci_adc_samp, sci_adc_skip)
        if sci.MWIR_OFFSET != (mwir_value + mwir_delta):
            event_log.error(
                f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {mwir_value + mwir_delta}"
            )

        event_log.info(f"Got the following MWIR High Reading: {sci.MWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.MWIR_HIGH >= config.MWIR_DAC_MIN_TH:
            mwir_value = mwir_value + mwir_delta

        # Check if we are within the range (we are done) otherwise loop
        if config.MWIR_DAC_MIN_TH <= sci.MWIR_HIGH <= config.MWIR_DAC_MAX_TH:
            event_log.info("MWIR offset in threshold finished!")
            event_log.info(f"Final MWIR value: {mwir_value}")
            return mwir_value

    event_log.error(f"No solution found. Last MWIR Offset set to: {sci.MWIR_OFFSET}")
    return sci.MWIR_OFFSET


def swir_binary_chop(port, mwir_fixed=2048, sci_adc_samp=4, sci_adc_skip=2, port_lock: Any = None, worker: Any = None):
    """
    This sets the MWIR DAC offset as per the functional call.
    It then itterates throgh the SWIR DAC offsets doing a binary search.
    The function aims for the science readings for the SWIR to be between the values set within the
    constants file.
    """
    event_log.info("Running abu swir_binary_chop")

    _enable_detector(port, port_lock, worker)

    swir_value = 0x0  # Seed Value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        swir_delta = 0x1 << (i - 1)
        event_log.info(f"Setting the SWIR value to: {swir_value + swir_delta}")
        _run_transaction(worker, port_lock, repeat, port, tc.sci_offset, swir_value + swir_delta, mwir_fixed)
        sci = _run_transaction(worker, port_lock, sq.check_sci, port, sci_adc_samp, sci_adc_skip)
        if sci.SWIR_OFFSET != (swir_value + swir_delta):
            event_log.error(
                f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}, Expected: {swir_value + swir_delta}"
            )

        event_log.info(f"Got the following SWIR High Reading: {sci.SWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.SWIR_HIGH > config.SWIR_DAC_MIN_TH:
            swir_value = swir_value + swir_delta

        # Check if we are within the range (we are done) otherwise loop
        if config.SWIR_DAC_MIN_TH <= sci.SWIR_HIGH <= config.SWIR_DAC_MAX_TH:
            event_log.info("SWIR offset in threshold finished!")
            event_log.info(f"Final SWIR value: {swir_value}")
            return swir_value

    event_log.error(f"No solution found. Last MWIR Offset set to: {sci.SWIR_OFFSET}")
    return sci.SWIR_OFFSET


def choose_dac_offsets(port: Any, port_lock: Any = None, worker: Any = None) -> None:
    """Select SWIR and MWIR DAC offsets using the ABU window method at the default chop locations."""
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
    swir_offset = swir_binary_chop(port, port_lock=port_lock, worker=worker)
    event_log.info(f"SWIR offset = {swir_offset}")

    # MWIR binary chop.
    checks.move_to_absolute_position(MWIR_BINARY_CHOP_LOCATION, label="MWIR DAC chop position")
    # Hold SWIR at its chosen offset so both chosen offsets remain applied afterwards.
    mwir_offset = mwir_binary_chop(port, swir_fixed=swir_offset, port_lock=port_lock, worker=worker)
    event_log.info(f"MWIR offset = {mwir_offset}")


# Direct copies of abu_sequences cal_motor_to_base / home_to_outer / mv_pos_steps / mv_neg_steps /
# move_and_measure / abu_measurement_scan. Same commands as ABU; serial access goes through the
# worker/port lock, and the checks ABU only logs are raised through *on_failure* (Continue/Abort).
def _hk(port: Any, port_lock: Any, worker: Any) -> Any:
    return _run_transaction(worker, port_lock, tc.hk_request, port)


def _sci(port: Any, sci_adc_samp: int, sci_adc_skip: int, port_lock: Any, worker: Any) -> Any:
    return _run_transaction(worker, port_lock, tc.sci_request, port, sci_adc_samp, sci_adc_skip)


def _repeat(port: Any, port_lock: Any, worker: Any, command: Any, *args: Any) -> Any:
    return _run_transaction(worker, port_lock, repeat, port, command, *args)


def _report_faults(label: str, errors: list[str], on_failure: Any) -> None:
    """Log faults; continue only if *on_failure* (label, errors) approves, otherwise stop the scan."""
    if not errors:
        return
    for error in errors:
        event_log.error(error)
    if on_failure is not None and on_failure(label, errors):
        return
    raise AssertionError(f"{label} failed:\n" + "\n".join(errors))


def _wait_while_moving(
    port: Any, port_lock: Any, worker: Any, hk_tm: Any, label: str, on_failure: Any, log_progress: bool
):
    deadline = time.monotonic() + limits.MOTOR_HOME_TIMEOUT_S
    while hk_tm.MTR_FLAGS.MOVING:
        if time.monotonic() >= deadline:
            _report_faults(label, [f"Motor still moving after {limits.MOTOR_HOME_TIMEOUT_S:.0f} s"], on_failure)
            break
        if log_progress:
            time.sleep(1)
        hk_tm = _hk(port, port_lock, worker)
        if log_progress:
            event_log.info(
                f"Motor MOVING: Absolute Steps : {hk_tm.MTR_ABS_STEPS:04d}, Relative Steps: {hk_tm.MTR_REL_STEPS:04d}"
            )
    return hk_tm


def cal_motor_to_base(port, port_lock: Any = None, worker: Any = None, on_failure: Any = None):
    """
    This function powers the Mechanism board (if it isn't already).
    Sets the default motor parameters
    Then commands the motor to HOME to BASE with CAL applied.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu cal_motor_to_base")
    # Check mechanism powered, if not enable.
    hk = _hk(port, port_lock, worker)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        _repeat(port, port_lock, worker, tc.power_control, hk.PWR_STAT | 0x01)

        resp = _hk(port, port_lock, worker)

    # Set motor parameters
    _repeat(port, port_lock, worker, tc.set_mtr_param, 64, 0, 60, 8)
    resp = _hk(port, port_lock, worker)
    if resp.MTR_CURRENT != 64 or resp.MTR_GUARD_SELECT != 0 or resp.MTR_CHOP != 60 or resp.MTR_SPEED != 8:
        _report_faults(
            "Measurement scan motor parameters",
            [
                "OB Parameters not initialized correctly:"
                + f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 64"
                + f"\n Guard Select : {resp.MTR_GUARD_SELECT}      ~ Expected : 0"
                + f"\n Chopper : {resp.MTR_CHOP}                  ~ Expected : 60"
                + f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 8"
            ],
            on_failure,
        )

    # Cal to BASE
    _repeat(port, port_lock, worker, tc.mtr_homing, True, False)
    hk_tm = _hk(port, port_lock, worker)

    # Check to see if at the Base
    if not hk_tm.MTR_FLAGS.BASE:
        event_log.info("Moving to the BASE, waiting for switch to be pressed.")
        hk_tm = _wait_while_moving(port, port_lock, worker, hk_tm, "Measurement scan cal to base", on_failure, True)
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, Base Flag Asserted")

    # Check motor status now its stopped.
    resp = _hk(port, port_lock, worker)
    errors = []
    if resp.MTR_FLAGS.CAL != 1:
        errors.append(f" Calibration Flag not Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0:
        errors.append(f" Calibration Dir not to BASE : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 0:
        errors.append(f"OUTER Switch Flag raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 1:
        errors.append(f"BASE Switch Flag is not asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        errors.append(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        errors.append(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")

    if resp.MTR_ABS_STEPS != 8960:
        errors.append(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
    if resp.MTR_REL_STEPS == 0:
        errors.append(f"Motor Steps Do not match expected REL : {resp.MTR_REL_STEPS} , Expected : 0")
    _report_faults("Measurement scan cal to base", errors, on_failure)

    event_log.info(f"Motor relative steps moved: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def home_to_outer(port, port_lock: Any = None, worker: Any = None, on_failure: Any = None):
    """
    This function powers the Mechanism board (if it isn't already).
    Then commands the motor to HOME to OUTER.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu home_to_outer")
    # Check mechanism powered, if not enable.
    hk = _hk(port, port_lock, worker)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        _repeat(port, port_lock, worker, tc.power_control, hk.PWR_STAT | 0x01)

        resp = _hk(port, port_lock, worker)

    # Home to Outer with no Cal
    _repeat(port, port_lock, worker, tc.mtr_homing, False, True)
    hk_tm = _hk(port, port_lock, worker)

    # Check to see if at the Outer
    if not hk_tm.MTR_FLAGS.OUTER:
        event_log.info("Moving to outer, waiting for switch to be pressed.")
        hk_tm = _wait_while_moving(port, port_lock, worker, hk_tm, "Measurement scan home to outer", on_failure, True)
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, Outer Flag Asserted")

    # Check motor status now its stopped.
    resp = _hk(port, port_lock, worker)
    errors = []
    if resp.MTR_FLAGS.CAL != 0:
        errors.append(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 1:
        errors.append(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 1:
        errors.append(f"OUTER Switch Flag not asserted : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 0:
        errors.append(f"Base Switch Flag is asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        errors.append(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        errors.append(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")

    if resp.MTR_REL_STEPS == 0:
        errors.append("Motor Steps Do not match expected : " + f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
    _report_faults("Measurement scan home to outer", errors, on_failure)

    event_log.info(f"Motor relative steps moved: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def _motor_error_details(hk: Any) -> list[str]:
    if hk.ERROR_MTR == 0:
        return []
    return [
        "***MOTOR ERROR*** got the following: "
        + f"\n CD : {hk.MTR_ERRORS.CD}"
        + f"\n AB : {hk.MTR_ERRORS.AB}"
        + f"\n ABS : {hk.MTR_ERRORS.ABS}"
        + f"\n DSE : {hk.MTR_ERRORS.DSE}"
    ]


def mv_pos_steps(port, pos_steps, port_lock: Any = None, worker: Any = None, on_failure: Any = None):
    """
    Script that moves the mechanism a certain number of steps positive (towards the base).
    Automatically checks that we are not already at the base.
    """
    event_log.info("Running ABU move positive steps")

    # First check that there we are are not already at the base.
    hk = _hk(port, port_lock, worker)

    if hk.MTR_FLAGS.BASE:
        event_log.error("Request to move positive steps but already at the base, skipping movement")
        return

    # Then move the desired number of steps
    _repeat(port, port_lock, worker, tc.mtr_mov_pos, pos_steps)

    # Request a HK and wait until no longer moving
    hk = _hk(port, port_lock, worker)
    hk = _wait_while_moving(port, port_lock, worker, hk, "Measurement scan move", on_failure, False)

    _report_faults("Measurement scan move", _motor_error_details(hk), on_failure)

    return


def mv_neg_steps(port, pos_steps, port_lock: Any = None, worker: Any = None, on_failure: Any = None):
    """
    Script that moves the mechanism a certain number of steps negative (towards the outer).
    Automatically checks that we are not already at the outer.
    """
    event_log.info("Running ABU move negative steps")

    # First check that we are not already at the outer.
    hk = _hk(port, port_lock, worker)

    if hk.MTR_FLAGS.OUTER:
        event_log.error("Request to move negative steps but already at the outer, skipping movement")
        return

    # Then move the desired number of steps
    _repeat(port, port_lock, worker, tc.mtr_mov_neg, pos_steps)

    # Request a HK and wait until no longer moving
    hk = _hk(port, port_lock, worker)
    hk = _wait_while_moving(port, port_lock, worker, hk, "Measurement scan move", on_failure, False)

    _report_faults("Measurement scan move", _motor_error_details(hk), on_failure)


def move_and_measure(
    port,
    pos_steps,
    sci_adc_samp=4,
    sci_adc_skip=20,
    port_lock: Any = None,
    worker: Any = None,
    on_failure: Any = None,
):
    """
    Moves the specified number of steps forward and then takes a measurement. 0 steps can be entered
    and the sequence will just measure the same point once again.

    This sequence should be executed once the motor has been HOMING and the offsets applied.

    The motor moves from the Outer to Base using (positive steps)
    """
    event_log.info("Running abu move_and_measure")

    if pos_steps > 0:
        mv_pos_steps(port, pos_steps, port_lock=port_lock, worker=worker, on_failure=on_failure)
    elif pos_steps < 0:
        mv_neg_steps(port, abs(pos_steps), port_lock=port_lock, worker=worker, on_failure=on_failure)
    else:
        event_log.info("No need to move any steps, proceeding to measurement")
    # Request a Science Mesaurement and log to the screen.
    sci = _sci(port, sci_adc_samp, sci_adc_skip, port_lock, worker)
    try:
        bg.check_science(sci, label="measurement scan science")
    except (AssertionError, RuntimeError) as exc:
        _report_faults("Measurement scan science", [str(exc)], on_failure)
    hk_tm = _hk(port, port_lock, worker)
    event_log.info(
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
    return


def measurement_scan(
    port: Any,
    step_spacing: int = 50,
    port_lock: Any = None,
    worker: Any = None,
    sci_adc_samp: int = 4,
    sci_adc_skip: int = 20,
    on_failure: Any = None,
) -> None:
    """
    Performs the basic Enfys science measurement
    Homes and Calibrates to Base
    Goes to the Outer
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    Halts once Base Stop is reached
    """
    event_log.info("Running ABU Measurement Scan")
    _hk(port, port_lock, worker)

    # Cal to Base
    cal_motor_to_base(port, port_lock=port_lock, worker=worker, on_failure=on_failure)

    # Home to Outer
    home_to_outer(port, port_lock=port_lock, worker=worker, on_failure=on_failure)

    # Measurement sequence
    event_log.info("Starting Science Measurements")
    move_and_measure(port, 0, sci_adc_samp, sci_adc_skip, port_lock=port_lock, worker=worker, on_failure=on_failure)
    for i in range(0, 8600, step_spacing):
        move_and_measure(
            port, step_spacing, sci_adc_samp, sci_adc_skip, port_lock=port_lock, worker=worker, on_failure=on_failure
        )

    event_log.info("Science Measurements Completed!!")


def measurement_scan_async(
    port: Any,
    *,
    step_spacing: int = 50,
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
