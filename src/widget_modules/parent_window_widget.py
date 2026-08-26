from __future__ import annotations

# Std library
import logging
from pathlib import Path
from typing import Any

# Added packages
from nicegui import app, ui

import widget_modules.ui_runtime_controller as ui_runtime_controller

# Local modules
# core
from core_modules import constants as const

# utilities
from utility_modules import (
    app_theme,
    eb_interface,
)
from utility_modules.cyclic_hk import CyclicHKController
from utility_modules import tc

# widgets
from widget_modules import (
    console_input_widget,
    detector_tab,
    log_terminal_widget,
    main_ob_tab,
    mechanism_tab,
    menu_widget,
    metrics_card_widget,
    monitoring_limits,
    packet_list_widget,
    packet_viewer_widget,
    plot_widget,
    psu_widget,
    traffic_light_widget,
)

logger = logging.getLogger("info_log")

_RSRC_DIR = Path(__file__).resolve().parent.parent.parent / "rsrc"
_CSS_PATH = _RSRC_DIR / "guimasterconfig.css"


def build_ui(
    *,
    default_mode: str = const.DEFAULT_STARTUP_MODE,
    psu_port: Any = None,
    psu_lock: Any = None,
    ob_port: Any = None,
    ob_worker: Any = None,
    port_lock: Any = None,
    stop_event: Any = None,
    psu_mode_state: Any = None,
) -> None:
    normalized_mode = str(default_mode).upper()
    if normalized_mode not in {"OB", "EB"}:
        normalized_mode = "OB"

    # Serve static resources and apply the master stylesheet globally.
    app.add_static_files("/rsrc", str(_RSRC_DIR))
    css_version = _CSS_PATH.stat().st_mtime_ns if _CSS_PATH.exists() else 0
    ui.add_head_html(f'<link rel="stylesheet" href="/rsrc/guimasterconfig.css?v={css_version}">', shared=True)

    # Parse CSS variables once at startup so Python-side code (matplotlib etc.)
    # uses the same colour values as the browser.  Default theme is dark.
    _theme_state: dict[str, str] = {"value": "dark"}
    _css_vars = app_theme.load_css_vars(_CSS_PATH, theme=_theme_state["value"])
    _palette = app_theme.get_theme_palette(_css_vars, theme=_theme_state["value"])

    # app_theme maps --plot-color-1 ... --plot-color-7 from CSS and
    # validates that every value is a concrete Matplotlib-compatible colour.
    plot_colors = app_theme.get_plot_colors(_palette, count=7)

    state: dict[str, Any] = {
        "mode": normalized_mode,
        "hk_display_mode": "REAL",
        "voltage_mode": "NOM",
        "logger": logger,
        "channels": {},
        "plot_refreshers": [],
        "mode_change_resetters": [],
        "refreshers": [],
        "timers": [],
        "disconnect_cleanup_done": False,
        "log_search": {"enabled": False},
        "packet_counts": {"hk": 0, "post": 0, "sci": 0},
        "last_ob_tm_time": None,
        "last_psu_readings": {
            "status": None,
            "PSU_ROV_HTR_V": None,
            "PSU_ROV_HTR_I": None,
            "PSU_EB_V": None,
            "PSU_EB_I": None,
            "CH1_V": None,
            "CH1_I": None,
            "CH2_V": None,
            "CH2_I": None,
            "CH3_V": None,
            "CH3_I": None,
            "CH4_V": None,
            "CH4_I": None,
        },
        "psu_replay": {
            "enabled": False,
            "source_path": None,
            "records": [],
            "index": 0,
            "hk_anchor": None,
            "latest_hk_time": None,
            "psu_anchor": None,
        },
        "mms": {
            "enabled": True,
            "latched": False,
            "in_progress": False,
            "pending": False,
            "mode_at_trigger": None,
            "triggered_at": None,
            "reasons": [],
            "tec_shutdown_requested": False,
            "ob5v_disable_requested": False,
            "last_error": None,
            # Every safety threshold is sourced from core_modules.constants
            # through the shared monitoring limit registry.
            "limits": monitoring_limits.mms_alarm_limits(),
        },
        "ob_port": ob_port,
        "ob_worker": ob_worker,
        "psu_port": psu_port,
        "psu_lock": psu_lock,
        "psu_mode_state": psu_mode_state,
        "port_lock": port_lock,
        "stop_event": stop_event,
    }

    cyclic_hk = None
    if ob_worker is not None:
        # Cyclic traffic shares the single-owner transaction queue.  Priority
        # 10 keeps user/script transactions (priority 1) responsive.
        cyclic_hk = CyclicHKController(
            lambda: ob_worker.submit(tc.hk_request, priority=10),
            interval_s=1.0,
            logger=logger,
        )
    state["cyclic_hk"] = cyclic_hk
    if cyclic_hk is not None:
        app.on_shutdown(cyclic_hk.close)

    set_mode = ui_runtime_controller.create_set_mode(app=app, state=state)
    set_psu_log_path = ui_runtime_controller.create_set_psu_log_path(state=state, logger=logger)

    app.state.set_egse_mode = set_mode
    app.state.egse_mode_state = set_mode
    app.state.egse_mode = normalized_mode
    app.state.log_search_state = state["log_search"]
    app.state.eb_interface = eb_interface
    app.state.set_psu_log_path = set_psu_log_path
    app.state.get_psu_replay_sample_count = lambda: len(state["psu_replay"].get("records") or [])
    app.state.theme_state = _theme_state
    app.state.hk_display_mode = state["hk_display_mode"]

    @ui.page("/")
    def index() -> None:
        def cleanup_disconnected_client() -> None:
            """Remove stale UI refresh callbacks when the browser client disappears."""
            if state.get("disconnect_cleanup_done"):
                return
            state["disconnect_cleanup_done"] = True

            for collection_name in ("plot_refreshers", "mode_change_resetters", "refreshers"):
                collection = state.get(collection_name)
                if isinstance(collection, list):
                    collection.clear()

            for timer in state.get("timers", []):
                try:
                    timer.active = False
                except Exception:
                    pass
            state["timers"] = []

        try:
            client = ui.context.client
            if client is not None:
                client.on_disconnect(cleanup_disconnected_client)
        except Exception:
            pass

        def build_left_drawer() -> dict[str, packet_viewer_widget.PacketViewerController]:
            """Placeholder method for left drawer content
            Creates packet viewer tabs and controllers, and returns the controllers for later updates."""
            with (
                ui.left_drawer(value=True)
                .props("no-swipe-open no-swipe-close breakpoint=0")
                .classes("egse-left-drawer")
            ):
                # Header with title and packet list button
                with ui.row().classes("w-full items-center justify-between"):
                    lbl = ui.label("Packet Viewers")
                    lbl.classes("font-bold p-2 egse-title")
                    packet_list_controller = packet_list_widget.create_packet_list(state, {})
                with ui.tabs().classes("w-full") as packet_tabs:
                    tab_eb_hk = ui.tab("EB HK").classes("egse-title")
                    tab_eb_post = ui.tab("EB POST").classes("egse-title")
                    tab_eb_sci = ui.tab("EB SCI").classes("egse-title")
                    tab_ob_hk = ui.tab("OB HK").classes("egse-title")
                    tab_ob_sci = ui.tab("OB SCI").classes("egse-title")

                tab_by_profile = {
                    "EB_HK": tab_eb_hk,
                    "EB_POST": tab_eb_post,
                    "EB_SCI": tab_eb_sci,
                    "OB_HK": tab_ob_hk,
                    "OB_SCI": tab_ob_sci,
                }

                pv_controllers: dict[str, packet_viewer_widget.PacketViewerController] = {}
                with ui.tab_panels(packet_tabs).classes("w-full egse-left-packet-panels egse-title"):
                    with ui.tab_panel(tab_eb_hk).classes("w-full egse-left-packet-panel egse-title") as panel_eb_hk:
                        pv_controllers["EB_HK"] = packet_viewer_widget.create_packet_viewer(state, packet_type="EB_HK")
                    with ui.tab_panel(tab_eb_post).classes("w-full egse-left-packet-panel egse-title") as panel_eb_post:
                        pv_controllers["EB_POST"] = packet_viewer_widget.create_packet_viewer(
                            state, packet_type="EB_POST"
                        )
                    with ui.tab_panel(tab_eb_sci).classes("w-full egse-left-packet-panel egse-title") as panel_eb_sci:
                        pv_controllers["EB_SCI"] = packet_viewer_widget.create_packet_viewer(
                            state, packet_type="EB_SCI"
                        )
                    with ui.tab_panel(tab_ob_hk).classes("w-full egse-left-packet-panel egse-title ") as panel_ob_hk:
                        pv_controllers["OB_HK"] = packet_viewer_widget.create_packet_viewer(state, packet_type="OB_HK")
                    with ui.tab_panel(tab_ob_sci).classes("w-full egse-left-packet-panel egse-title") as panel_ob_sci:
                        pv_controllers["OB_SCI"] = packet_viewer_widget.create_packet_viewer(
                            state, packet_type="OB_SCI"
                        )

                # Update packet list controller with references to packet viewers
                if packet_list_controller is not None:
                    packet_list_controller.packet_viewer_controllers = pv_controllers
                    state["packet_list_controller"] = packet_list_controller

                panel_by_profile = {
                    "EB_HK": panel_eb_hk,
                    "EB_POST": panel_eb_post,
                    "EB_SCI": panel_eb_sci,
                    "OB_HK": panel_ob_hk,
                    "OB_SCI": panel_ob_sci,
                }

                def set_profile_visible(profile: str, visible: bool) -> None:
                    if visible:
                        tab_by_profile[profile].classes(remove="hidden")
                        panel_by_profile[profile].classes(remove="hidden")
                    else:
                        tab_by_profile[profile].classes(add="hidden")
                        panel_by_profile[profile].classes(add="hidden")

                def sync_packet_tabs(mode: str) -> None:
                    eb_visible = mode == "EB"
                    for profile in ("EB_HK", "EB_POST", "EB_SCI"):
                        set_profile_visible(profile, eb_visible)
                    for profile in ("OB_HK", "OB_SCI"):
                        set_profile_visible(profile, not eb_visible)
                    packet_tabs.value = tab_eb_hk if eb_visible else tab_ob_hk

                state["sync_packet_tabs"] = sync_packet_tabs
            return pv_controllers

        # Logo source will be set dynamically based on theme
        logo_images = []

        def build_top_bar() -> None:
            """Build fixed top header with brand logo and warning lights."""
            with (
                ui.header()
                .classes("w-full px-4 py-1 items-center")
                .style("z-index: 1300; backdrop-filter: none; background: var(--primary-bg);")
            ):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.row().classes("items-center gap-3"):
                        menu_controller = menu_widget.create_menu(
                            state,
                            set_mode_fn=set_mode,
                            set_psu_log_path_fn=set_psu_log_path,
                            get_psu_sample_count_fn=app.state.get_psu_replay_sample_count,
                        )
                        menu_controller.button.props("flat dense no-caps")
                        menu_controller.button.classes("rounded-md p-0 min-w-0")
                        menu_controller.button.style(
                            "height: 56px; min-width: 56px; width: auto; padding-left: 0.35rem; padding-right: 0.5rem;"
                        )
                        initial_logo_src = (
                            _css_vars.get("logo-dark-src", "/rsrc/Enfys_logo_-_FINAL_-_WHITE.png")
                            if _theme_state["value"] == "dark"
                            else _css_vars.get("logo-light-src", "/rsrc/Enfys_logo.png")
                        )
                        initial_logo_src = str(initial_logo_src).strip().strip('"').strip("'")
                        logo = (
                            ui.image(initial_logo_src)
                            .props("fit=contain")
                            .style("height: 40px; width: 180px; max-width: 180px; margin-left: 0.4rem;")
                        )
                        logo_images.append(logo)
                    with ui.row().classes("items-center gap-4"):
                        state["alarm_lights"] = traffic_light_widget.create_traffic_lights([("ob", "OB"), ("eb", "EB")])
                        ob_light = state["alarm_lights"]["ob"]
                        ob_light.on_clear = lambda: ui_runtime_controller.reset_ob_fdir_simulator(state)

                        def _on_ob_ignore(muted_details: set) -> None:
                            ignored: set = state.setdefault("ob_fdir_ignored_flags", set())
                            for detail in muted_details:
                                # Detail strings look like "OB FDIR Alarm: FLAG_NAME (simulated, latched)"
                                try:
                                    flag = detail.split(": ", 1)[1].split(" (")[0]
                                    ignored.add(flag)
                                except Exception:
                                    pass

                        ob_light.on_ignore = _on_ob_ignore

        def build_centre_console() -> tuple[Any, Any]:
            """Placeholder method for centre console content"""

            with ui.column().classes("egse-centre-console w-full gap-2 min-w-0"):
                with ui.column().classes("w-full gap-0.5"):
                    state["packet_metrics_card"] = metrics_card_widget.create_packet_metrics_card(state)
                    state["plot_refreshers"].append(state["packet_metrics_card"].set_mode)
                    state["plot_refreshers"].append(lambda mode: state["alarm_lights"]["eb"].set_visible(mode == "EB"))
                    state["eb_metrics_card"] = metrics_card_widget.create_default_eb_metrics_card()
                    state["plot_refreshers"].append(lambda mode: state["eb_metrics_card"].set_visible(mode == "EB"))
                    state["ob_metrics_card"] = metrics_card_widget.create_default_ob_metrics_card()
                    state["mode_change_resetters"].append(state["packet_metrics_card"].set_no_data)
                    state["mode_change_resetters"].append(state["eb_metrics_card"].set_no_data)
                    state["mode_change_resetters"].append(state["ob_metrics_card"].set_no_data)
                    # Add right drawer content here as needed
                trp_limits = monitoring_limits.get_limit("ob_trp")
                ob_3v3_limits = monitoring_limits.get_limit("ob_3v3")
                ob_1v5_limits = monitoring_limits.get_limit("ob_1v5")
                eb_3v3_limits = monitoring_limits.get_limit("eb_3v3")
                trp_display_limits = {
                    "REAL": monitoring_limits.recommended_plot_limits(("ob_trp",), "REAL", minimum_padding=5.0),
                    "ADU": monitoring_limits.recommended_plot_limits(("ob_trp",), "ADU"),
                }
                voltage_display_limits = {
                    "REAL": monitoring_limits.recommended_plot_limits(
                        ("ob_3v3", "ob_1v5", "eb_3v3"), "REAL", minimum_padding=0.25
                    ),
                    "ADU": monitoring_limits.recommended_plot_limits(("ob_3v3", "ob_1v5", "eb_3v3"), "ADU"),
                }

                with ui.row().classes("w-full gap-4 items-stretch min-w-0"):
                    # Warning/alarm lines use one shared band for all four
                    # thermistors because their limits are identical.
                    trp_card = plot_widget.create_plot_card(
                        "Thermistors",
                        series=[
                            plot_widget.SeriesConfig("DIG TRP", plot_colors[1]),
                            plot_widget.SeriesConfig("DET TRP", plot_colors[2]),
                            plot_widget.SeriesConfig("MECH TRP", plot_colors[3]),
                            plot_widget.SeriesConfig("MTR TRP", plot_colors[4]),
                        ],
                        y_label="°C",
                        y_limits=trp_display_limits["REAL"],
                        display_limits=trp_display_limits,
                        limit_bands=[
                            plot_widget.LimitBandConfig(
                                label="TRP shared",
                                warning_limits={"*": trp_limits.warning_by_display()},
                                alarm_limits={"*": trp_limits.alarm_by_display()},
                            )
                        ],
                        show_toggles=True,
                    )
                    state["plot_refreshers"].append(trp_card.set_mode)
                    trp_card.set_mode(state["mode"])
                    trp_card.set_display_mode(state.get("hk_display_mode", "REAL"))

                with ui.row().classes("w-full gap-4 items-stretch min-w-0"):
                    voltage_card = plot_widget.create_plot_card(
                        "Voltages",
                        series=[
                            plot_widget.SeriesConfig("OB 3V3", plot_colors[5]),
                            plot_widget.SeriesConfig("OB 1V5", plot_colors[1]),
                            plot_widget.SeriesConfig("EB 3V3", plot_colors[6], modes=("EB",)),
                        ],
                        y_label="V",
                        y_limits=voltage_display_limits["REAL"],
                        display_limits=voltage_display_limits,
                        limit_bands=[
                            plot_widget.LimitBandConfig(
                                label="OB 3V3",
                                warning_limits={"*": ob_3v3_limits.warning_by_display()},
                                alarm_limits={"*": ob_3v3_limits.alarm_by_display()},
                            ),
                            plot_widget.LimitBandConfig(
                                label="OB 1V5",
                                warning_limits={"*": ob_1v5_limits.warning_by_display()},
                                alarm_limits={"*": ob_1v5_limits.alarm_by_display()},
                            ),
                            plot_widget.LimitBandConfig(
                                label="EB 3V3",
                                warning_limits={"EB": eb_3v3_limits.warning_by_display()},
                                alarm_limits={"EB": eb_3v3_limits.alarm_by_display()},
                            ),
                        ],
                        show_toggles=True,
                    )
                    state["plot_refreshers"].append(voltage_card.set_mode)
                    voltage_card.set_mode(state["mode"])
                    voltage_card.set_display_mode(state.get("hk_display_mode", "REAL"))

            # HK Parameter Explorer
            # hk_explorer_card = parameter_explorer.create_hk_parameter_explorer(state, _palette)
            # state["plot_refreshers"].append(hk_explorer_card.set_mode)
            # hk_explorer_card.set_mode(state["mode"])

            return trp_card, voltage_card

        def build_right_drawer(mode: str):
            """Build centre console plot cards and return their controllers."""
            with ui.right_drawer(value=True).props("breakpoint=0").classes("egse-right-drawer"):
                (
                    set_ob_master_toggle_visible,
                    sync_ob_master_toggle_value,
                    bind_ob_master_toggle_cards,
                ) = psu_widget.create_ob_master_channels_toggle(state)

                with ui.column().classes("w-full gap-4 items-stretch min-w-0"):
                    ch1_card = psu_widget.create_psu_channel_card(
                        state,
                        key="psu_ch1",
                        title="CH1",
                        color=plot_colors[7],
                        mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                        live_voltage_key="CH1_V",
                        live_current_key="CH1_I",
                        enabled_switch="enabled",
                        replay_channel_by_mode={"OB": ["CH1"], "EB": ["CH1"]},
                    )
                    ch2_card = psu_widget.create_psu_channel_card(
                        state,
                        key="psu_ch2",
                        title="CH2",
                        color=plot_colors[1],
                        mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                        live_voltage_key="CH2_V",
                        live_current_key="CH2_I",
                        enabled_switch="enabled",
                        replay_channel_by_mode={"OB": ["CH2"], "EB": ["CH2"]},
                    )
                    ch3_card = psu_widget.create_psu_channel_card(
                        state,
                        key="psu_ch3",
                        title="CH3",
                        color=plot_colors[7],
                        mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                        live_voltage_key="CH3_V",
                        live_current_key="CH3_I",
                        enabled_switch="enabled",
                        replay_channel_by_mode={"OB": ["CH3"], "EB": ["CH3"]},
                    )
                    ch4_card = psu_widget.create_psu_channel_card(
                        state,
                        key="psu_ch4",
                        title="CH4",
                        color=plot_colors[1],
                        mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                        live_voltage_key="CH4_V",
                        live_current_key="CH4_I",
                        enabled_switch="enabled",
                        replay_channel_by_mode={"OB": ["CH4"], "EB": ["CH4"]},
                    )

                bind_ob_master_toggle_cards(
                    ch1_card,
                    ch2_card,
                    ch3_card,
                )
                state["sync_ob_master_toggle_value"] = sync_ob_master_toggle_value
                state["plot_refreshers"].append(set_ob_master_toggle_visible)
                state["plot_refreshers"].append(lambda _mode: sync_ob_master_toggle_value())

                set_psu_card_profiles = ui_runtime_controller.create_set_psu_card_profiles(
                    ch1_card=ch1_card,
                    ch2_card=ch2_card,
                    ch3_card=ch3_card,
                    ch4_card=ch4_card,
                )
                state["plot_refreshers"].append(set_psu_card_profiles)
                set_psu_card_profiles(state["mode"])
            return [ch1_card, ch2_card, ch3_card, ch4_card]

        def build_ob_controls() -> Any:
            """Build OB-only mechanism/detector control tabs and return visibility sync callback."""
            with ui.column().classes("w-full") as ob_controls_container:
                with ui.tabs().classes("w-full") as ob_tabs:
                    main_ob_controls_tab = ui.tab("Main OB")
                    mechanism_controls_tab = ui.tab("Mechanism")
                    detector_controls_tab = ui.tab("Detector")

                with ui.tab_panels(ob_tabs, value=main_ob_controls_tab).classes("w-full"):
                    with ui.tab_panel(main_ob_controls_tab).classes("w-full"):
                        main_ob_tab.create_main_ob_tab(state)

                    with ui.tab_panel(mechanism_controls_tab).classes("w-full"):
                        mechanism_tab.create_mechanism_tab(state)
                    with ui.tab_panel(detector_controls_tab).classes("w-full"):
                        detector_tab.create_detector_tab(state)

            def set_ob_controls_visible(mode: str) -> None:
                if mode == "OB":
                    ob_controls_container.classes(remove="hidden")
                else:
                    ob_controls_container.classes(add="hidden")

            return set_ob_controls_visible

        def build_footer():
            """Method that builds the footer content, which currently consists of the log terminal and its toggle button"""
            footer_state = {"open": True}

            with ui.footer().classes("w-full px-2 py-1").style("z-index: 1200;"):
                with ui.row().classes("w-full justify-end"):
                    toggle_btn = ui.button(icon="keyboard_arrow_down").props("flat dense round")
                with ui.column().classes("w-full") as footer_content:
                    state["log_terminal_controller"] = log_terminal_widget.create_log_terminal(logger)
                    with ui.column().classes("w-full") as console_input_container:
                        state["console_terminal"] = console_input_widget.create_console_input_widget(state)

            def _set_console_input_visible(mode: str) -> None:
                console_input_container.classes(remove="hidden")

            state["plot_refreshers"].append(_set_console_input_visible)
            _set_console_input_visible(state.get("mode", "OB"))

            def _set_footer_open(open_state: bool) -> None:
                """Set the footer open or closed, showing or hiding its content and updating the toggle button icon."""
                footer_state["open"] = open_state
                if open_state:
                    footer_content.classes(remove="hidden")
                    toggle_btn.props("icon=keyboard_arrow_down")
                else:
                    footer_content.classes(add="hidden")
                    toggle_btn.props("icon=keyboard_arrow_up")

            def _toggle_footer(_: Any | None = None) -> None:
                """Toggle the footer open or closed based on its current state."""
                _set_footer_open(not footer_state["open"])

            toggle_btn.on_click(_toggle_footer)

        packet_viewer_controllers = build_left_drawer()
        state["packet_viewer_controllers"] = packet_viewer_controllers
        build_top_bar()
        psu_cards = build_right_drawer(state["mode"])
        build_footer()
        trp_card, voltage_card = build_centre_console()
        hk_explorer_card = state.get("hk_explorer_card")
        state["trp_card"] = trp_card
        state["voltage_card"] = voltage_card
        state["hk_explorer_card"] = hk_explorer_card
        set_ob_controls_visible = build_ob_controls()
        state["plot_refreshers"].append(set_ob_controls_visible)
        set_ob_controls_visible(state["mode"])

        eb_metrics_card = state["eb_metrics_card"]
        ob_metrics_card = state["ob_metrics_card"]
        packet_metrics_card = state["packet_metrics_card"]
        eb_metrics_card.set_visible(state["mode"] == "EB")

        theme_plots = [trp_card.plot, voltage_card.plot]
        theme_plots.extend(psu_card.plot.plot for psu_card in psu_cards)

        set_theme = ui_runtime_controller.create_set_theme(
            ui=ui,
            app=app,
            state=state,
            css_path=_CSS_PATH,
            theme_state=_theme_state,
            theme_plots=theme_plots,
            logo_images=logo_images,
        )

        app.state.set_theme = set_theme
        set_theme(_theme_state["value"])

        # Keep controllers referenced in this scope for future extension hooks.
        _ = state.get("log_terminal_controller")

        poll_psu = ui_runtime_controller.create_poll_psu(
            state=state,
            const=const,
            psu_cards=psu_cards,
        )
        poll_tm = ui_runtime_controller.create_poll_tm(
            app=app,
            state=state,
            const=const,
            logger=logger,
            eb_metrics_card=eb_metrics_card,
            ob_metrics_card=ob_metrics_card,
            packet_metrics_card=packet_metrics_card,
            packet_viewer_controllers=packet_viewer_controllers,
            trp_card=trp_card,
            voltage_card=voltage_card,
            hk_explorer_card=hk_explorer_card,
        )

        poll_psu_timer = ui.timer(0.2, poll_psu)
        poll_tm_timer = ui.timer(0.2, poll_tm)
        state["timers"].extend((poll_psu_timer, poll_tm_timer))
        set_mode(normalized_mode)
