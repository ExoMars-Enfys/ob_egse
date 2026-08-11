from __future__ import annotations

from typing import Any

from nicegui import ui

import widget_modules.ui_runtime_controller as ui_runtime_controller
from utility_modules import tc


def create_mechanism_tab(state: dict[str, Any]) -> None:
    """Build mechanism controls (legacy motor panel) for OB mode."""
    with ui.card().classes("w-full p-3 gap-2"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Motion").classes("font-bold")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Request HK",
                    on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.hk_request),
                )
                mtr_steps = ui.number(
                    label="mech_steps",
                    value=100,
                    format="%d",
                    min=1,
                    max=10000,
                    precision=0,
                    step=10,
                ).classes("w-40")
                ui.button(
                    "Move Pos",
                    on_click=lambda: ui_runtime_controller.dispatch_ob_tc(
                        state, tc.mtr_mov_pos, int(mtr_steps.value or 0)
                    ),
                )
                ui.button(
                    "Move Neg",
                    on_click=lambda: ui_runtime_controller.dispatch_ob_tc(
                        state, tc.mtr_mov_neg, int(mtr_steps.value or 0)
                    ),
                )
                ui.button("HALT", on_click=lambda: ui_runtime_controller.dispatch_ob_tc(state, tc.mtr_halt))

    with ui.card().classes("w-full p-3 gap-3"):
        ui.label("Motor Parameters").classes("font-bold")
        with ui.row().classes("w-full items-end gap-2"):
            current_input = ui.number(
                label="Current",
                value=0x40,
                format="%d",
                min=0,
                max=0x7F,
                precision=0,
                step=1,
            ).classes("w-28")
            guard_input = ui.number(
                label="Guard",
                value=0x00,
                format="%d",
                min=0,
                max=0xFF,
                precision=0,
                step=1,
            ).classes("w-28")
            chopper_input = ui.number(
                label="Chopper",
                value=0x3C,
                format="%d",
                min=0,
                max=0xFF,
                precision=0,
                step=1,
            ).classes("w-28")
            speed_input = ui.number(
                label="Speed",
                value=0x08,
                format="%d",
                min=0,
                max=0x0F,
                precision=0,
                step=1,
            ).classes("w-28")

        def send_motor_params() -> None:
            ui_runtime_controller.dispatch_ob_tc(
                state,
                tc.set_mtr_param,
                int(current_input.value or 0x40),
                int(guard_input.value or 0x00),
                int(chopper_input.value or 0x3C),
                int(speed_input.value or 0x08),
            )

        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Send the values above as one motor-parameter command.").classes("text-sm text-gray-500")
            ui.button("Set Parameters", on_click=send_motor_params)

    with ui.card().classes("w-full p-3 gap-2"):
        ui.label("Homing").classes("font-bold")
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
