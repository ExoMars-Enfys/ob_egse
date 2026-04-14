from __future__ import annotations

# Std library
from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Any

# Added packages
from nicegui import app, ui

# Local modules
# widgets
from widget_modules import file_dialog_window_widget
from utility_modules import eb_interface


@dataclass
class MenuController:
    button: Any
    card: Any
    _state: dict[str, bool]

    def open(self) -> None:
        """Opens the menu by setting the state and applying styles to show the card."""
        self._state["open"] = True
        self.card.style(
            "transform: translateX(0); opacity: 1; pointer-events: auto;"
            "transition: transform .2s ease, opacity .2s ease;"
        )

    def close(self) -> None:
        """Closes the menu by setting the state and applying styles to hide the card."""
        self._state["open"] = False
        self.card.style(
            "transform: translateX(-120%); opacity: 0; pointer-events: none;"
            "transition: transform .2s ease, opacity .2s ease;"
        )

    def toggle(self, *_: Any) -> None:
        """Toggles the menu open or closed based on the current state."""
        if self._state["open"]:
            self.close()
        else:
            self.open()


def create_menu(
    state: dict[str, Any],
    *,
    set_mode_fn: Any | None = None,
    set_psu_log_path_fn: Any | None = None,
    get_psu_sample_count_fn: Any | None = None,
) -> MenuController:
    """Creates the menu for the application. The menu contains buttons to start/stop EB EGSE tools, select a log file, and take a log snapshot."""
    menu_state = {"open": False}
    state.setdefault("egse_tools_started", bool(getattr(app.state.eb_interface, "egse_started", False)))
    with ui.element("div").classes("relative inline-block"):
        menu_button = ui.button(icon="menu").props("flat dense round").classes("self-start")

        with ui.card().classes("absolute left-0 top-10 z-30 shadow-xl rounded-xl w-max max-w-none") as menu_card:
            with ui.column().classes("gap-2 whitespace-nowrap"):
                with ui.row().classes("items-center justify-start gap-2"):
                    ui.label("OB").classes("text-xs")
                    ui.switch(
                        value=(state["mode"] == "EB"),
                        on_change=lambda e: _call_set_mode(set_mode_fn, "EB" if e.value else "OB"),
                    )
                    ui.label("EB").classes("text-xs")
                    ui.space()
                    ui.label("Light").classes("text-xs")
                    ui.switch(
                        value=(getattr(app.state, "theme_state", {}).get("value", "light") == "dark"),
                        on_change=lambda e: getattr(app.state, "set_theme", lambda _theme: None)(
                            "dark" if e.value else "light"
                        ),
                    )
                    ui.label("Dark").classes("text-xs")
                start_tools_btn = ui.button(
                    "Start EB EGSE Tools",
                    on_click=lambda: _start_egse_tools(state, _sync_egse_tools_buttons),
                ).classes("w-full whitespace-nowrap")
                stop_tools_btn = ui.button(
                    "Stop EB EGSE Tools",
                    on_click=lambda: _stop_egse_tools(state, _sync_egse_tools_buttons),
                ).classes("w-full whitespace-nowrap")
                def _select_log_and_sync() -> None:
                    state["log_search"]["enabled"] = app.state.eb_interface.select_rs422_log(state["logger"])
                    _sync_egse_tools_buttons(state.get("mode", "EB"))

                ui.button(
                    "Select Log",
                    on_click=_select_log_and_sync,
                ).classes("w-full whitespace-nowrap")
                ui.button(
                    "Select PSU Log",
                    on_click=lambda: _select_psu_log(
                        state,
                        set_psu_log_path_fn=set_psu_log_path_fn,
                        get_psu_sample_count_fn=get_psu_sample_count_fn,
                    ),
                ).classes("w-full whitespace-nowrap")

                with ui.column().classes("w-full gap-1") as scripts_controls:
                    ui.label("Scripts").classes("text-xs")
                    script_select = ui.select(
                        options={"fft": "FFT", "txt_script": "Text Script (.txt)"},
                        value="fft",
                    ).classes("w-full")
                    with ui.row().classes("w-full justify-end gap-2") as script_buttons_row:
                        ui.button(
                            icon="play_arrow",
                            on_click=lambda: _run_selected_script(state, str(script_select.value or ""), script_buttons_row),
                        ).props("flat round dense")
                        ui.button(
                            icon="pause", on_click=lambda: _pause_selected_script(state, str(script_select.value or ""))
                        ).props("flat round dense")
                        ui.button(
                            icon="stop", on_click=lambda: _abort_selected_script(state, str(script_select.value or ""))
                        ).props("flat round dense")
                    ui.keyboard(on_key=lambda e: _handle_script_hotkeys(state, str(script_select.value or ""), e))

                ui.button("Log Snapshot", on_click=lambda: _log_snapshot(state)).classes("w-full whitespace-nowrap")
                ui.button("Stop", color="negative", on_click=lambda: stop_and_shutdown(state, state["stop_event"])).classes(
                    "w-full whitespace-nowrap"
                )

    def _sync_egse_tools_buttons(mode: str) -> None:
        eb_mode = mode == "EB"
        tools_started = bool(state.get("egse_tools_started", False))
        log_selected = bool(getattr(app.state.eb_interface, "rs422_log_path", None))
        if eb_mode:
            start_tools_btn.classes(remove="hidden")
            stop_tools_btn.classes(remove="hidden")
            if tools_started and log_selected:
                scripts_controls.classes(remove="hidden")
            else:
                scripts_controls.classes(add="hidden")
        else:
            start_tools_btn.classes(add="hidden")
            stop_tools_btn.classes(add="hidden")
            scripts_controls.classes(add="hidden")

    if isinstance(state.get("plot_refreshers"), list):
        state["plot_refreshers"].append(_sync_egse_tools_buttons)
    _sync_egse_tools_buttons(state.get("mode", "EB"))

    controller = MenuController(button=menu_button, card=menu_card, _state=menu_state)
    controller.close()
    menu_button.on_click(controller.toggle)
    return controller


def _call_set_mode(set_mode_fn: Any | None, mode: str) -> None:
    handler = set_mode_fn if callable(set_mode_fn) else getattr(app.state, "set_egse_mode", None)
    if callable(handler):
        handler(mode)


def _log_psu_snapshot(state: dict[str, Any]) -> None:
    """Logs the current PSU readings to the info log."""
    logger = state["logger"]
    readings = state["last_psu_readings"]
    status_value = readings["status"]
    if status_value is None:
        logger.info("PSU status: no PSU readings available yet")
        return
    logger.info(
        "PSU status: STATUS=%s | ROV_HTR: V=%.2f, I=%.1f mA | EB: V=%.2f, I=%.1f mA",
        status_value,
        float(readings["PSU_ROV_HTR_V"]) if readings["PSU_ROV_HTR_V"] is not None else float("nan"),
        (float(readings["PSU_ROV_HTR_I"]) * 1000) if readings["PSU_ROV_HTR_I"] is not None else float("nan"),
        float(readings["PSU_EB_V"]) if readings["PSU_EB_V"] is not None else float("nan"),
        (float(readings["PSU_EB_I"]) * 1000) if readings["PSU_EB_I"] is not None else float("nan"),
    )


def _log_snapshot(state: dict[str, Any]) -> None:
    """Takes a snapshot of the current logs and PSU readings, and logs them to the info log."""
    state["logger"].info('Log Snapshot at "%s"', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    _log_psu_snapshot(state)


def _select_psu_log(
    state: dict[str, Any],
    *,
    set_psu_log_path_fn: Any | None = None,
    get_psu_sample_count_fn: Any | None = None,
) -> None:
    """Open a PSU log picker and register selected replay file in app state."""
    logger = state["logger"]
    try:
        file_path = file_dialog_window_widget.select_file_dialog(
            title="Select PSU Log",
            filetypes=[("PSU Log Files", "*_PSU.log"), ("Log Files", "*.log"), ("All Files", "*.*")],
        )
    except Exception as exc:
        logger.error("Error while selecting PSU log file: %s", exc)
        ui.notify("Failed to open PSU log picker", color="negative")
        return

    if not file_path:
        return

    set_psu_log_path = (
        set_psu_log_path_fn if callable(set_psu_log_path_fn) else getattr(app.state, "set_psu_log_path", None)
    )
    if not callable(set_psu_log_path):
        ui.notify("PSU log setter not available", color="negative")
        return

    try:
        if set_psu_log_path(file_path):
            sample_count = 0
            get_sample_count = (
                get_psu_sample_count_fn
                if callable(get_psu_sample_count_fn)
                else getattr(app.state, "get_psu_replay_sample_count", None)
            )
            if callable(get_sample_count):
                try:
                    raw_count = get_sample_count()
                    if isinstance(raw_count, (int, float, str)):
                        sample_count = int(raw_count)
                except Exception:
                    sample_count = 0
            message = f"PSU log selected ({sample_count} samples)" if sample_count > 0 else "PSU log selected"
            ui.notify(message)
        else:
            ui.notify("No valid PSU samples found in selected log", color="negative")
    except Exception as exc:
        logger.error("Error while loading PSU replay log '%s': %s", file_path, exc)
        ui.notify("Failed to load PSU log", color="negative")


def _run_txt_script(state: dict[str, Any], buttons_row: Any = None) -> None:
    """Pick a .txt script file and typecast it to CmdTool."""
    file_path = file_dialog_window_widget.select_file_dialog(
        title="Select Text Script",
        filetypes=[("Text Scripts", "*.txt"), ("All Files", "*.*")],
    )
    if not file_path:
        return

    try:
        interface = eb_interface.get_egse_interface()
        state["logger"].info("Typecasting text script: %s", file_path)
        ok = interface.typecast(file_path, verbose=True)
        if ok:
            state["logger"].info("Text script completed: %s", file_path)
            ui.notify("Text script sent to CmdTool")
        else:
            state["logger"].warning("Text script failed: %s", file_path)
            ui.notify("Text script failed", color="negative")
    except Exception as exc:
        state["logger"].error("Text script error: %s", exc)
        ui.notify("Text script error", color="negative")

    if buttons_row is not None:
        buttons_row.classes(add="hidden")


def _run_selected_script(state: dict[str, Any], script_key: str, buttons_row: Any = None) -> None:
    """Run the selected EB script from the menu."""
    key = (script_key or "").strip().lower()

    if key == "txt_script":
        _run_txt_script(state, buttons_row)
        return

    if key != "fft":
        ui.notify("Unsupported script selected", color="negative")
        return

    script_control = state.setdefault(
        "script_control",
        {
            "running": False,
            "pause_event": threading.Event(),
            "abort_event": threading.Event(),
        },
    )
    if bool(script_control.get("running")):
        ui.notify("A script is already running", color="warning")
        return

    script_control["running"] = True
    script_control["pause_event"].clear()
    script_control["abort_event"].clear()

    def _runner() -> None:
        try:
            from scripts_modules import fft as fft_script
            from utility_modules import ebtcs
            from widget_modules import ui_runtime_controller

            state["logger"].info("Starting FFT script from menu")
            ebtcs.configure_send_flow_control(
                should_pause=lambda: bool(script_control["pause_event"].is_set()) or ui_runtime_controller.is_force_paused(),
                should_abort=lambda: bool(script_control["abort_event"].is_set()),
            )
            fft_script.run_fft()
            if bool(script_control["abort_event"].is_set()):
                state["logger"].warning("FFT script aborted")
            else:
                state["logger"].info("FFT script completed")
        except Exception as exc:
            state["logger"].error("FFT script failed: %s", exc)
        finally:
            try:
                from utility_modules import ebtcs

                ebtcs.clear_send_flow_control()
            except Exception:
                pass
            script_control["running"] = False
            script_control["pause_event"].clear()

    threading.Thread(target=_runner, daemon=True).start()
    ui.notify("FFT script started")


def _start_egse_tools(state: dict[str, Any], sync_visibility_fn: Any) -> None:
    """Start EB EGSE tools and expose script controls only on successful startup."""
    app.state.eb_interface.start_egse_tools(state["logger"])
    started = bool(getattr(app.state.eb_interface, "egse_started", False))
    state["egse_tools_started"] = started
    state["log_search"]["enabled"] = started
    if callable(sync_visibility_fn):
        sync_visibility_fn(state.get("mode", "EB"))


def _stop_egse_tools(state: dict[str, Any], sync_visibility_fn: Any) -> None:
    """Stop EB EGSE tools and hide script controls."""
    app.state.eb_interface.stop_egse_tools(state["logger"])
    state["egse_tools_started"] = False
    state["log_search"]["enabled"] = False
    if callable(sync_visibility_fn):
        sync_visibility_fn(state.get("mode", "EB"))


def _pause_selected_script(state: dict[str, Any], script_key: str) -> None:
    """Toggle pause/resume for a running script."""
    key = (script_key or "").strip().lower()
    if key != "fft":
        ui.notify("Unsupported script selected", color="negative")
        return

    script_control = state.setdefault(
        "script_control",
        {
            "running": False,
            "pause_event": threading.Event(),
            "abort_event": threading.Event(),
        },
    )
    if not bool(script_control.get("running")):
        ui.notify("No running script", color="warning")
        return

    try:
        from widget_modules import ui_runtime_controller

        if ui_runtime_controller.is_force_paused():
            ui_runtime_controller.clear_force_pause()
            ui.notify("Script resumed")
            return
    except Exception:
        pass

    pause_event = script_control["pause_event"]
    if pause_event.is_set():
        pause_event.clear()
        ui.notify("Script resumed")
    else:
        pause_event.set()
        ui.notify("Script paused")


def _abort_selected_script(state: dict[str, Any], script_key: str) -> None:
    """Abort a running script."""
    key = (script_key or "").strip().lower()
    if key != "fft":
        ui.notify("Unsupported script selected", color="negative")
        return

    script_control = state.setdefault(
        "script_control",
        {
            "running": False,
            "pause_event": threading.Event(),
            "abort_event": threading.Event(),
        },
    )
    if not bool(script_control.get("running")):
        ui.notify("No running script", color="warning")
        return

    script_control["abort_event"].set()
    script_control["pause_event"].clear()
    ui.notify("Script abort requested", color="warning")


def _handle_script_hotkeys(state: dict[str, Any], script_key: str, event: Any) -> None:
    """Map keyboard shortcuts to existing script pause/abort actions."""
    action = str(getattr(event, "action", "") or "").lower()
    if action and action != "keydown":
        return

    key = str(getattr(event, "key", "") or "").lower()
    if key in {" ", "space", "spacebar"}:
        _pause_selected_script(state, script_key)
    elif key in {"escape", "esc"}:
        _abort_selected_script(state, script_key)


def stop_and_shutdown(state: dict[str, Any], stop_event: Any) -> None:
    """Stops any running processes and shuts down the application."""
    # Reuse the same method as the Stop EB EGSE Tools button
    _stop_egse_tools(state, sync_visibility_fn=None)
    if stop_event is not None:
        stop_event.set()
    app.shutdown()
