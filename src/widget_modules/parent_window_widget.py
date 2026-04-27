from __future__ import annotations

# Std library
import logging
from pathlib import Path
from typing import Any

# Added packages
from nicegui import app, ui

# Local modules
# core
from core_modules import constants as const

# utilities
from utility_modules import (
    app_theme,
    eb_interface,
)

# widgets
from widget_modules import (
    detector_tab,
    log_terminal_widget,
    mechanism_tab,
    menu_widget,
    metrics_card_widget,
    packet_viewer_widget,
    psu_widget,
    plot_widget,
    traffic_light_widget,
)
import widget_modules.ui_runtime_controller as ui_runtime_controller


logger = logging.getLogger("info_log")

_RSRC_DIR = Path(__file__).resolve().parent.parent.parent / "rsrc"
_CSS_PATH = _RSRC_DIR / "guimasterconfig.css"


def build_ui(
    *,
    default_mode: str,
    psu_port: Any = None,
    psu_lock: Any = None,
    ob_port: Any = None,
    port_lock: Any = None,
    stop_event: Any = None,
    psu_mode_state: Any = None,
) -> None:
    # Serve static resources and apply the master stylesheet globally.
    app.add_static_files("/rsrc", str(_RSRC_DIR))
    ui.add_head_html('<link rel="stylesheet" href="/rsrc/guimasterconfig.css">', shared=True)

    # Parse CSS variables once at startup so Python-side code (matplotlib etc.)
    # uses the same colour values as the browser.  Default theme is dark.
    _theme_state: dict[str, str] = {"value": "dark"}
    _css_vars = app_theme.load_css_vars(_CSS_PATH, theme=_theme_state["value"])
    _palette = app_theme.get_theme_palette(_css_vars, theme=_theme_state["value"])

    state: dict[str, Any] = {
        "mode": default_mode,
        "voltage_mode": "NOM",
        "logger": logger,
        "channels": {},
        "plot_refreshers": [],
        "mode_change_resetters": [],
        "refreshers": [],
        "log_search": {"enabled": False},
        "packet_counts": {"hk": 0, "post": 0, "sci": 0},
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
            # Limit set chosen to match existing alarm semantics in this codebase.
            "limits": {
                "eb_12v": (11.0, 13.0),
                "eb_neg12v": (-13.0, -11.0),
                "eb_5v": (4.5, 5.5),
                "eb_3v3": const.ALIM_3V3,
                "eb_mcu_temp": const.EB_ALIM_TPR,
                "eb_internal_trp_temp": const.ALIM_TPR,
                "eb_psu_trp_temp": const.ALIM_TPR,
                "eb_tec_rail_v": (const.ALIM_3V3[0], None),
                "ob_fpga_core_v": const.ALIM_3V3,
                "ob_fpga_io_v": const.ALIM_1V5,
                "ob_digital_trp": const.ALIM_TPR,
                "ob_detector_trp": const.ALIM_TPR,
                "ob_mechanism_trp": const.ALIM_TPR,
                "ob_motor_trp": const.ALIM_TPR,
            },
        },
        "ob_port": ob_port,
        "psu_port": psu_port,
        "psu_lock": psu_lock,
        "psu_mode_state": psu_mode_state,
        "port_lock": port_lock,
        "stop_event": stop_event,
    }

    set_mode = ui_runtime_controller.create_set_mode(app=app, state=state)
    set_psu_log_path = ui_runtime_controller.create_set_psu_log_path(state=state, logger=logger)

    app.state.set_egse_mode = set_mode
    app.state.egse_mode_state = set_mode
    app.state.egse_mode = default_mode
    app.state.log_search_state = state["log_search"]
    app.state.eb_interface = eb_interface
    app.state.set_psu_log_path = set_psu_log_path
    app.state.get_psu_replay_sample_count = lambda: len(state["psu_replay"].get("records") or [])
    app.state.theme_state = _theme_state

    @ui.page("/")
    def index() -> None:
        def build_left_drawer() -> dict[str, packet_viewer_widget.PacketViewerController]:
            """Placeholder method for left drawer content
            Creates packet viewer tabs and controllers, and returns the controllers for later updates."""
            with ui.left_drawer(value=True).props("width=400 no-swipe-open no-swipe-close"):
                ui.label("Packet Viewers").classes("text-sm font-bold p-2")
                with ui.tabs().classes("w-full") as packet_tabs:
                    tab_eb_hk = ui.tab("EB HK")
                    tab_eb_post = ui.tab("EB POST")
                    tab_eb_sci = ui.tab("EB SCI")
                    tab_ob_hk = ui.tab("OB HK")
                    tab_ob_sci = ui.tab("OB SCI")

                tab_by_profile = {
                    "EB_HK": tab_eb_hk,
                    "EB_POST": tab_eb_post,
                    "EB_SCI": tab_eb_sci,
                    "OB_HK": tab_ob_hk,
                    "OB_SCI": tab_ob_sci,
                }

                pv_controllers: dict[str, packet_viewer_widget.PacketViewerController] = {}
                with ui.tab_panels(packet_tabs).classes("w-full"):
                    with ui.tab_panel(tab_eb_hk).classes("w-full") as panel_eb_hk:
                        pv_controllers["EB_HK"] = packet_viewer_widget.create_packet_viewer(state, packet_type="EB_HK")
                    with ui.tab_panel(tab_eb_post).classes("w-full") as panel_eb_post:
                        pv_controllers["EB_POST"] = packet_viewer_widget.create_packet_viewer(
                            state, packet_type="EB_POST"
                        )
                    with ui.tab_panel(tab_eb_sci).classes("w-full") as panel_eb_sci:
                        pv_controllers["EB_SCI"] = packet_viewer_widget.create_packet_viewer(
                            state, packet_type="EB_SCI"
                        )
                    with ui.tab_panel(tab_ob_hk).classes("w-full") as panel_ob_hk:
                        pv_controllers["OB_HK"] = packet_viewer_widget.create_packet_viewer(state, packet_type="OB_HK")
                    with ui.tab_panel(tab_ob_sci).classes("w-full") as panel_ob_sci:
                        pv_controllers["OB_SCI"] = packet_viewer_widget.create_packet_viewer(
                            state, packet_type="OB_SCI"
                        )

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
                .style(
                    "z-index: 1300; backdrop-filter: blur(8px); background: color-mix(in srgb, var(--secondary-bg) 92%, transparent);"
                )
            ):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.row().classes("items-center gap-3"):
                        menu_controller = menu_widget.create_menu(
                            state,
                            set_mode_fn=set_mode,
                            set_psu_log_path_fn=set_psu_log_path,
                            get_psu_sample_count_fn=app.state.get_psu_replay_sample_count,
                        )
                        menu_controller.button.props("flat dense round")
                        initial_logo_src = (
                            _css_vars.get("logo-dark-src", "/rsrc/Enfys_logo_-_FINAL_-_WHITE.png")
                            if _theme_state["value"] == "dark"
                            else _css_vars.get("logo-light-src", "/rsrc/Enfys_logo.png")
                        )
                        logo = ui.image(initial_logo_src).classes("h-auto w-auto max-h-14 max-w-[260px] object-contain")
                        logo_images.append(logo)
                    with ui.row().classes("items-center gap-4"):
                        state["alarm_lights"] = traffic_light_widget.create_traffic_lights([("ob", "OB"), ("eb", "EB")])

        def build_right_drawer() -> None:
            """Placeholder method for right drawer content"""
            with ui.right_drawer().props("width=525"):
                with ui.column().classes("w-full gap-4 mt-2"):
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

        def build_centre_console():
            """Build centre console plot cards and return their controllers."""
            with ui.row().classes("w-full gap-4"):
                ch1_card = psu_widget.create_psu_channel_card(
                    state,
                    key="psu_ch1",
                    title="CH1",
                    color=_palette["chart_rov_htr"],
                    mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                    live_voltage_key="CH1_V",
                    live_current_key="CH1_I",
                    replay_channel_by_mode={"OB": ["CH1"], "EB": ["CH1"]},
                )
                ch2_card = psu_widget.create_psu_channel_card(
                    state,
                    key="psu_ch2",
                    title="CH2",
                    color=_palette["chart_eb_current"],
                    mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                    live_voltage_key="CH2_V",
                    live_current_key="CH2_I",
                    replay_channel_by_mode={"OB": ["CH2"], "EB": ["CH2"]},
                )
                ch3_card = psu_widget.create_psu_channel_card(
                    state,
                    key="psu_ch3",
                    title="CH3",
                    color=_palette["chart_rov_htr"],
                    mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                    live_voltage_key="CH3_V",
                    live_current_key="CH3_I",
                    replay_channel_by_mode={"OB": ["CH3"], "EB": ["CH3"]},
                )
                ch4_card = psu_widget.create_psu_channel_card(
                    state,
                    key="psu_ch4",
                    title="CH4",
                    color=_palette["chart_eb_current"],
                    mode_limits={"OB": (0.0, 500.0), "EB": (0.0, 1000.0)},
                    live_voltage_key="CH4_V",
                    live_current_key="CH4_I",
                    replay_channel_by_mode={"OB": ["CH4"], "EB": ["CH4"]},
                )

            set_psu_card_profiles = ui_runtime_controller.create_set_psu_card_profiles(
                ch1_card=ch1_card,
                ch2_card=ch2_card,
                ch3_card=ch3_card,
                ch4_card=ch4_card,
            )
            state["plot_refreshers"].append(set_psu_card_profiles)
            set_psu_card_profiles(state["mode"])
            with ui.row().classes("w-full gap-4"):
                ob_trp_card = plot_widget.create_plot_card(
                    "OB Thermistors",
                    series=[
                        plot_widget.SeriesConfig("DIG TRP", _palette["series_dig_trp"]),
                        plot_widget.SeriesConfig("DET TRP", _palette["series_det_trp"]),
                        plot_widget.SeriesConfig("MECH TRP", _palette["series_mech_trp"]),
                        plot_widget.SeriesConfig("MTR TRP", _palette["series_mtr_trp"], visible=False),
                    ],
                    y_label="°C",
                    y_limits=(-30.0, 80.0),
                    show_toggles=True,
                )
                state["plot_refreshers"].append(ob_trp_card.set_mode)
                ob_trp_card.set_mode(state["mode"])
            with ui.row().classes("w-full gap-4"):
                voltage_3v3_card = plot_widget.create_plot_card(
                    "OB Voltages",
                    series=[
                        plot_widget.SeriesConfig("OB 3V3", _palette["series_ob_3v3"]),
                        plot_widget.SeriesConfig("EB 3V3", _palette["series_eb_3v3"]),
                    ],
                    y_label="V",
                    y_limits=(3, 4),
                    show_toggles=True,
                )
                state["plot_refreshers"].append(voltage_3v3_card.set_mode)
                voltage_3v3_card.set_mode(state["mode"])

            return [ch1_card, ch2_card, ch3_card, ch4_card], ob_trp_card, voltage_3v3_card

        def build_ob_controls() -> Any:
            """Build OB-only mechanism/detector control tabs and return visibility sync callback."""
            with ui.column().classes("w-full") as ob_controls_container:
                with ui.tabs().classes("w-full") as ob_tabs:
                    mechanism_controls_tab = ui.tab("Mechanism")
                    detector_controls_tab = ui.tab("Detector")

                with ui.tab_panels(ob_tabs, value=mechanism_controls_tab).classes("w-full"):
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
        build_top_bar()
        build_right_drawer()
        build_footer()
        psu_cards, OB_TRP_card, voltage_3v3_card = build_centre_console()
        set_ob_controls_visible = build_ob_controls()
        state["plot_refreshers"].append(set_ob_controls_visible)
        set_ob_controls_visible(state["mode"])

        eb_metrics_card = state["eb_metrics_card"]
        ob_metrics_card = state["ob_metrics_card"]
        packet_metrics_card = state["packet_metrics_card"]
        eb_metrics_card.set_visible(state["mode"] == "EB")

        theme_plots = [OB_TRP_card.plot, voltage_3v3_card.plot]
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
            ob_trp_card=OB_TRP_card,
            voltage_3v3_card=voltage_3v3_card,
        )

        ui.timer(0.2, poll_psu)
        ui.timer(0.2, poll_tm)
        set_mode(default_mode)
