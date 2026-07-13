from __future__ import annotations

from typing import Any

from nicegui import ui

import widget_modules.ui_runtime_controller as ui_runtime_controller
from utility_modules import tc


def create_mechanism_tab(state: dict[str, Any]) -> None:
    """Build mechanism controls (legacy motor panel) for OB mode."""
    mtr_steps = ui.number(
        label="mech_steps",
        value=100,
        format="%d",
        min=1,
        max=10000,
        precision=0,
        step=10,
    ).classes("w-56")

    ui.button(
        "Move Pos",
        on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.mtr_mov_pos, int(mtr_steps.value or 0)),
    )
    ui.button(
        "Move Neg",
        on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.mtr_mov_neg, int(mtr_steps.value or 0)),
    )
    ui.button("HALT", on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.mtr_halt))

    home_cal = ui.checkbox("HOME_CAL")
    home_dir = ui.checkbox("HOME_DIR")

    ui.button(
        "Home",
        on_click=lambda: ui_runtime_controller.dispatch_ob_tc(
            state,
            tc.mtr_homing,
            bool(home_cal.value),
            bool(home_dir.value),
        ),
    )
