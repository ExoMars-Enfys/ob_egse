from __future__ import annotations

# Std library
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
import math
import statistics
import threading
from types import SimpleNamespace
import time
from typing import Any
from queue import Empty
import logging
import asyncio
from nicegui import app as _nicegui_app
from nicegui import core as _nicegui_core
from nicegui import ui, run
from nicegui.client import Client as _NiceGuiClient

# utilities
from utility_modules import app_theme, eb_interface, eb_packet_utility, ebtcs, hk_conversions, psu, psu_log_utility
from utility_modules.eb_packet_utility import get_latest_hk, get_latest_psu, set_latest_psu, wait_for_fresh_hk

# core
from core_modules import tmstruct, constants as const
from core_modules.constants import HEATER_INCLUSIVE_STATES, MODEL_CONSUMPTION

from widget_modules import monitoring_limits

info_log = logging.getLogger("info_log")

"""This module contains backend controller functions for the UI, which are responsible for handling user interactions, updating the application state, and coordinating between different UI components and the underlying data. These controllers are designed to be bound to specific UI elements and provide a clear separation of concerns between the UI layout and the logic that drives it."""

_FORCE_PAUSE_EVENT = threading.Event()
_SCRIPT_PSU_MA_WINDOW_SAMPLES = 5
_SCI_ACQ_TRIGGER_S = 150.0
_SCI_CONSUMPTION_CHECK_DURATION_S = 5.0
_SCI_CONSUMPTION_PER_SAMPLE_TIMEOUT_S = 0.25
_SCI_CONSUMPTION_MIN_SAMPLES = 25
_SCI_CONSUMPTION_MOVING_MIN_FRACTION = 0.50
_POST_REQUIRED_FIELDS = (
    "POST_WARNING_FLAGS",
    "POST_ERROR_FLAGS",
    "NUM_BAD_FLASH_BLOCKS",
    "NUM_BAD_SRAM_BLOCKS",
    "ASW_IMAGE_1_CRC",
    "ASW_IMAGE_2_CRC",
    "ASW_IMAGE_3_CRC",
    "ASW_IMAGE_4_CRC",
    "ASW_IMAGE_5_CRC",
    "BSW_IMAGE_CRC",
    "MEASUREMENT_TABLE_CRC",
)


# ---------------------------------------------------------------------------
# MMS helpers — limit checking
# ---------------------------------------------------------------------------
# region MMS helpers — limit checking


def append_violation(
    reasons: list[str], label: str, value: float | None, limits: tuple[float | None, float | None]
) -> bool:
    if not violates_limits(value, limits):
        return False
    low, high = limits
    reasons.append(f"{label} out of limits: value={value}, limits=({low}, {high})")
    return True


def limit_tuple(value: Any) -> tuple[float | None, float | None]:
    if isinstance(value, tuple) and len(value) == 2:
        return value
    return (None, None)


def mms_reasons(hk: Any, limits: dict[str, Any]) -> tuple[list[str], bool, bool]:
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
        violated = append_violation(reasons, label, decoded(hk, field_name), limit_tuple(limits.get(limit_key)))
        tec_pre_action = tec_pre_action or (tec_field and violated)
        ob5v_pre_action = ob5v_pre_action or (label.startswith("OB ") and violated)

    if bool(getattr(hk, "POST_ERROR_FLAGS", 0)):
        reasons.append("POST Error Flags asserted")

    if bool(getattr(hk, "ERROR_FLAGS", 0)):
        ns = getattr(hk, "ERROR_FLAGS_BITS", None)
        eb_flags = sorted(k for k, v in vars(ns).items() if v == 1 and k != "RESERVED") if ns is not None else []
        if const.MMS_MASK_OB_GENERAL_ERROR:
            eb_flags = [f for f in eb_flags if f != "OB_GENERAL_ERROR"]
        if eb_flags:
            reasons.append(f"HK Error Flags asserted: {', '.join(eb_flags)}")
        elif ns is None:
            reasons.append("HK Error Flags asserted")

    # OB error details — decoded from OB_LAST_ERROR byte.
    # OB_GENERAL_ERROR on EB is sticky: the OB register may already be 0 by the time
    # MMS fires.  Always include the raw byte value so operators have full context.
    ob_last_error_raw = getattr(hk, "OB_LAST_ERROR", None)
    ob_err_active = (
        sorted(k for k, v in vars(ns).items() if v == 1 and k not in {"UNUSED1", "UNUSED2"})
        if (ns := getattr(hk, "ERRORS", None)) is not None
        else []
    )
    if ob_err_active:
        reasons.append(f"OB Errors: {', '.join(ob_err_active)} (OB_LAST_ERROR=0x{ob_last_error_raw:02X})")
    elif ob_last_error_raw is not None and ob_last_error_raw != 0:
        reasons.append(f"OB_LAST_ERROR=0x{ob_last_error_raw:02X} (no active bits decoded)")

    # Motor error details — decoded from OB_MOTOR_ERROR byte.
    ob_motor_error_raw = getattr(hk, "OB_MOTOR_ERROR", None)
    mtr_err_active = (
        sorted(k for k, v in vars(ns).items() if v == 1 and k != "UNUSED")
        if (ns := getattr(hk, "MTR_ERRORS", None)) is not None
        else []
    )
    if mtr_err_active:
        reasons.append(f"OB Motor Errors: {', '.join(mtr_err_active)} (OB_MOTOR_ERROR=0x{ob_motor_error_raw:02X})")
    elif ob_motor_error_raw is not None and ob_motor_error_raw != 0:
        reasons.append(f"OB_MOTOR_ERROR=0x{ob_motor_error_raw:02X} (no active bits decoded)")

    return reasons, tec_pre_action, ob5v_pre_action


def violates_limits(value: float | None, limits: tuple[float | None, float | None]) -> bool:
    if value is None:
        return False
    low, high = limits
    return (low is not None and value < low) or (high is not None and value > high)


# endregion


# ---------------------------------------------------------------------------
# FDIR Simulator — limit checking
# ---------------------------------------------------------------------------
# region FDIR Simulator — limit checking
ObFdirParameter = monitoring_limits.ObFdirParameter
OB_FDIR_PARAMETERS = monitoring_limits.OB_FDIR_PARAMETERS


def _ob_fdir_display_mode(state: dict[str, Any]) -> str:
    """Return the active HK presentation mode used by logs and dialogs."""
    mode = str(state.get("hk_display_mode") or getattr(_nicegui_app.state, "hk_display_mode", "REAL") or "REAL").upper()
    return "ADU" if mode == "ADU" else "REAL"


def _format_ob_fdir_number(value: Any, unit: str) -> str:
    """Format one FDIR engineering value without unnecessary trailing zeros."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if not math.isfinite(numeric):
        return "N/A"
    if unit == "V":
        return f"{numeric:.3f}"
    if unit == "°C":
        return f"{numeric:.1f}"
    return f"{numeric:g}"


def _ob_fdir_real_value(parameter: ObFdirParameter, adu: int | None) -> float | None:
    """Convert one normalised standalone-OB ADU to its engineering value."""
    if adu is None:
        return None
    packet = SimpleNamespace(**{parameter.hk_field: int(adu)})
    # decode_plot_field is defined later in this module; it is available when
    # telemetry processing calls this helper after module initialisation.
    return decode_plot_field(packet, parameter.hk_field, {"hk_display_mode": "REAL"})


def _format_ob_fdir_measurement(
    state: dict[str, Any],
    parameter: ObFdirParameter,
    adu: int | None,
    severity: str,
) -> str:
    """Format value and limits in the operator-selected REAL/ADU mode."""
    is_alarm = str(severity).lower() == "alarm"
    limit_label = "alarm limits" if is_alarm else "warning limits"

    if _ob_fdir_display_mode(state) == "ADU":
        limits = parameter.alarm_limits if is_alarm else parameter.warning_limits
        value_text = "N/A" if adu is None else str(int(adu))
        return f"{parameter.hk_field}={value_text} ADU, {limit_label}=({int(limits[0])}, {int(limits[1])}) ADU"

    limits_real = parameter.alarm_limits_real if is_alarm else parameter.warning_limits_real
    real_value = _ob_fdir_real_value(parameter, adu)
    value_text = _format_ob_fdir_number(real_value, parameter.real_unit)
    low_text = _format_ob_fdir_number(limits_real[0], parameter.real_unit)
    high_text = _format_ob_fdir_number(limits_real[1], parameter.real_unit)
    return (
        f"{parameter.hk_field}={value_text} {parameter.real_unit}, "
        f"{limit_label}=({low_text}, {high_text}) {parameter.real_unit}"
    )


def _ob_fdir_simulator_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return persistent standalone-OB FDIR simulator state.

    Warning and alarm flags are independently latched, matching the two FDIR
    bitmaps reported by EB telemetry. They remain asserted after the analogue
    value returns in range and are cleared only by reset_ob_fdir_simulator().
    """
    simulator = state.setdefault("ob_fdir_simulator", {})
    simulator.setdefault("enabled", True)
    simulator.setdefault("warning_latched", set())
    simulator.setdefault("alarm_latched", set())
    simulator.setdefault("current_warning", set())
    simulator.setdefault("current_alarm", set())
    simulator.setdefault("latest_adu", {})

    # Be tolerant of state restored from JSON-like storage.
    for key in ("warning_latched", "alarm_latched", "current_warning", "current_alarm"):
        if not isinstance(simulator.get(key), set):
            simulator[key] = set(simulator.get(key) or [])
    if not isinstance(simulator.get("latest_adu"), dict):
        simulator["latest_adu"] = {}
    return simulator


def _ob_fdir_bitmask(flag_names: set[str]) -> int:
    """Build the aggregate bitmap using tmstruct.eb_fdir_flags ordering."""
    mask = 0
    for bit_index, flag_name in enumerate(_FDIR_NAMES):
        if flag_name in flag_names:
            mask |= 1 << bit_index
    return mask


def _attach_simulated_ob_fdir_fields(
    hk: Any,
    warning_latched: set[str],
    alarm_latched: set[str],
) -> None:
    """Expose simulated fields on standalone OB HK packets when mutable."""
    warning_ns = SimpleNamespace(**{name: int(name in warning_latched) for name in _FDIR_NAMES})
    alarm_ns = SimpleNamespace(**{name: int(name in alarm_latched) for name in _FDIR_NAMES})
    try:
        hk.FDIR_WARNING_FLAGS_BITS = warning_ns
        hk.FDIR_ALARM_FLAGS_BITS = alarm_ns
        hk.FDIR_WARNING_FLAGS = _ob_fdir_bitmask(warning_latched)
        hk.FDIR_ALARM_FLAGS = _ob_fdir_bitmask(alarm_latched)
    except (AttributeError, TypeError):
        # Alarm-light simulation still works even for immutable packet objects.
        pass


_OB_VOLTAGE_FDIR_FLAGS = {"FPGA_IO_POWER_SUPPLY", "FPGA_CORE_POWER_SUPPLY"}
_OB_THERMISTOR_FDIR_FLAGS = {
    "DIGITAL_BOARD_TRP",
    "DETECTOR_BOARD_TRP",
    "MECH_BOARD_TRP",
    "MOTOR_TRP",
}


def _ob_psu_protection_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return persistent OB PSU protection/action state."""
    protection = state.setdefault(
        "ob_psu_protection",
        {
            "shutdown_in_progress": False,
            "shutdown_latched": False,
            "last_shutdown_reason": [],
            "last_error": None,
            "pending_prompt_details": set(),
            "dialog": None,
            "dialog_details_label": None,
        },
    )
    protection.setdefault("shutdown_in_progress", False)
    protection.setdefault("shutdown_latched", False)
    protection.setdefault("last_shutdown_reason", [])
    protection.setdefault("last_error", None)
    protection.setdefault("pending_prompt_details", set())
    protection.setdefault("dialog", None)
    protection.setdefault("dialog_details_label", None)
    return protection


def _request_ob_psu_emergency_shutdown(
    state: dict[str, Any],
    logger: Any,
    reasons: list[str],
    *,
    automatic: bool,
) -> bool:
    """Request a non-blocking PSU emergency shutdown once per protection latch."""
    protection = _ob_psu_protection_state(state)
    active_logger = logger if logger is not None else info_log

    if protection.get("shutdown_latched") or protection.get("shutdown_in_progress"):
        return False

    psu_port = state.get("psu_port")
    if psu_port is None:
        message = "OB PSU shutdown requested, but no PSU port is available."
        protection["last_error"] = message
        active_logger.error(message)
        notify(message, color="negative")
        return False

    protection["shutdown_in_progress"] = True
    protection["last_shutdown_reason"] = list(reasons)
    protection["last_error"] = None

    dialog = protection.get("dialog")
    if dialog is not None:
        try:
            dialog.close()
        except Exception:
            pass
    protection["pending_prompt_details"] = set()

    reason_text = "; ".join(reasons) if reasons else "OB protection trigger"
    action_label = "automatic voltage-alarm shutdown" if automatic else "operator-confirmed shutdown"
    active_logger.error("OB PSU %s requested: %s", action_label, reason_text)

    def _shutdown_worker() -> None:
        try:
            lock = state.get("psu_lock")
            lock_ctx = lock if lock is not None else nullcontext()
            with lock_ctx:
                psu.shutdown_psu_outputs(psu_port)
            protection["shutdown_latched"] = True
            active_logger.error("OB PSU emergency shutdown executed: %s", reason_text)
            notify("PSU emergency shutdown executed.\n" + reason_text, color="negative")
        except Exception as exc:
            protection["last_error"] = str(exc)
            active_logger.exception("OB PSU emergency shutdown failed: %s", exc)
            notify(f"PSU emergency shutdown failed: {exc}", color="negative")
        finally:
            protection["shutdown_in_progress"] = False

    threading.Thread(target=_shutdown_worker, name="ob-psu-emergency-shutdown", daemon=True).start()
    return True


def _open_ob_psu_shutdown_dialog(state: dict[str, Any], logger: Any, details: list[str]) -> None:
    """Ask the operator whether warning/error/thermistor conditions should shut down the PSU."""
    if not details:
        return

    protection = _ob_psu_protection_state(state)
    if protection.get("shutdown_latched") or protection.get("shutdown_in_progress"):
        return

    pending: set[str] = protection["pending_prompt_details"]
    pending.update(str(detail) for detail in details if detail)
    active_logger = logger if logger is not None else info_log

    dialog = protection.get("dialog")
    details_label = protection.get("dialog_details_label")

    if dialog is None or details_label is None:
        try:
            with ui.dialog() as dialog:
                with ui.card().classes("w-[34rem] max-w-full"):
                    ui.label("OB protection condition").classes("font-bold egse-title warning-text")
                    ui.label("A thermistor condition, error, or warning has been raised. Shut down the PSU?").classes(
                        "egse-text"
                    )
                    ui.separator()
                    details_label = ui.label("").classes("whitespace-pre-wrap warning-text")
                    with ui.row().classes("w-full justify-end gap-2"):

                        def _keep_psu_on() -> None:
                            retained = sorted(protection["pending_prompt_details"])
                            protection["pending_prompt_details"] = set()
                            active_logger.warning(
                                "Operator kept PSU on after OB protection prompt: %s",
                                "; ".join(retained),
                            )
                            dialog.close()

                        def _confirm_shutdown() -> None:
                            confirmed = sorted(protection["pending_prompt_details"])
                            protection["pending_prompt_details"] = set()
                            dialog.close()
                            _request_ob_psu_emergency_shutdown(
                                state,
                                active_logger,
                                confirmed,
                                automatic=False,
                            )

                        ui.button("Keep PSU on", on_click=_keep_psu_on).props("outline")
                        ui.button("Shut down PSU", on_click=_confirm_shutdown).classes("error-text")

            protection["dialog"] = dialog
            protection["dialog_details_label"] = details_label
        except Exception as exc:
            active_logger.exception("Could not open OB PSU shutdown confirmation dialog: %s", exc)
            notify(
                "OB protection condition requires PSU shutdown confirmation:\n"
                + "\n".join(f"• {detail}" for detail in sorted(pending)),
                color="warning",
            )
            return

    details_label.set_text("\n".join(f"• {detail}" for detail in sorted(pending)))
    active_logger.warning("OB PSU shutdown confirmation requested: %s", "; ".join(sorted(pending)))
    try:
        dialog.open()
    except Exception as exc:
        active_logger.exception("Could not open OB PSU shutdown confirmation dialog: %s", exc)


def _reset_ob_psu_protection_actions(state: dict[str, Any]) -> None:
    """Reset trigger de-duplication state without changing the physical PSU state."""
    protection = _ob_psu_protection_state(state)
    protection["shutdown_in_progress"] = False
    protection["shutdown_latched"] = False
    protection["last_shutdown_reason"] = []
    protection["last_error"] = None
    protection["pending_prompt_details"] = set()
    dialog = protection.get("dialog")
    if dialog is not None:
        try:
            dialog.close()
        except Exception:
            pass

    # Also clear the MMS latch so a new trigger can fire after recovery.
    mms_cfg = state.get("mms")
    if isinstance(mms_cfg, dict):
        mms_cfg["latched"] = False
        mms_cfg["in_progress"] = False


def simulate_ob_fdir(state: dict[str, Any], hk: Any, logger: Any = None) -> list[str]:
    """Evaluate and latch standalone-OB FDIR warning/alarm conditions.

    Classification is mutually exclusive for each parameter:

    * inside warning limits: no new FDIR
    * outside warning but inside alarm limits: warning
    * outside alarm limits: alarm

    Alarm severity supersedes a previously latched warning for the same
    parameter.  Latches remain asserted until reset_ob_fdir_simulator().
    """
    simulator = _ob_fdir_simulator_state(state)
    if not bool(simulator.get("enabled", True)):
        simulator["current_warning"] = set()
        simulator["current_alarm"] = set()
        _attach_simulated_ob_fdir_fields(hk, set(), set())
        return []

    warning_latched: set[str] = simulator["warning_latched"]
    alarm_latched: set[str] = simulator["alarm_latched"]
    previous_warning = set(warning_latched)
    previous_alarm = set(alarm_latched)
    current_warning: set[str] = set()
    current_alarm: set[str] = set()
    latest_adu: dict[str, int] = {}

    for parameter in OB_FDIR_PARAMETERS:
        adu = _ob_adc12(getattr(hk, parameter.hk_field, None))
        if adu is None:
            continue
        latest_adu[parameter.flag_name] = adu

        outside_alarm = violates_limits(float(adu), parameter.alarm_limits)
        outside_warning = violates_limits(float(adu), parameter.warning_limits)

        if outside_alarm:
            current_alarm.add(parameter.flag_name)
            alarm_latched.add(parameter.flag_name)
            # Alarm dominates the warning presentation for this parameter.
            warning_latched.discard(parameter.flag_name)
        elif outside_warning:
            current_warning.add(parameter.flag_name)
            if parameter.flag_name not in alarm_latched:
                warning_latched.add(parameter.flag_name)

    simulator["current_warning"] = current_warning
    simulator["current_alarm"] = current_alarm
    simulator["latest_adu"] = latest_adu

    new_warning = warning_latched - previous_warning
    new_alarm = alarm_latched - previous_alarm
    active_logger = logger if logger is not None else info_log
    parameter_by_flag = {parameter.flag_name: parameter for parameter in OB_FDIR_PARAMETERS}

    warning_messages: list[str] = []
    for flag_name in sorted(new_warning):
        parameter = parameter_by_flag[flag_name]
        measurement = _format_ob_fdir_measurement(
            state,
            parameter,
            latest_adu.get(flag_name),
            "warning",
        )
        message = f"{flag_name} ({measurement})"
        warning_messages.append(message)
        active_logger.warning("OB simulated FDIR warning latched: %s", message)

    alarm_messages: list[str] = []
    for flag_name in sorted(new_alarm):
        parameter = parameter_by_flag[flag_name]
        measurement = _format_ob_fdir_measurement(
            state,
            parameter,
            latest_adu.get(flag_name),
            "alarm",
        )
        message = f"{flag_name} ({measurement})"
        alarm_messages.append(message)
        active_logger.error("OB simulated FDIR alarm latched: %s", message)

    if warning_messages:
        notify(
            "OB FDIR warning latched:\n" + "\n".join(f"• {message}" for message in warning_messages),
            color="warning",
        )
    if alarm_messages:
        notify(
            "OB FDIR alarm latched:\n" + "\n".join(f"• {message}" for message in alarm_messages),
            color="negative",
        )

    # PSU protection policy for standalone OB FDIR simulation:
    #   * voltage alarms shut down immediately;
    #   * every warning and every thermistor alarm asks the operator first.
    # Skip all protection actions when MMS is disabled.
    if not bool(state.get("mms", {}).get("enabled", True)):
        _attach_simulated_ob_fdir_fields(hk, warning_latched, alarm_latched)
        return simulated_ob_fdir_details(state)

    # Remove flags the operator has chosen to ignore.
    ignored_flags: set[str] = state.get("ob_fdir_ignored_flags") or set()
    voltage_alarm_flags = sorted((new_alarm - ignored_flags) & _OB_VOLTAGE_FDIR_FLAGS)
    if voltage_alarm_flags:
        shutdown_reasons = []
        for flag_name in voltage_alarm_flags:
            parameter = parameter_by_flag[flag_name]
            measurement = _format_ob_fdir_measurement(
                state,
                parameter,
                latest_adu.get(flag_name),
                "alarm",
            )
            shutdown_reasons.append(f"OB voltage alarm: {flag_name} ({measurement})")
        _request_ob_psu_emergency_shutdown(
            state,
            active_logger,
            shutdown_reasons,
            automatic=True,
        )
    else:
        prompt_reasons: list[str] = []
        for flag_name in sorted(new_warning - ignored_flags):
            parameter = parameter_by_flag[flag_name]
            measurement = _format_ob_fdir_measurement(
                state,
                parameter,
                latest_adu.get(flag_name),
                "warning",
            )
            prompt_reasons.append(f"OB FDIR warning: {flag_name} ({measurement})")
        for flag_name in sorted((new_alarm & _OB_THERMISTOR_FDIR_FLAGS) - ignored_flags):
            parameter = parameter_by_flag[flag_name]
            measurement = _format_ob_fdir_measurement(
                state,
                parameter,
                latest_adu.get(flag_name),
                "alarm",
            )
            prompt_reasons.append(f"OB thermistor alarm: {flag_name} ({measurement})")
        _open_ob_psu_shutdown_dialog(state, active_logger, prompt_reasons)

    _attach_simulated_ob_fdir_fields(hk, warning_latched, alarm_latched)
    return simulated_ob_fdir_details(state)


def simulated_ob_fdir_details(state: dict[str, Any]) -> list[str]:
    """Return display strings for all latched standalone-OB FDIRs."""
    simulator = _ob_fdir_simulator_state(state)
    warning_latched = set(simulator.get("warning_latched") or set())
    alarm_latched = set(simulator.get("alarm_latched") or set())
    details = [f"OB FDIR Alarm: {name} (simulated, latched)" for name in sorted(alarm_latched)]
    details.extend(f"OB FDIR Warning: {name} (simulated, latched)" for name in sorted(warning_latched))
    return details


def reset_ob_fdir_simulator(state: dict[str, Any], logger: Any = None) -> None:
    """Clear all simulated OB FDIR latches after a successful Clear_Errors TC."""
    simulator = _ob_fdir_simulator_state(state)
    had_latches = bool(simulator["warning_latched"] or simulator["alarm_latched"])
    simulator["warning_latched"].clear()
    simulator["alarm_latched"].clear()
    simulator["current_warning"].clear()
    simulator["current_alarm"].clear()
    simulator["latest_adu"].clear()
    _reset_ob_psu_protection_actions(state)

    ob_light = (state.get("alarm_lights") or {}).get("ob")
    if ob_light is not None:
        reset_latches = getattr(ob_light, "reset_latches", None)
        if callable(reset_latches):
            reset_latches()
        update_from_faults = getattr(ob_light, "update_from_faults", None)
        if callable(update_from_faults):
            update_from_faults({}, source="ob_fdir_sim")

    if had_latches:
        (logger if logger is not None else info_log).info("OB simulated FDIR latches cleared.")
        notify("OB simulated FDIR latches cleared.", color="positive")


# end region


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
# region Notifications


def clear_force_pause() -> None:
    """Release a previously requested forced pause."""
    _FORCE_PAUSE_EVENT.clear()


def is_force_paused() -> bool:
    """Return True when script execution is held by a forced pause."""
    return _FORCE_PAUSE_EVENT.is_set()


def notify(msg: str, color: str = "primary") -> None:
    """Send a UI notification that is safe to call from any thread.

    Uses ``loop.call_soon_threadsafe`` to enqueue the notification message
    directly into each connected client's outbox on the NiceGUI event loop
    thread.  This mirrors what ``ui.notify`` does internally but is safe to
    call from background threads (e.g. scripts running via ``run.io_bound``).
    """
    loop = _nicegui_core.loop
    if loop is None or not loop.is_running():
        info_log.info("[notify] %s", msg)
        return

    def _enqueue() -> None:
        for client in list(_NiceGuiClient.instances.values()):
            try:
                with client:
                    ui.notify(str(msg), color=color, multi_line=True)
            except Exception as exc:
                info_log.debug("notify: failed for client %s: %s", client.id, exc)

    loop.call_soon_threadsafe(_enqueue)


def notify_negative(msg) -> None:
    notify(msg, color="negative")


def notify_positive(msg) -> None:
    notify(msg, color="positive")


def notify_script_done() -> None:
    """Notify the user that the script has completed."""
    notify("Script execution complete.", color="positive")


def notify_script_pause(current: int, total: int) -> None:
    """Notify the user that the script is paused, showing progress."""
    notify(f"Script paused, command {current} of {total}", color="warning")


def request_force_pause(msg: str = "") -> None:
    """Request a forced pause — blocks script execution until the user resumes or aborts.

    Sets ``_FORCE_PAUSE_EVENT``, shows a notification, then polls until the event is
    cleared by ``clear_force_pause()`` (triggered by the UI resume button) or the
    script abort event fires.
    """
    if msg:
        notify(msg, color="warning")
    _FORCE_PAUSE_EVENT.set()
    while _FORCE_PAUSE_EVENT.is_set():
        if is_aborted():
            _FORCE_PAUSE_EVENT.clear()
            raise RuntimeError("Script aborted during forced pause.")
        time.sleep(0.25)


# endregion


# ---------------------------------------------------------------------------
# PSU helpers — consumption check (public)
# ---------------------------------------------------------------------------
# region PSU helpers — consumption check (public)


def consumption_check(state_names, psu_sample: dict, errors: list[str], latest_hk: Any = None) -> float | None:
    """
    Checks PSU current for the given state(s) and current OB model.
    Accepts a single state name (str) or a list of state names.
    Sums expected values for all provided states.
    Appends error to errors if out of range.
    Model is read from app.state.current_model.

    If latest_hk is provided, verify_heater_states() is called automatically and the
    active heater states (["MechHTR", "DetHTR"] subset) are appended to state_names.
    """
    from nicegui import app as _app

    model = getattr(_app.state, "current_model", None)
    if model is None:
        errors.append("No model specified for PSU consumption check.")
        return None
    if model not in MODEL_CONSUMPTION:
        errors.append(f"Unknown OB model: {model}")
        return None
    model_dict = MODEL_CONSUMPTION[model]
    if isinstance(state_names, str):
        state_names = [state_names]
    else:
        state_names = list(state_names)
    if latest_hk is not None:
        heater_states = verify_heater_states(latest_hk, errors)
        if not any(s in HEATER_INCLUSIVE_STATES for s in state_names):
            state_names += heater_states
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


# Per-heater history for verify_heater_states() — persists across HK poll cycles.
# Tracks the last definitive expected state (established when TRP was outside the
# hysteresis band) and the previous mode flags so that enable-transitions can be
# detected (the firmware initialises to OFF when transitioning from disabled → auto).
_heater_state_history: dict[str, dict] = {
    "Mech": {"last_expected": None, "last_trp": None, "prev_auto": False, "prev_manual": False},
    "Det": {"last_expected": None, "last_trp": None, "prev_auto": False, "prev_manual": False},
}
# endregion


# ---------------------------------------------------------------------------
# PSU helpers — moving-average smoothing
# ---------------------------------------------------------------------------
# region PSU helpers — moving-average smoothing


def get_smoothed_psu_sample(
    psu_queue: Any,
    *,
    timeout: float = 2.0,
    window_samples: int = _SCRIPT_PSU_MA_WINDOW_SAMPLES,
) -> dict[str, Any]:
    """Read PSU queue samples and return a sample with MA-smoothed current fields.

    The first sample is read with timeout. Any immediately available additional
    samples are drained up to *window_samples* to build a fixed-size moving
    average used by script-side current checks.
    """
    first_sample = psu_queue.get(timeout=timeout)
    samples = [first_sample]
    max_samples = max(1, int(window_samples))

    for _ in range(max_samples - 1):
        try:
            samples.append(psu_queue.get_nowait())
        except Empty:
            break

    if not isinstance(first_sample, dict):
        return first_sample

    averaged_sample = dict(first_sample)
    latest_sample = samples[-1] if samples else first_sample
    if isinstance(latest_sample, dict):
        averaged_sample["TIME"] = latest_sample.get("TIME", averaged_sample.get("TIME"))
        averaged_sample["STATUS"] = latest_sample.get("STATUS", averaged_sample.get("STATUS"))

    current_keys = ("PSU_ROV_HTR_I", "PSU_EB_I", "CH1_I", "CH2_I", "CH3_I", "CH4_I")
    for key in current_keys:
        values: list[float] = []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            value = sample.get(key)
            if value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        if values:
            averaged_sample[key] = sum(values) / len(values)

    return averaged_sample


def resolve_consumption_bounds(
    state_names: str | list[str],
    errors: list[str],
    latest_hk: Any = None,
) -> tuple[list[str], float, float] | None:
    """Resolve expected PSU_EB_I bounds for the requested state(s)."""
    from nicegui import app as _app

    model = getattr(_app.state, "current_model", None)
    if model is None:
        errors.append("No model specified for PSU consumption check.")
        return None
    if model not in MODEL_CONSUMPTION:
        errors.append(f"Unknown OB model: {model}")
        return None

    model_dict = MODEL_CONSUMPTION[model]
    if isinstance(state_names, str):
        resolved_states = [state_names]
    else:
        resolved_states = list(state_names)

    if latest_hk is not None:
        heater_states = verify_heater_states(latest_hk, errors)
        if not any(s in HEATER_INCLUSIVE_STATES for s in resolved_states):
            resolved_states += heater_states

    missing = [s for s in resolved_states if s not in model_dict]
    if missing:
        errors.append(f"Unknown state(s) {missing} for model '{model}'")
        return None

    base_current_ma = sum(model_dict[s] for s in resolved_states)
    min_i = base_current_ma - 10
    max_i = base_current_ma + 10
    return resolved_states, min_i, max_i


def windowed_consumption_check(
    state_names: str | list[str],
    errors: list[str],
    latest_hk: Any = None,
    *,
    duration_s: float = _SCI_CONSUMPTION_CHECK_DURATION_S,
    per_sample_timeout_s: float = _SCI_CONSUMPTION_PER_SAMPLE_TIMEOUT_S,
    min_samples: int = _SCI_CONSUMPTION_MIN_SAMPLES,
    require_motor_moving: bool = False,
    moving_fraction_required: float = _SCI_CONSUMPTION_MOVING_MIN_FRACTION,
) -> float | None:
    """Run a repeatable PSU consumption check over a short time window.

    Samples are MA-smoothed per sample via `get_smoothed_psu_sample`.
    Pass/fail is decided by whether the window median lies within expected
    bounds. Returns the median measured current in mA.
    """
    bounds = resolve_consumption_bounds(state_names, errors, latest_hk)
    if bounds is None:
        return None
    resolved_states, min_i, max_i = bounds

    deadline = time.monotonic() + max(float(duration_s), float(per_sample_timeout_s))
    measured_ma: list[float] = []
    moving_obs_count = 0
    moving_true_count = 0

    while time.monotonic() < deadline:
        try:
            sample = get_smoothed_psu_sample(const.psu_queue, timeout=per_sample_timeout_s)
        except Empty:
            continue
        if not isinstance(sample, dict):
            continue
        measured_current_ma = float(sample.get("PSU_EB_I") or 0.0) * 1000.0
        measured_ma.append(measured_current_ma)

        if require_motor_moving:
            hk_now = get_latest_hk() or latest_hk
            if hk_now is not None:
                mtr = getattr(hk_now, "MTR_FLAGS", None)
                moving = bool(getattr(mtr, "MOVING", 0))
                moving_obs_count += 1
                if moving:
                    moving_true_count += 1

    if not measured_ma:
        errors.append("No PSU samples captured during SCI ACQ windowed current check.")
        return None

    sample_count = len(measured_ma)
    median_ma = statistics.median(measured_ma)

    if sample_count < int(min_samples):
        errors.append(
            "SCI ACQ consumption check collected too few PSU samples "
            f"({sample_count} < {int(min_samples)}) over {duration_s:.1f}s."
        )

    if not (min_i <= median_ma <= max_i):
        errors.append(
            "PSU_EB_I median out of range for "
            f"{resolved_states}: median={median_ma:.2f} mA, "
            f"expected {min_i:.1f}-{max_i:.1f} mA"
        )

    if require_motor_moving:
        if moving_obs_count <= 0:
            errors.append("SCI ACQ check could not verify motor motion (no HK MTR_FLAGS observations in window).")
        else:
            moving_fraction = moving_true_count / moving_obs_count
            if moving_fraction < float(moving_fraction_required):
                errors.append(
                    "SCI ACQ check did not run during sufficient motor motion: "
                    f"MOVING true {moving_true_count}/{moving_obs_count} "
                    f"({moving_fraction * 100:.1f}%), required >= {float(moving_fraction_required) * 100:.1f}%"
                )

    info_log.info(
        "SCI ACQ windowed consumption stats - states=%s expected=[%.1f, %.1f] mA samples=%d "
        "median=%.2f mA moving_obs=%d moving_true=%d",
        resolved_states,
        min_i,
        max_i,
        sample_count,
        median_ma,
        moving_obs_count,
        moving_true_count,
    )
    return float(median_ma)


# endregion


# ---------------------------------------------------------------------------
# PSU helpers — runtime polling / replay / cards
# ---------------------------------------------------------------------------
# region PSU helpers — runtime polling / replay / cards


def apply_psu_sample(state: dict[str, Any], psu_cards: list[Any], psu_sample: dict[str, Any]) -> None:
    update_psu_readings(state, psu_sample)
    update_psu_cards(psu_cards, psu_sample)
    sync_master = state.get("sync_ob_master_toggle_value")
    if callable(sync_master):
        sync_master()


def build_replay_psu_sample(state: dict[str, Any], psu_cards: list[Any], record: dict[str, Any]) -> dict[str, Any]:
    channels = record.get("CHANNELS", {})
    sample: dict[str, Any] = {key: None for key in _PSU_SAMPLE_KEYS if key != "status"}
    sample.update({"TIME": datetime.now(), "STATUS": bool(record.get("STATUS", True))})

    for card in psu_cards:
        channel_data: dict[str, Any] = {}
        preferred_channels, allow_fallback = card_channel_preferences(card, state["mode"])
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


def card_channel_preferences(card: Any, mode: str) -> tuple[list[str], bool]:
    by_mode = card.channel.get("replay_channel_by_mode", {})
    configured = by_mode.get(mode, by_mode.get("EB") or "CH3")
    if isinstance(configured, str):
        return [configured.upper()], True
    if isinstance(configured, list):
        channels = [str(ch).upper() for ch in configured if str(ch)]
        return channels, bool(channels)
    return ["CH3"], True


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
            ingest_live_psu_sample(state, psu_cards, latest_live_sample)
            processed += 1

        if latest_live_sample is not None:
            # Draw one point per UI tick while MA includes all drained live samples.
            for card in psu_cards:
                card.push_smoothed(latest_live_sample.get("TIME"))

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
        sample = build_replay_psu_sample(state, psu_cards, records[idx % len(records)])
        apply_psu_sample(state, psu_cards, sample)
        replay["index"] = idx + 1

    return poll_psu


# TM helpers


_NATIVE_OB_TRP_FIELDS = (
    "DIGITAL_TRP",
    "DETEC_TRP",
    "MECH_TRP",
    "MOTOR_TRP",
)

_NATIVE_OB_ADC12_FIELDS = {
    "HK_V_3V3",
    "HK_V_1V5",
    "DIGITAL_TRP",
    "DETEC_TRP",
    "MECH_TRP",
    "MOTOR_TRP",
}

_EB_OB_TRP_FIELDS = (
    "OB_DIGITAL_TRP",
    "OB_DETECTOR_TRP",
    "OB_MECHANISM_TRP",
    "OB_MOTOR_TRP",
)
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


def create_set_psu_card_profiles(*, ch1_card: Any, ch2_card: Any, ch3_card: Any, ch4_card: Any) -> Any:
    """Create mode-dependent PSU card profile callback bound to PSU card controllers."""

    def set_psu_card_profiles(mode: str) -> None:
        ob_mode = mode == "OB"
        ch1_card.apply_profile(
            title=" CH1 +12V I",
            visible=ob_mode,
            live_voltage_key="CH1_V",
            live_current_key="CH1_I",
            replay_channels=["CH1"],
            show_enabled_toggle=False,
        )
        ch2_card.apply_profile(
            title=" CH2 -12V I",
            visible=ob_mode,
            live_voltage_key="CH2_V",
            live_current_key="CH2_I",
            replay_channels=["CH2"],
            show_enabled_toggle=False,
        )
        ch3_card.apply_profile(
            title=" CH3 +5V I" if ob_mode else " CH3 ROVHTR I",
            visible=True,
            live_voltage_key="CH3_V" if ob_mode else "PSU_ROV_HTR_V",
            live_current_key="CH3_I" if ob_mode else "PSU_ROV_HTR_I",
            replay_channels=["CH3"],
            show_enabled_toggle=(not ob_mode),
        )
        ch4_card.apply_profile(
            title=" CH4 ROVHTR I" if ob_mode else " CH4 +28V I",
            visible=True,
            live_voltage_key="CH4_V" if ob_mode else "PSU_EB_V",
            live_current_key="CH4_I" if ob_mode else "PSU_EB_I",
            replay_channels=["CH4"],
            show_enabled_toggle=True,
            show_lisn_toggle=(not ob_mode),
        )

    return set_psu_card_profiles


def create_set_psu_log_path(*, state: dict[str, Any], logger: Any) -> Any:
    """Create PSU replay-log setter callback bound to current state."""

    def set_psu_log_path(psu_log_path: str | None) -> bool:
        replay = state["psu_replay"]
        if not psu_log_path:
            reset_psu_replay(replay)
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


def ingest_live_psu_sample(state: dict[str, Any], psu_cards: list[Any], psu_sample: dict[str, Any]) -> None:
    """Feed live PSU samples into MA buffers without plotting each one."""
    set_latest_psu(psu_sample)
    update_psu_readings(state, psu_sample)
    update_psu_cards(psu_cards, psu_sample, plot_sample=False)
    sync_master = state.get("sync_ob_master_toggle_value")
    if callable(sync_master):
        sync_master()


def reset_psu_replay(replay: dict[str, Any]) -> None:
    replay["enabled"] = False
    replay["source_path"] = None
    replay["records"] = []
    replay["index"] = 0
    replay["hk_anchor"] = None
    replay["latest_hk_time"] = None
    replay["psu_anchor"] = None


def update_psu_cards(psu_cards: list[Any], psu_sample: dict[str, Any], *, plot_sample: bool = True) -> None:
    for card in psu_cards:
        status_key = card.channel.get("status_key")
        if isinstance(status_key, str) and status_key in psu_sample and psu_sample.get(status_key) is not None:
            card.set_enabled_from_psu(bool(psu_sample.get(status_key)))
        current_key = card.channel.get("live_current_key")
        if isinstance(current_key, str):
            if plot_sample:
                card.push_sample(psu_sample.get("TIME"), psu_sample.get(current_key))
            else:
                card.ingest_sample(psu_sample.get(current_key))


def update_psu_readings(state: dict[str, Any], psu_sample: dict[str, Any]) -> None:
    readings = state["last_psu_readings"]
    for key in _PSU_SAMPLE_KEYS:
        source_key = "STATUS" if key == "status" else key
        readings[key] = psu_sample.get(source_key)


# endregion


# ---------------------------------------------------------------------------
# Script checks — HK / POST verification
# ---------------------------------------------------------------------------
# region Script checks — HK / POST verification


async def perform_acq_check(
    acq_mode: int = 0,
    acq_duration_s: int = 0,
    acq_timeout_s: float | None = None,
    acq_sample_time_ms: int = 0,
) -> None:
    """Async wrapper that runs the synchronous acquisition check in an executor."""
    await run.io_bound(lambda: perform_acq_check_sync(acq_mode, acq_duration_s, acq_timeout_s, acq_sample_time_ms))


def perform_acq_check_sync(
    acq_mode: int = 0,
    acq_duration_s: int = 0,
    acq_timeout_s: float | None = None,
    acq_sample_time_ms: int = 0,
) -> None:
    """Synchronous acquisition wait helper. Blocks until acquisition completes or timeout/abort.

    Completion is determined by firmware state: waits for CURRENT_OPERATING_STATE to
    enter 0x08 (Acquisition), then waits for it to leave 0x08 (back to Standby/Safe).
    This is correct regardless of acquisition mode, sample spacing, or packet count.

    For mode 2 (Fixed-point) acquisitions the firmware runs a setup phase (ADC
    initialisation / pre-scan) *inside* the 0x08 state before data collection begins.
    The firmware enforces a minimum spacing of 250 ms even when a smaller value is
    configured.  The timeout is therefore:

        timeout = acq_duration_s + setup_overhead + 120 s safety margin

    where setup_overhead = (effective_spacing_ms / 250) * 360 s  (6 min at the 250 ms
    minimum, scaling linearly for larger spacings).
    effective_spacing_ms = max(acq_sample_time_ms, 250) when acq_sample_time_ms > 0,
    otherwise 250 ms is assumed.

    All other modes default to 300 s.

    Args:
        acq_mode: acquisition mode (2 = Fixed-point; others use the default 300 s timeout).
        acq_duration_s: ACQ_DURATION field from SET_ACQ_CONFIGS, in seconds.
        acq_timeout_s: override the computed timeout (seconds).
        acq_sample_time_ms: ACQ_SAMPLE_TIME field from SET_ACQ_CONFIGS, in ms.
            Used to compute effective spacing; values below 250 are clamped to 250.

    This can be called from synchronous script code (e.g. inside `run_fft`).
    For async callers, use `await perform_acq_check()` which delegates to `run.io_bound`.
    """
    if acq_timeout_s is None:
        if acq_mode == 2 and acq_duration_s > 0:
            effective_spacing_ms = max(acq_sample_time_ms, 250) if acq_sample_time_ms > 0 else 250
            # Setup overhead: firmware ADC setup inside 0x08 takes ~4 min at 250 ms
            # minimum spacing; scale linearly for larger spacings.
            setup_overhead_s = int(effective_spacing_ms / 250 * 360)
            safety_s = 120
            acq_timeout_s = acq_duration_s + setup_overhead_s + safety_s
            info_log.debug(
                "Mode 2 acquisition: effective_spacing=%d ms, setup_overhead=%d s,"
                " timeout=%d s (duration %d s + setup %d s + safety %d s)",
                effective_spacing_ms,
                setup_overhead_s,
                acq_timeout_s,
                acq_duration_s,
                setup_overhead_s,
                safety_s,
            )
        else:
            acq_timeout_s = 300
    _ACQ_STATE = 0x08
    start_time = time.monotonic()
    _acq_150s_checked = False

    info_log.debug("Starting acquisition wait: waiting for CURRENT_OPERATING_STATE=0x08...")

    # --- Phase 1: wait for the EB to enter Acquisition state ---
    while True:
        if is_aborted():
            notify_negative("Acquisition aborted by user.")
            raise RuntimeError("Acquisition aborted by user.")
        if time.monotonic() - start_time > acq_timeout_s:
            notify_negative("Timeout waiting for acquisition to start.")
            raise TimeoutError("Timeout waiting for acquisition to start.")
        latest_hk = get_latest_hk()
        if latest_hk is not None and getattr(latest_hk, "CURRENT_OPERATING_STATE", None) == _ACQ_STATE:
            sci_count = getattr(latest_hk, "SCIENCE_PACKETS_SENT", 0)
            info_log.info(
                "Acquisition started (CURRENT_OPERATING_STATE=0x08), initial SCIENCE_PACKETS_SENT=%s",
                sci_count,
            )
            break
        time.sleep(1)

    # --- Phase 2: wait for the EB to leave Acquisition state ---
    while True:
        if is_aborted():
            notify_negative("Acquisition aborted by user.")
            raise RuntimeError("Acquisition aborted by user.")
        if time.monotonic() - start_time > acq_timeout_s:
            notify_negative("Timeout waiting for acquisition to complete.")
            raise TimeoutError("Timeout waiting for acquisition to complete.")

        latest_hk = get_latest_hk()
        if latest_hk is None:
            time.sleep(1)
            continue

        # One-shot PSU current check at t+150s from ACQ sequence start.
        # This aligns with the SCI flow timing where cooldown/homing/dark/start-move
        # typically occupy most of the first ~150 s before science data collection.
        if not _acq_150s_checked and time.monotonic() - start_time >= _SCI_ACQ_TRIGGER_S:
            _acq_150s_checked = True
            try:
                errors: list[str] = []
                ch4_current_ma = windowed_consumption_check(
                    ["State6"],
                    errors,
                    latest_hk,
                )
                thrm = getattr(latest_hk, "THRM_STATUS", None)
                if errors:
                    count = len(errors)
                    numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
                    info_log.warning(
                        "SCI ACQ t+150s check \u2014 %d error%s: %s",
                        count,
                        "s" if count != 1 else "",
                        "; ".join(numbered),
                    )
                    notify_negative(
                        f"SCI ACQ t+150s check failed ({count} error{'s' if count != 1 else ''}):\n"
                        + "\n".join(numbered)
                    )
                else:
                    msg = (
                        f"Power State 6 : SCI ACQ (windowed) \u2014 PSU_EB_I median: {ch4_current_ma:.2f} mA, "
                        f"CURRENT_OPERATING_STATE: {getattr(latest_hk, 'CURRENT_OPERATING_STATE', None)}, "
                        f"THRM_STATUS.HMS: {getattr(thrm, 'HMS', 0)}, THRM_STATUS.HDS: {getattr(thrm, 'HDS', 0)}, "
                        f"TEC_SETPOINT: {getattr(latest_hk, 'TEC_SETPOINT', None)}"
                    )
                    info_log.info(msg)
                    notify_positive(msg)
            except Exception as exc:
                info_log.warning("Acquisition t+150s PSU current check failed: %s", exc)

        cos = getattr(latest_hk, "CURRENT_OPERATING_STATE", None)
        if cos != _ACQ_STATE:
            sci_count_end = getattr(latest_hk, "SCIENCE_PACKETS_SENT", "N/A")
            acq_complete_msg = (
                (f"Acquisition complete — CURRENT_OPERATING_STATE=0x{cos:02X}, SCIENCE_PACKETS_SENT={sci_count_end}")
                if cos is not None
                else (f"Acquisition complete — SCIENCE_PACKETS_SENT={sci_count_end}")
            )
            info_log.info(
                "Acquisition complete: CURRENT_OPERATING_STATE=0x%02X, SCIENCE_PACKETS_SENT=%s at %s",
                cos if cos is not None else 0,
                sci_count_end,
                getattr(latest_hk, "TIME", None),
            )
            notify_positive(acq_complete_msg)
            # Drain one SCI packet from the queue for logging if available
            try:
                sci_packet = const.sci_queue.get(timeout=2.0)
                info_log.info("SCI packet received: %s", sci_packet)
            except Exception:
                pass
            return

        info_log.info(
            "Acquisition in progress (CURRENT_OPERATING_STATE=0x08, SCIENCE_PACKETS_SENT=%s)",
            getattr(latest_hk, "SCIENCE_PACKETS_SENT", "N/A"),
        )
        time.sleep(10)


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
            getattr(post, "POST_WARNING_FLAGS", None) == 0
            and getattr(post, "POST_ERROR_FLAGS", None) == 0
            and getattr(post, "NUM_BAD_FLASH_BLOCKS", None) == 0
            and getattr(post, "NUM_BAD_SRAM_BLOCKS", None) == 0
            and getattr(post, "ASW_IMAGE_1_CRC", None) == 0x2B22
            and getattr(post, "ASW_IMAGE_2_CRC", None) == 0xD46C
            and getattr(post, "ASW_IMAGE_3_CRC", None) == 0x8156
            and getattr(post, "ASW_IMAGE_4_CRC", None) == 0x0696
            and getattr(post, "ASW_IMAGE_5_CRC", None) == 0x6FEB
            and getattr(post, "BSW_IMAGE_CRC", None) == 0xD2D7
            and getattr(post, "MEASUREMENT_TABLE_CRC", None) == 0xF624
        )
        if not all_post_passed:
            result["passed"] = False
            # Add details for each failed check
            if getattr(post, "POST_WARNING_FLAGS", None) != 0:
                result["details"].append(f"POST_WARNING_FLAGS: {getattr(post, 'POST_WARNING_FLAGS', None)}")
            if getattr(post, "POST_ERROR_FLAGS", None) != 0:
                result["details"].append(f"POST_ERROR_FLAGS: {getattr(post, 'POST_ERROR_FLAGS', None)}")
            if getattr(post, "NUM_BAD_FLASH_BLOCKS", None) != 0:
                result["details"].append(f"NUM_BAD_FLASH_BLOCKS: {getattr(post, 'NUM_BAD_FLASH_BLOCKS', None)}")
            if getattr(post, "NUM_BAD_SRAM_BLOCKS", None) != 0:
                result["details"].append(f"NUM_BAD_SRAM_BLOCKS: {getattr(post, 'NUM_BAD_SRAM_BLOCKS', None)}")
            if getattr(post, "ASW_IMAGE_1_CRC", None) != 0x2B22:
                result["details"].append(f"ASW_IMAGE_1_CRC: {getattr(post, 'ASW_IMAGE_1_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_2_CRC", None) != 0xD46C:
                result["details"].append(f"ASW_IMAGE_2_CRC: {getattr(post, 'ASW_IMAGE_2_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_3_CRC", None) != 0x8156:
                result["details"].append(f"ASW_IMAGE_3_CRC: {getattr(post, 'ASW_IMAGE_3_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_4_CRC", None) != 0x0696:
                result["details"].append(f"ASW_IMAGE_4_CRC: {getattr(post, 'ASW_IMAGE_4_CRC', None):#06x}")
            if getattr(post, "ASW_IMAGE_5_CRC", None) != 0x6FEB:
                result["details"].append(f"ASW_IMAGE_5_CRC: {getattr(post, 'ASW_IMAGE_5_CRC', None):#06x}")
            if getattr(post, "BSW_IMAGE_CRC", None) != 0xD2D7:
                result["details"].append(f"BSW_IMAGE_CRC: {getattr(post, 'BSW_IMAGE_CRC', None):#06x}")
            if getattr(post, "MEASUREMENT_TABLE_CRC", None) != 0xF624:
                result["details"].append(f"MEASUREMENT_TABLE_CRC: {getattr(post, 'MEASUREMENT_TABLE_CRC', None):#06x}")
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


async def perform_homing_check(homing_timeout_s: float = 60.0) -> None:
    """Async wrapper that runs the synchronous homing check in an executor."""
    await run.io_bound(lambda: perform_homing_check_sync(homing_timeout_s))


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
        if homing_complete == 1:
            info_log.info("HOMING_COMPLETE detected in HK at %s", hk_time)
            return
        if time.monotonic() - start_time > homing_timeout_s:
            info_log.error("Timeout waiting for HOMING_COMPLETE flag in HK telemetry (waited %ss)", homing_timeout_s)
            notify_negative("Timeout waiting for HOMING_COMPLETE flag in HK telemetry.")
            raise TimeoutError("Timeout waiting for HOMING_COMPLETE flag in HK telemetry.")
        time.sleep(1)  # Sleep briefly to avoid busy-waiting


# endregion


# ---------------------------------------------------------------------------
# Script checks — heater state verification
# ---------------------------------------------------------------------------
# region Script checks — heater state verification


def verify_heater_states(
    latest_hk: Any,
    errors: list[str],
) -> list[str]:
    if latest_hk is None:
        errors.append("No HK packet available for heater state check.")
        return []

    thrm = getattr(latest_hk, "THRM_STATUS", None)
    if thrm is None:
        errors.append("THRM_STATUS not available in HK packet.")
        return []

    mm = bool(getattr(thrm, "MM", 0))
    ma = bool(getattr(thrm, "MA", 0))
    dm = bool(getattr(thrm, "DM", 0))
    da = bool(getattr(thrm, "DA", 0))
    act_hms = int(getattr(thrm, "HMS", 0))
    act_hds = int(getattr(thrm, "HDS", 0))

    info_log.info(
        "Heater check \u2014 THRM_STATUS: MM=%s MA=%s HMS=%s | DM=%s DA=%s HDS=%s",
        int(mm),
        int(ma),
        act_hms,
        int(dm),
        int(da),
        act_hds,
    )

    # --- Step 1: TC command check (informational only) ---
    if not mm and not ma:
        info_log.info("Heater check \u2014 Mech heater not commanded ON (THRM_STATUS.MM=0, MA=0)")
    if not dm and not da:
        info_log.info("Heater check \u2014 Det heater not commanded ON (THRM_STATUS.DM=0, DA=0)")

    # --- Step 2: Temperature / status check ---
    # Firmware bang-bang hysteresis algorithm:
    #   HMS/HDS turns ON  when BOTH current AND previous TRP < ON_SP  (OB_THERMAL_*_MIN)
    #   HMS/HDS turns OFF when BOTH current AND previous TRP > OFF_SP (OB_THERMAL_*_MAX)
    #   Otherwise (TRP in band): maintain PREV_STATUS — state is history-dependent.
    # _heater_state_history persists the last definitive expected state across poll cycles
    # so that the hysteresis band case can still be verified.  When transitioning from
    # disabled → auto the firmware initialises PREV_STATUS to OFF, which is reflected here.
    def _check_htr(label, mode_manual, mode_auto, trp_attr, on_sp_attr, off_sp_attr, act):
        h = _heater_state_history[label]
        if mode_manual:
            # Manual mode: heater must always be physically ON; record known state
            if not h["prev_manual"]:
                info_log.info("%s heater: Manual mode enabled — recording expected=ON", label)
            h.update(last_expected=True, prev_auto=False, prev_manual=True)
            if not act:
                errors.append(f"{label} heater in Manual mode but HMS/HDS={act} (expected 1)")
        elif mode_auto:
            trp = getattr(latest_hk, trp_attr, None)
            on_sp = getattr(latest_hk, on_sp_attr, None)
            off_sp = getattr(latest_hk, off_sp_attr, None)
            # Detect disabled→auto transition (firmware PREV_STATUS initialises to OFF)
            newly_enabled = not h["prev_auto"] and not h["prev_manual"]
            if newly_enabled:
                info_log.info(
                    "%s heater: Auto mode just enabled — TRP=%s [ON_SP=%s, OFF_SP=%s] — firmware initialises to OFF",
                    label,
                    trp,
                    on_sp,
                    off_sp,
                )
                if h["last_expected"] is None:
                    h["last_expected"] = False  # firmware default at first enable
            h.update(prev_auto=True, prev_manual=False)
            if None in (trp, on_sp, off_sp):
                info_log.warning(
                    "%s heater Auto mode — fields missing (%s=%s, %s=%s, %s=%s), skipping check",
                    label,
                    trp_attr,
                    trp,
                    on_sp_attr,
                    on_sp,
                    off_sp_attr,
                    off_sp,
                )
                return
            h["last_trp"] = trp
            info_log.info(
                "%s heater Auto mode \u2014 TRP=%s [ON_SP=%s, OFF_SP=%s] last_expected=%s",
                label,
                trp,
                on_sp,
                off_sp,
                h["last_expected"],
            )
            if trp < on_sp:
                # Below ON threshold — heater must be ON; record boundary crossing
                h["last_expected"] = True
                if not act:
                    errors.append(f"{label} heater: TRP={trp} < ON_SP={on_sp} \u2192 expected ON, got HMS/HDS={act}")
            elif trp > off_sp:
                # Above OFF threshold — heater must be OFF; record boundary crossing
                h["last_expected"] = False
                if act:
                    errors.append(f"{label} heater: TRP={trp} > OFF_SP={off_sp} \u2192 expected OFF, got HMS/HDS={act}")
            else:
                # TRP in hysteresis band [ON_SP, OFF_SP] — use recorded history
                exp = h["last_expected"]
                if newly_enabled:
                    # First poll for this heater (EGSE started mid-test, or heater was
                    # re-enabled while TRP was already in band).  We have no reliable
                    # history of which boundary was last crossed, so we cannot verify
                    # the state — use the actual HMS/HDS as the baseline for future polls.
                    info_log.info(
                        "%s heater: auto first detected with TRP=%s in band [%s, %s],"
                        " HMS/HDS=%s — using as history baseline (cannot verify initial state)",
                        label,
                        trp,
                        on_sp,
                        off_sp,
                        act,
                    )
                    h["last_expected"] = bool(act)
                elif exp is True:
                    if not act:
                        errors.append(
                            f"{label} heater: TRP={trp} in band [{on_sp}, {off_sp}],"
                            f" last boundary \u2192 ON, but HMS/HDS={act}"
                        )
                    else:
                        info_log.info(
                            "%s heater: TRP=%s in band [%s, %s] \u2014 last boundary \u2192 ON, HMS/HDS=%s (OK)",
                            label,
                            trp,
                            on_sp,
                            off_sp,
                            act,
                        )
                elif exp is False:
                    if act:
                        errors.append(
                            f"{label} heater: TRP={trp} in band [{on_sp}, {off_sp}],"
                            f" last boundary \u2192 OFF, but HMS/HDS={act}"
                        )
                    else:
                        info_log.info(
                            "%s heater: TRP=%s in band [%s, %s] \u2014 last boundary \u2192 OFF, HMS/HDS=%s (OK)",
                            label,
                            trp,
                            on_sp,
                            off_sp,
                            act,
                        )
                else:
                    # No history yet (e.g. TRP has been in band since enable) — cannot verify
                    info_log.info(
                        "%s heater: TRP=%s in band [%s, %s] \u2014 no boundary history, HMS/HDS=%s",
                        label,
                        trp,
                        on_sp,
                        off_sp,
                        act,
                    )
        else:
            # Heater not commanded — reset history ready for the next enable event
            h.update(last_expected=None, last_trp=None, prev_auto=False, prev_manual=False)

    _check_htr("Mech", mm, ma, "OB_MECHANISM_TRP", "OB_THERMAL_MECH_MIN", "OB_THERMAL_MECH_MAX", act_hms)
    _check_htr("Det", dm, da, "OB_DETECTOR_TRP", "OB_THERMAL_DET_MIN", "OB_THERMAL_DET_MAX", act_hds)

    # Return active heater state names for consumption_check
    states: list[str] = []
    if act_hms:
        states.append("MechHTR")
    if act_hds:
        states.append("DetHTR")
    return states


# Central script runtime control (play / pause / abort)
_SCRIPT_CONTROL = {
    "running": False,
    "pause_event": threading.Event(),
    "abort_event": threading.Event(),
    "current_script": None,
}
# endregion


# ---------------------------------------------------------------------------
# Script checks — RET / state verification
# ---------------------------------------------------------------------------
# region Script checks — RET / state verification


def is_valid_post_packet(post: Any) -> bool:
    return all(hasattr(post, field_name) for field_name in _POST_REQUIRED_FIELDS)


def pull_post_after_ret(timeout_s: float = 6.0, poll_s: float = 0.2) -> Any | None:
    """Return a valid POST packet after RET, retrying queue reads and RS422 refresh."""
    deadline = time.monotonic() + max(0.1, timeout_s)
    while time.monotonic() < deadline:
        while not const.eb_post_queue.empty():
            post = const.eb_post_queue.get()
            if is_valid_post_packet(post):
                return post

        rs422_log_path = getattr(getattr(_nicegui_app.state, "eb_interface", None), "rs422_log_path", None)
        if rs422_log_path:
            try:
                eb_packet_utility.read_pkt(rs422_log_path, latest_only=True)
            except Exception:
                pass

        time.sleep(max(0.05, poll_s))

    return None


def pull_psu_after_ret(timeout_s: float = 6.0, poll_timeout_s: float = 0.5) -> dict[str, Any] | None:
    """Return a smoothed PSU sample after RET, with fallback to cached latest sample."""
    deadline = time.monotonic() + max(0.1, timeout_s)
    while time.monotonic() < deadline:
        try:
            sample = get_smoothed_psu_sample(const.psu_queue, timeout=poll_timeout_s)
            if isinstance(sample, dict):
                set_latest_psu(sample)
                return sample
        except Empty:
            cached = get_latest_psu()
            if isinstance(cached, dict):
                return cached
        time.sleep(0.1)

    cached = get_latest_psu()
    return cached if isinstance(cached, dict) else None


def verify_power_state(state: str) -> tuple[str, bool]:
    """Verify the OB is in the expected power state.

    Fetches the latest HK and PSU samples from their queues, runs a PSU
    consumption check for *state*, then performs additional HK field checks
    appropriate for that state:

    State2  — OB Heating:           heater verification (via consumption_check)
    State3  — OB Heating + Boards:  State2 checks + mech/det boards enabled
    State4  — OB Heating + TEC 1A:  State3 checks + TEC current > 1 A
    State5  — Boards + TEC 1A:      boards enabled + TEC current > 1 A
    State7  — All Active:           State4 checks + motor moving

    Returns (msg, passed) — the same contract as verify_safe_ret / verify_standby_ret.
    """
    _BOARD_STATES = {"State3", "State4", "State5", "State7"}
    _TEC_STATES = {"State4", "State5", "State7"}

    errors: list[str] = []
    ch4_current_ma: float | None = None

    try:
        latest_hk = get_latest_hk()
        latest_psu = get_smoothed_psu_sample(const.psu_queue, timeout=2.0)
    except Empty:
        errors.append(f"Missing HK or PSU queue data for {state} verification")
        latest_hk = None
        latest_psu = None

    # --- PSU consumption + heater check ---
    if latest_psu is not None:
        ch4_current_ma = consumption_check(state, latest_psu, errors, latest_hk)

    if latest_hk is not None:
        instr = getattr(latest_hk, "INSTR_STATUS_FLAGS", None)

        # --- Boards enabled (State3 / State4 / State5 / State7) ---
        if state in _BOARD_STATES:
            mech_board = bool(getattr(instr, "OB_MECHANISM_BOARD_ENABLED", 0))
            det_board = bool(getattr(instr, "OB_DETECTOR_BOARD_ENABLED", 0))
            if not mech_board:
                errors.append("Mech board not enabled (INSTR_STATUS_FLAGS.OB_MECHANISM_BOARD_ENABLED=0)")
            if not det_board:
                errors.append("Det board not enabled (INSTR_STATUS_FLAGS.OB_DETECTOR_BOARD_ENABLED=0)")

        # --- TEC at 1 A (State4 / State5 / State7) ---
        if state in _TEC_STATES:
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
            if tec_current <= 1.0:
                # TEC may still be ramping — poll for up to 30 s before failing
                info_log.debug(
                    "%s TEC current %.3f A <= 1.0 A, waiting for ramp-up (up to 30 s)...", state, tec_current
                )
                _tec_ramped = False
                for _ in range(30):
                    time.sleep(1)
                    _poll_hk = get_latest_hk()
                    if _poll_hk is not None:
                        tec_current = getattr(_poll_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
                        if tec_current > 1.0:
                            latest_hk = _poll_hk  # use the fresher HK for remaining checks
                            _tec_ramped = True
                            break
                if not _tec_ramped:
                    errors.append(f"TEC current not at 1 A: {tec_current:.3f} A (expected > 1.0 A)")

        # --- Motor moving (State7) ---
        if state == "State7":
            mtr = getattr(latest_hk, "MTR_FLAGS", None)
            if not bool(getattr(mtr, "MOVING", 0)):
                errors.append("Motor not moving (MTR_FLAGS.MOVING=0)")

    cos = getattr(latest_hk, "CURRENT_OPERATING_STATE", None) if latest_hk is not None else None

    if errors:
        count = len(errors)
        numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
        info_log.error(
            "%s verification failed: %d error%s — PSU_EB_I: %s mA",
            state,
            count,
            "s" if count != 1 else "",
            f"{ch4_current_ma:.2f}" if ch4_current_ma is not None else "N/A",
        )
        msg = f"{state} verification failed: {count} error{'s' if count != 1 else ''}:\n" + "\n".join(numbered)
        notify(msg, color="negative")
        return msg, False
    else:
        msg = f"Power {state} OK — PSU_EB_I: {ch4_current_ma:.2f} mA, CURRENT_OPERATING_STATE: {cos}"
        info_log.info(msg)
        notify(msg, color="positive")
        return msg, True


def verify_safe_ret():
    errors = []
    # ?RET and first check
    # This block performs the SAFE RET verification after issuing a RET and HK request.
    latest_post = pull_post_after_ret(timeout_s=6.0)
    latest_psu = pull_psu_after_ret(timeout_s=6.0)

    if latest_post is None:
        errors.append("\nMissing POST queue data after RET")
    if latest_psu is None:
        errors.append("\nMissing PSU queue data after RET")

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
        info_log.error(f"PSU_EB_I: {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA")
        msg = f"SAFE RET verification failed: {count} error{'s' if count != 1 else ''} :\n" + "\n".join(numbered)
        notify_negative(msg)
        return msg, False
    else:
        msg = f"Power State 1 - SAFE mode: EB PSU I : {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA, \nPOST Packet Check Result: {result}"
        info_log.info(msg)
        notify_positive(msg)
        return msg, True


def verify_standby_ret():
    errors = []
    # Wait for a fresh HK packet that arrives after the standby TC, not a cached one
    try:
        latest_hk = wait_for_fresh_hk(timeout=5.0)
        if latest_hk is None:
            errors.append("Timed out waiting for fresh HK after STANDBY")
        latest_psu = get_smoothed_psu_sample(const.psu_queue, timeout=2.0)
    except Empty:
        errors.append("\nMissing PSU queue data after STANDBY")
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
        notify_negative(msg)
        return msg, False
    else:
        msg = f"Standby mode: EB PSU I : {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA, \nHK Check Result: {result}"
        info_log.info(msg)
        notify_positive(msg)
        return msg, True


# endregion


# ---------------------------------------------------------------------------
# Script controls — pause / abort / run state
# ---------------------------------------------------------------------------
# region Script controls — pause / abort / run state


def clear_abort() -> None:
    _SCRIPT_CONTROL["abort_event"].clear()


def clear_pause() -> None:
    _SCRIPT_CONTROL["pause_event"].clear()


def finish_script() -> None:
    """Clear running state and reset control events."""
    _SCRIPT_CONTROL["running"] = False
    _SCRIPT_CONTROL["pause_event"].clear()
    _SCRIPT_CONTROL["abort_event"].clear()
    _SCRIPT_CONTROL["current_script"] = None


def get_script_control() -> dict:
    """Return the runtime script control dictionary.

    Keys: `running` (bool), `pause_event` (threading.Event),
    `abort_event` (threading.Event), `current_script` (optional name).
    """
    return _SCRIPT_CONTROL


def is_aborted() -> bool:
    return _SCRIPT_CONTROL["abort_event"].is_set()


def is_paused() -> bool:
    return _SCRIPT_CONTROL["pause_event"].is_set()


def is_script_running() -> bool:
    return bool(_SCRIPT_CONTROL.get("running"))


def request_abort() -> None:
    _SCRIPT_CONTROL["abort_event"].set()


def request_pause() -> None:
    _SCRIPT_CONTROL["pause_event"].set()


def start_script(script_name: str | None = None) -> None:
    """Mark a script as running and clear control events."""
    _SCRIPT_CONTROL["running"] = True
    _SCRIPT_CONTROL["current_script"] = script_name
    _SCRIPT_CONTROL["pause_event"].clear()
    _SCRIPT_CONTROL["abort_event"].clear()
    # Ensure any UI-forced pause is released when starting a new script
    _FORCE_PAUSE_EVENT.clear()


def toggle_pause() -> None:
    if is_force_paused():
        # If a UI-forced pause was active, clear it first
        clear_force_pause()
        return
    if is_paused():
        clear_pause()
    else:
        request_pause()


# endregion


# ---------------------------------------------------------------------------
# Theme helpers
# ---------------------------------------------------------------------------
# region Theme helpers


def apply_theme_to_ui(
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
        apply_theme_to_ui(
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
# endregion


# ---------------------------------------------------------------------------
# TM / HK helpers — decoding, alarm lights, plot cards
# ---------------------------------------------------------------------------
# region TM / HK helpers — decoding, alarm lights, plot cards


def active_flag_names(flag_ns: Any, ordered_names: list[str]) -> list[str]:
    if flag_ns is None:
        return []
    return [
        name
        for name in ordered_names
        if not name.startswith("UNUSED") and not name.startswith("RESERVED") and bool(getattr(flag_ns, name, 0))
    ]


def any_flag(flag_ns: Any) -> bool:
    return bool(flag_ns) and any(bool(value) for value in flag_ns.__dict__.values())


def _ob_adc12(raw: Any) -> int | None:
    """Normalise a standalone OB ADC field to a 12-bit ADU value.

    Native ``tmstruct.hk`` packets normally expose the ADC as an already
    normalised 0..4095 value.  The fallback also accepts a 16-bit left-aligned
    representation used by some older decoders.
    """
    try:
        raw_value = int(raw)
    except (TypeError, ValueError):
        return None

    if 0 <= raw_value <= 0x0FFF:
        return raw_value
    if 0 <= raw_value <= 0xFFFF:
        return (raw_value >> 4) & 0x0FFF
    return raw_value & 0x0FFF


def decode_plot_field(
    packet: Any,
    field_name: str,
    state: dict[str, Any] | None = None,
) -> float | None:
    raw = getattr(packet, field_name, None)
    if raw is None:
        return None

    display_mode = str(
        (state or {}).get("hk_display_mode") or getattr(_nicegui_app.state, "hk_display_mode", "REAL")
    ).upper()

    # Native standalone OB analogue fields must be normalised before conversion.
    if field_name in _NATIVE_OB_ADC12_FIELDS:
        adu = _ob_adc12(raw)
        if adu is None:
            return None

        if display_mode == "ADU":
            return float(adu)

        try:
            if field_name == "HK_V_3V3":
                value = adu * 4.05 / 4095.0 * 2.0

            elif field_name == "HK_V_1V5":
                value = adu * 4.05 / 4095.0

            elif field_name in {
                "DIGITAL_TRP",
                "DETEC_TRP",
                "MECH_TRP",
                "MOTOR_TRP",
            }:
                # Endpoint ADC values normally cannot produce a valid
                # thermistor resistance/temperature.
                if adu <= 0 or adu >= 4095:
                    return None

                value = float(eb_packet_utility.adu_to_temp(adu))

            else:
                return None

        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            return None

        return float(value) if math.isfinite(float(value)) else None

    # Existing EB conversion path.
    if display_mode == "ADU":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    try:
        value = hk_conversions.decode_field(packet, field_name)
        value = float(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None

    return value if math.isfinite(value) else None


def decode_tuple(
    packet: Any,
    field_names: tuple[str, ...],
    state: dict[str, Any] | None = None,
) -> list[float] | None:
    values: list[float] = []

    for field_name in field_names:
        value = decode_plot_field(packet, field_name, state)
        if value is None:
            return None
        values.append(value)

    return values


def decoded(packet: Any, field_name: str) -> float | None:
    value = hk_conversions.decode_field(packet, field_name)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def drain_packet_queue(queue: Any, handler: Any) -> None:
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
    ("OB FPGA I/O", "OB_3V3_VOLTAGE", "ob_fpga_io_v", False),
    ("OB FPGA Core", "OB_1V5_VOLTAGE", "ob_fpga_core_v", False),
    ("OB DIG TRP", "OB_DIGITAL_TRP", "ob_digital_trp", False),
    ("OB DET TRP", "OB_DETECTOR_TRP", "ob_detector_trp", False),
    ("OB MECH TRP", "OB_MECHANISM_TRP", "ob_mechanism_trp", False),
    ("OB MOTOR TRP", "OB_MOTOR_TRP", "ob_motor_trp", False),
)


def eb_alarm_details(hk: Any) -> list[str]:
    warning_bits = active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), _WARNING_NAMES)
    fdir_alarm_bits = active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), _FDIR_NAMES)
    fdir_warning_bits = active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), _FDIR_NAMES)

    details: list[str] = []
    tcs_rejected = int(getattr(hk, "TCS_REJECTED", 0) or 0)
    if tcs_rejected > 0:
        details.append(f"TCS Rejected: {tcs_rejected}")
    details.extend([f"EB Warning: {flag}" for flag in warning_bits if flag in _EB_WARNING_FLAGS])
    details.extend([f"EB FDIR Alarm: {flag}" for flag in fdir_alarm_bits if flag in _EB_FDIR_FLAGS])
    details.extend([f"EB FDIR Warning: {flag}" for flag in fdir_warning_bits if flag in _EB_FDIR_FLAGS])
    return details


def log_new_hk_alarm_details(state: dict[str, Any], logger: Any, channel: str, details: list[str]) -> None:
    active_details = state.setdefault("hk_active_alarm_details", {"ob": set(), "eb": set()})
    previous = set(active_details.get(channel, set()))
    current = set(details)

    for detail in sorted(current - previous):
        detail_lower = detail.lower()
        if "error" in detail_lower or "alarm" in detail_lower:
            logger.error("HK %s alarm raised: %s", channel.upper(), detail)
        else:
            logger.warning("HK %s warning raised: %s", channel.upper(), detail)

    active_details[channel] = current


def ob_alarm_details(hk: Any) -> list[str]:
    warning_bits = active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), _WARNING_NAMES)
    fdir_alarm_bits = active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), _FDIR_NAMES)
    fdir_warning_bits = active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), _FDIR_NAMES)

    details = [f"OB Warning: {flag}" for flag in warning_bits if flag in _OB_WARNING_FLAGS]
    details.extend([f"OB FDIR Alarm: {flag}" for flag in fdir_alarm_bits if flag in _OB_FDIR_FLAGS])
    details.extend([f"OB FDIR Warning: {flag}" for flag in fdir_warning_bits if flag in _OB_FDIR_FLAGS])
    if any_flag(getattr(hk, "ERRORS", None)):
        details.append("OB Error flags active")
    if any_flag(getattr(hk, "MTR_ERRORS", None)):
        details.append("OB Motor error flags active")
    return details


def update_hk_alarm_lights(state: dict[str, Any], hk: Any, logger: Any) -> None:
    alarm_lights = state.get("alarm_lights") or {}
    mode = str(state.get("mode", "EB")).upper()

    # In standalone OB mode, FDIR bitmaps are simulated from native OB ADCs.
    # Keep packet-reported errors and simulated FDIR latches as separate light
    # sources so Clear_Errors can reset only the simulator source.
    ob_details = ob_alarm_details(hk)
    simulated_details = simulated_ob_fdir_details(state) if mode == "OB" else []
    if mode == "OB":
        ob_details = [detail for detail in ob_details if "OB FDIR " not in detail]
    eb_details = eb_alarm_details(hk)

    active_logger = logger if logger is not None else info_log
    active_details = state.setdefault("hk_active_alarm_details", {"ob": set(), "eb": set()})
    previous_ob_details = set(active_details.get("ob", set()))
    newly_raised_ob_details = sorted(set(ob_details) - previous_ob_details)

    # Simulated latches are logged with their raw ADU and limits when first
    # asserted by simulate_ob_fdir(); avoid emitting a second generic log here.
    log_new_hk_alarm_details(state, active_logger, "ob", ob_details)
    log_new_hk_alarm_details(state, active_logger, "eb", eb_details)

    # Native OB warnings and error flags never shut the PSU down automatically.
    # They ask the operator once when newly asserted. Simulated FDIR warnings
    # and thermistor alarms are handled directly by simulate_ob_fdir().
    if mode == "OB" and newly_raised_ob_details:
        _open_ob_psu_shutdown_dialog(state, active_logger, newly_raised_ob_details)

    if "ob" in alarm_lights:
        alarm_lights["ob"].update_from_faults({detail: True for detail in ob_details}, source="hk")
        alarm_lights["ob"].update_from_faults(
            {detail: True for detail in simulated_details},
            source="ob_fdir_sim",
        )
    if "eb" in alarm_lights:
        alarm_lights["eb"].update_from_faults({detail: True for detail in eb_details}, source="hk")


def update_packet_viewer(
    mode: str, packet_viewer_controllers: dict[str, Any], hk: Any, packet_list_controller: Any = None
) -> None:
    packet_type = "OB_HK" if mode == "OB" else "EB_HK"
    viewer = packet_viewer_controllers.get(packet_type)
    if viewer is None:
        return
    # Route each HK packet popped from const.hk_queue directly to the active HK viewer profile.
    viewer.update_from_packet(packet_type, hk)

    # Add to packet list if available
    if packet_list_controller is not None:
        packet_data = hk.__dict__
        label = f"TM: {packet_type}"
        packet_list_controller.add_packet(packet_type, packet_data, label)


def update_plot_cards(
    state: dict[str, Any],
    hk: Any,
    trp_card: Any,
    voltage_card: Any,
) -> None:
    time_value = getattr(hk, "TIME", None)
    if time_value is None:
        return

    replay = state["psu_replay"]
    replay["latest_hk_time"] = time_value
    if replay.get("hk_anchor") is None:
        replay["hk_anchor"] = time_value

    mode = str(state.get("mode", "EB")).upper()

    if mode == "OB":
        # Receiving a standalone OB HK packet proves that the OB stream is alive.
        trp_card.set_stream_enabled(True)
        voltage_card.set_stream_enabled(True)

        trp_values = decode_tuple(hk, _NATIVE_OB_TRP_FIELDS, state)
        if trp_values is not None:
            trp_card.push(
                [time_value],
                [[value] for value in trp_values],
            )

        ob_3v3 = decode_plot_field(hk, "HK_V_3V3", state)
        ob_1v5 = decode_plot_field(hk, "HK_V_1V5", state)
        if ob_3v3 is not None or ob_1v5 is not None:
            # The voltage card has three series: OB 3V3, OB 1V5 and EB 3V3.
            # Do not update the EB series from a standalone OB packet.
            voltage_card.push(
                [time_value],
                [
                    [ob_3v3 if ob_3v3 is not None else float("nan")],
                    [ob_1v5 if ob_1v5 is not None else float("nan")],
                    [float("nan")],
                ],
            )

        return

    # EB mode uses the combined EB HK packet.
    instr_flags = getattr(hk, "INSTR_STATUS_FLAGS", None)

    if instr_flags is not None:
        ob_enabled = bool(getattr(instr_flags, "OB_5V_ENABLED", 0))
    else:
        # Fallback for packets containing only the numeric flag field.
        try:
            numeric_flags = int(getattr(hk, "INSTRUMENT_STATUS_FLAGS", 0))
            ob_enabled = bool((numeric_flags >> 5) & 0x1)
        except (TypeError, ValueError):
            ob_enabled = False

    trp_card.set_stream_enabled(ob_enabled)
    voltage_card.set_stream_enabled(ob_enabled)

    if not ob_enabled:
        return

    trp_values = decode_tuple(hk, _EB_OB_TRP_FIELDS, state)
    if trp_values is not None:
        trp_card.push(
            [time_value],
            [[value] for value in trp_values],
        )

    voltage_values = decode_tuple(
        hk,
        ("OB_3V3_VOLTAGE", "OB_1V5_VOLTAGE", "EB_MEAS_3V3"),
        state,
    )
    if voltage_values is not None:
        voltage_card.push(
            [time_value],
            [[value] for value in voltage_values],
        )


# endregion


# ---------------------------------------------------------------------------
# TM polling — create_poll_tm and supporting helpers
# ---------------------------------------------------------------------------
# region TM polling — create_poll_tm and supporting helpers


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
    trp_card: Any,
    voltage_card: Any,
    hk_explorer_card: Any = None,
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

        # Process HK packets (match legacy `ebgui` behaviour: increment on every HK pop)
        while not const.hk_queue.empty():
            processed_hk = True
            hk = const.hk_queue.get()
            now = datetime.now()
            if mode == "OB":
                state["last_ob_tm_time"] = getattr(hk, "TIME", now)
            # Calculate time since last HK
            if last_hk_time is not None:
                hk_delta = (now - last_hk_time).total_seconds()
            else:
                hk_delta = 0.0
            state["hk_time_since_last"] = hk_delta
            state["latest_hk_time"] = now
            last_hk_time = now

            # Legacy behaviour: increment HK counter for each HK packet popped from the queue
            counts["hk"] = int(counts.get("hk", 0)) + 1

            if not hasattr(hk, "TIME"):
                hk.TIME = now

            if mode == "OB":
                simulate_ob_fdir(state, hk, logger)

            eb_metrics_card.update_from_packet(hk)
            ob_metrics_card.update_from_packet(hk)
            update_hk_alarm_lights(state, hk, logger)

            # MMS runs continuously while in EB mode and latches on first trigger.
            mms_cfg = state.get("mms") or {}
            if state.get("mode") == "EB" and bool(mms_cfg.get("enabled", True)):
                reasons, tec_pre_action, ob5v_pre_action = mms_reasons(hk, mms_cfg.get("limits") or {})
                if reasons:
                    if mms_cfg.get("latched") or mms_cfg.get("in_progress") or mms_cfg.get("pending"):
                        pass
                    else:
                        mms_cfg["pending"] = True

                        async def _schedule_mms_call() -> None:
                            try:
                                await mms(
                                    app,
                                    state,
                                    logger,
                                    hk,
                                    list(reasons),
                                    tec_pre_action,
                                    ob5v_pre_action,
                                )
                            except Exception as exc:
                                logger.exception("Failed to execute MMS actions: %s", exc)
                            finally:
                                current_cfg = state.setdefault("mms", {})
                                current_cfg["pending"] = False

                        try:
                            asyncio.create_task(_schedule_mms_call())
                        except Exception as exc:
                            mms_cfg["pending"] = False
                            logger.exception("Could not schedule MMS task: %s", exc)

            update_plot_cards(state, hk, trp_card, voltage_card)
            if hk_explorer_card is not None:
                hk_explorer_card.push_data({"EB_HK": hk})
            packet_list_controller = state.get("packet_list_controller")
            update_packet_viewer(mode, packet_viewer_controllers, hk, packet_list_controller)

        # In static/mock-log runs, HK may stop updating. Keep replay time moving so
        # PSU log playback can continue even without fresh HK packets.
        replay = state["psu_replay"]
        if replay.get("enabled") and replay.get("hk_anchor") is not None and not processed_hk:
            replay["latest_hk_time"] = datetime.now()

        # Process one POST packet per cycle, matching ebgui behaviour and dedupe by identity
        if not const.eb_post_queue.empty():
            post = const.eb_post_queue.get()
            required_post_fields = (
                "POST_WARNING_FLAGS",
                "POST_ERROR_FLAGS",
                "NUM_BAD_FLASH_BLOCKS",
                "NUM_BAD_SRAM_BLOCKS",
                "ASW_IMAGE_1_CRC",
                "ASW_IMAGE_2_CRC",
                "ASW_IMAGE_3_CRC",
                "ASW_IMAGE_4_CRC",
                "ASW_IMAGE_5_CRC",
                "BSW_IMAGE_CRC",
                "MEASUREMENT_TABLE_CRC",
            )
            if not all(hasattr(post, field_name) for field_name in required_post_fields):
                logger.debug("Ignoring non-POST packet in POST queue")
            else:
                post_identity = tuple(getattr(post, field_name, None) for field_name in required_post_fields)
                last_post_identity = state.setdefault("last_post_identity", {"value": None})
                if post_identity == last_post_identity.get("value"):
                    logger.debug("Ignoring duplicate POST packet in POST queue")
                else:
                    last_post_identity["value"] = post_identity
                    counts["post"] = int(counts.get("post", 0)) + 1
                    state.setdefault("packet_counts", counts)
                    state["last_post"] = post
                    # Update POST viewer if present
                    if "EB_POST" in packet_viewer_controllers:
                        try:
                            packet_viewer_controllers["EB_POST"].update_from_packet(post)
                        except Exception:
                            logger.debug("Failed to update EB_POST packet viewer")

                    # Add to packet list if available
                    packet_list_controller = state.get("packet_list_controller")
                    if packet_list_controller is not None:
                        post_data = (
                            post.__dict__
                            if hasattr(post, "__dict__")
                            else (dict(post) if isinstance(post, dict) else {})
                        )
                        label = "TM: Post"
                        packet_list_controller.add_packet("EB_POST", post_data, label)

        # Process SCI packets from TM queues.
        # EB SCI and OB SCI have different packet shapes, so we handle them separately.
        if not const.sci_queue.empty():
            if mode == "OB":
                new_ob_sci_packets = 0
                latest_ob_sci = None
                ob_recent_identities = state.setdefault("ob_sci_recent_identities", [])
                ob_recent_identity_set = state.setdefault("ob_sci_recent_identity_set", set())
                max_ob_recent_identities = int(state.get("ob_sci_dedupe_window", 128) or 128)

                while not const.sci_queue.empty():
                    candidate = const.sci_queue.get()
                    if not hasattr(candidate, "__dict__") and not isinstance(candidate, dict):
                        logger.debug("Ignoring non-object packet in SCI queue")
                        continue

                    latest_sci = candidate
                    if isinstance(latest_sci, dict):
                        latest_sci.setdefault("TIME", datetime.now())
                        state["last_ob_tm_time"] = latest_sci.get("TIME")

                        def _field(name: str) -> Any:
                            return latest_sci.get(name)

                    else:
                        if not hasattr(latest_sci, "TIME"):
                            latest_sci.TIME = datetime.now()
                        state["last_ob_tm_time"] = getattr(latest_sci, "TIME", datetime.now())

                        def _field(name: str) -> Any:
                            return getattr(latest_sci, name, None)

                    # OB SCI identity based on command counter and key measurement values.
                    sci_identity = (
                        "OB_SCI",
                        _field("CMD_CNT"),
                        _field("SWIR_HIGH"),
                        _field("SWIR_MED"),
                        _field("SWIR_LOW"),
                        _field("MWIR_HIGH"),
                        _field("MWIR_MED"),
                        _field("MWIR_LOW"),
                    )
                    if sci_identity in ob_recent_identity_set:
                        logger.debug("Ignoring duplicate OB science packet in SCI queue")
                        continue

                    ob_recent_identities.append(sci_identity)
                    ob_recent_identity_set.add(sci_identity)
                    if len(ob_recent_identities) > max_ob_recent_identities:
                        expired = ob_recent_identities.pop(0)
                        if expired not in ob_recent_identities:
                            ob_recent_identity_set.discard(expired)

                    latest_ob_sci = latest_sci
                    counts["sci"] = int(counts.get("sci", 0)) + 1
                    new_ob_sci_packets += 1

                if new_ob_sci_packets > 0 and latest_ob_sci is not None and "OB_SCI" in packet_viewer_controllers:
                    try:
                        packet_viewer_controllers["OB_SCI"].update_from_packet(latest_ob_sci)

                        packet_list_controller = state.get("packet_list_controller")
                        if packet_list_controller is not None:
                            sci_data = (
                                latest_ob_sci.__dict__
                                if hasattr(latest_ob_sci, "__dict__")
                                else (dict(latest_ob_sci) if isinstance(latest_ob_sci, dict) else {})
                            )
                            packet_list_controller.add_packet("OB_SCI", sci_data, "TM: OB Science")
                    except Exception:
                        logger.debug("Failed to update OB_SCI packet viewer")
            else:
                new_sci_packets = 0
                required_sci_fields = (
                    "PACKET_NUMBER",
                    "SCI_POINT_COUNT",
                    "SCI_PACKET_CRITICALITY",
                )
                sci_packets = state.setdefault("sci_packets", [])
                sci_packet_identities = state.setdefault("sci_packet_identities", set())
                while not const.sci_queue.empty():
                    latest_sci = const.sci_queue.get()
                    if not all(hasattr(latest_sci, field_name) for field_name in required_sci_fields):
                        logger.debug("Ignoring non-SCI packet in SCI queue")
                        continue
                    if not hasattr(latest_sci, "TIME"):
                        latest_sci.TIME = datetime.now()
                    # Build identity tuple (packet_number, criticality, point_count, first_abs_step, last_abs_step)
                    packet_number = getattr(latest_sci, "PACKET_NUMBER", None)
                    criticality = getattr(latest_sci, "SCI_PACKET_CRITICALITY", None)
                    point_count = int(getattr(latest_sci, "SCI_POINT_COUNT", 0) or 0)
                    first_abs_step = None
                    last_abs_step = None
                    sci_points = getattr(latest_sci, "SCI_POINTS", None)
                    if sci_points:
                        first_abs_step = getattr(sci_points[0], "ABS_STEPS", None)
                        last_abs_step = getattr(sci_points[-1], "ABS_STEPS", None)
                    elif hasattr(latest_sci, "ABS_STEPS"):
                        first_abs_step = getattr(latest_sci, "ABS_STEPS", None)
                        last_abs_step = first_abs_step
                    sci_identity = (packet_number, criticality, point_count, first_abs_step, last_abs_step)
                    if sci_identity in sci_packet_identities:
                        logger.debug("Ignoring duplicate science packet in SCI queue")
                        continue
                    sci_packets.append(latest_sci)
                    sci_packet_identities.add(sci_identity)
                    counts["sci"] = int(counts.get("sci", 0)) + 1
                    new_sci_packets += 1

                # Sort and trim buffer as legacy GUI
                try:
                    sci_packets.sort(key=lambda p: int(getattr(p, "PACKET_NUMBER", 0)))
                except Exception:
                    pass

                max_sci_packets = 12
                if len(sci_packets) > max_sci_packets:
                    del sci_packets[:-max_sci_packets]

                # Rebuild identity set from retained packets
                state["sci_packet_identities"] = {
                    (
                        getattr(p, "PACKET_NUMBER", None),
                        getattr(p, "SCI_PACKET_CRITICALITY", None),
                        int(getattr(p, "SCI_POINT_COUNT", 0) or 0),
                        (
                            getattr(p.SCI_POINTS[0], "ABS_STEPS", None)
                            if getattr(p, "SCI_POINTS", None)
                            else getattr(p, "ABS_STEPS", None)
                        ),
                        (
                            getattr(p.SCI_POINTS[-1], "ABS_STEPS", None)
                            if getattr(p, "SCI_POINTS", None)
                            else getattr(p, "ABS_STEPS", None)
                        ),
                    )
                    for p in sci_packets
                }

                if new_sci_packets > 0:
                    if "EB_SCI" in packet_viewer_controllers and sci_packets:
                        try:
                            latest_sci = sci_packets[-1]
                            packet_viewer_controllers["EB_SCI"].update_from_packet(latest_sci)

                            # Add to packet list if available
                            packet_list_controller = state.get("packet_list_controller")
                            if packet_list_controller is not None:
                                sci_data = (
                                    latest_sci.__dict__
                                    if hasattr(latest_sci, "__dict__")
                                    else (dict(latest_sci) if isinstance(latest_sci, dict) else {})
                                )
                                packet_num = getattr(latest_sci, "PACKET_NUMBER", "")
                                label = f"TM: Science (pkt {packet_num})" if packet_num else "TM: Science"
                                packet_list_controller.add_packet("EB_SCI", sci_data, label)
                        except Exception:
                            logger.debug("Failed to update SCI packet viewer")

        packet_metrics_card.refresh()

    return poll_tm


def disable_ob5v(logger: Any) -> None:
    try:
        interface = eb_interface.get_egse_interface()
        status = ebtcs.en_ob5v(interface, 0)
        if status == "ERROR":
            logger.warning("MMS pre-action: OB 5V disable command failed over EB link.")
            return
        logger.warning("MMS pre-action: OB 5V disable command sent over EB link.")
    except Exception as exc:
        logger.error(f"MMS pre-action failed while disabling OB 5V over EB link: {exc}")


async def mms(
    app: Any,
    state: dict[str, Any],
    logger: Any,
    hk: Any,
    reasons: list[str],
    tec_pre_action: bool,
    ob5v_pre_action: bool,
):
    mms_cfg = state.setdefault("mms", {})
    if mms_cfg.get("latched"):
        return
    if mms_cfg.get("in_progress"):
        return

    mms_cfg["in_progress"] = True

    def _run_mms_actions() -> None:
        mms_cfg = state.setdefault("mms", {})
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
            disable_ob5v(logger)
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

        # Latch MMS state first so trigger information is recorded even if shutdown fails.
        mms_cfg["latched"] = True
        mms_cfg["mode_at_trigger"] = state.get("mode")
        mms_cfg["triggered_at"] = datetime.now().isoformat(timespec="seconds")
        mms_cfg["reasons"] = reasons

        # Always attempt PSU emergency shutdown if PSU port is available, regardless of SAFE confirmation.
        if psu_port is not None:
            if not safe_confirmed:
                logger.warning("MMS action: SAFE state was not confirmed; proceeding with PSU shutdown anyway.")
            lock = state.get("port_lock")
            lock_ctx = lock if lock is not None else nullcontext()
            try:
                with lock_ctx:
                    psu.shutdown_psu_outputs(psu_port)
                logger.warning(
                    "MMS action: PSU emergency shutdown executed (all channels OFF). Reasons: %s",
                    "; ".join(reasons) if reasons else "none",
                )
            except Exception as exc:
                logger.error(f"MMS action failed during PSU emergency shutdown: {exc}")
        else:
            logger.warning("MMS action: PSU emergency shutdown skipped because PSU port is unavailable.")

    try:
        await run.io_bound(_run_mms_actions)
    except Exception as exc:
        mms_cfg["last_error"] = str(exc)
        raise
    finally:
        mms_cfg["in_progress"] = False


# endregion


# ---------------------------------------------------------------------------
# UI controllers — general
# ---------------------------------------------------------------------------
# region UI controllers — general


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
                    psu.setChannels(psu_port, ebmode, state.get("voltage_mode", "NOM"))
            # Run mode change resetters
            for reset in state.get("mode_change_resetters", []):
                reset()
        sync_packet_tabs = state.get("sync_packet_tabs")
        if callable(sync_packet_tabs):
            sync_packet_tabs(mode)

    return set_mode


def dispatch_ob_tc(state: dict[str, Any], command: Any, *args: Any, **kwargs: Any) -> Any:
    """Send an OB TC using the shared OB port lock when available."""
    ob_port = state.get("ob_port")
    if ob_port is None:
        ui.notify("OB port unavailable", color="negative")
        return

    lock = state.get("port_lock")
    lock_ctx = lock if lock is not None else nullcontext()
    with lock_ctx:
        return command(ob_port, *args, **kwargs)


def dispatch_eb_tc(state: dict[str, Any], command: Any, *args: Any, **kwargs: Any) -> Any:
    """Send an EB TC using the shared EB interface when available."""
    from utility_modules import eb_interface

    interface = state.get("eb_interface")
    if interface is None:
        interface = eb_interface.get_egse_interface()
        state["eb_interface"] = interface
    if interface is None:
        ui.notify("EB interface unavailable", color="negative")
        return

    return command(interface, *args, **kwargs)


# endregion


# ---------------------------------------------------------------------------
# UI controllers — SCI packet navigation
# ---------------------------------------------------------------------------
# region UI controllers — SCI packet navigation


def create_sci_navigation_state(max_packets: int = 12) -> dict[str, Any]:
    """Create backend-owned SCI navigation state for packet/point swiping."""
    return {
        "packets": [],
        "identities": set(),
        "packet_index": 0,
        "point_index": 0,
        "max_packets": max_packets,
    }


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


def sci_shift_packet_index(sci_state: dict[str, Any], delta: int) -> Any | None:
    current = int(sci_state.get("packet_index", 0))
    return sci_set_packet_index(sci_state, current + delta)


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


# endregion
