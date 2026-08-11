from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from nicegui import app, ui

from core_modules import cmd_ids
from utility_modules import eb_interface, ebtcs, tc
from utility_modules.send_cmd import cmd_repeat
from widget_modules import ui_runtime_controller


OB_DEFAULT_COMMANDS = list(cmd_ids.cmd_ids.values())
OB_COMMAND_TO_TC_FUNC = {
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

EB_DEFAULT_COMMANDS = list(cmd_ids.enfys_tc_defs.keys())
EB_COMMAND_TO_TC_FUNC = {
    "RET": ebtcs.ret,
    "REQUEST_HK": ebtcs.hk_request,
    "PATCH": ebtcs.patch,
    "DUMP": ebtcs.dump,
    "SET_HK_RATE": ebtcs.set_hk_rate,
    "MONITOR_ADDR": ebtcs.monitor_addr,
    "ABORT": ebtcs.abort,
    "GENERIC_TC": ebtcs.generic_tc,
    "SAFE": ebtcs.safe,
    "STANDBY": ebtcs.standby,
    "ACQUISITION": ebtcs.acquisition,
    "SET_MOTOR_CONFIGS": ebtcs.set_motor_configs,
    "SET_HEATER_CONFIGS": ebtcs.set_heater_configs,
    "SET_ACQ_CONFIGS": ebtcs.set_acq_configs,
    "SET_TEC_SETPOINT": ebtcs.set_tec_setpoint,
    "SET_FDIR": ebtcs.set_fdir,
    "EN_MECH_BOARD": ebtcs.en_mech_board,
    "EN_DET_BOARD": ebtcs.en_det_board,
    "EN_MECH_HEATER": ebtcs.en_mech_heater,
    "EN_DET_HEATER": ebtcs.en_det_heater,
    "EN_OB5V": ebtcs.en_ob5v,
    "OB_PARK": ebtcs.ob_park,
    "OB_HOMING": ebtcs.ob_homing,
    "OB_HK": ebtcs.ob_hk,
    "CHECK_MEMORY": ebtcs.check_memory,
    "GOTO": ebtcs.goto,
    "COPY_MEMORY": ebtcs.copy_memory,
    "SWITCH_RS422": ebtcs.switch_rs422,
    "SET_TEC_CURRENT": ebtcs.set_tec_current,
}


@dataclass
class ConsoleInputController:
    command_selector: Any
    command_input: Any


_HEX_INTEGER_RE = re.compile(r"^[+-]?0[xX][0-9a-fA-F]+$")
_DECIMAL_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_DECIMAL_FLOAT_RE = re.compile(r"^[+-]?(?:(?:[0-9]+(?:\.[0-9]*)?)|(?:\.[0-9]+))(?:[eE][+-]?[0-9]+)?$")


def _parse_command_token(token: str) -> Any:
    """Parse one console parameter using explicit operator-friendly rules.

    * ``0x``/``0X`` prefixed values are hexadecimal integers.
    * Digit-only values are decimal integers, including leading-zero forms
      such as ``03``.
    * Decimal-point or scientific-notation values are floats.
    * Booleans and quoted/container literals retain the previous behaviour.
    """
    stripped = str(token).strip()
    lower = stripped.lower()

    if lower in {"true", "false"}:
        return lower == "true"

    if _HEX_INTEGER_RE.fullmatch(stripped):
        return int(stripped, 16)

    if _DECIMAL_INTEGER_RE.fullmatch(stripped):
        return int(stripped, 10)

    if _DECIMAL_FLOAT_RE.fullmatch(stripped) and ("." in stripped or "e" in lower):
        value = float(stripped)
        if math.isfinite(value):
            return value

    try:
        return ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return stripped


def _parse_command_params(raw_text: str) -> list[Any]:
    text = str(raw_text or "").strip()
    if not text:
        return []

    def _split_params(value: str) -> list[str]:
        parts: list[str] = []
        token: list[str] = []
        quote: str | None = None
        escape = False
        depth = 0

        for char in value:
            if escape:
                token.append(char)
                escape = False
                continue

            if quote is not None:
                token.append(char)
                if char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue

            if char in {'"', "'"}:
                quote = char
                token.append(char)
                continue

            if char in "([{":
                depth += 1
                token.append(char)
                continue

            if char in ")]}":
                depth = max(0, depth - 1)
                token.append(char)
                continue

            # Accept either commas or plain spaces as separators at top-level.
            if depth == 0 and (char == "," or char.isspace()):
                piece = "".join(token).strip()
                if piece:
                    parts.append(piece)
                token = []
                continue

            token.append(char)

        tail = "".join(token).strip()
        if tail:
            parts.append(tail)
        return parts

    return [_parse_command_token(part) for part in _split_params(text)]


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
    logger = state.get("logger")
    mode_cache = {"value": str(state.get("mode", "OB")).upper()}

    def _mode_to_backend(mode: str) -> str:
        return "EB" if str(mode).upper() == "EB" else "OB"

    def _commands_for_mode(mode: str) -> list[str]:
        if commands:
            return list(commands)
        if mode == "EB":
            return list(state.get("console_commands_eb") or EB_DEFAULT_COMMANDS)
        return list(state.get("console_commands") or OB_DEFAULT_COMMANDS)

    def _command_map_for_mode(mode: str) -> dict[str, Callable[..., Any]]:
        return EB_COMMAND_TO_TC_FUNC if mode == "EB" else OB_COMMAND_TO_TC_FUNC

    mode_key = _mode_to_backend(mode_cache["value"])
    command_list = _commands_for_mode(mode_key)
    mode_command_state = state.setdefault("console_selected_command_by_mode", {})

    def _add_command_id(e: Any) -> None:
        selected = getattr(e, "value", None)
        if selected:
            mode = _mode_to_backend(mode_cache["value"])
            mode_command_state[mode] = str(selected)
            state["cmd"] = str(selected)
            command_input.value = ""

    def _sync_for_mode(mode: str) -> None:
        backend_mode = _mode_to_backend(mode)
        mode_cache["value"] = backend_mode
        options = _commands_for_mode(backend_mode)
        previous = str(command_selector.value or "").strip()
        remembered = str(mode_command_state.get(backend_mode, "") or "").strip()

        selected = remembered or previous
        if selected not in options:
            selected = options[0] if options else None

        command_selector.options = options
        command_selector.value = selected
        if selected:
            mode_command_state[backend_mode] = str(selected)
            state["cmd"] = str(selected)
        command_input.value = ""
        command_selector.update()
        command_input.update()

    async def _send_command() -> None:
        mode = _mode_to_backend(mode_cache["value"])
        selected_command = str(command_selector.value or state.get("cmd") or "").strip()
        if not selected_command:
            if logger is not None:
                logger.error("Console send error: no command selected")
            return

        tc_func = _command_map_for_mode(mode).get(selected_command)
        if tc_func is None:
            if logger is not None:
                logger.error("Console send error: unsupported %s command %s", mode, selected_command)
            return

        params = _parse_command_params(command_input.value or "")
        if logger is not None:
            logger.info("Console command [%s]: %s(%s)", mode, selected_command, ", ".join(map(str, params)))

        if callable(on_send):
            try:
                on_send(selected_command)
            except Exception as exc:
                if logger is not None:
                    logger.error("Console send callback error: %s", exc)
        try:
            if mode == "EB":
                if not bool(getattr(getattr(app.state, "eb_interface", None), "egse_started", False)):
                    if logger is not None:
                        logger.warning("Console send warning: EB EGSE tools are not started")
                interface = eb_interface.get_egse_interface()
                result = tc_func(interface, *params)
            else:
                if state.get("ob_port") is None:
                    if logger is not None:
                        logger.error("Console send error: OB port unavailable")
                    return

                def _dispatch(port: Any) -> Any:
                    return cmd_repeat(port, tc_func, *params)

                result = ui_runtime_controller.dispatch_ob_tc(state, _dispatch)
                if result != "ERROR" and selected_command == "Clear_Errors":
                    ui_runtime_controller.reset_ob_fdir_simulator(state, logger)

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
                value=mode_command_state.get(mode_key, state.get("cmd", command_list[0] if command_list else None)),
                label="Select command",
                on_change=_add_command_id,
            )
            .props("clearable")
            .classes("w-64")
        )

        command_input = ui.input(
            label="Command parameters",
            placeholder="Space/comma separated: 03 0x03 true or 03,0x03,true",
        ).classes("grow")

        command_input.on("keydown.enter", lambda _e: _send_command())

        ui.button(
            "Send",
            icon="send",
            on_click=_send_command,
        )

    if isinstance(state.get("plot_refreshers"), list):
        state["plot_refreshers"].append(_sync_for_mode)
    _sync_for_mode(state.get("mode", mode_key))

    return ConsoleInputController(
        command_selector=command_selector,
        command_input=command_input,
    )
