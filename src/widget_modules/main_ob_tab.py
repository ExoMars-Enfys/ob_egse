from __future__ import annotations

from typing import Any

from nicegui import ui

from core_modules import cmd_ids
from utility_modules import tc
from widget_modules import ui_runtime_controller

tcs = list(cmd_ids.cmd_ids)


def _on_cmd_pick(state: dict[str, Any], e: Any) -> None:
    """Update selected OB command in shared UI state.

    If a callback is provided in state as ``on_main_ob_cmd_change``, invoke it
    with the selected command value.
    """
    cmd = e.value
    state["cmd"] = cmd
    callback = state.get("on_main_ob_cmd_change")
    if callable(callback):
        try:
            callback(cmd)
        except Exception:
            # Keep UI responsive if downstream callback fails.
            pass


def create_main_ob_tab(state: dict[str, Any]) -> None:
    """Build OB command picker controls for the Main OB tab."""
    with ui.row().classes("w-full items-center justify-start"):
        ui.button(
            "Move Pos",
            on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.hk_request),
        )
