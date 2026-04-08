from __future__ import annotations

from typing import Any


def format_flag_snapshot(flag_ns: Any, keys: list[str] | None) -> str:
    if flag_ns is None:
        return "No data"
    if keys is None:
        keys = list(flag_ns.__dict__.keys())
    items = [f"{key}: {getattr(flag_ns, key)}" for key in keys if hasattr(flag_ns, key)]
    return "\n".join(items) if items else "No flags"


def get_flag_dialog_text(hk: Any, attr_name: str, tmstruct: Any) -> str:
    if hk is None:
        return "No HK data yet."

    order_map = {
        "ERROR_FLAGS_BITS": [name for name, _ in tmstruct.eb_warning_flags],
        "WARNING_FLAGS_BITS": [name for name, _ in tmstruct.eb_warning_flags],
        "FDIR_ALARM_FLAGS_BITS": [name for name, _ in tmstruct.eb_fdir_flags],
        "FDIR_WARNING_FLAGS_BITS": [name for name, _ in tmstruct.eb_fdir_flags],
    }
    return format_flag_snapshot(getattr(hk, attr_name, None), order_map.get(attr_name))
