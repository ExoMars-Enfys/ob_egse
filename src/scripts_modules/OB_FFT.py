from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from core_modules import config
from scripts_modules import abu_sequences
from utility_modules import psu, tc
from utility_modules.send_cmd import cmd_repeat as repeat
from widget_modules import ui_runtime_controller

event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")

# PSU channel map for OB mode: CH1 = +12 V rail, CH2 = -12 V rail (heaters), CH3 = +5 V, CH4 = ROV heater.


def fft(port: Any, psu_port: Any = None, nopsu: bool = False) -> None:
    """Run both OB-only FFT stages in the order defined by the test notes."""
    event_log.info(
        "\n- - - - -              OB FFT V1               - - - - -"
        "\n- - - - - Follows section 2.1 of the OB-EB ICD V3.0 - - - - -"
        "\n- - - - -          %s         - - - - -"
        "\n- - - - -       Using COM port: %s       - - - - -",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        getattr(port, "port", port),
    )
    fft_stage_1(port, psu_port=psu_port, nopsu=nopsu)
    fft_stage_2(port, psu_port=psu_port, nopsu=nopsu)


# region OB FFT - Stage 1: full qualification without TEC
def fft_stage_1(port: Any, psu_port: Any = None, nopsu: bool = False) -> Any:
    """Run the full no-TEC OB FFT qualification sequence."""
    event_log.info("- - - - - Stage 1 - FULL SCRIPT WITHOUT TEC - - - - -")
    ui_runtime_controller.request_force_pause("Record idle impedances, then resume the script.")
    switchPsu(psu_port, enabled=not nopsu)
    logPsuSnapshot(psu_port, "Stage 1 idle consumption")
    ui_runtime_controller.request_force_pause("Verify idle PSU consumption, then resume the script.")
    response = hk_check(port)

    # 4-8. Manual mechanism heater check.
    ui_runtime_controller.request_force_pause(
        "Confirm mechanism temperature is below the +40 C maximum operating limit, then resume the script."
    )
    repeat(port, tc.heater_control, False, False, False, True, False)
    response = requestHk(port, "manual mechanism heater enable")
    errors: list[str] = []
    verifyMechanismHeaterOn(response, errors)
    checkMechanismCurrentZero(response, errors)
    measured = checkPsuCurrent(psu_port, "CH2", 83.0, errors)
    raiseIfErrors("Manual mechanism heater ON", errors, {"CH2_mA": measured})
    initial_mechanism = getattr(response, "MECH_TRP", None)
    initial_motor = getattr(response, "MOTOR_TRP", None)
    ui_runtime_controller.abortible_sleep(60)
    response = requestHk(port, "manual mechanism heater thermal response")
    logThermalStatus(response)
    errors = []
    verifyThermalResponse(response, initial_mechanism, initial_motor, "mechanism", errors)
    raiseIfErrors("Manual mechanism heater thermal response", errors)
    repeat(port, tc.heater_control, False, False, False, False, False)
    response = requestHk(port, "manual mechanism heater disable")
    errors = []
    verifyManualHeatersOff(response, errors)
    checkMechanismCurrentZero(response, errors)
    measured = checkPsuCurrent(psu_port, "CH2", 0.0, errors, tolerance_fraction=0.0)
    raiseIfErrors("Manual mechanism heater OFF", errors, {"CH2_mA": measured})

    # 9-13. Manual detector heater check.
    ui_runtime_controller.request_force_pause(
        "Confirm detector temperature is below the +40 C maximum operating limit, then resume the script."
    )
    repeat(port, tc.heater_control, False, True, False, False, False)
    response = requestHk(port, "manual detector heater enable")
    errors = []
    verifyManualHeater(response, detector=True, enabled=True, errors=errors)
    checkMechanismCurrentZero(response, errors)
    measured = checkPsuCurrent(psu_port, "CH2", 41.0, errors)
    raiseIfErrors("Manual detector heater ON", errors, {"CH2_mA": measured})
    initial_mechanism = getattr(response, "MECH_TRP", None)
    initial_motor = getattr(response, "MOTOR_TRP", None)
    ui_runtime_controller.abortible_sleep(30)
    response = requestHk(port, "manual detector heater thermal response")
    logThermalStatus(response)
    errors = []
    verifyThermalResponse(response, initial_mechanism, initial_motor, "detector", errors)
    raiseIfErrors("Manual detector heater thermal response", errors)
    repeat(port, tc.heater_control, False, False, False, False, False)
    response = requestHk(port, "manual detector heater disable")
    errors = []
    verifyManualHeatersOff(response, errors)
    checkMechanismCurrentZero(response, errors)
    measured = checkPsuCurrent(psu_port, "CH2", 0.0, errors, tolerance_fraction=0.0)
    raiseIfErrors("Manual detector heater OFF", errors, {"CH2_mA": measured})

    # 14-17. Dual manual heaters, State 2, then off.
    repeat(port, tc.heater_control, False, True, False, True, False)
    response = requestHk(port, "dual heater enable")
    errors = []
    verifyMechanismHeaterOn(response, errors)
    verifyManualHeater(response, detector=True, enabled=True, errors=errors)
    checkMechanismCurrentZero(response, errors)
    measured = checkPsuCurrent(psu_port, "CH2", 124.0, errors)
    raiseIfErrors("State 2 dual heater ON", errors, {"CH2_mA": measured})
    repeat(port, tc.heater_control, False, False, False, False, False)
    response = requestHk(port, "State 2 heater disable")
    errors = []
    verifyManualHeatersOff(response, errors)
    measured = checkPsuCurrent(psu_port, "CH2", 0.0, errors, tolerance_fraction=0.0)
    raiseIfErrors("State 2 dual heater OFF", errors, {"CH2_mA": measured})

    # 18-34. Mechanism board, motion, homing, and current qualification.
    repeat(port, tc.power_control, 0x01)
    response = requestHk(port, "mechanism board power on")
    errors = []
    verifyState(response, 0x01, errors)
    measured = checkPsuCurrent(psu_port, "CH1", 3.0, errors)
    raiseIfErrors("Mechanism board ON", errors, {"CH1_mA": measured})
    setAndVerifyMotorParameters(port, current=64, guard=0, chopper=60, speed=8)
    homeAndVerify(port, calibration=True, outer=True, label="calibration to outer", expected_steps=1000)
    moveAndVerify(port, negative=True, steps=480, label="negative 480-step move")
    repeat(port, tc.mtr_halt)
    verifyMotorStopped(requestHk(port, "motor halt"), "motor halt")
    logPsuSnapshot(psu_port, "Motor halt current")
    homeAndVerify(port, calibration=False, outer=True, label="return to outer")
    homeAndVerify(port, calibration=False, outer=False, label="home to base")
    for current in (20, 40, 64):
        setAndVerifyMotorParameters(port, current=current, guard=0, chopper=60, speed=8)
        moveAndVerify(port, negative=False, steps=20, label=f"motor current {current} movement")
        logPsuSnapshot(psu_port, f"Motor current {current} PSU and HK check")
        moveAndVerify(port, negative=True, steps=20, label=f"motor current {current} return")
    homeAndVerify(port, calibration=False, outer=False, label="repeat home to base")
    setAndVerifyMotorParameters(port, current=64, guard=0, chopper=60, speed=0)
    homeAndVerify(port, calibration=False, outer=True, label="speed 0 home to outer")
    setAndVerifyMotorParameters(port, current=64, guard=0, chopper=60, speed=15)
    homeAndVerify(port, calibration=False, outer=False, label="speed 15 home to base")
    setAndVerifyMotorParameters(port, current=64, guard=0, chopper=60, speed=8)
    ui_runtime_controller.request_force_pause("Move to the ABU-defined SWIR dark position, then resume the script.")
    repeat(port, tc.power_control, 0x00)
    response = requestHk(port, "mechanism board power off")
    errors = []
    verifyState(response, 0, errors)
    checkMechanismCurrentZero(response, errors)
    measured = checkPsuCurrent(psu_port, "CH1", 0.0, errors, tolerance_fraction=0.0)
    raiseIfErrors("Mechanism board OFF", errors, {"CH1_mA": measured})

    # 35-44. Detector dark measurements, offsets, and ABU measurement scan.
    repeat(port, tc.power_control, 0x02)
    response = requestHk(port, "Stage 1 detector board power on")
    errors = []
    verifyState(response, 0x02, errors)
    ch1 = checkPsuCurrent(psu_port, "CH1", 14.4, errors)
    ch2 = checkPsuCurrent(psu_port, "CH2", 5.7, errors)
    raiseIfErrors("Stage 1 detector board ON", errors, {"CH1_mA": ch1, "CH2_mA": ch2})
    science = requestScience(port, "detector dark measurement")
    logScienceMeasurement(science, "Initial dark measurement")
    ui_runtime_controller.request_force_pause("Record the displayed initial dark measurement, then resume the script.")
    repeat(port, tc.sci_offset, 0xFFF, 0xFFF)
    response = requestHk(port, "SCI offset set to 4095")
    errors = []
    verifyScienceOffsets(response, 0xFFF, 0xFFF, errors)
    raiseIfErrors("SCI offset set to 4095", errors)
    logScienceMeasurement(requestScience(port, "offset dark measurement"), "Dark measurement at offset 4095")
    repeat(port, tc.power_control, 0x03)
    response = requestHk(port, "Stage 1 mechanism and detector boards power on")
    errors = []
    verifyState(response, 0x03, errors)
    ch1 = checkPsuCurrent(psu_port, "CH1", 18.0, errors)
    ch2 = checkPsuCurrent(psu_port, "CH2", 5.7, errors)
    raiseIfErrors("Stage 1 all boards ON", errors, {"CH1_mA": ch1, "CH2_mA": ch2})
    abu_sequences.mwir_binary_chop(port)
    abu_sequences.swir_binary_chop(port)
    abu_sequences.abu_measurement_scan(port, step_spacing=50)

    # 45-48. Heated State 3 and State 7 checks.
    repeat(port, tc.heater_control, False, True, False, True, False)
    response = requestHk(port, "Stage 1 heaters on with both boards powered")
    errors = []
    verifyMechanismHeaterOn(response, errors)
    verifyManualHeater(response, detector=True, enabled=True, errors=errors)
    verifyState(response, 0x03, errors)
    ch1 = checkPsuCurrent(psu_port, "CH1", 18.0, errors)
    ch2 = checkPsuCurrent(psu_port, "CH2", 129.0, errors)
    raiseIfErrors("State 3", errors, {"CH1_mA": ch1, "CH2_mA": ch2})
    homeAndVerify(port, calibration=False, outer=True, label="State 7 home to outer")
    logPsuSnapshot(psu_port, "State 7 power consumption")
    repeat(port, tc.heater_control, False, False, False, False, False)
    errors = []
    verifyManualHeatersOff(requestHk(port, "State 7 heater disable"), errors)
    raiseIfErrors("State 7 heater disable", errors)

    # 49-56. ROV heater thermal check.
    if psu_port is None:
        event_log.warning("ROV heater test skipped because no PSU port is available.")
    else:
        ui_runtime_controller.request_force_pause(
            "Confirm the initial ROV thermistor resistance, then resume the script."
        )
        psu.switch_psu_channel(psu_port, 4, 1)
        logPsuSnapshot(psu_port, "ROV heater enabled")
        logThermalStatus(requestHk(port, "ROV heater initial digital temperature"))
        ui_runtime_controller.request_force_pause(
            "Enable the ROV thermistor and wait for the specified resistance change, then resume the script."
        )
        logThermalStatus(requestHk(port, "ROV heater digital temperature change"))
        psu.switch_psu_channel(psu_port, 4, 0)
        logPsuSnapshot(psu_port, "ROV heater disabled")

    repeat(port, tc.power_control, 0)
    response = requestHk(port, "Stage 1 power off")
    errors = []
    verifyState(response, 0, errors)
    checkMechanismCurrentZero(response, errors)
    ch1 = checkPsuCurrent(psu_port, "CH1", 0.0, errors, tolerance_fraction=0.0)
    ch2 = checkPsuCurrent(psu_port, "CH2", 0.0, errors, tolerance_fraction=0.0)
    raiseIfErrors("Stage 1 final power off", errors, {"CH1_mA": ch1, "CH2_mA": ch2})
    ui_runtime_controller.request_force_pause("Generate the Stage 1 data graphs, then resume the script.")
    return response


# endregion


# region OB FFT - Stage 2: TEC on, baffle hat off
def fft_stage_2(port: Any, psu_port: Any = None, nopsu: bool = False) -> Any:
    """Run the baffle-hat-off measurement sequence with an externally controlled TEC."""
    event_log.info("- - - - - Stage 2 - TEC ON, BAFFLE HAT OFF - - - - -")
    switchPsu(psu_port, enabled=not nopsu)
    logPsuSnapshot(psu_port, "Stage 2 idle consumption")
    ui_runtime_controller.request_force_pause("Verify Stage 2 idle PSU consumption, then resume the script.")
    hk_check(port)

    repeat(port, tc.power_control, 0x03)
    response = requestHk(port, "Stage 2 board power on")
    errors = []
    verifyState(response, 0x03, errors)
    raiseIfErrors("Stage 2 all boards powered", errors, logPsuSnapshot(psu_port, "Stage 2 all boards powered"))
    ui_runtime_controller.request_force_pause(
        "Turn on the TEC cube and verify its consumption and temperature, then resume the script."
    )
    ui_runtime_controller.request_force_pause("Resume only when the TEC cube is at its required temperature.")
    ui_runtime_controller.request_force_pause(
        "Remove the baffle hat, then resume the script to start the Stage 2 ABU sequence."
    )

    logPsuSnapshot(psu_port, "Stage 2 ABU sequence baseline")
    abu_sequences.mwir_binary_chop(port)
    abu_sequences.swir_binary_chop(port)
    abu_sequences.abu_measurement_scan(port, step_spacing=50)
    logPsuSnapshot(psu_port, "Stage 2 ABU sequence complete")
    repeat(port, tc.power_control, 0)
    response = requestHk(port, "Stage 2 power off")
    errors = []
    verifyState(response, 0, errors)
    ch1 = checkPsuCurrent(psu_port, "CH1", 0.0, errors, tolerance_fraction=0.0)
    ch2 = checkPsuCurrent(psu_port, "CH2", 0.0, errors, tolerance_fraction=0.0)
    raiseIfErrors("Stage 2 final power off", errors, {"CH1_mA": ch1, "CH2_mA": ch2})
    ui_runtime_controller.request_force_pause(
        "Generate Stage 2 graphs and correlate them with Stage 1 data, then resume the script to finish."
    )
    return response


# endregion


def switchPsu(psu_port: Any, *, enabled: bool) -> None:
    if psu_port is None:
        info_log.info("PSU unavailable; skipping PSU channel switch.")
        return
    psu.switch_all_psu_channels(psu_port, 1 if enabled else 0)


def hk_check(port: Any) -> Any:
    """Request, validate, and log boot HK for the OB FFT checklist."""
    response = requestHk(port, "boot")
    expected_model = getattr(config, "EXP_MODEL_ID", None)
    actual_model = getattr(response, "MOD_ID", getattr(response, "MODEL_ID", None))
    if expected_model is not None and actual_model not in (None, expected_model):
        raise AssertionError(f"Boot HK model mismatch: got {actual_model}, expected {expected_model}")

    info_log.info("OB FFT boot HK response: %s", response)
    return response


def requestHk(port: Any, checkpoint: str) -> Any:
    response = repeat(port, tc.hk_request)
    if response == "ERROR" or response is None:
        raise RuntimeError(f"No valid HK response received during {checkpoint}")
    return response


def verifyMechanismHeaterOn(response: Any, errors: list[str]) -> None:
    thermal_status = getattr(response, "THRM_STATUS", None)
    hms = bool(getattr(thermal_status, "HMS", 0))
    manual_mechanism = bool(getattr(thermal_status, "MM", 0))
    if not (hms and manual_mechanism):
        errors.append(
            "Mechanism manual heater not on: "
            f"THRM_STATUS_BYTE={getattr(response, 'THRM_STATUS_BYTE', 'N/A')}, HMS={int(hms)}, MM={int(manual_mechanism)}"
        )


def verifyManualHeatersOff(response: Any, errors: list[str]) -> None:
    thermal_status = getattr(response, "THRM_STATUS", None)
    manual_detector = bool(getattr(thermal_status, "DM", 0))
    manual_mechanism = bool(getattr(thermal_status, "MM", 0))
    if manual_detector or manual_mechanism:
        errors.append(
            "Manual heaters not disabled: "
            f"THRM_STATUS_BYTE={getattr(response, 'THRM_STATUS_BYTE', 'N/A')}, DM={int(manual_detector)}, MM={int(manual_mechanism)}"
        )


def logThermalStatus(response: Any) -> None:
    info_log.info(
        "OB FFT thermal review: mechanism TRP=%s, motor TRP=%s",
        getattr(response, "MECH_TRP", "N/A"),
        getattr(response, "MOTOR_TRP", getattr(response, "MTR_TRP", "N/A")),
    )


def setAndVerifyMotorParameters(port: Any, *, current: int, guard: int, chopper: int, speed: int) -> None:
    repeat(port, tc.set_mtr_param, current, guard, chopper, speed)
    response = requestHk(port, "motor parameter verification")
    actual = (response.MTR_CURRENT, response.MTR_GUARD_SELECT, response.MTR_CHOP, response.MTR_SPEED)
    expected = (current, guard, chopper, speed)
    if actual != expected:
        raise AssertionError(f"Motor parameter verification failed: got {actual}, expected {expected}")


def homeAndVerify(port: Any, *, calibration: bool, outer: bool, label: str, expected_steps: int | None = None) -> Any:
    start = time.monotonic()
    repeat(port, tc.mtr_homing, calibration, outer)
    response = waitForMotorStop(port, label)
    elapsed = time.monotonic() - start
    flags = response.MTR_FLAGS
    expected_direction = 1 if outer else 0
    expected_switch = "OUTER" if outer else "BASE"
    if (
        response.ERROR_MTR != 0
        or flags.MOVING
        or flags.HOMING
        or flags.DIR != expected_direction
        or not getattr(flags, expected_switch)
    ):
        raise AssertionError(f"{label} verification failed: errors={response.ERROR_MTR}, flags={vars(flags)}")
    if expected_steps is not None and response.MTR_ABS_STEPS != expected_steps:
        raise AssertionError(f"{label} ended at {response.MTR_ABS_STEPS} steps; expected {expected_steps}")
    event_log.info("%s completed in %.2f s at %s steps.", label, elapsed, response.MTR_ABS_STEPS)
    return response


def moveAndVerify(port: Any, *, negative: bool, steps: int, label: str) -> Any:
    command = tc.mtr_mov_neg if negative else tc.mtr_mov_pos
    repeat(port, command, steps)
    response = requestHk(port, f"{label} start")
    if response.ERROR_MTR != 0:
        raise AssertionError(f"{label} reported motor error {response.ERROR_MTR}")
    response = waitForMotorStop(port, label)
    verifyMotorStopped(response, label)
    return response


def waitForMotorStop(port: Any, checkpoint: str, timeout_s: float = 120.0) -> Any:
    deadline = time.monotonic() + timeout_s
    response = requestHk(port, checkpoint)
    while getattr(response.MTR_FLAGS, "MOVING", 0):
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for motor movement during {checkpoint}")
        ui_runtime_controller.abortible_sleep(1)
        response = requestHk(port, checkpoint)
    return response


def verifyMotorStopped(response: Any, checkpoint: str) -> None:
    if response.ERROR_MTR != 0 or response.MTR_FLAGS.MOVING or response.MTR_FLAGS.HOMING:
        raise AssertionError(
            f"{checkpoint} did not finish cleanly: errors={response.ERROR_MTR}, flags={vars(response.MTR_FLAGS)}"
        )


def verifyState(response: Any, expected_power_state: int, errors: list[str]) -> None:
    if getattr(response, "PWR_STAT", None) != expected_power_state:
        errors.append(f"PWR_STAT={response.PWR_STAT}, expected {expected_power_state}")


def verifyManualHeater(response: Any, *, detector: bool, enabled: bool, errors: list[str]) -> None:
    thermal_status = getattr(response, "THRM_STATUS", None)
    field_name = "DM" if detector else "MM"
    heater_name = "Detector" if detector else "Mechanism"
    actual = bool(getattr(thermal_status, field_name, 0))
    if actual != enabled:
        errors.append(f"{heater_name} manual heater state {int(actual)} does not match expected {int(enabled)}")


def verifyThermalResponse(
    response: Any, initial_mechanism: Any, initial_motor: Any, heater_name: str, errors: list[str]
) -> None:
    values = (getattr(response, "MECH_TRP", None), getattr(response, "MOTOR_TRP", None))
    if initial_mechanism is None or initial_motor is None or any(value is None for value in values):
        event_log.warning("%s heater thermal response cannot be compared because a TRP value is missing.", heater_name)
        return
    if values[0] <= initial_mechanism and values[1] <= initial_motor:
        errors.append(f"{heater_name} heater did not increase mechanism or motor TRP")


def verifyScienceOffsets(response: Any, swir_offset: int, mwir_offset: int, errors: list[str]) -> None:
    if response.SWIR_OFFSET != swir_offset or response.MWIR_OFFSET != mwir_offset:
        errors.append(
            f"SCI offsets not applied: SWIR={response.SWIR_OFFSET}, MWIR={response.MWIR_OFFSET}; "
            f"expected SWIR={swir_offset}, MWIR={mwir_offset}"
        )


def requestScience(port: Any, checkpoint: str) -> Any:
    response = repeat(port, tc.sci_request, 4, 20)
    if response == "ERROR" or response is None:
        raise RuntimeError(f"No valid science response received during {checkpoint}")
    return response


def logScienceMeasurement(response: Any, label: str) -> None:
    event_log.info(
        "%s: SWIR H/M/L=%s/%s/%s, MWIR H/M/L=%s/%s/%s, SWIR temp=%s, heat sink=%s",
        label,
        response.SWIR_HIGH,
        response.SWIR_MED,
        response.SWIR_LOW,
        response.MWIR_HIGH,
        response.MWIR_MED,
        response.MWIR_LOW,
        response.SWIR_TEMP,
        response.HT_SINK_TEMP,
    )


def getPsuReadings(psu_port: Any) -> dict[str, tuple[float, float]]:
    """Read CH1-CH4 (voltage, current) in (V, A) directly from the PSU."""
    if psu_port is None:
        return {}
    return {
        f"CH{channel}": (
            psu.parse_psu_reading(psu.psuRead(psu_port, str(channel), "V", True)),
            psu.parse_psu_reading(psu.psuRead(psu_port, str(channel), "I", True)),
        )
        for channel in range(1, 5)
    }


def logPsuSnapshot(psu_port: Any, label: str) -> dict[str, tuple[float, float]]:
    """Log PSU channel readings for operator review only (no pass/fail target)."""
    readings = getPsuReadings(psu_port)
    if not readings:
        event_log.info("%s: PSU snapshot unavailable.", label)
    else:
        event_log.info("%s: %s", label, readings)
    return readings


def checkPsuCurrent(
    psu_port: Any, channel: str, expected_ma: float, errors: list[str], *, tolerance_fraction: float = 0.15
) -> float | None:
    """Append an error if channel current is missing or outside tolerance of expected_ma."""
    reading = getPsuReadings(psu_port).get(channel)
    if reading is None:
        errors.append(f"{channel} current unavailable for verification (expected {expected_ma:.1f} mA)")
        return None
    measured_ma = reading[1] * 1000.0
    tolerance = max(1.0, expected_ma * tolerance_fraction)
    if abs(measured_ma - expected_ma) > tolerance:
        errors.append(
            f"{channel} current out of range: got {measured_ma:.2f} mA, expected {expected_ma:.1f} +/- {tolerance:.1f} mA"
        )
    return measured_ma


def checkMechanismCurrentZero(response: Any, errors: list[str], max_adu: int = 5) -> None:
    """Append an error if the HK mechanism current sense (HK_MECH_CUR) is not near zero."""
    mech_current_adu = getattr(response, "HK_MECH_CUR", None)
    if mech_current_adu is None:
        errors.append("HK_MECH_CUR not present in HK response")
        return
    if (mech_current_adu >> 4) > max_adu:
        errors.append(f"HK_MECH_CUR not at zero: got {mech_current_adu >> 4} ADU, expected <= {max_adu}")


def raiseIfErrors(label: str, errors: list[str], readings: dict[str, Any] | None = None) -> None:
    """Combine errors into one report, notify, and raise — mirrors the fft.py verification pattern."""
    if errors:
        count = len(errors)
        numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
        message = f"{label} verification failed: {count} error{'s' if count != 1 else ''}:\n" + "\n".join(numbered)
        ui_runtime_controller.notify_negative(message)
        raise AssertionError(message)
    message = f"{label} verification passed" + (f": {readings}" if readings else "")
    info_log.info(message)
    ui_runtime_controller.notify_positive(message)
