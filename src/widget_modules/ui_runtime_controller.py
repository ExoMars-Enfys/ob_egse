from __future__ import annotations

# Std library
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
import threading
from types import SimpleNamespace
import time
from typing import Any
from queue import Empty
import logging

from nicegui import ui, run

# utilities
from utility_modules import app_theme, eb_interface, eb_packet_utility, ebtcs, hk_conversions, psu, psu_log_utility
from utility_modules.eb_packet_utility import get_latest_hk

# core
from core_modules import tmstruct, constants as const
from core_modules.config import MODEL_CONSUMPTION

info_log = logging.getLogger("info_log")

"""This module contains backend controller functions for the UI, which are responsible for handling user interactions, updating the application state, and coordinating between different UI components and the underlying data. These controllers are designed to be bound to specific UI elements and provide a clear separation of concerns between the UI layout and the logic that drives it."""


# Script force-pause control

_FORCE_PAUSE_EVENT = threading.Event()


# --- HK and POST check for scripts (ported from ebgui) ---
def perform_hk_check(hk: Any = None, post: Any = None, hk_type: str = "hk") -> dict:
    """
    Perform HK or POST check as in ebgui, returning a result dict.
    Args:
        hk: Housekeeping packet object (for regular HK)
        post: POST packet object (for post HK)
        hk_type: 'hk' for regular HK, 'post' for POST check
    Returns:
        dict with keys: 'passed' (bool), 'details' (list of str)
    """
    result = {"passed": True, "details": []}

    if hk_type == "hk":
        if hk is None:
            result["passed"] = False
            result["details"].append("No HK data available.")
            return result
        # Values are already decoded, just check ranges

        # Extract, convert, and check for None before formatting
        try:
            eb_12v_raw = hk.EB_MEAS_MAIN_12V
            eb_neg12v_raw = hk.EB_MEAS_MAIN_NEG12V
            eb_5v_raw = hk.EB_MEAS_5V
            eb_3v3_raw = hk.EB_MEAS_3V3
            eb_tec_v_raw = hk.EB_MEAS_TEC_RAIL
            eb_0v_raw = hk.EB_0V_ADC_READING
            eb_tec_i_raw = hk.EB_TEC_DRIVE_CURRENT
        except Exception as e:
            result["passed"] = False
            result["details"].append(f"Missing HK field: {e}")
            return result

        value_fields = [
            (eb_12v_raw, "EB_MEAS_MAIN_12V"),
            (eb_neg12v_raw, "EB_MEAS_MAIN_NEG12V"),
            (eb_5v_raw, "EB_MEAS_5V"),
            (eb_3v3_raw, "EB_MEAS_3V3"),
            (eb_tec_v_raw, "EB_MEAS_TEC_RAIL"),
            (eb_0v_raw, "EB_0V_ADC_READING"),
            (eb_tec_i_raw, "EB_TEC_DRIVE_CURRENT"),
        ]
        for val, name in value_fields:
            if val is None:
                result["passed"] = False
                result["details"].append(f"{name} is None")

        # Only check ranges if all values are present
        if all(val is not None for val, _ in value_fields):
            eb_12v = eb_12v_raw * 0.000400543
            eb_neg12v = eb_neg12v_raw * -0.00038147
            eb_5v = eb_5v_raw * 0.000152829
            eb_3v3 = eb_3v3_raw * 0.0000763
            eb_tec_v = eb_tec_v_raw * 0.0000763
            eb_0v = eb_0v_raw * 0.0000763
            eb_tec_i = eb_tec_i_raw * 0.0000162
            checks = [
                (11.0 <= eb_12v <= 13.0, f"EB 12V out of range: {eb_12v:.2f} V"),
                (-13.0 <= eb_neg12v <= -11.0, f"EB -12V out of range: {eb_neg12v:.2f} V"),
                (4.5 <= eb_5v <= 5.5, f"EB 5V out of range: {eb_5v:.2f} V"),
                (2.8 <= eb_3v3 <= 3.8, f"EB 3V3 out of range: {eb_3v3:.2f} V"),
                (-0.5 <= eb_tec_v <= 0.5, f"EB TEC V out of range: {eb_tec_v:.2f} V"),
                (-0.5 <= eb_0v <= 0.5, f"EB 0V out of range: {eb_0v:.2f} V"),
                (-0.1 <= eb_tec_i <= 0.1, f"EB TEC I out of range: {eb_tec_i:.4f} A"),
            ]
            for ok, msg in checks:
                if not ok:
                    result["passed"] = False
                    result["details"].append(msg)

        if getattr(hk, "TCS_REJECTED", None) != 0:
            result["passed"] = False
            result["details"].append(f"TCS_REJECTED not 0: {getattr(hk, 'TCS_REJECTED', None)}")
        if getattr(hk, "INSTRUMENT_STATUS_FLAGS", None) != 25604:
            result["passed"] = False
            result["details"].append(
                f"INSTRUMENT_STATUS_FLAGS not 25604: {getattr(hk, 'INSTRUMENT_STATUS_FLAGS', None)}"
            )
        if getattr(hk, "ERROR_FLAGS", None) != 0:
            result["passed"] = False
            result["details"].append(f"ERROR_FLAGS not 0: {getattr(hk, 'ERROR_FLAGS', None)}")
        if getattr(hk, "WARNING_FLAGS", None) != 0:
            result["passed"] = False
            result["details"].append(f"WARNING_FLAGS not 0: {getattr(hk, 'WARNING_FLAGS', None)}")
        if getattr(hk, "FDIR_ALARM_FLAGS", None) != 0:
            result["passed"] = False
            result["details"].append(f"FDIR_ALARM_FLAGS not 0: {getattr(hk, 'FDIR_ALARM_FLAGS', None)}")
        if getattr(hk, "FDIR_WARNING_FLAGS", None) != 0:
            result["passed"] = False
            result["details"].append(f"FDIR_WARNING_FLAGS not 0: {getattr(hk, 'FDIR_WARNING_FLAGS', None)}")
        return result

    elif hk_type == "post":
        if post is None:
            result["passed"] = False
            result["details"].append("No POST data available.")
            return result
        # Convert POST voltages/temps if present
        try:
            tm_12v = post.TM_12V * 0.000400543 if hasattr(post, "TM_12V") else None
            tm_neg12v = post.TM_NEG12V * -0.00038147 if hasattr(post, "TM_NEG12V") else None
            tm_5v = post.TM_5V * 0.000152829 if hasattr(post, "TM_5V") else None
            tm_3v3 = post.TM_3V3 * 0.0000763 if hasattr(post, "TM_3V3") else None
            eb_processor_temp = (
                post.EB_PROCESSOR_TEMP * 0.01637198 - 273 if hasattr(post, "EB_PROCESSOR_TEMP") else None
            )
            tec_detector_temp = (
                post.TEC_DETECTOR_TEMP * -0.001830011 + 51.27039922 if hasattr(post, "TEC_DETECTOR_TEMP") else None
            )
        except Exception as e:
            result["passed"] = False
            result["details"].append(f"POST conversion error: {e}")
            return result

        # POST checks as in ebgui
        all_post_passed = (
            # getattr(post, "POST_WARNING_FLAGS", None) == 0
            getattr(post, "POST_ERROR_FLAGS", None) == 0
            and getattr(post, "NUM_BAD_FLASH_BLOCKS", None) == 0
            and getattr(post, "NUM_BAD_SRAM_BLOCKS", None) == 0
            and getattr(post, "ASW_IMAGE_1_CRC", None) == 0xBAF7
            and getattr(post, "ASW_IMAGE_2_CRC", None) == 0x5C55
            and getattr(post, "ASW_IMAGE_3_CRC", None) == 0x01CB
            and getattr(post, "ASW_IMAGE_4_CRC", None) == 0x5318
            and getattr(post, "ASW_IMAGE_5_CRC", None) == 0xDCAE
            and getattr(post, "BSW_IMAGE_CRC", None) == 0xD2D7
            # and getattr(post, "MEASUREMENT_TABLE_CRC", None) == 0x9D9B
        )
        if not all_post_passed:
            result["passed"] = False
            # Add details for each failed check
            # if getattr(post, "POST_WARNING_FLAGS", None) != 0:
            #     result["details"].append(f"POST_WARNING_FLAGS: {getattr(post, 'POST_WARNING_FLAGS', None)}")
            if getattr(post, "POST_ERROR_FLAGS", None) != 0:
                result["details"].append(f"POST_ERROR_FLAGS: {getattr(post, 'POST_ERROR_FLAGS', None)}")
            if getattr(post, "NUM_BAD_FLASH_BLOCKS", None) != 0:
                result["details"].append(f"NUM_BAD_FLASH_BLOCKS: {getattr(post, 'NUM_BAD_FLASH_BLOCKS', None)}")
            if getattr(post, "NUM_BAD_SRAM_BLOCKS", None) != 0:
                result["details"].append(f"NUM_BAD_SRAM_BLOCKS: {getattr(post, 'NUM_BAD_SRAM_BLOCKS', None)}")
            if getattr(post, "ASW_IMAGE_1_CRC", None) != 0xBAF7:
                result["details"].append(f"ASW_IMAGE_1_CRC: {getattr(post, 'ASW_IMAGE_1_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_2_CRC", None) != 0x5C55:
                result["details"].append(f"ASW_IMAGE_2_CRC: {getattr(post, 'ASW_IMAGE_2_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_3_CRC", None) != 0x01CB:
                result["details"].append(f"ASW_IMAGE_3_CRC: {getattr(post, 'ASW_IMAGE_3_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_4_CRC", None) != 0x5318:
                result["details"].append(f"ASW_IMAGE_4_CRC: {getattr(post, 'ASW_IMAGE_4_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_5_CRC", None) != 0xDCAE:
                result["details"].append(f"ASW_IMAGE_5_CRC: {getattr(post, 'ASW_IMAGE_5_CRC', None):#06x}")
            if getattr(post, "BSW_IMAGE_CRC", None) != 0xD2D7:
                result["details"].append(f"BSW_IMAGE_CRC: {getattr(post, 'BSW_IMAGE_CRC', None):#06x}")
            # if getattr(post, "MEASUREMENT_TABLE_CRC", None) != 0x9D9B:
            #     result["details"].append(f"MEASUREMENT_TABLE_CRC: {getattr(post, 'MEASUREMENT_TABLE_CRC', None):#06x}")
            # Optionally, add converted values to details for debugging
            if tm_12v is not None:
                result["details"].append(f"TM_12V: {tm_12v:.2f} V")
            if tm_neg12v is not None:
                result["details"].append(f"TM_NEG12V: {tm_neg12v:.2f} V")
            if tm_5v is not None:
                result["details"].append(f"TM_5V: {tm_5v:.2f} V")
            if tm_3v3 is not None:
                result["details"].append(f"TM_3V3: {tm_3v3:.2f} V")
            if eb_processor_temp is not None:
                result["details"].append(f"EB_PROCESSOR_TEMP: {eb_processor_temp:.2f} C")
            if tec_detector_temp is not None:
                result["details"].append(f"TEC_DETECTOR_TEMP: {tec_detector_temp:.2f} C")
        return result

    else:
        result["passed"] = False
        result["details"].append(f"Unknown hk_type: {hk_type}")
        return result


def perform_homing_check_sync(homing_timeout_s: float = 90) -> None:
    """Synchronous homing wait helper. Blocks until HOMING_COMPLETE or timeout/abort.

    This can be called from synchronous script code (e.g. inside `run_emc_init`).
    For async callers, use `await perform_homing_check()` which delegates to `run.io_bound`.
    """
    start_time = time.monotonic()
    info_log.debug("Starting homing wait loop for HOMING_COMPLETE flag...")

    homing_complete = 0
    while homing_complete == 0:
        latest_hk = get_latest_hk()

        # Allow user to abort the script while waiting
        if is_aborted():
            info_log.warning("Homing wait aborted by user.")
            notify_negative("Homing aborted by user.")
            raise RuntimeError("Homing aborted by user.")

        info_log.debug("No HK packet yet while waiting for HOMING_COMPLETE; continuing to wait.")

        # Prefer the decoded bitfield object `INSTR_STATUS_FLAGS` (set by parser).
        # Fall back to the numeric `INSTRUMENT_STATUS_FLAGS` if necessary.
        if latest_hk is None:
            homing_complete = 0
        elif hasattr(latest_hk, "INSTR_STATUS_FLAGS"):
            homing_complete = int(getattr(latest_hk.INSTR_STATUS_FLAGS, "HOMING_COMPLETE", 0) or 0)
        elif hasattr(latest_hk, "INSTRUMENT_STATUS_FLAGS"):
            # Fallback: treat numeric flags as bitmask and check LSB as HOMING_COMPLETE.
            try:
                homing_complete = 1 if (int(getattr(latest_hk, "INSTRUMENT_STATUS_FLAGS", 0)) & 0x1) != 0 else 0
            except Exception:
                homing_complete = 0
        else:
            homing_complete = 0

        hk_time = getattr(latest_hk, "TIME", None)
        info_log.info("Polling HK for HOMING_COMPLETE flag... Current value: %s, HK TIME: %s", homing_complete, hk_time)
        if homing_complete == 1:
            return
        if time.monotonic() - start_time > homing_timeout_s:
            info_log.error("Timeout waiting for HOMING_COMPLETE flag in HK telemetry (waited %ss)", homing_timeout_s)
            notify_negative("Timeout waiting for HOMING_COMPLETE flag in HK telemetry.")
            raise TimeoutError("Timeout waiting for HOMING_COMPLETE flag in HK telemetry.")
        time.sleep(1)  # Sleep briefly to avoid busy-waiting


def perform_acq_check_sync(acq_timeout_s: float = 300) -> None:
    """Synchronous acquisition wait helper. Blocks until ACQ_COMPLETE or timeout/abort.

    This can be called from synchronous script code (e.g. inside `run_emc_init`).
    For async callers, use `await perform_homing_check()` which delegates to `run.io_bound`.
    """
    start_time = time.monotonic()
    info_log.debug("Starting acquisition wait loop for ACQ -> Standby transition...")

    seen_acq = False
    while True:
        latest_hk = get_latest_hk()

        # Allow user to abort the script while waiting
        if is_aborted():
            info_log.warning("Acquisition wait aborted by user.")
            notify_negative("Acquisition aborted by user.")
            raise RuntimeError("Acquisition aborted by user.")

        if latest_hk is None:
            info_log.debug("No HK packet yet while waiting for acquisition to complete; continuing to wait.")
            if time.monotonic() - start_time > acq_timeout_s:
                info_log.error("Timeout waiting for acquisition to complete (waited %ss)", acq_timeout_s)
                notify_negative("Timeout waiting for acquisition to complete.")
                raise TimeoutError("Timeout waiting for acquisition to complete.")
            time.sleep(1)
            continue

        # Read CURRENT_OPERATING_STATE which may be a numeric code or a descriptive string
        state_val = getattr(latest_hk, "CURRENT_OPERATING_STATE", None)
        state_is_acq = False
        state_is_standby = False

        if isinstance(state_val, str):
            s = state_val.strip().upper()
            state_is_acq = s in ("ACQUISITION", "ACQ")
            state_is_standby = s in ("STANDBY",)
        else:
            if state_val is None:
                state_is_acq = False
                state_is_standby = False
            else:
                try:
                    state_int = int(state_val)
                    state_is_acq = state_int == 0x08
                    state_is_standby = state_int == 0x04
                except Exception:
                    # fallback to string representation if conversion failed
                    try:
                        s = str(state_val).strip().upper()
                        state_is_acq = s in ("ACQUISITION", "ACQ")
                        state_is_standby = s in ("STANDBY",)
                    except Exception:
                        state_is_acq = False
                        state_is_standby = False

        hk_time = getattr(latest_hk, "TIME", None)
        info_log.info(
            "Polling HK for ACQ->Standby: state=%s (acq=%s, standby=%s) at %s",
            state_val,
            state_is_acq,
            state_is_standby,
            hk_time,
        )

        if state_is_acq:
            seen_acq = True

        # If we have observed acquisition and now see standby, succeed
        if seen_acq and state_is_standby:
            info_log.info("Acquisition completed: transitioned to Standby.")
            notify_positive("Acquisition complete: Standby detected.")
            return

        # If we never saw acquisition but already in standby, just return
        if (not seen_acq) and state_is_standby:
            info_log.info("Already in Standby; no acquisition active.")
            return

        if time.monotonic() - start_time > acq_timeout_s:
            info_log.error("Timeout waiting for acquisition to complete (waited %ss)", acq_timeout_s)
            notify_negative("Timeout waiting for acquisition to complete.")
            raise TimeoutError("Timeout waiting for acquisition to complete.")

        time.sleep(1)  # Sleep briefly to avoid busy-waiting


async def perform_homing_check(homing_timeout_s: float = 60.0) -> None:
    """Async wrapper that runs the synchronous homing check in an executor."""
    await run.io_bound(lambda: perform_homing_check_sync(homing_timeout_s))


def verify_safe_ret():
    errors = []
    # ?RET and first check
    # This block performs the SAFE RET verification after issuing a RET and HK request.
    try:
        latest_post = const.eb_post_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty:
        errors.append("\nMissing POST or PSU queue data after RET")
        latest_post = None
        latest_psu = None

    ch4_current_ma = None
    if latest_psu is not None:
        consumption_check("State1", latest_psu, errors)
        ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0

    result = None
    if latest_post is not None:
        result = perform_hk_check(hk=None, post=latest_post, hk_type="post")

        # Check the POST packet for all required fields and limits
        if not (result and result.get("passed", False)):
            if result and "details" in result and result["details"]:
                errors.extend(result["details"])
            else:
                errors.append(f"POST Packet Check failed with unknown error: {result}")
    if errors:
        count = len(errors)
        numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
        info_log.info(f"PSU_EB_I: {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA")
        msg = f"SAFE RET verification failed: {count} error{'s' if count != 1 else ''} :\n" + "\n".join(numbered)
        return msg, False
    else:
        msg = f"Power State 1 - SAFE mode: EB PSU I : {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA, \nPOST Packet Check Result: {result}"
        info_log.info(msg)
        return msg, True


def verify_standby_ret():
    errors = []
    # ?Standby and check
    # This block performs the STANDBY RET verification after issuing a Standby, RET, and HK request.
    try:
        latest_hk = get_latest_hk()
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty:
        errors.append("\nMissing HK or PSU queue data after STANDBY")
        latest_hk = None
        latest_psu = None

    ch4_current_ma = None
    if latest_psu is not None:
        consumption_check("Standby", latest_psu, errors)
        ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0

    result = None
    if latest_hk is not None:
        result = perform_hk_check(hk=latest_hk, post=None, hk_type="hk")

        # Check the HK packet for all required fields and limits
        if not (result and result.get("passed", False)):
            if result and "details" in result and result["details"]:
                errors.extend(result["details"])
            else:
                errors.append(f"HK Check failed with unknown error: {result}")
    if errors:
        count = len(errors)
        numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
        info_log.info(f"PSU_EB_I: {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA")
        msg = f"STANDBY RET verification failed: {count} error{'s' if count != 1 else ''} :\n" + "\n".join(numbered)
        return msg, False
    else:
        msg = f"Standby mode: EB PSU I : {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA, \nHK Check Result: {result}"
        info_log.info(msg)
        return msg, True


def notify_script_pause(current: int, total: int) -> None:
    """Notify the user that the script is paused, showing progress."""
    msg = f"Script paused, command {current} of {total}"
    try:
        ui.notify(msg, color="warning")
    except Exception:
        # If UI notify cannot be created from this context (background
        # thread or client deleted), fall back to console output.
        try:
            print(msg)
        except Exception:
            pass


def request_force_pause() -> None:
    """Request a forced pause — blocks script execution until released."""
    _FORCE_PAUSE_EVENT.set()


def clear_force_pause() -> None:
    """Release a previously requested forced pause."""
    _FORCE_PAUSE_EVENT.clear()


def is_force_paused() -> bool:
    """Return True when script execution is held by a forced pause."""
    return _FORCE_PAUSE_EVENT.is_set()


def notify_script_done() -> None:
    """Notify the user that the script has completed."""
    msg = "Script execution complete."
    try:
        ui.notify(msg, color="positive")
    except Exception:
        try:
            print(msg)
        except Exception:
            pass


def notify_positive(msg) -> None:
    try:
        ui.notify(msg, color="positive")
    except Exception:
        try:
            print(msg)
        except Exception:
            pass


def notify_negative(msg) -> None:
    try:
        ui.notify(msg, color="negative")
    except Exception:
        try:
            print(msg)
        except Exception:
            pass


def consumption_check(state_names, psu_sample: dict, errors: list[str]) -> float | None:
    """
    Checks PSU current for the given state(s) and current OB model.
    Accepts a single state name (str) or a list of state names.
    Sums expected values for all provided states.
    Appends error to errors if out of range.
    Model is read from app.state.current_model.
    """
    from nicegui import app

    model = getattr(app.state, "current_model", None)
    if model is None:
        errors.append("No model specified for PSU consumption check.")
        return None
    if model not in MODEL_CONSUMPTION:
        errors.append(f"Unknown OB model: {model}")
        return None
    model_dict = MODEL_CONSUMPTION[model]
    if isinstance(state_names, str):
        state_names = [state_names]
    missing = [s for s in state_names if s not in model_dict]
    if missing:
        errors.append(f"Unknown state(s) {missing} for model '{model}'")
        return None
    if psu_sample is None:
        errors.append("No PSU sample provided for consumption check.")
        return None
    measured_current_ma = float(psu_sample.get("PSU_EB_I") or 0.0) * 1000.0
    base = sum(model_dict[s] for s in state_names)
    min_i = base - 10
    max_i = base + 10
    if not (min_i <= measured_current_ma <= max_i):
        errors.append(
            f"PSU_EB_I out of range for {state_names} ({model}): got {measured_current_ma:.2f} mA, expected {min_i}-{max_i}"
        )
    return measured_current_ma


# Central script runtime control (play / pause / abort)
_SCRIPT_CONTROL = {
    "running": False,
    "pause_event": threading.Event(),
    "abort_event": threading.Event(),
    "current_script": None,
}


def get_script_control() -> dict:
    """Return the runtime script control dictionary.

    Keys: `running` (bool), `pause_event` (threading.Event),
    `abort_event` (threading.Event), `current_script` (optional name).
    """
    return _SCRIPT_CONTROL


def start_script(script_name: str | None = None) -> None:
    """Mark a script as running and clear control events."""
    _SCRIPT_CONTROL["running"] = True
    _SCRIPT_CONTROL["current_script"] = script_name
    _SCRIPT_CONTROL["pause_event"].clear()
    _SCRIPT_CONTROL["abort_event"].clear()
    # Ensure any UI-forced pause is released when starting a new script
    _FORCE_PAUSE_EVENT.clear()


def finish_script() -> None:
    """Clear running state and reset control events."""
    _SCRIPT_CONTROL["running"] = False
    _SCRIPT_CONTROL["pause_event"].clear()
    _SCRIPT_CONTROL["abort_event"].clear()
    _SCRIPT_CONTROL["current_script"] = None


def is_script_running() -> bool:
    return bool(_SCRIPT_CONTROL.get("running"))


def request_pause() -> None:
    _SCRIPT_CONTROL["pause_event"].set()


def clear_pause() -> None:
    _SCRIPT_CONTROL["pause_event"].clear()


def is_paused() -> bool:
    return _SCRIPT_CONTROL["pause_event"].is_set()


def toggle_pause() -> None:
    if is_force_paused():
        # If a UI-forced pause was active, clear it first
        clear_force_pause()
        return
    if is_paused():
        clear_pause()
    else:
        request_pause()


def request_abort() -> None:
    _SCRIPT_CONTROL["abort_event"].set()


def clear_abort() -> None:
    _SCRIPT_CONTROL["abort_event"].clear()


def is_aborted() -> bool:
    return _SCRIPT_CONTROL["abort_event"].is_set()


# General controllers


def create_set_mode(*, app: Any, state: dict[str, Any]) -> Any:
    """Create a mode setter callback bound to current state and app."""

    def set_mode(mode: str) -> None:
        if mode not in ("EB", "OB"):
            return
        previous_mode = state.get("mode")
        state["mode"] = mode
        app.state.egse_mode = mode
        for refresh in state["plot_refreshers"]:
            refresh(mode)
        if previous_mode != mode:
            # Update PSU channels based on the new mode
            psu_port = state.get("psu_port")
            psu_lock = state.get("psu_lock")
            psu_mode_state = state.get("psu_mode_state")
            if isinstance(psu_mode_state, dict):
                psu_mode_state["ebmode"] = mode == "EB"
            if psu_port:
                ebmode = mode == "EB"
                lock_ctx = psu_lock if psu_lock is not None else nullcontext()
                with lock_ctx:
                    psu.setChannels(psu_port, ebmode)
            # Run mode change resetters
            for reset in state.get("mode_change_resetters", []):
                reset()
        sync_packet_tabs = state.get("sync_packet_tabs")
        if callable(sync_packet_tabs):
            sync_packet_tabs(mode)

    return set_mode


def dispatch_ob_tc(state: dict[str, Any], command: Any, *args: Any, **kwargs: Any) -> None:
    """Send an OB TC using the shared OB port lock when available."""
    ob_port = state.get("ob_port")
    if ob_port is None:
        ui.notify("OB port unavailable", color="negative")
        return

    lock = state.get("port_lock")
    lock_ctx = lock if lock is not None else nullcontext()
    with lock_ctx:
        command(ob_port, *args, **kwargs)


def create_sci_navigation_state(max_packets: int = 12) -> dict[str, Any]:
    """Create backend-owned SCI navigation state for packet/point swiping."""
    return {
        "packets": [],
        "identities": set(),
        "packet_index": 0,
        "point_index": 0,
        "max_packets": max_packets,
    }


def sci_current_packet(sci_state: dict[str, Any]) -> Any | None:
    packets = sci_state.get("packets") or []
    if not packets:
        return None
    idx = int(sci_state.get("packet_index", 0)) % len(packets)
    return packets[idx]


def sci_set_packet_index(sci_state: dict[str, Any], packet_index: int) -> Any | None:
    packets = sci_state.get("packets") or []
    if not packets:
        sci_state["packet_index"] = 0
        sci_state["point_index"] = 0
        return None
    sci_state["packet_index"] = packet_index % len(packets)
    sci_state["point_index"] = 0
    return sci_current_packet(sci_state)


def sci_shift_packet_index(sci_state: dict[str, Any], delta: int) -> Any | None:
    current = int(sci_state.get("packet_index", 0))
    return sci_set_packet_index(sci_state, current + delta)


def sci_set_point_index(sci_state: dict[str, Any], point_index: int) -> int:
    packet = sci_current_packet(sci_state)
    if packet is None:
        sci_state["point_index"] = 0
        return 0
    point_count = int(getattr(packet, "SCI_POINT_COUNT", 0) or 0)
    if point_count <= 0:
        sci_state["point_index"] = 0
        return 0
    sci_state["point_index"] = min(max(point_index, 0), point_count - 1)
    return sci_state["point_index"]


def sci_shift_point_index(sci_state: dict[str, Any], delta: int) -> int:
    packet = sci_current_packet(sci_state)
    if packet is None:
        sci_state["point_index"] = 0
        return 0
    point_count = int(getattr(packet, "SCI_POINT_COUNT", 0) or 0)
    if point_count <= 0:
        sci_state["point_index"] = 0
        return 0
    current = int(sci_state.get("point_index", 0))
    sci_state["point_index"] = (current + delta) % point_count
    return sci_state["point_index"]


def sci_add_packet(sci_state: dict[str, Any], raw_packet: Any) -> Any | None:
    """Normalize, dedupe, and insert an SCI packet into backend state."""
    packet_obj = raw_packet
    if not hasattr(packet_obj, "__dict__") and isinstance(packet_obj, dict):
        packet_obj = SimpleNamespace(**packet_obj)
    if not hasattr(packet_obj, "__dict__"):
        return None

    packet_obj = eb_packet_utility.merge_sci_data_packet(packet_obj)

    def _packet_sort_key(packet: Any) -> int:
        try:
            return int(getattr(packet, "PACKET_NUMBER", 0))
        except (TypeError, ValueError):
            return 0

    def _packet_identity(packet: Any) -> tuple[Any, ...]:
        packet_number = getattr(packet, "PACKET_NUMBER", None)
        criticality = getattr(packet, "SCI_PACKET_CRITICALITY", None)
        point_count = int(getattr(packet, "SCI_POINT_COUNT", 0) or 0)
        first_abs_step = None
        last_abs_step = None
        sci_points = getattr(packet, "SCI_POINTS", None)
        if sci_points:
            first_abs_step = getattr(sci_points[0], "ABS_STEPS", None)
            last_abs_step = getattr(sci_points[-1], "ABS_STEPS", None)
        elif hasattr(packet, "ABS_STEPS"):
            first_abs_step = getattr(packet, "ABS_STEPS", None)
            last_abs_step = first_abs_step
        return (packet_number, criticality, point_count, first_abs_step, last_abs_step)

    identities = sci_state.setdefault("identities", set())
    identity = _packet_identity(packet_obj)
    if identity in identities:
        return packet_obj

    packets = sci_state.setdefault("packets", [])
    packets.append(packet_obj)
    packets.sort(key=_packet_sort_key)

    max_packets = int(sci_state.get("max_packets", 12) or 12)
    if len(packets) > max_packets:
        sci_state["packets"] = packets[-max_packets:]
        packets = sci_state["packets"]

    sci_state["identities"] = {_packet_identity(packet) for packet in packets}
    sci_set_packet_index(sci_state, len(packets) - 1)
    return packet_obj


# Theme helpers


def _apply_theme_to_ui(
    *,
    ui: Any,
    app: Any,
    theme: str,
    css_path: Path,
    theme_state: dict[str, str],
    theme_plots: list[Any],
    logo_images: list[Any],
) -> None:
    theme_state["value"] = theme
    css_vars = app_theme.load_css_vars(css_path, theme=theme)
    app.state.theme_vars = css_vars
    app.state.theme_palette = app_theme.get_theme_palette(css_vars, theme)
    plot_labels = {f"plot_{idx}": plot for idx, plot in enumerate(theme_plots)}
    app_theme.apply_theme(
        ui,
        theme,
        css_vars,
        plot_labels,
        list(plot_labels.keys()),
        logo_images,
        css_vars.get("logo-light-src", "/rsrc/Enfys_logo.png"),
        css_vars.get("logo-dark-src", "/rsrc/Enfys_logo_-_FINAL_-_WHITE.png"),
    )


def create_set_theme(
    *,
    ui: Any,
    app: Any,
    state: dict[str, Any],
    css_path: Path,
    theme_state: dict[str, str],
    theme_plots: list[Any],
    logo_images: list[Any] | None = None,
) -> Any:
    """Create a theme setter callback bound to current UI controllers."""

    def set_theme(theme: str) -> None:
        if theme not in ("dark", "light"):
            return
        _apply_theme_to_ui(
            ui=ui,
            app=app,
            theme=theme,
            css_path=css_path,
            theme_state=theme_state,
            theme_plots=theme_plots,
            logo_images=logo_images or [],
        )

    return set_theme


# PSU helpers


_PSU_SAMPLE_KEYS = (
    "status",
    "CH1_STATUS",
    "CH2_STATUS",
    "CH3_STATUS",
    "CH4_STATUS",
    "PSU_ROV_HTR_V",
    "PSU_ROV_HTR_I",
    "PSU_EB_V",
    "PSU_EB_I",
    "CH1_V",
    "CH1_I",
    "CH2_V",
    "CH2_I",
    "CH3_V",
    "CH3_I",
    "CH4_V",
    "CH4_I",
)


def _reset_psu_replay(replay: dict[str, Any]) -> None:
    replay["enabled"] = False
    replay["source_path"] = None
    replay["records"] = []
    replay["index"] = 0
    replay["hk_anchor"] = None
    replay["latest_hk_time"] = None
    replay["psu_anchor"] = None


def _card_channel_preferences(card: Any, mode: str) -> tuple[list[str], bool]:
    by_mode = card.channel.get("replay_channel_by_mode", {})
    configured = by_mode.get(mode, by_mode.get("EB") or "CH3")
    if isinstance(configured, str):
        return [configured.upper()], True
    if isinstance(configured, list):
        channels = [str(ch).upper() for ch in configured if str(ch)]
        return channels, bool(channels)
    return ["CH3"], True


def _update_psu_readings(state: dict[str, Any], psu_sample: dict[str, Any]) -> None:
    readings = state["last_psu_readings"]
    for key in _PSU_SAMPLE_KEYS:
        source_key = "STATUS" if key == "status" else key
        readings[key] = psu_sample.get(source_key)


def _update_psu_cards(psu_cards: list[Any], psu_sample: dict[str, Any]) -> None:
    for card in psu_cards:
        status_key = card.channel.get("status_key")
        if isinstance(status_key, str) and status_key in psu_sample and psu_sample.get(status_key) is not None:
            card.set_enabled_from_psu(bool(psu_sample.get(status_key)))
        current_key = card.channel.get("live_current_key")
        if isinstance(current_key, str):
            card.push_sample(psu_sample.get("TIME"), psu_sample.get(current_key))


def _update_psu_alarm_lights(state: dict[str, Any], psu_sample: dict[str, Any]) -> None:
    status_ok = bool(psu_sample.get("STATUS"))
    alarm_lights = state.get("alarm_lights") or {}
    if "ob" in alarm_lights:
        alarm_lights["ob"].update_from_faults(
            {"PSU status is not OK": state["mode"] == "OB" and not status_ok}, source="psu"
        )
    if "eb" in alarm_lights:
        alarm_lights["eb"].update_from_faults(
            {"PSU status is not OK": state["mode"] == "EB" and not status_ok}, source="psu"
        )


def _apply_psu_sample(state: dict[str, Any], psu_cards: list[Any], psu_sample: dict[str, Any]) -> None:
    _update_psu_readings(state, psu_sample)
    _update_psu_cards(psu_cards, psu_sample)
    _update_psu_alarm_lights(state, psu_sample)


def _build_replay_psu_sample(state: dict[str, Any], psu_cards: list[Any], record: dict[str, Any]) -> dict[str, Any]:
    channels = record.get("CHANNELS", {})
    sample: dict[str, Any] = {key: None for key in _PSU_SAMPLE_KEYS if key != "status"}
    sample.update({"TIME": datetime.now(), "STATUS": bool(record.get("STATUS", True))})

    for card in psu_cards:
        channel_data: dict[str, Any] = {}
        preferred_channels, allow_fallback = _card_channel_preferences(card, state["mode"])
        for channel_name in preferred_channels:
            candidate = channels.get(channel_name, {})
            if candidate.get("V") is not None or candidate.get("I") is not None:
                channel_data = candidate
                break
        if not channel_data and allow_fallback:
            for fallback_name in ("CH4", "CH3", "CH2", "CH1"):
                candidate = channels.get(fallback_name, {})
                if candidate.get("V") is not None or candidate.get("I") is not None:
                    channel_data = candidate
                    break

        voltage_key = card.channel.get("live_voltage_key")
        current_key = card.channel.get("live_current_key")
        if isinstance(voltage_key, str):
            sample[voltage_key] = channel_data.get("V")
        if isinstance(current_key, str):
            sample[current_key] = channel_data.get("I")

    return sample


def create_set_psu_log_path(*, state: dict[str, Any], logger: Any) -> Any:
    """Create PSU replay-log setter callback bound to current state."""

    def set_psu_log_path(psu_log_path: str | None) -> bool:
        replay = state["psu_replay"]
        if not psu_log_path:
            _reset_psu_replay(replay)
            return False

        records = psu_log_utility.load_psu_channel_samples(psu_log_path)
        now = datetime.now()
        replay["enabled"] = bool(records)
        replay["source_path"] = psu_log_path
        replay["records"] = records
        replay["index"] = 0
        replay["hk_anchor"] = now if records else None
        replay["latest_hk_time"] = now if records else None
        replay["psu_anchor"] = records[0]["TIME"] if records else None

        if records:
            logger.info("Loaded %d PSU replay samples from %s", len(records), psu_log_path)
            return True

        logger.warning("No valid PSU replay samples found in %s", psu_log_path)
        return False

    return set_psu_log_path


def create_set_psu_card_profiles(*, ch1_card: Any, ch2_card: Any, ch3_card: Any, ch4_card: Any) -> Any:
    """Create mode-dependent PSU card profile callback bound to PSU card controllers."""

    def set_psu_card_profiles(mode: str) -> None:
        ob_mode = mode == "OB"
        ch1_card.apply_profile(
            title="CH1 +12V Current",
            visible=ob_mode,
            live_voltage_key="CH1_V",
            live_current_key="CH1_I",
            replay_channels=["CH1"],
        )
        ch2_card.apply_profile(
            title="CH2 -12V Current",
            visible=ob_mode,
            live_voltage_key="CH2_V",
            live_current_key="CH2_I",
            replay_channels=["CH2"],
        )
        ch3_card.apply_profile(
            title="CH3 +5V Current" if ob_mode else "CH3 ROVHTR Current",
            visible=True,
            live_voltage_key="CH3_V" if ob_mode else "PSU_ROV_HTR_V",
            live_current_key="CH3_I" if ob_mode else "PSU_ROV_HTR_I",
            replay_channels=["CH3"],
        )
        ch4_card.apply_profile(
            title="CH4 ROVHTR Current" if ob_mode else "CH4 +28V Current",
            visible=True,
            live_voltage_key="CH4_V" if ob_mode else "PSU_EB_V",
            live_current_key="CH4_I" if ob_mode else "PSU_EB_I",
            replay_channels=["CH4"],
        )

    return set_psu_card_profiles


def create_poll_psu(*, state: dict[str, Any], const: Any, psu_cards: list[Any]) -> Any:
    """Create PSU polling callback bound to the current UI state and cards."""

    def poll_psu() -> None:
        replay = state["psu_replay"]
        saw_live_psu = False
        latest_live_sample = None
        # Bound per-tick queue work to keep the UI event loop responsive.
        max_live_samples_per_tick = 25
        processed = 0
        while not const.psu_queue.empty() and processed < max_live_samples_per_tick:
            saw_live_psu = True
            latest_live_sample = const.psu_queue.get()
            processed += 1

        if latest_live_sample is not None:
            _apply_psu_sample(state, psu_cards, latest_live_sample)

        if saw_live_psu:
            return

        # Replay is only used when there are no live PSU samples available.
        if not state["log_search"]["enabled"] and not replay.get("enabled"):
            return

        if not replay.get("enabled"):
            return
        records = replay.get("records") or []
        if not records:
            return

        idx = int(replay.get("index", 0))
        sample = _build_replay_psu_sample(state, psu_cards, records[idx % len(records)])
        _apply_psu_sample(state, psu_cards, sample)
        replay["index"] = idx + 1

    return poll_psu


# TM helpers


_OB_TRP_FIELDS = tuple(name for name in ("OB_DIGITAL_TRP", "OB_DETECTOR_TRP", "OB_MECHANISM_TRP", "OB_MOTOR_TRP"))
_VOLTAGE_3V3_FIELDS = tuple(name for name in ("OB_3V3_VOLTAGE", "EB_MEAS_3V3"))
_WARNING_NAMES = [name for name, _ in tmstruct.eb_warning_flags]
_FDIR_NAMES = [name for name, _ in tmstruct.eb_fdir_flags]
_OB_WARNING_FLAGS = {
    "OB_FDIR_ALARM",
    "OB_GENERAL_ERROR",
    "OB_MOTOR_ERROR",
    "OB_UNRESPONSIVE",
    "OB_STEP_COUNT_MISMATCH",
}
_OB_FDIR_FLAGS = {
    "FPGA_IO_POWER_SUPPLY",
    "FPGA_CORE_POWER_SUPPLY",
    "DIGITAL_BOARD_TRP",
    "DETECTOR_BOARD_TRP",
    "MECH_BOARD_TRP",
    "MOTOR_TRP",
}
_EB_WARNING_FLAGS = {
    "GENERAL_ERROR",
    "EB_FDIR_ALARM",
    "WATCHDOG_TIMEOUT_DETECTED",
    "NO_RET_RECEIVED",
    "NO_HEALTHY_ASW_IMAGE",
    "PATCH_WRITING_ERROR",
    "RS422_RECEIVE_ERROR",
    "RS422_TRANSMIT_ERROR",
    "RS485_RECEIVE_ERROR",
    "RS485_TRANSMIT_ERROR",
}
_EB_FDIR_FLAGS = {
    "EB_PLUS_12V_SUPPLY",
    "EB_MINUS_12V_SUPPLY",
    "EB_PLUS_5V_SUPPLY",
    "EB_PLUS_3V3_SUPPLY",
    "PROCESSOR_INTERNAL_TEMPERATURE",
    "INTERNAL_TRP_TEMPERATURE",
    "PSU_BOARD_TEMPERATURE",
}


def _decode_tuple(packet: Any, field_names: tuple[str, ...]) -> list[float] | None:
    values: list[float] = []
    for name in field_names:
        value = hk_conversions.decode_field(packet, name)
        if value is None:
            return None
        values.append(value)
    return values


def _decoded(packet: Any, field_name: str) -> float | None:
    value = hk_conversions.decode_field(packet, field_name)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _active_flag_names(flag_ns: Any, ordered_names: list[str]) -> list[str]:
    if flag_ns is None:
        return []
    return [
        name
        for name in ordered_names
        if not name.startswith("UNUSED") and not name.startswith("RESERVED") and bool(getattr(flag_ns, name, 0))
    ]


def _any_flag(flag_ns: Any) -> bool:
    return bool(flag_ns) and any(bool(value) for value in flag_ns.__dict__.values())


def _ob_alarm_details(hk: Any) -> list[str]:
    warning_bits = _active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), _WARNING_NAMES)
    fdir_alarm_bits = _active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), _FDIR_NAMES)
    fdir_warning_bits = _active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), _FDIR_NAMES)

    details = [f"OB Warning: {flag}" for flag in warning_bits if flag in _OB_WARNING_FLAGS]
    details.extend([f"OB FDIR Alarm: {flag}" for flag in fdir_alarm_bits if flag in _OB_FDIR_FLAGS])
    details.extend([f"OB FDIR Warning: {flag}" for flag in fdir_warning_bits if flag in _OB_FDIR_FLAGS])
    if _any_flag(getattr(hk, "ERRORS", None)):
        details.append("OB Error flags active")
    if _any_flag(getattr(hk, "MTR_ERRORS", None)):
        details.append("OB Motor error flags active")
    return details


def _eb_alarm_details(hk: Any) -> list[str]:
    warning_bits = _active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), _WARNING_NAMES)
    fdir_alarm_bits = _active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), _FDIR_NAMES)
    fdir_warning_bits = _active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), _FDIR_NAMES)

    details: list[str] = []
    tcs_rejected = int(getattr(hk, "TCS_REJECTED", 0) or 0)
    if tcs_rejected > 0:
        details.append(f"TCS Rejected: {tcs_rejected}")
    details.extend([f"EB Warning: {flag}" for flag in warning_bits if flag in _EB_WARNING_FLAGS])
    details.extend([f"EB FDIR Alarm: {flag}" for flag in fdir_alarm_bits if flag in _EB_FDIR_FLAGS])
    details.extend([f"EB FDIR Warning: {flag}" for flag in fdir_warning_bits if flag in _EB_FDIR_FLAGS])
    return details


def _update_hk_alarm_lights(state: dict[str, Any], hk: Any) -> None:
    alarm_lights = state.get("alarm_lights") or {}
    ob_details = _ob_alarm_details(hk)
    eb_details = _eb_alarm_details(hk)
    if "ob" in alarm_lights:
        alarm_lights["ob"].update_from_faults({detail: True for detail in ob_details}, source="hk")
    if "eb" in alarm_lights:
        alarm_lights["eb"].update_from_faults({detail: True for detail in eb_details}, source="hk")


def _update_plot_cards(state: dict[str, Any], hk: Any, ob_trp_card: Any, voltage_3v3_card: Any) -> None:
    time_value = getattr(hk, "TIME", None)
    if time_value is None:
        return

    replay = state["psu_replay"]
    replay["latest_hk_time"] = time_value
    if replay.get("hk_anchor") is None:
        replay["hk_anchor"] = time_value

    instr_flags = getattr(hk, "INSTR_STATUS_FLAGS", None)
    ob_enabled = bool(getattr(instr_flags, "OB_5V_ENABLED", 0))
    ob_trp_card.set_stream_enabled(ob_enabled)
    voltage_3v3_card.set_stream_enabled(ob_enabled)

    if not ob_enabled:
        return

    ob_trp_vals = _decode_tuple(hk, _OB_TRP_FIELDS)
    if ob_trp_vals is not None:
        ob_trp_card.push([time_value], [[v] for v in ob_trp_vals])

    voltage_vals = _decode_tuple(hk, _VOLTAGE_3V3_FIELDS)
    if voltage_vals is not None:
        voltage_3v3_card.push([time_value], [[v] for v in voltage_vals])


def _update_packet_viewer(mode: str, packet_viewer_controllers: dict[str, Any], hk: Any) -> None:
    packet_viewer_controllers["OB_HK" if mode == "OB" else "EB_HK"].update_from_packet(hk)


def _drain_packet_queue(queue: Any, handler: Any) -> None:
    while not queue.empty():
        handler(queue.get())


# MMS helpers


_MMS_FIELDS = (
    ("EB +12V", "EB_MEAS_MAIN_12V", "eb_12v", False),
    ("EB -12V", "EB_MEAS_MAIN_NEG12V", "eb_neg12v", False),
    ("EB +5V", "EB_MEAS_5V", "eb_5v", False),
    ("EB +3V3", "EB_MEAS_3V3", "eb_3v3", False),
    ("EB MCU Temp", "EB_MCU_INTERNAL_TEMP", "eb_mcu_temp", False),
    ("EB Internal TRP", "EB_INTERNAL_TRP_TEMP", "eb_internal_trp_temp", False),
    ("EB PSU TRP", "EB_PSU_BOARD_TEMP", "eb_psu_trp_temp", False),
    ("EB TEC rail", "EB_MEAS_TEC_RAIL", "eb_tec_rail_v", True),
    ("OB FPGA Core", "OB_3V3_VOLTAGE", "ob_fpga_core_v", False),
    ("OB FPGA IO", "OB_1V5_VOLTAGE", "ob_fpga_io_v", False),
    ("OB DIG TRP", "OB_DIGITAL_TRP", "ob_digital_trp", False),
    ("OB DET TRP", "OB_DETECTOR_TRP", "ob_detector_trp", False),
    ("OB MECH TRP", "OB_MECHANISM_TRP", "ob_mechanism_trp", False),
    ("OB MOTOR TRP", "OB_MOTOR_TRP", "ob_motor_trp", False),
)


def _violates_limits(value: float | None, limits: tuple[float | None, float | None]) -> bool:
    if value is None:
        return False
    low, high = limits
    return (low is not None and value < low) or (high is not None and value > high)


def _append_violation(
    reasons: list[str], label: str, value: float | None, limits: tuple[float | None, float | None]
) -> bool:
    if not _violates_limits(value, limits):
        return False
    low, high = limits
    reasons.append(f"{label} out of limits: value={value}, limits=({low}, {high})")
    return True


def _limit_tuple(value: Any) -> tuple[float | None, float | None]:
    if isinstance(value, tuple) and len(value) == 2:
        return value
    return (None, None)


def _mms_reasons(hk: Any, limits: dict[str, Any]) -> tuple[list[str], bool, bool]:
    reasons: list[str] = []
    tec_pre_action = False
    ob5v_pre_action = False

    # Check OB_5V_ENABLED and SAFE mode
    instr_status_flags = int(getattr(hk, "INSTRUMENT_STATUS_FLAGS", 0))
    ob_5v_enabled = (instr_status_flags >> 5) & 0x1  # OB_5V_ENABLED is bit 5
    current_state = int(
        getattr(hk, "CURRENT_OPERATING_STATE", 0) if getattr(hk, "CURRENT_OPERATING_STATE", None) is not None else 0
    )
    skip_ob_checks = (not ob_5v_enabled) or (current_state == 0x02)

    for label, field_name, limit_key, tec_field in _MMS_FIELDS:
        if label.startswith("OB ") and skip_ob_checks:
            continue  # Skip OB parameter checks if OB is off or in SAFE
        violated = _append_violation(reasons, label, _decoded(hk, field_name), _limit_tuple(limits.get(limit_key)))
        tec_pre_action = tec_pre_action or (tec_field and violated)
        ob5v_pre_action = ob5v_pre_action or (label.startswith("OB ") and violated)

    if bool(getattr(hk, "POST_ERROR_FLAGS", 0)):
        reasons.append("POST Error Flags asserted")
    if bool(getattr(hk, "ERROR_FLAGS", 0)):
        reasons.append("HK Error Flags asserted")

    return reasons, tec_pre_action, ob5v_pre_action


def _disable_ob5v(logger: Any) -> None:
    try:
        interface = eb_interface.get_egse_interface()
        status = ebtcs.en_ob5v(interface, 0)
        if status == "ERROR":
            logger.warning("MMS pre-action: OB 5V disable command failed over EB link.")
            return
        logger.warning("MMS pre-action: OB 5V disable command sent over EB link.")
    except Exception as exc:
        logger.error(f"MMS pre-action failed while disabling OB 5V over EB link: {exc}")


def _run_mms_actions(
    app: Any,
    state: dict[str, Any],
    logger: Any,
    hk: Any,
    reasons: list[str],
    tec_pre_action: bool,
    ob5v_pre_action: bool,
) -> None:
    mms_cfg = state.get("mms") or {}
    if mms_cfg.get("latched"):
        return

    # Abort any running script before taking safety actions.
    if is_script_running():
        request_abort()
        clear_pause()
        clear_force_pause()
        logger.warning("MMS action: running script aborted.")

    if tec_pre_action:
        mms_cfg["tec_shutdown_requested"] = True
        logger.warning("MMS pre-action: TEC current should be forced to 0 (TC not yet implemented).")

    # Only attempt OB 5V disable when EB is not already in SAFE.
    current_state = int(
        getattr(hk, "CURRENT_OPERATING_STATE", 0) if getattr(hk, "CURRENT_OPERATING_STATE", None) is not None else 0
    )
    if ob5v_pre_action and current_state != 0x02:
        mms_cfg["ob5v_disable_requested"] = True
        _disable_ob5v(logger)
    elif ob5v_pre_action:
        logger.info("MMS pre-action: OB 5V disable skipped — EB already in SAFE state.")

    logger.warning("MMS trigger detected: attempting SET SAFE then PSU shutdown. Reasons: %s", "; ".join(reasons))
    safe_confirmed = False
    try:
        interface = eb_interface.get_egse_interface()
        safe_status = ebtcs.safe(interface, 0)
        if safe_status != "ERROR":
            time.sleep(2)
            ret_status = ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
        else:
            ret_status = "ERROR"

        if safe_status != "ERROR" and ret_status != "ERROR":
            logger.warning("MMS action: SAFE and RET commands sent via ebtcs.")
            rs422_log_path = getattr(app.state.eb_interface, "rs422_log_path", None)
            safe_confirmed = interface.wait_for_safe_state(rs422_log_path, timeout_s=10.0, poll_s=0.5)
            logger.warning(
                "MMS action: %s",
                "SAFE operating state confirmed from HK."
                if safe_confirmed
                else "SAFE operating state could not be confirmed from HK.",
            )
        else:
            logger.warning("MMS action: SAFE/RET command sequence failed.")
    except Exception as exc:
        logger.error(f"MMS action failed while sending SET SAFE command: {exc}")

    psu_port = state.get("psu_port")
    if safe_confirmed and psu_port is not None:
        lock = state.get("port_lock")
        lock_ctx = lock if lock is not None else nullcontext()
        try:
            with lock_ctx:
                psu.emergencyShutDown(psu_port)
            logger.warning("MMS action: PSU emergency shutdown executed (all channels OFF).")
        except Exception as exc:
            logger.error(f"MMS action failed during PSU emergency shutdown: {exc}")
    elif not safe_confirmed:
        logger.warning("MMS action: PSU shutdown skipped because SAFE state was not confirmed.")
    else:
        logger.warning("MMS action: PSU emergency shutdown skipped because PSU port is unavailable.")

    mms_cfg["latched"] = True
    mms_cfg["mode_at_trigger"] = state.get("mode")
    mms_cfg["triggered_at"] = datetime.now().isoformat(timespec="seconds")
    mms_cfg["reasons"] = reasons


def create_poll_tm(
    *,
    app: Any,
    state: dict[str, Any],
    const: Any,
    logger: Any,
    eb_metrics_card: Any,
    ob_metrics_card: Any,
    packet_metrics_card: Any,
    packet_viewer_controllers: dict[str, Any],
    ob_trp_card: Any,
    voltage_3v3_card: Any,
) -> Any:
    """Create TM polling callback bound to current controllers and state."""

    def poll_tm() -> None:
        # Independent packet counters
        counts = state.setdefault("packet_counts", {"hk": 0, "post": 0, "sci": 0})
        mode = state.get("mode", "EB")
        if mode == "EB":
            rs422_log_path = getattr(app.state.eb_interface, "rs422_log_path", None)
            log_selected = bool(rs422_log_path)
            if not log_selected:
                eb_metrics_card.set_no_data()
                ob_metrics_card.set_no_data()
                packet_metrics_card.set_no_data()
                return

            if not state["log_search"]["enabled"]:
                return

            # EB mode packets are sourced from the RS422 decode path.
            # Only re-read when file mtime changes.
            if eb_interface.rs422_log_changed(Path(rs422_log_path)):
                try:
                    eb_packet_utility.read_pkt(rs422_log_path, latest_only=True)
                except Exception as e:
                    logger.error(f"Failed to read packet log: {e}")

        processed_hk = False
        last_hk_time = state.setdefault("latest_hk_time", None)
        while not const.hk_queue.empty():
            processed_hk = True
            hk = const.hk_queue.get()
            now = datetime.now()
            # Calculate time since last HK
            if last_hk_time is not None:
                hk_delta = (now - last_hk_time).total_seconds()
            else:
                hk_delta = 0.0
            state["hk_time_since_last"] = hk_delta
            state["latest_hk_time"] = now
            last_hk_time = now

            # Increment HK counter only for new HK packets
            last_hk_id = state.setdefault("last_hk_id", None)
            hk_id = getattr(hk, "PACKET_NUMBER", None) or getattr(hk, "TIME", None)
            if hk_id != last_hk_id:
                counts["hk"] += 1
                state["last_hk_id"] = hk_id

            eb_metrics_card.update_from_packet(hk)
            ob_metrics_card.update_from_packet(hk)
            _update_hk_alarm_lights(state, hk)

            # MMS runs continuously while in EB mode and latches on first trigger.
            mms_cfg = state.get("mms") or {}
            if state.get("mode") == "EB" and bool(mms_cfg.get("enabled", True)):
                reasons, tec_pre_action, ob5v_pre_action = _mms_reasons(hk, mms_cfg.get("limits") or {})
                if reasons:
                    _run_mms_actions(app, state, logger, hk, reasons, tec_pre_action, ob5v_pre_action)

            _update_plot_cards(state, hk, ob_trp_card, voltage_3v3_card)
            _update_packet_viewer(mode, packet_viewer_controllers, hk)

        # In static/mock-log runs, HK may stop updating. Keep replay time moving so
        # PSU log playback can continue even without fresh HK packets.
        replay = state["psu_replay"]
        if replay.get("enabled") and replay.get("hk_anchor") is not None and not processed_hk:
            replay["latest_hk_time"] = datetime.now()

        # Only increment post packet counter when a new post packet is received
        def post_packet_handler(post_hk):
            # Only increment if this is a new post packet (by unique identifier, e.g., timestamp or counter)
            last_post_id = state.setdefault("last_post_id", None)
            post_id = getattr(post_hk, "PACKET_NUMBER", None) or getattr(post_hk, "TIME", None)
            if post_id != last_post_id:
                counts["post"] += 1
                packet_viewer_controllers["EB_POST"].update_from_packet(post_hk)
                state["last_post_id"] = post_id

        _drain_packet_queue(
            const.eb_post_queue,
            lambda post_hk: mode == "EB" and post_packet_handler(post_hk),
        )

        def sci_packet_handler(sci_packet):
            last_sci_id = state.setdefault("last_sci_id", None)
            sci_id = getattr(sci_packet, "PACKET_NUMBER", None) or getattr(sci_packet, "TIME", None)
            if sci_id != last_sci_id:
                counts["sci"] += 1
                state["last_sci_id"] = sci_id
            packet_viewer_controllers["OB_SCI" if mode == "OB" else "EB_SCI"].update_from_packet(sci_packet)

        _drain_packet_queue(
            const.sci_queue,
            sci_packet_handler,
        )

        packet_metrics_card.refresh()

    return poll_tm
