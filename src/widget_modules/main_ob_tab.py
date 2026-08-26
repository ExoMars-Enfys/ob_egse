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
            "Request HK",
            on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.hk_request),
        )
        cyclic_hk = state.get("cyclic_hk")
        cyclic_toggle = ui.switch("Cyclic HK", value=bool(cyclic_hk and cyclic_hk.enabled))
        cyclic_period = ui.number(
            "Period (s)",
            value=cyclic_hk.interval_s if cyclic_hk else 1.0,
            min=0.1,
            step=0.1,
            format="%.1f",
        ).classes("w-28")

        if cyclic_hk is None:
            cyclic_toggle.disable()
            cyclic_period.disable()
            cyclic_toggle.tooltip("OB port unavailable")
        else:
            def set_cyclic_enabled(event: Any) -> None:
                cyclic_hk.set_enabled(bool(event.value))

            def set_cyclic_period(event: Any) -> None:
                try:
                    cyclic_hk.set_interval(float(event.value))
                except (TypeError, ValueError):
                    cyclic_period.value = cyclic_hk.interval_s
                    cyclic_period.update()
                    ui.notify("Cyclic HK period must be at least 0.1 s", color="negative")

            cyclic_toggle.on_value_change(set_cyclic_enabled)
            cyclic_period.on_value_change(set_cyclic_period)
