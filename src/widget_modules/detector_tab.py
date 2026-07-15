from __future__ import annotations

from typing import Any

from nicegui import ui

import widget_modules.ui_runtime_controller as ui_runtime_controller
from utility_modules import tc


def create_detector_tab(state: dict[str, Any]) -> None:
    """Build detector controls (legacy detector panel) for OB mode."""
    ui.button("Request SCI", on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.sci_request, 8, 100))

    with ui.grid(columns=3).classes("w-full gap-2"):
        swir_dac_offset = ui.number(
            label="SWIR DAC",
            value=2048,
            format="%d",
            min=0,
            max=4095,
            precision=0,
            step=10,
        )
        mwir_dac_offset = ui.number(
            label="MWIR DAC",
            value=2048,
            format="%d",
            min=0,
            max=4095,
            precision=0,
            step=10,
        )
        ui.button(
            "Set SCI Offset",
            on_click=lambda: ui_runtime_controller.dispatch_ob_tc(
                state,
                tc.sci_offset,
                int(swir_dac_offset.value or 0),
                int(mwir_dac_offset.value or 0),
            ),
        )
