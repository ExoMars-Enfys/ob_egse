from __future__ import annotations

# Std library
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any


# Added packages
from nicegui import app, ui, run

# Local modules
from core_modules import constants as const
from widget_modules import file_dialog_window_widget, ui_runtime_controller
from utility_modules.desktop_launcher import destroy_desktop_window
from utility_modules import eb_interface, ebtcs, app_theme
from scripts_modules import fft, EMC_Init, EMC_HE, EMC_HS, EMC_ReInit


@dataclass
class MenuController:
    button: Any
    card: Any
    _state: dict[str, bool]

    def open(self) -> None:
        self._state["open"] = True
        self.card.style(
            "transform: translateX(0); opacity: 1; pointer-events: auto;"
            "transition: transform .2s ease, opacity .2s ease;"
        )

    def close(self) -> None:
        self._state["open"] = False
        self.card.style(
            "transform: translateX(-120%); opacity: 0; pointer-events: none;"
            "transition: transform .2s ease, opacity .2s ease;"
        )

    def toggle(self, *_: Any) -> None:
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
    # Theme-aware sizes
    palette = getattr(app.state, "theme_palette", None)
    menu_label_size = app_theme.ui_font_size(palette.get("metric_label_size") if isinstance(palette, dict) else None)
    with ui.element("div").classes("relative inline-block"):
        menu_button = ui.button(icon="menu").props("flat dense round").classes("self-start rounded-full w-36 h-12")

        with ui.card().classes("absolute left-0 top-10 z-30 shadow-xl rounded-xl w-max max-w-none") as menu_card:
            with ui.column().classes("w-full gap-2 whitespace-nowrap"):
                # --- SAFE TC handler ---
                def send_safe_tc():
                    interface = eb_interface.get_egse_interface()
                    ebtcs.safe(interface, 0)
                    ui.notify("SAFE TC sent", type="positive")

                with ui.row().classes("items-center justify-start gap-2"):
                    lbl_ob = ui.label("OB")
                    lbl_ob.style(f"font-size: {menu_label_size}")
                    ui.switch(
                        value=(state["mode"] == "EB"),
                        on_change=lambda e: _call_set_mode(set_mode_fn, "EB" if e.value else "OB"),
                    )
                    lbl_eb = ui.label("EB")
                    lbl_eb.style(f"font-size: {menu_label_size}")

                    def _current_theme() -> str:
                        return getattr(app.state, "theme_state", {}).get("value", "dark")

                    def _theme_icon(theme: str) -> str:
                        # Show the icon for the target theme when pressed.
                        return "light_mode" if theme == "dark" else "brightness_2"

                    def _theme_icon_color(_theme: str) -> str:
                        # Keep icon color sourced from active theme tokens.
                        return "var(--text-color)"

                    theme_button = ui.button(icon=_theme_icon(_current_theme())).props("flat dense round")
                    theme_button.props("text-color=grey-7")
                    theme_button.style(f"color: {_theme_icon_color(_current_theme())};")

                    def _toggle_theme() -> None:
                        next_theme = "light" if _current_theme() == "dark" else "dark"
                        getattr(app.state, "set_theme", lambda _theme: None)(next_theme)
                        theme_button.props(f"icon={_theme_icon(next_theme)}")
                        theme_button.props("text-color=grey-7")
                        theme_button.style(f"color: {_theme_icon_color(next_theme)};")

                    theme_button.on_click(_toggle_theme)
                    lbl_real = ui.label("Real")
                    lbl_real.style(f"font-size: {menu_label_size}")
                    ui.switch(
                        value=(str(state.get("hk_display_mode", "REAL")).upper() == "ADU"),
                        on_change=lambda e: _set_hk_display_mode(state, "ADU" if e.value else "REAL"),
                    )
                    lbl_adu = ui.label("ADU")
                    lbl_adu.style(f"font-size: {menu_label_size}")
                model_options = const.MODELS
                model_labels = list(model_options)
                model_keys = {label: label for label in model_options}

                def on_model_change(e):
                    state["model"] = e.value
                    app.state.current_model = e.value
                
                def _on_mms_toggle(e: Any) -> None:
                    enabled = bool(e.value)
                    mms_cfg = state.setdefault("mms", {})
                    mms_cfg["enabled"] = enabled
                    ui.notify(f"MMS {'enabled' if enabled else 'disabled'}", type="warning" if enabled else "info")

                with ui.row().classes("items-center justify-start gap-2 w-full"):
                    lbl_mms = ui.label("MMS")
                    lbl_mms.style(f"font-size: {menu_label_size}")
                    ui.switch(
                        value=bool(state.get("mms", {}).get("enabled", True)),
                        on_change=_on_mms_toggle,
                    )
                    lbl_mms_state = ui.label("Enabled" if state.get("mms", {}).get("enabled", True) else "Disabled")
                    lbl_mms_state.style(f"font-size: {menu_label_size}")

                with ui.row().classes("items-center gap-2 w-full"):
                    selected_model = ui.select(
                        model_labels,
                        value=state.get("model", model_labels[0]),
                        label="Select Model",
                        on_change=on_model_change,
                    ).classes("flex-1")
                    ui.select(
                        options=["MIN", "NOM", "MAX"],
                        value=state.get("voltage_mode", "NOM"),
                        label="Bus V",
                        on_change=lambda e: _on_voltage_mode_change(e, state),
                    ).classes("w-24")
                # Initialize state and app.state with default model if not set
                if "model" not in state:
                    state["model"] = model_labels[0]
                if not hasattr(app.state, "current_model"):
                    app.state.current_model = state["model"]

                # --- Unified two-column button layout ---
                with ui.row().classes("gap-2 w-full no-wrap"):
                    with ui.column().classes("gap-2 w-full"):
                        ui.button(
                            "Start",
                            on_click=lambda: _start_egse_tools(state, None),
                        ).classes("w-full whitespace-nowrap rounded-full")
                        ui.button(
                            "Log",
                            on_click=lambda: (
                                state.__setitem__(
                                    "log_search", {"enabled": app.state.eb_interface.select_rs422_log(state["logger"])}
                                ),
                            ),
                        ).classes("w-full whitespace-nowrap rounded-full")
                        ui.button(
                            "TXT Script",
                            on_click=lambda: _run_txt_script(state),
                        ).classes("w-full whitespace-nowrap rounded-full")
                    with ui.column().classes("gap-2 w-full"):
                        ui.button(
                            "Stop",
                            on_click=lambda: _stop_egse_tools(state, None),
                        ).classes("w-full whitespace-nowrap rounded-full")
                        ui.button(
                            "PSU Log",
                            on_click=lambda: _select_psu_log(
                                state,
                                set_psu_log_path_fn=set_psu_log_path_fn,
                                get_psu_sample_count_fn=get_psu_sample_count_fn,
                            ),
                        ).classes("w-full whitespace-nowrap rounded-full")
                        ui.button(
                            "Send SAFE TC",
                            on_click=send_safe_tc,
                        ).classes("w-full whitespace-nowrap rounded-full")

                # --- Script selection and controls ---
                script_options = [
                    ("FFT", "fft"),
                    ("EMC_Init", "emc_init"),
                    ("EMC_HE", "emc_he"),
                    ("EMC_HS", "emc_hs"),
                    ("EMC_ReInit", "emc_reinit"),
                ]
                script_labels = [label for label, _ in script_options]
                script_keys = {label: key for label, key in script_options}
                selected_script = ui.select(
                    script_labels,
                    value=script_labels[0],
                    label="Select Script",
                ).classes("w-full")

                def get_selected_key():
                    val = selected_script.value
                    if val in script_keys:
                        return script_keys[val]
                    return script_keys[script_labels[0]]

                with ui.row().classes("w-full justify-end gap-2") as script_buttons_row:

                    def _pause_click(e: Any = None) -> None:
                        _pause_selected_script(state, get_selected_key())

                    def _stop_click(e: Any = None) -> None:
                        _abort_selected_script(state, get_selected_key())

                    ui.button(
                        icon="play_arrow",
                        on_click=lambda: (_run_selected_script(state, get_selected_key(), script_buttons_row)),
                    ).props("flat round dense").classes("rounded-full w-20 h-12")
                    ui.button(icon="pause", on_click=_pause_click).props("flat round dense").classes(
                        "rounded-full w-20 h-12"
                    )
                    ui.button(icon="stop", on_click=_stop_click).props("flat round dense").classes(
                        "rounded-full w-20 h-12"
                    )

                ui.keyboard(on_key=lambda e: _handle_script_hotkeys(state, get_selected_key(), e))

                # (Removed duplicate Run Text Script button)

                ui.button("Log Snapshot", on_click=lambda: _log_snapshot(state)).classes(
                    "w-full whitespace-nowrap rounded-full w-36 h-12"
                )
                ui.button(
                    "Shutdown", color="negative", on_click=lambda: stop_and_shutdown(state, state["stop_event"])
                ).classes("w-full whitespace-nowrap rounded-full w-36 h-12")

    def _sync_egse_tools_buttons(mode: str) -> None:
        eb_mode = mode == "EB"
        bool(state.get("egse_tools_started", False))
        bool(getattr(app.state.eb_interface, "rs422_log_path", None))
        if eb_mode:
            # Dynamic show/hide logic removed (undefined variables)
            pass

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


def _on_voltage_mode_change(e: Any, state: dict[str, Any]) -> None:
    """Handle voltage mode change and apply to PSU."""
    from contextlib import nullcontext
    from utility_modules import psu

    new_mode = e.value
    state["voltage_mode"] = new_mode

    port = state.get("psu_port")
    psu_lock = state.get("psu_lock")
    if not port:
        return

    lock_ctx = psu_lock if psu_lock is not None else nullcontext()
    with lock_ctx:
        psu.apply_voltage_mode(port, new_mode, state.get("mode", "OB"))


def _set_hk_display_mode(state: dict[str, Any], mode: str) -> None:
    mode_upper = str(mode or "REAL").upper()
    if mode_upper not in {"ADU", "REAL"}:
        mode_upper = "REAL"

    state["hk_display_mode"] = mode_upper
    app.state.hk_display_mode = mode_upper

    for controller in (state.get("packet_viewer_controllers") or {}).values():
        try:
            controller.refresh()
        except Exception:
            continue

    for key in ("eb_metrics_card", "ob_metrics_card"):
        controller = state.get(key)
        if controller is None:
            continue
        packet = getattr(controller, "last_packet", None)
        if packet is not None:
            try:
                controller.update_from_packet(packet)
            except Exception:
                continue

    # Reset plot traces to avoid mixing REAL and ADU y-values in the same history window.
    for key in ("trp_card", "voltage_card"):
        plot_controller = state.get(key)
        if plot_controller is None:
            continue
        try:
            plot_controller.set_stream_enabled(False)
            plot_controller.set_stream_enabled(True)
        except Exception:
            continue


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


async def _run_selected_script(state: dict[str, Any], script_key: str, buttons_row: Any = None) -> None:
    """Run the selected EB script from the menu."""
    key = (script_key or "").strip().lower()

    if key == "txt_script":
        _run_txt_script(state, buttons_row)
        return

    supported_scripts = {
        "fft": "fft",
        "emc_init": "emc_init",
        "emc_he": "emc_he",
        "emc_hs": "emc_hs",
        "emc_reinit": "emc_reinit",
    }
    if key not in supported_scripts:
        ui.notify("Unsupported script selected", color="negative")
        return

    script_control = ui_runtime_controller.get_script_control()
    if bool(script_control.get("running")):
        ui.notify("A script is already running", color="warning")
        return

    ui_runtime_controller.start_script(script_name=key)

    def _runner() -> None:
        try:
            state["logger"].info(f"Starting {key} script from menu")
            ebtcs.configure_send_flow_control(
                should_pause=lambda: ui_runtime_controller.is_paused() or ui_runtime_controller.is_force_paused(),
                should_abort=lambda: ui_runtime_controller.is_aborted(),
            )

            # Call the correct function for each script directly
            if key == "fft":
                fft.run_fft()
            elif key == "emc_init":
                EMC_Init.run_emc_init()
            elif key == "emc_he":
                EMC_HE.run_emc_he()
            elif key == "emc_hs":
                EMC_HS.run_emc_hs()
            elif key == "emc_reinit":
                EMC_ReInit.run_emc_reinit()
            else:
                ui.notify("Script not implemented", color="negative")
                return

            if ui_runtime_controller.is_aborted():
                state["logger"].warning(f"{key} script aborted")
            else:
                state["logger"].info(f"{key} script completed")
        except Exception as exc:
            state["logger"].error("%s script failed: %s", key, exc)
        finally:
            try:
                ebtcs.clear_send_flow_control()
            except Exception:
                pass
            ui_runtime_controller.finish_script()
            # ensure UI-visible pause state cleared
            ui_runtime_controller.clear_pause()

    ui.notify(f"{key} script started")
    await run.io_bound(_runner)


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

    # Allow pause for all scripts

    # log entry for debugging which callback was invoked
    try:
        logger = state.get("logger")
        if logger:
            logger.info("_pause_selected_script invoked for key=%s", script_key)
    except Exception:
        pass

    if not ui_runtime_controller.is_script_running():
        ui.notify("No running script", color="warning")
        return

    # If a UI-forced pause is active, clear that first (resume)
    if ui_runtime_controller.is_force_paused():
        ui_runtime_controller.clear_force_pause()
        ui.notify("Script resumed")
        return

    # Toggle runtime pause event
    if ui_runtime_controller.is_paused():
        ui_runtime_controller.clear_pause()
        ui.notify("Script resumed")
    else:
        ui_runtime_controller.request_pause()
        ui.notify("Script paused")


def _abort_selected_script(state: dict[str, Any], script_key: str) -> None:
    """Abort a running script."""

    # Allow abort for all scripts

    if not ui_runtime_controller.is_script_running():
        ui.notify("No running script", color="warning")
        return

    ui_runtime_controller.request_abort()
    ui_runtime_controller.clear_pause()
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
    from contextlib import nullcontext
    from utility_modules import psu

    # Reuse the same method as the Stop EB EGSE Tools button
    _stop_egse_tools(state, sync_visibility_fn=None)

    psu_port = state.get("psu_port")
    if psu_port is not None:
        lock = state.get("psu_lock")
        lock_ctx = lock if lock is not None else nullcontext()
        with lock_ctx:
            psu.emergencyShutDown(psu_port)

    if stop_event is not None:
        stop_event.set()

    def _close_and_open_logs() -> None:
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(const.LOG_PATH))
        except Exception as exc:
            state["logger"].warning("Could not open session log folder: %s", exc)
        ui.run_javascript(
            "window.open('', '_self');window.close();if (!window.closed) { window.location.href = 'about:blank'; }"
        )
        # Shut down NiceGUI server first, then destroy the pywebview window.
        # destroy_desktop_window() dispatches on a daemon thread so it doesn't
        # block the event loop; the short delay lets app.shutdown() run first.
        app.shutdown()
        ui.timer(0.25, destroy_desktop_window, once=True)

    with ui.dialog() as shutdown_dialog, ui.card().classes("w-96"):
        ui.label("EGSE tools shut down.").classes("text-base")
        ui.label("Close the window to open the session log folder.").classes("text-sm")
        with ui.row().classes("justify-end w-full"):
            ui.button("Close the window", color="negative", on_click=_close_and_open_logs)

    shutdown_dialog.open()
