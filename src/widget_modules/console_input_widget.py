from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Callable

from nicegui import ui

from core_modules import cmd_ids
from utility_modules import tc
from utility_modules.send_cmd import cmd_repeat
from widget_modules import ui_runtime_controller


DEFAULT_COMMANDS = list(cmd_ids.cmd_ids.values())
COMMAND_TO_TC_FUNC = {
    "HK_Request": tc.hk_request,
    "Clear_Errors": tc.clear_errors,
    "Set_Errors": tc.set_errors,
    "Power_Control": tc.power_control,
    "Heater_Control": tc.heater_control,
    "Set_Mech_SP": tc.set_mech_sp,
    "Set_Detec_SP": tc.set_detec_sp,
    "Set_MTR_Param": tc.set_mtr_param,
    "MTR_Mov_Pos": tc.mtr_mov_pos,
    "MTR_Mov_Neg": tc.mtr_mov_neg,
    "MTR_Halt": tc.mtr_halt,
    "MTR_Homing": tc.mtr_homing,
    "Set_HK_Samples": tc.set_hk_samples,
    "SCI_Offset": tc.sci_offset,
    "SCI_Request": tc.sci_request,
}


@dataclass
class ConsoleInputController:
    command_selector: Any
    command_input: Any


def _parse_command_params(raw_text: str) -> list[Any]:
    text = str(raw_text or "").strip()
    if not text:
        return []

    values: list[Any] = []
    for token in [part.strip() for part in text.split(",") if part.strip()]:
        lower = token.lower()
        if lower in {"true", "false"}:
            values.append(lower == "true")
            continue
        try:
            values.append(int(token, 0))
            continue
        except ValueError:
            pass
        try:
            values.append(ast.literal_eval(token))
            continue
        except (ValueError, SyntaxError):
            values.append(token)
    return values


def create_console_input_widget(
    state: dict[str, Any],
    *,
    commands: list[str] | None = None,
    on_send: Callable[[str], None] | None = None,
) -> ConsoleInputController:
    """Create a simple command console with optional send callback.

    Args:
        state: Shared UI state dictionary.
        commands: Optional command list for selector choices.
        on_send: Optional callback invoked with command text when sent.
    """
    command_list = list(commands or state.get("console_commands") or DEFAULT_COMMANDS)
    logger = state.get("logger")

    def _add_command_id(e: Any) -> None:
        selected = getattr(e, "value", None)
        if selected:
            state["cmd"] = str(selected)
            command_input.value = ""

    async def _send_command() -> None:
        selected_command = str(command_selector.value or state.get("cmd") or "").strip()
        if not selected_command:
            if logger is not None:
                logger.error("Console send error: no command selected")
            return

        tc_func = COMMAND_TO_TC_FUNC.get(selected_command)
        if tc_func is None:
            if logger is not None:
                logger.error("Console send error: unsupported command %s", selected_command)
            return

        params = _parse_command_params(command_input.value or "")
        if logger is not None:
            logger.info("Console command: %s(%s)", selected_command, ", ".join(map(str, params)))

        if state.get("ob_port") is None:
            if logger is not None:
                logger.error("Console send error: OB port unavailable")
            return

        def _dispatch(port: Any) -> Any:
            return cmd_repeat(port, tc_func, *params)

        if callable(on_send):
            try:
                on_send(selected_command)
            except Exception as exc:
                if logger is not None:
                    logger.error("Console send callback error: %s", exc)
        try:
            result = ui_runtime_controller.dispatch_ob_tc(state, _dispatch)
            if logger is not None:
                if result == "ERROR":
                    logger.error("Console command response: ERROR")
                elif result is not None:
                    logger.info("Console command response: %s", type(result).__name__)
        except Exception as exc:
            if logger is not None:
                logger.error("Console send error: %s", exc)
        command_input.value = ""

    with ui.row().classes("w-full items-end"):
        command_selector = (
            ui.select(
                options=command_list,
                value=state.get("cmd", command_list[0] if command_list else None),
                label="Select command",
                on_change=_add_command_id,
            )
            .props("clearable")
            .classes("w-64")
        )

        command_input = ui.input(
            label="Command parameters",
            placeholder="Comma-separated params, e.g. 1, 2 or true, false",
        ).classes("grow")

        command_input.on("keydown.enter", lambda _e: _send_command())

        ui.button(
            "Send",
            icon="send",
            on_click=_send_command,
        )

    return ConsoleInputController(
        command_selector=command_selector,
        command_input=command_input,
    )
