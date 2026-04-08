from __future__ import annotations

from datetime import datetime
from typing import Any


def set_status_light(light: Any, ok: bool) -> None:
    if ok:
        light.classes(remove="alarm", add="ok")
    else:
        light.classes(remove="ok", add="alarm")


def any_flag(ns: Any) -> bool:
    if ns is None:
        return False
    return any(bool(v) for v in ns.__dict__.values())


def active_flag_names(flag_ns: Any, ordered_names: list[str]) -> list[str]:
    if flag_ns is None:
        return []
    return [
        name
        for name in ordered_names
        if not name.startswith("UNUSED") and not name.startswith("RESERVED") and getattr(flag_ns, name, 0)
    ]


def check_ob_fdir_alarm(hk: Any, tmstruct: Any) -> bool:
    if hk is None:
        return False

    warning_names = [name for name, _ in tmstruct.eb_warning_flags]
    fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]

    warning_bits = active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)
    fdir_alarm_bits = active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
    fdir_warning_bits = active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)

    ob_warning_flags = [
        "OB_FDIR_ALARM",
        "OB_GENERAL_ERROR",
        "OB_MOTOR_ERROR",
        "OB_UNRESPONSIVE",
        "OB_STEP_COUNT_MISMATCH",
    ]

    ob_fdir_flags = [
        "FPGA_IO_POWER_SUPPLY",
        "FPGA_CORE_POWER_SUPPLY",
        "DIGITAL_BOARD_TRP",
        "DETECTOR_BOARD_TRP",
        "MECH_BOARD_TRP",
        "MOTOR_TRP",
    ]

    if any(flag in warning_bits for flag in ob_warning_flags):
        return True

    if any(flag in fdir_alarm_bits for flag in ob_fdir_flags):
        return True
    if any(flag in fdir_warning_bits for flag in ob_fdir_flags):
        return True

    if any_flag(getattr(hk, "ERRORS", None)):
        return True
    if any_flag(getattr(hk, "MTR_ERRORS", None)):
        return True

    return False


def check_eb_fdir_alarm(hk: Any, tmstruct: Any) -> bool:
    if hk is None:
        return False

    if hasattr(hk, "TCS_REJECTED") and hk.TCS_REJECTED != 0:
        return True

    warning_names = [name for name, _ in tmstruct.eb_warning_flags]
    fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]

    warning_bits = active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)
    fdir_alarm_bits = active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
    fdir_warning_bits = active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)

    eb_warning_flags = [
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
    ]

    eb_fdir_flags = [
        "EB_PLUS_12V_SUPPLY",
        "EB_MINUS_12V_SUPPLY",
        "EB_PLUS_5V_SUPPLY",
        "EB_PLUS_3V3_SUPPLY",
        "PROCESSOR_INTERNAL_TEMPERATURE",
        "INTERNAL_TRP_TEMPERATURE",
        "PSU_BOARD_TEMPERATURE",
    ]

    if any(flag in warning_bits for flag in eb_warning_flags):
        return True

    if any(flag in fdir_alarm_bits for flag in eb_fdir_flags):
        return True
    if any(flag in fdir_warning_bits for flag in eb_fdir_flags):
        return True

    return False


def format_alarm_details(kind: str, hk: Any, tmstruct: Any) -> list[str]:
    if hk is None:
        return ["No HK data yet."]
    if kind == "ob":
        details = []

        error_names = [name for name, _ in tmstruct.error_struct]
        errors = active_flag_names(getattr(hk, "ERRORS", None), error_names)
        for error in errors:
            details.append(f"OB Error: {error}")

        mtr_error_names = [name for name, _ in tmstruct.mtr_error_struct]
        mtr_errors = active_flag_names(getattr(hk, "MTR_ERRORS", None), mtr_error_names)
        for error in mtr_errors:
            details.append(f"OB Motor Error: {error}")

        warning_names = [name for name, _ in tmstruct.eb_warning_flags]
        warning_bits = active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)
        ob_warning_flags = [
            "OB_FDIR_ALARM",
            "OB_GENERAL_ERROR",
            "OB_MOTOR_ERROR",
            "OB_UNRESPONSIVE",
            "OB_STEP_COUNT_MISMATCH",
        ]
        for flag in warning_bits:
            if flag in ob_warning_flags:
                details.append(f"OB Warning: {flag}")

        fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]
        ob_fdir_flags = [
            "FPGA_IO_POWER_SUPPLY",
            "FPGA_CORE_POWER_SUPPLY",
            "DIGITAL_BOARD_TRP",
            "DETECTOR_BOARD_TRP",
            "MECH_BOARD_TRP",
            "MOTOR_TRP",
        ]

        fdir_alarm_bits = active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
        for flag in fdir_alarm_bits:
            if flag in ob_fdir_flags:
                details.append(f"OB FDIR Alarm: {flag}")

        fdir_warning_bits = active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)
        for flag in fdir_warning_bits:
            if flag in ob_fdir_flags:
                details.append(f"OB FDIR Warning: {flag}")

        return details if details else ["No OB alarms"]

    if kind == "eb":
        details = []

        if hasattr(hk, "TCS_REJECTED") and hk.TCS_REJECTED != 0:
            details.append("TCS Rejected")

        warning_names = [name for name, _ in tmstruct.eb_warning_flags]
        warning_bits = active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)

        eb_warning_flags = [
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
        ]

        for flag in warning_bits:
            if flag in eb_warning_flags:
                details.append(f"EB Warning: {flag}")

        fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]
        fdir_alarm_bits = active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
        fdir_warning_bits = active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)

        eb_fdir_flags = [
            "EB_PLUS_12V_SUPPLY",
            "EB_MINUS_12V_SUPPLY",
            "EB_PLUS_5V_SUPPLY",
            "EB_PLUS_3V3_SUPPLY",
            "PROCESSOR_INTERNAL_TEMPERATURE",
            "INTERNAL_TRP_TEMPERATURE",
            "PSU_BOARD_TEMPERATURE",
        ]

        for flag in fdir_alarm_bits:
            if flag in eb_fdir_flags:
                details.append(f"EB FDIR Alarm: {flag}")

        for flag in fdir_warning_bits:
            if flag in eb_fdir_flags:
                details.append(f"EB FDIR Warning: {flag}")

        return details if details else ["No EB alarms"]

    return ["Unknown alarm type."]


def alarm_signature(kind: str, hk: Any, tmstruct: Any) -> str:
    return "|".join(format_alarm_details(kind, hk, tmstruct))


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def format_alarm_entry(entry: dict[str, object]) -> str:
    timestamp = entry.get("time")
    if isinstance(timestamp, datetime):
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    else:
        time_str = "Unknown time"
    details = entry.get("details", [])
    detail_text = "<br>".join(f"- {escape_html(str(detail))}" for detail in details if details) or "- No details"
    return f"<b>{time_str}</b><br>{detail_text}"
