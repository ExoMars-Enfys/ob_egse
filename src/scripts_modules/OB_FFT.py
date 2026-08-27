# region imports
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from scripts_modules import sci_acq
from utility_modules import tc
from utility_modules.background_checks import (
    CommandChecks,
    check_current_profile,
    check_mechanism_current_zero,
    check_mechanism_idle,
    check_motor_hold_current,
    check_motor_stopped,
    check_science,
    check_science_offsets,
    check_thermal_response,
    log_psu_snapshot,
    log_science_measurement,
    log_thermal_status,
    read_psu_channels as _read_psu_channels,
    report_check as _background_report_check,
    request_hk,
    request_science,
    switch_psu,
)
from core_modules import measurement_config as limits
from utility_modules.send_cmd import cmd_repeat as repeat
from widget_modules import ui_runtime_controller

event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")

CURRENT_CHECK_SETTLE_S = 1.0


def read_psu_channels(psu_port: Any, psu_lock: Any = None) -> dict[str, tuple[float, float]]:
    """Allow the PSU monitor to publish a post-transition sample before checks."""
    ui_runtime_controller.abortible_sleep(CURRENT_CHECK_SETTLE_S)
    return _read_psu_channels(psu_port, psu_lock)


def report_check(*args: Any, **kwargs: Any) -> None:
    """Use the OB FFT operator decision flow for every grouped check failure."""
    kwargs.setdefault("on_failure", ui_runtime_controller.handle_script_check_failure)
    _background_report_check(*args, **kwargs)


def _run_ob_transaction(worker: Any, port_lock: Any, command: Any, port: Any, *args: Any) -> Any:
    if worker is not None:
        return worker.call(command, *args, priority=1)
    if port_lock is not None:
        with port_lock:
            return command(port, *args)
    return command(port, *args)


def _confirm_stage_2_start(psu_port: Any = None, nopsu: bool = False, psu_lock: Any = None) -> bool:
    """Block until the user confirms Stage 2 via a UI dialog. Switches off the PSU on cancellation."""
    confirmed = ui_runtime_controller.request_confirmation(
        "Stage 2 will run ROVTherm and TEC Science Acquisition tests.\n\nConfirm you are ready to proceed.",
        title="Ready to start Stage 2?",
        confirm_label="Proceed to Stage 2",
        cancel_label="Cancel",
    )
    if not confirmed:
        event_log.info("Stage 2 cancelled by user. Switching off PSU.")
        switch_psu(psu_port, enabled=False, psu_lock=psu_lock)
    return confirmed


# endregion


# PSU channel map for OB mode: CH1 = +12 V rail, CH2 = -12 V rail (heaters), CH3 = +5 V, CH4 = ROV heater.
def run_OB_fft(
    port: Any,
    psu_port: Any = None,
    nopsu: bool = False,
    psu_lock: Any = None,
    port_lock: Any = None,
    worker: Any = None,
) -> None:
    """Run both OB-only FFT stages in the order defined by the test notes."""
    event_log.info(
        "\n- - - - -              OB FFT V1               - - - - -"
        "\n- - - - -          %s         - - - - -"
        "\n- - - - -       Using COM port: %s       - - - - -",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        getattr(port, "port", port),
    )
    # fft_stage_1(port, psu_port=psu_port, nopsu=nopsu, psu_lock=psu_lock, port_lock=port_lock, worker=worker)

    # Stage 2 can be repeated; re-confirm with the user before each run.
    while _confirm_stage_2_start(psu_port=psu_port, nopsu=nopsu, psu_lock=psu_lock):
        fft_stage_2(port, psu_port=psu_port, nopsu=nopsu, psu_lock=psu_lock, port_lock=port_lock, worker=worker)

    event_log.info("Stage 2 was cancelled. Exiting OB FFT script.")


def fft_stage_1(
    port: Any,
    psu_port: Any = None,
    nopsu: bool = False,
    psu_lock: Any = None,
    port_lock: Any = None,
    worker: Any = None,
) -> Any:
    """Stage 1 : Idle Checks"""
    ui_runtime_controller.abortible_sleep(2)
    switch_psu(psu_port, enabled=not nopsu, psu_lock=psu_lock)
    ui_runtime_controller.abortible_sleep(5)
    checks = CommandChecks(
        port,
        sleep=ui_runtime_controller.abortible_sleep,
        # Moving checks must sample immediately; stationary checks use the
        # settled wrapper below before validating cached PSU telemetry.
        current_reader=(lambda: _read_psu_channels(psu_port, psu_lock)) if psu_port is not None and not nopsu else None,
        progress_factory=ui_runtime_controller.ProgressNotifier,
        port_lock=port_lock,
        transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
    )
    errors = []
    response = checks.hk("boot", check_model=True)
    measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
    ui_runtime_controller.request_force_pause(
        "State 1 — initial power on, boards off",
        errors=errors,
        readings=measured,
    )

    # region Mechanism Heater
    #  4-8. Manual mechanism heater check only if not at max ops.
    mech_trp = getattr(response, "MECH_TRP", None)
    mtr_trp = getattr(response, "MOTOR_TRP", None)
    if mech_trp is None or mtr_trp is None:
        event_log.warning("Skipping mechanism heater enable: MECH_TRP or MOTOR_TRP is unavailable")
    elif (mech_trp >> 4) <= 2196 or (mtr_trp >> 4) <= 2196:  # Enable only at or below +40 C.
        response = checks.heater(False, False, False, True, False, label="manual mechanism heater enable")
        errors: list[str] = []
        check_mechanism_current_zero(response, errors)
        ui_runtime_controller.abortible_sleep(5)
        measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
        report_check(
            "Manual mechanism heater ON",
            errors,
            measured,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )
        initial_thermal_values = {
            "MECH_TRP": getattr(response, "MECH_TRP", None),
            "MOTOR_TRP": getattr(response, "MOTOR_TRP", None),
        }
        ui_runtime_controller.abortible_sleep_with_progress(30, "Manual mechanism heater thermal response wait")
        response = request_hk(
            port,
            "manual mechanism heater thermal response",
            port_lock=port_lock,
            transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
        )
        log_thermal_status(response)
        errors = []
        check_thermal_response(response, initial_thermal_values, "mechanism", errors)
        report_check(
            "Manual mechanism heater thermal response",
            errors,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )
        response = checks.heater(False, False, False, False, False, label="manual mechanism heater disable")
        errors = []
        check_mechanism_current_zero(response, errors)
        ui_runtime_controller.abortible_sleep(5)
        measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
        report_check(
            "Manual mechanism heater OFF",
            errors,
            measured,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )

    # endregion

    # region Detector Heater
    # 9-13. Manual detector heater check only if not at max ops.
    det_trp = getattr(response, "DETEC_TRP", None)
    if det_trp is None:
        event_log.warning("Skipping detector heater enable: DETEC_TRP is unavailable")
    elif (det_trp >> 4) <= 2196:  # Enable only at or below +40 C.
        response = checks.heater(False, True, False, False, False, label="manual detector heater enable")
        errors = []
        ui_runtime_controller.abortible_sleep(5)
        measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
        report_check(
            "Manual detector heater ON",
            errors,
            measured,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )
        initial_thermal_values = {"DETEC_TRP": getattr(response, "DETEC_TRP", None)}
        ui_runtime_controller.abortible_sleep_with_progress(30, "Manual detector heater thermal response wait")
        response = request_hk(
            port,
            "manual detector heater thermal response",
            port_lock=port_lock,
            transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
        )
        log_thermal_status(response)
        errors = []
        check_thermal_response(response, initial_thermal_values, "detector", errors)
        report_check(
            "Manual detector heater thermal response",
            errors,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )
        response = checks.heater(False, False, False, False, False, label="manual detector heater disable")
        errors = []
        ui_runtime_controller.abortible_sleep(5)
        measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
        report_check(
            "Manual detector heater OFF",
            errors,
            measured,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )
    # endregion

    # region State 2 Heaters ON
    # 14-17. Dual manual heaters, State 2, then off only if not at max ops.
    mech_trp = getattr(response, "MECH_TRP", None)
    mtr_trp = getattr(response, "MOTOR_TRP", None)
    det_trp = getattr(response, "DETEC_TRP", None)
    if mech_trp is None or mtr_trp is None or det_trp is None:
        event_log.warning("Skipping STATE 2 - HEATER TRPs are unavailable")
    elif (mech_trp >> 4) <= 2196 or (mtr_trp >> 4) <= 2196 or (det_trp >> 4) <= 2196:  # Enable only at or below +40 C.
        response = checks.heater(False, True, False, True, False, label="dual heater enable")
        ui_runtime_controller.abortible_sleep(5)
        checks.state(
            "State2",
            {} if nopsu else read_psu_channels(psu_port, psu_lock),
            response=response,
            allow_psu_unavailable=nopsu,
        )
        errors = []
        check_mechanism_current_zero(response, errors)
        ui_runtime_controller.abortible_sleep(5)
        measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
        report_check(
            "State 2 dual heater ON",
            errors,
            measured,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )

        ui_runtime_controller.request_force_pause(
            "State 2 — heaters only on",
            errors=errors,
            readings=measured,
        )

        response = checks.heater(False, False, False, False, False, label="State 2 heater disable")
        errors = []
        ui_runtime_controller.abortible_sleep(5)
        measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
        report_check(
            "State 2 dual heater OFF",
            errors,
            measured,
            notify_negative=ui_runtime_controller.notify_negative,
            notify_positive=ui_runtime_controller.notify_positive,
        )
    # endregion

    # region Mechanism Board & MOTOR PARAMS
    # 18-21. Mechanism board, and motor params
    ui_runtime_controller.abortible_sleep(5)
    response = checks.power(0x01, label="mechanism board power on")
    errors = []
    ui_runtime_controller.abortible_sleep(5)
    measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
    report_check(
        "Mechanism board ON",
        errors,
        measured,
        notify_negative=ui_runtime_controller.notify_negative,
        notify_positive=ui_runtime_controller.notify_positive,
    )
    checks.set_nominal_motor_params()
    # endregion

    # region MOVEMENT, HOLD and HALT
    ui_runtime_controller.abortible_sleep(5)
    checks.home(calibration=True, outer=True, label="calibration to outer")
    ui_runtime_controller.abortible_sleep(5)
    response = checks.move(negative=False, steps=480, label="negative 480-step move")
    errors = []
    readings = None if nopsu else read_psu_channels(psu_port, psu_lock)
    ui_runtime_controller.abortible_sleep(5)
    check_motor_hold_current(response, errors, readings)
    report_check(
        "Motor hold current before halt",
        errors,
        notify_negative=ui_runtime_controller.notify_negative,
        notify_positive=ui_runtime_controller.notify_positive,
    )
    _run_ob_transaction(worker, port_lock, repeat, port, tc.mtr_halt)
    ui_runtime_controller.abortible_sleep(2)
    response = request_hk(
        port,
        "motor halt",
        port_lock=port_lock,
        transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
    )
    check_motor_stopped(response, "motor halt")
    ui_runtime_controller.abortible_sleep(2)
    errors = []
    check_mechanism_idle(response, errors)
    measured = (
        check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors) if not nopsu else {}
    )
    report_check(
        "Motor current after halt",
        errors,
        measured,
        notify_negative=ui_runtime_controller.notify_negative,
        notify_positive=ui_runtime_controller.notify_positive,
    )
    log_psu_snapshot(psu_port, "Motor halt current", psu_lock)
    ui_runtime_controller.request_force_pause("Pause for region MOVE HOLD HALT!")
    # endregion

    # region CURRENT and SPEED CHECKS
    checks.home(calibration=True, outer=True, label="return to outer")
    ui_runtime_controller.abortible_sleep(2)
    checks.home(calibration=False, outer=False, label="home to base")
    motion = checks.last_motion_report or {}
    ui_runtime_controller.request_force_pause(
        "Motor spacing report\n\n"
        f"Absolute position: {int(motion.get('absolute_steps', 0))} steps\n"
        f"Relative movement: {int(motion.get('relative_steps', 0))} steps\n"
        f"Elapsed time: {float(motion.get('elapsed_s', 0.0)):.2f} s\n"
        f"Speed: {float(motion.get('speed_mm_s', 0.0)):.3f} mm/s"
    )
    ui_runtime_controller.abortible_sleep(2)
    for motor_current in (20, 40, 64):
        checks.set_motor_current(motor_current)
        expected_motor_params = (
            motor_current,
            limits.MOTOR_NOMINAL_GUARD,
            limits.MOTOR_NOMINAL_CHOPPER,
            limits.MOTOR_NOMINAL_SPEED,
        )
        checks.move(
            negative=True,
            steps=1500,
            label=f"motor current {motor_current} movement",
            active_state="Moving",
            expected_motor_params=expected_motor_params,
        )
        checks.move(
            negative=False,
            steps=1500,
            label=f"motor current {motor_current} movement",
            active_state="Moving",
            expected_motor_params=expected_motor_params,
        )
        ui_runtime_controller.abortible_sleep(2)
    checks.home(calibration=False, outer=False, label="home to base")
    checks.set_motor_speed(0)
    speed_zero_params = (
        limits.MOTOR_NOMINAL_CURRENT,
        limits.MOTOR_NOMINAL_GUARD,
        limits.MOTOR_NOMINAL_CHOPPER,
        0,
    )
    checks.home(
        calibration=False,
        outer=True,
        label="motor speed 0 home to outer",
        expected_motor_params=speed_zero_params,
        max_duration_s=limits.MOTOR_SPEED_MAX_DURATION_S[0],
    )
    checks.set_motor_speed(15)
    speed_max_params = (
        limits.MOTOR_NOMINAL_CURRENT,
        limits.MOTOR_NOMINAL_GUARD,
        limits.MOTOR_NOMINAL_CHOPPER,
        15,
    )
    checks.home(
        calibration=False,
        outer=False,
        label="motor speed 15 home to base",
        expected_motor_params=speed_max_params,
        max_duration_s=limits.MOTOR_SPEED_MAX_DURATION_S[15],
    )
    checks.set_nominal_motor_params()
    ui_runtime_controller.abortible_sleep(5)
    checks.move_to_absolute_position(
        limits.DARK_POSITIONS["SWIR"],
        label="SWIR dark position",
    )
    ui_runtime_controller.abortible_sleep(5)
    response = checks.power(0x00, label="mechanism board power off")
    errors = []
    check_mechanism_idle(response, errors)
    ui_runtime_controller.abortible_sleep(5)
    measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
    report_check(
        "Mechanism board OFF",
        errors,
        measured,
        notify_negative=ui_runtime_controller.notify_negative,
        notify_positive=ui_runtime_controller.notify_positive,
    )
    ui_runtime_controller.request_force_pause("Pause before Dark region measurements")
    # endregion

    # region Detector Dark Measurements
    # 35-44. Detector dark measurements, offsets, and ABU measurement scan.
    response = checks.power(0x02, label="Stage 1 detector board power on")
    errors = []
    ui_runtime_controller.abortible_sleep(5)
    measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
    report_check(
        "Detector board ON",
        errors,
        measured,
        notify_negative=ui_runtime_controller.notify_negative,
        notify_positive=ui_runtime_controller.notify_positive,
    )

    # Stage 1 science and operating-state checks.
    _run_ob_transaction(worker, port_lock, repeat, port, tc.sci_offset, 2048, 2048)
    dark_science = request_science(
        port,
        "initial dark science measurement",
        port_lock=port_lock,
        transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
    )
    check_science(dark_science, label="initial dark science measurement")
    log_science_measurement(dark_science, "Initial dark science measurement; record this reading")
    _run_ob_transaction(worker, port_lock, repeat, port, tc.sci_offset, 4095, 4095)
    offset_science = request_science(
        port,
        "science offset 4095 verification",
        port_lock=port_lock,
        transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
    )
    check_science(offset_science, label="science offset 4095 verification")
    errors = []
    check_science_offsets(offset_science, 4095, 4095, errors)
    for field in ("SWIR_HIGH", "SWIR_MED", "SWIR_LOW", "MWIR_HIGH", "MWIR_MED", "MWIR_LOW"):
        initial_value = getattr(dark_science, field, None)
        offset_value = getattr(offset_science, field, None)
        if initial_value is None or offset_value is None:
            errors.append(f"{field} is unavailable for dark-offset comparison")
        elif initial_value == 0 and offset_value == 0:
            # The channel can legitimately sit at the zero floor before and after
            # the offset command; in that case there is no measurable decrease to
            # prove and the result should not be treated as a failure.
            continue
        elif offset_value >= initial_value:
            errors.append(f"{field} did not decrease after offset 4095: {initial_value} -> {offset_value}")
    report_check(
        "Science dark offset 4095",
        errors,
        notify_negative=ui_runtime_controller.notify_negative,
        notify_positive=ui_runtime_controller.notify_positive,
    )
    log_science_measurement(offset_science, "Dark science after offset 4095")
    # endregion

    # region SCI ACQ
    response = checks.power(0x03, label="mechanism and detector boards power on")
    ui_runtime_controller.abortible_sleep(5)
    measured = checks.state(
        "State5",
        {} if nopsu else read_psu_channels(psu_port, psu_lock),
        response=response,
        allow_psu_unavailable=nopsu,
    )
    ui_runtime_controller.request_force_pause(
        "State 5 — boards on, heaters off",
        errors=[],
        readings=measured,
    )
    ui_runtime_controller.request_force_pause("Click to continue once ready for the science scan.")
    sci_acq.choose_dac_offsets(port, port_lock=port_lock, worker=worker)
    capture_id = ui_runtime_controller.begin_ob_sci_capture("OB FFT Stage 1 science scan")
    try:
        sci_acq.measurement_scan(port, step_spacing=50, port_lock=port_lock, worker=worker)
        ui_runtime_controller.request_force_pause("Click to continue once finished from the science scan.")
    except BaseException:
        ui_runtime_controller.cancel_ob_sci_capture(capture_id)
        raise
    else:
        ui_runtime_controller.end_ob_sci_capture(capture_id)
    _run_ob_transaction(worker, port_lock, tc.mtr_halt, port)
    ui_runtime_controller.abortible_sleep(2)

    # The measurement scan can finish at the base stop. Re-establish a known
    # outer starting position before enabling heaters so the subsequent
    # base-home operation necessarily provides moving State7 samples.
    checks.home(calibration=True, outer=True, label="prepare State 7 at outer stop")

    response = checks.heater(False, True, False, True, False, label="State 3 heaters enable")
    ui_runtime_controller.abortible_sleep(5)
    response = checks.hk("State 3 heaters settled")

    measured = checks.state(
        "State3",
        {} if nopsu else read_psu_channels(psu_port, psu_lock),
        response=response,
        allow_psu_unavailable=nopsu,
    )
    ui_runtime_controller.request_force_pause(
        "State 3 — heaters and all boards powered on",
        errors=[],
        readings=measured,
    )
    checks.home(
        calibration=False, outer=False, label="State 7 home to base", active_state="State7"
    )  #! Check the consumption limits
    ui_runtime_controller.request_force_pause(
        "State 7 — boards on, heaters on, moving",
        errors=[],
        readings=checks.last_state_readings or {},
    )
    response = checks.heater(False, False, False, False, False, label="heaters disable after base home")
    ui_runtime_controller.abortible_sleep(5)
    checks.move_to_absolute_position(
        limits.PARK_POSITION,
        label="PARK position",
    )
    #! Park
    checks.power(0x00, label="OB boards power off")
    ui_runtime_controller.abortible_sleep(5)
    switch_psu(psu_port, enabled=False, psu_lock=psu_lock)

    # endregion

    return response


# region OB FFT - Stage 2: TEC on, baffle hat off
def fft_stage_2(
    port: Any,
    psu_port: Any = None,
    nopsu: bool = False,
    psu_lock: Any = None,
    port_lock: Any = None,
    worker: Any = None,
) -> Any:
    """Stage 2 : ROVTherm and TEC Sci ACQ"""
    # region 2nd Boot up
    ui_runtime_controller.request_force_pause("Make sure TEC is on and at Temperature to continue with the SCI ACQ")
    ui_runtime_controller.abortible_sleep(2)
    switch_psu(psu_port, enabled=not nopsu, psu_lock=psu_lock)
    ui_runtime_controller.abortible_sleep(5)
    checks = CommandChecks(
        port,
        sleep=ui_runtime_controller.abortible_sleep,
        current_reader=(lambda: _read_psu_channels(psu_port, psu_lock)) if psu_port is not None and not nopsu else None,
        progress_factory=ui_runtime_controller.ProgressNotifier,
        port_lock=port_lock,
        transaction_runner=(lambda func, *args: worker.call(func, *args)) if worker is not None else None,
    )

    response = checks.hk("boot", check_model=True)
    # endregion

    # region Cal and set up for measurement
    ui_runtime_controller.abortible_sleep(5)
    response = checks.power(0x01, label="mechanism board power on")
    errors = []
    ui_runtime_controller.abortible_sleep(5)
    measured = check_current_profile(read_psu_channels(psu_port, psu_lock), response, errors=errors)
    report_check(
        "Mechanism board ON",
        errors,
        measured,
        notify_negative=ui_runtime_controller.notify_negative,
        notify_positive=ui_runtime_controller.notify_positive,
    )
    checks.set_nominal_motor_params()
    ui_runtime_controller.abortible_sleep(5)
    checks.home(calibration=True, outer=True, label="calibration to outer")
    # endregion

    # region SCI ACQ with TEC
    response = checks.power(0x03, label="mechanism and detector boards power on")
    ui_runtime_controller.request_force_pause("Click to continue once ready for the science scan.")
    # sci_acq.choose_dac_offsets(port, port_lock=port_lock, worker=worker)
    capture_id = ui_runtime_controller.begin_ob_sci_capture("OB FFT Stage 2 TEC science scan")
    try:
        sci_acq.measurement_scan(port, step_spacing=50, port_lock=port_lock, worker=worker)
    except BaseException:
        ui_runtime_controller.cancel_ob_sci_capture(capture_id)
        raise
    else:
        ui_runtime_controller.end_ob_sci_capture(capture_id)

    # endregion

    # region Home, Park, and Automatic Power OFF
    ui_runtime_controller.abortible_sleep(5)
    checks.home(calibration=False, outer=False, label="Stage 2 home to base")
    checks.move_to_absolute_position(
        limits.PARK_POSITION,
        label="Stage 2 PARK position",
    )
    _run_ob_transaction(worker, port_lock, tc.mtr_halt, port)
    response = checks.power(0x00, label="Stage 2 automatic OB boards power off")
    ui_runtime_controller.abortible_sleep(5)
    switch_psu(psu_port, enabled=False, psu_lock=psu_lock)
    # endregion

    return response


# endregion
