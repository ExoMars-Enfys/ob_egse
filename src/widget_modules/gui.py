# Std library
import logging

# Added packages
from contextlib import nullcontext
from pathlib import Path
from nicegui import app, ui
from matplotlib import dates as mdates

# Local modules
# core
from core_modules import config as config
from core_modules import constants as const
from core_modules import tmstruct as tmstruct

# utilities
from utility_modules import comms as comms
from utility_modules import tc as tc
from utility_modules import tm as tm

logger = logging.getLogger("info_log")
level_options = {"INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}


# Define a custom handler for the GUI
class LogElementHandler(logging.Handler):
    """A logging handler that emits messages to a ui.log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:
        self.element = element
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Map log levels to Tailwind text color classes
            color_map = {
                logging.DEBUG: "text-grey",
                logging.INFO: "text-blue",
                logging.WARNING: "text-orange",
                logging.ERROR: "text-red",
                logging.CRITICAL: "text-red font-bold",
            }
            # Get the class for the current level, default to no class
            log_class = color_map.get(record.levelno, "")
            self.element.push(msg, classes=log_class)  # Push with styling
        except Exception:
            self.handleError(record)


def build_ui(ob_port, psu_port, port_lock=None, stop_event=None) -> None:
    rsrc_dir = Path(__file__).resolve().parent.parent.parent / "rsrc"
    app.add_static_files("/rsrc", rsrc_dir)
    labels: dict[str, ui.label] = {}
    status: dict[str, int] = {"pwr": 0, "psu": 0}
    temp_series_order = ["DIG", "DET", "MECH", "MOT"]
    temp_visibility = {key: True for key in temp_series_order}
    lock_ctx = port_lock if port_lock is not None else nullcontext()

    def guarded_tc(func, *args, **kwargs):
        with lock_ctx:
            return func(ob_port, *args, **kwargs)

    def update_hk_display() -> None:
        def apply_temp_visibility() -> None:
            if "plot_temps" not in labels:
                return
            plot_ax = labels["plot_temps"].fig.axes[0]
            for idx, key in enumerate(temp_series_order):
                plot_ax.lines[idx].set_visible(temp_visibility[key])

        def get_temp_y_limits(hk) -> tuple[float, float]:
            temp_values = {
                "DIG": hk.DIGITAL_TRP,
                "DET": hk.DETEC_TRP,
                "MECH": hk.MECH_TRP,
                "MOT": hk.MOTOR_TRP,
            }
            selected_values = [temp_values[key] for key in temp_series_order if temp_visibility[key]]
            if selected_values:
                min_val = min(selected_values) - 20
                max_val = max(selected_values) + 20
            else:
                min_val = const.WLIM_TPR_ADU[0] - 20
                max_val = const.WLIM_TPR_ADU[1] + 20
            return (min_val, max_val)

        def poll_latest_hk() -> None:
            if not const.hk_queue.empty():
                hk = const.hk_queue.get()

                # Should implement better way to sort these.
                hk.HK_V_3V3 = hk.HK_V_3V3 / (16 * 1000) * 2
                hk.HK_V_1V5 = hk.HK_V_1V5 / (16 * 1000)
                hk.DIGITAL_TRP = hk.DIGITAL_TRP >> 4
                hk.DETEC_TRP = hk.DETEC_TRP >> 4
                hk.MECH_TRP = hk.MECH_TRP >> 4
                hk.MOTOR_TRP = hk.MOTOR_TRP >> 4

                labels["plot_3v3"].push([hk.TIME], [[hk.HK_V_3V3]], y_limits=(3.0, 3.6))

                labels["plot_1v5"].push([hk.TIME], [[hk.HK_V_1V5]], y_limits=(1.3, 1.7))

                apply_temp_visibility()
                labels["plot_temps"].push([hk.TIME], [[hk.DIGITAL_TRP], [hk.DETEC_TRP], [hk.MECH_TRP], [hk.MOTOR_TRP]])

                status["pwr"] = hk.PWR_STAT

                labels["cmd_cnt"].set_text(f"{hk.CMD_CNT}")
                labels["3v3"].set_text(f"{hk.HK_V_3V3} V")
                labels["1v5"].set_text(f"{hk.HK_V_1V5} V")
                labels["MECH_PWR"].set_background_color("green" if (hk.PWR_STAT & 0x01) else "red")
                labels["DET_PWR"].set_background_color("green" if (hk.PWR_STAT & 0x02) else "red")
                labels["MECH_HTR_STAT"].set_text_color("green" if hk.THRM_STATUS.HMS else "red")
                labels["MECH_HTR_MAN"].set_background_color("green" if hk.THRM_STATUS.MM else "grey")
                labels["MECH_HTR_MAN"].set_icon("check_circle_outline" if hk.THRM_STATUS.MM else "highlight_off")
                labels["MECH_HTR_AUTO"].set_background_color("green" if hk.THRM_STATUS.MA else "grey")
                labels["MECH_HTR_AUTO"].set_icon("check_circle_outline" if hk.THRM_STATUS.MA else "highlight_off")

                labels["DET_HTR_STAT"].set_text_color("green" if hk.THRM_STATUS.HDS else "red")
                labels["DET_HTR_MAN"].set_background_color("green" if hk.THRM_STATUS.DM else "grey")
                labels["DET_HTR_MAN"].set_icon("check_circle_outline" if hk.THRM_STATUS.DM else "highlight_off")
                labels["DET_HTR_AUTO"].set_background_color("green" if hk.THRM_STATUS.DA else "grey")
                labels["DET_HTR_AUTO"].set_icon("check_circle_outline" if hk.THRM_STATUS.DA else "highlight_off")
                labels["HTR_SCI"].set_background_color("green" if hk.THRM_STATUS.S else "grey")
                labels["HTR_SCI"].set_icon("check_circle_outline" if hk.THRM_STATUS.S else "highlight_off")

                labels["ERR_IPI"].set_background_color("red" if hk.ERRORS.IPI else "grey")
                labels["ERR_IOS"].set_background_color("red" if hk.ERRORS.IOS else "grey")
                labels["ERR_ICR"].set_background_color("red" if hk.ERRORS.ICR else "grey")
                labels["ERR_MOR"].set_background_color("red" if hk.ERRORS.MOR else "grey")
                labels["ERR_TMO"].set_background_color("red" if hk.ERRORS.TMO else "grey")
                labels["ERR_IPA"].set_background_color("red" if hk.ERRORS.IPA else "grey")

                labels["ERR_CD"].set_background_color("red" if hk.MTR_ERRORS.CD else "grey")
                labels["ERR_AB"].set_background_color("red" if hk.MTR_ERRORS.AB else "grey")
                labels["ERR_ABS"].set_background_color("red" if hk.MTR_ERRORS.ABS else "grey")
                labels["ERR_DSE"].set_background_color("red" if hk.MTR_ERRORS.DSE else "grey")

            if not const.psu_queue.empty():
                psu = const.psu_queue.get()

                status["psu"] = psu["STATUS"]

                labels["PSU_STATUS"].set_text(f"PSU {'ON' if psu['STATUS'] else 'OFF'}")

                labels["PSU_CH1V"].set_text(f"V: {psu['CH1_V']:.2f}")
                labels["PSU_CH1I"].set_text(f"mA: {psu['CH1_I'] * 1000:.1f}")

                labels["PSU_CH2V"].set_text(f"V: {psu['CH2_V']:.2f}")
                labels["PSU_CH2I"].set_text(f"mA: {psu['CH2_I'] * 1000:.1f}")

                labels["PSU_CH3V"].set_text(f"V: {psu['CH3_V']:.2f}")
                labels["PSU_CH3I"].set_text(f"mA: {psu['CH3_I'] * 1000:.1f}")

                labels["plot_psu_ch1"].push(
                    [psu["TIME"]],
                    [[psu["CH1_I"] * 1000]],
                )

                labels["plot_psu_ch2"].push(
                    [psu["TIME"]],
                    [[psu["CH2_I"] * 1000]],
                )

                labels["plot_psu_ch3"].push(
                    [psu["TIME"]],
                    [[psu["CH3_I"] * 1000]],
                )

        ui.timer(0.2, poll_latest_hk)

    # Decorator needed to allow nicegui to properly route to the index page
    @ui.page("/")
    def index() -> None:
        def stop_and_shutdown() -> None:
            if stop_event is not None:
                stop_event.set()
            app.shutdown()

        def set_temp_visibility(series_key: str, enabled: bool) -> None:
            temp_visibility[series_key] = enabled

        fullscreen = ui.fullscreen()

        # Display logger in UI as well, add first so that we can toggle visibility in the left_drawer
        with ui.footer(value=True).style("background-color: #fafafa") as footer:
            with ui.row(align_items="center"):
                ui.label("Log level to display in window").classes("text-black")
                ui.radio(
                    list(level_options.keys()),
                    value="WARNING",
                    on_change=lambda event: handler.setLevel(level_options[event.value]),
                ).props("inline").classes("text-black")

            log = ui.log(max_lines=200).classes("w-full h-64 border")

            handler = LogElementHandler(log, level=logging.WARNING)
            # Set formatting for the UI Log
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            logger.addHandler(handler)

        with ui.left_drawer(top_corner=True, bottom_corner=True).style("background-color: #d7e3f4"):
            ui.image("/rsrc/Enfys_logo.png")
            ui.markdown("**Enfys OB EGSE GUI v0.5**").style("text-align: center")

            with ui.row(align_items="center"):
                with ui.card().tight():
                    ui.markdown("**CMD CNT**")
                    labels["cmd_cnt"] = ui.label("---")

                with ui.card().tight():
                    ui.markdown("**3V3**")
                    labels["3v3"] = ui.label("---")

                with ui.card().tight():
                    ui.markdown("**1V5**")
                    labels["1v5"] = ui.label("---")

            ui.button("Request HK", on_click=lambda: guarded_tc(tc.hk_request))

            ui.separator()

            with ui.button_group():
                labels["MECH_PWR"] = ui.button(
                    "MECH PWR",
                    on_click=lambda: guarded_tc(tc.power_control, status["pwr"] ^ 0x01),
                )
                labels["DET_PWR"] = ui.button(
                    "DET PWR",
                    on_click=lambda: guarded_tc(tc.power_control, status["pwr"] ^ 0x02),
                )

            ui.separator()

            ui.markdown("**HEATER STATUS**").classes("gap-0")

            with ui.row(align_items="center"):
                with ui.card().tight():
                    ui.markdown("**MECH**")
                    labels["MECH_HTR_STAT"] = ui.icon("fiber_manual_record", size="2em").classes("text-red")
                    labels["MECH_HTR_MAN"] = ui.chip("MAN", selectable=False, icon="highlight_off", color="grey")
                    labels["MECH_HTR_AUTO"] = ui.chip("AUTO", selectable=False, icon="highlight_off", color="grey")

                with ui.card().tight():
                    ui.markdown("**DET**")
                    labels["DET_HTR_STAT"] = ui.icon("fiber_manual_record", size="2em").classes("text-red")
                    labels["DET_HTR_MAN"] = ui.chip("MAN", selectable=False, icon="highlight_off", color="grey")
                    labels["DET_HTR_AUTO"] = ui.chip("AUTO", selectable=False, icon="highlight_off", color="grey")

                labels["HTR_SCI"] = ui.chip("SCI TOGGLE", selectable=False, icon="highlight_off", color="grey")

            ui.separator()

            ui.markdown("**OB ERRORS**")

            with ui.grid(columns=2).classes("w-full gap-x-4 gap-y-1 p-0"):
                labels["ERR_IPI"] = ui.chip("IPI", color="grey").classes("m-0 w-full")
                labels["ERR_CD"] = ui.chip("CD", color="grey").classes("m-0 w-full")

                labels["ERR_IOS"] = ui.chip("IOS", color="grey").classes("m-0 w-full")
                labels["ERR_AB"] = ui.chip("AB", color="grey").classes("m-0 w-full")

                labels["ERR_ICR"] = ui.chip("ICR", color="grey").classes("m-0 w-full")
                labels["ERR_ABS"] = ui.chip("ABS", color="grey").classes("m-0 w-full")

                labels["ERR_MOR"] = ui.chip("MOR", color="grey").classes("m-0 w-full")
                labels["ERR_DSE"] = ui.chip("DSE", color="grey").classes("m-0 w-full")

                labels["ERR_TMO"] = ui.chip("TMO", color="grey").classes("m-0 w-full")
                ui.element("div").classes("w-full")  # Spacer to keep grid layout consistent

                labels["ERR_IPA"] = ui.chip("IPA", color="grey").classes("m-0 w-full")

            with ui.row(align_items="center").classes("w-full justify-center"):
                ui.button("Clear Errors", on_click=lambda: guarded_tc(tc.clear_errors))
                ui.separator()
                with ui.button_group():
                    ui.button("Display Log Terminal", on_click=footer.toggle)
                    ui.button("Toggle Fullscreen", on_click=fullscreen.toggle)

        with ui.right_drawer(fixed=True).style("background-color: #ebf1fa").props("width=350 bordered") as right_drawer:
            with ui.grid(columns=2):
                ui.button(
                    "Toggle PSU", on_click=lambda: psu.switchPSU(psu_port, ebmode=False, state=not (status["psu"]))
                )

                labels["PSU_STATUS"] = ui.label(f"PSU OFF")
                with ui.card().tight():
                    ui.markdown("**CH1**")
                    with ui.grid(columns=2):
                        labels["PSU_CH1V"] = ui.label(f"V: --")
                        labels["PSU_CH1I"] = ui.label(f"mA: --")

                with ui.card().tight().classes("width-full"):
                    ui.markdown("**CH2**")
                    with ui.grid(columns=2):
                        labels["PSU_CH2V"] = ui.label(f"V: --")
                        labels["PSU_CH2I"] = ui.label(f"mA: --")

                with ui.card().tight():
                    ui.markdown("**CH3**")
                    with ui.grid(columns=2):
                        labels["PSU_CH3V"] = ui.label(f"V: --")
                        labels["PSU_CH3I"] = ui.label(f"mA: --")

            labels["plot_psu_ch1"] = ui.line_plot(n=1, limit=40, figsize=(3.4, 1.8), update_every=1)
            plot_ax = labels["plot_psu_ch1"].fig.axes[0]
            plot_ax.set_title("+12V Current (mA)")
            plot_ax.lines[0].set_marker("x")
            plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)

            labels["plot_psu_ch2"] = ui.line_plot(n=1, limit=40, figsize=(3.4, 1.8), update_every=1)
            plot_ax = labels["plot_psu_ch2"].fig.axes[0]
            plot_ax.set_title("-12V Current (mA)")
            plot_ax.lines[0].set_marker("x")
            plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)

            labels["plot_psu_ch3"] = ui.line_plot(n=1, limit=40, figsize=(3.4, 1.8), update_every=1)
            plot_ax = labels["plot_psu_ch3"].fig.axes[0]
            plot_ax.set_title("+5V Current (mA)")
            plot_ax.lines[0].set_marker("x")
            plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)

        with ui.grid(columns=2):
            labels["plot_3v3"] = ui.line_plot(n=1, limit=20, figsize=(9, 2), update_every=1)
            plot_ax = labels["plot_3v3"].fig.axes[0]
            plot_ax.set_title("3V3 Voltage (ADU)")
            plot_ax.lines[0].set_marker("x")
            plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)
            plot_ax.axhline(const.WLIM_3V3_ADU[0], color="orange", linewidth=1.0, linestyle="--")
            plot_ax.axhline(const.WLIM_3V3_ADU[1], color="orange", linewidth=1.0, linestyle="--")
            plot_ax.axhline(const.ALIM_3V3_ADU[0], color="red", linewidth=1.0, linestyle="--")
            plot_ax.axhline(const.ALIM_3V3_ADU[1], color="red", linewidth=1.0, linestyle="--")

            labels["plot_1v5"] = ui.line_plot(n=1, limit=20, figsize=(9, 2), update_every=1)
            plot_ax = labels["plot_1v5"].fig.axes[0]
            plot_ax.set_title("1V5 Voltage (ADU)")
            plot_ax.lines[0].set_marker("x")
            plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)
            plot_ax.axhline(const.WLIM_1V5_ADU[0], color="orange", linewidth=1.0, linestyle="--")
            plot_ax.axhline(const.WLIM_1V5_ADU[1], color="orange", linewidth=1.0, linestyle="--")
            plot_ax.axhline(const.ALIM_1V5_ADU[0], color="red", linewidth=1.0, linestyle="--")
            plot_ax.axhline(const.ALIM_1V5_ADU[1], color="red", linewidth=1.0, linestyle="--")

        with ui.row(align_items="center"):
            ui.label("Temps")
            for key in temp_series_order:
                ui.checkbox(key, value=True, on_change=lambda event, k=key: set_temp_visibility(k, event.value))

        labels["plot_temps"] = ui.line_plot(n=4, limit=40, figsize=(20, 2.5), update_every=1).with_legend(
            ["DIG", "DET", "MECH", "MOT"], loc="upper right", ncol=1
        )
        plot_ax = labels["plot_temps"].fig.axes[0]
        plot_ax.set_title("Temperatures (ADU)")
        plot_ax.lines[0].set_marker("o")
        plot_ax.lines[1].set_marker("^")
        plot_ax.lines[2].set_marker("2")
        plot_ax.lines[3].set_marker("x")
        plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)
        plot_ax.axhline(const.WLIM_TPR_ADU[0], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.WLIM_TPR_ADU[1], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_TPR_ADU[0], color="red", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_TPR_ADU[1], color="red", linewidth=1.0, linestyle="--")

        with ui.tabs().classes("w-full") as tabs:
            heater_tab = ui.tab("Heater Control")
            motor_tab = ui.tab("Motor Control")
            detec_tab = ui.tab("Detector Control")

        with ui.tab_panels(tabs, value=heater_tab).classes("w-full"):
            with ui.tab_panel(heater_tab):
                with ui.row():
                    ui.label("Man Heater Controls")
                    with ui.button_group():
                        # TODO Replace with check boxes that update based on HK
                        ui.button("Disable Both", on_click=lambda: guarded_tc(tc.heater_control))
                        ui.button("Enable Mech", on_click=lambda: guarded_tc(tc.heater_control, htr_mech_man=True))
                        ui.button("Enable Det", on_click=lambda: guarded_tc(tc.heater_control, htr_detec_man=True))
                        ui.button(
                            "Enable Both",
                            on_click=lambda: guarded_tc(tc.heater_control, htr_mech_man=True, htr_detec_man=True),
                        )

            with ui.tab_panel(motor_tab):
                mtr_steps = ui.number(
                    label="mech_steps",
                    value=100,
                    format="%d",
                    min=1,
                    max=10000,
                    precision=0,
                    step=10,
                    on_change=lambda e: mtr_steps_label.set_text(f"MTR Step CMD: {int(e.value)} steps"),
                )
                mtr_steps_label = ui.label("MTR Step CMD: 100 steps")
                ui.button(f"Move Pos", on_click=lambda: guarded_tc(tc.mtr_mov_pos, int(mtr_steps.value)))
                ui.button(f"Move Neg", on_click=lambda: guarded_tc(tc.mtr_mov_neg, int(mtr_steps.value)))
                ui.button("HALT", on_click=lambda: guarded_tc(tc.mtr_halt))
                home_cal = ui.checkbox("HOME_CAL")
                home_dir = ui.checkbox("HOME_DIR")
                ui.button(
                    "Home",
                    on_click=lambda: guarded_tc(
                        tc.mtr_homing,
                        home_cal=home_cal.value,
                        home_dir=home_dir.value,
                    ),
                )

            with ui.tab_panel(detec_tab):
                ui.button("Request SCI", on_click=lambda: guarded_tc(tc.sci_request, 8, 100))
                with ui.grid(columns=3):
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
                        on_click=lambda: guarded_tc(
                            tc.sci_offset, int(swir_dac_offset.value), int(mwir_dac_offset.value)
                        ),
                    )

        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            ui.button("shutdown", on_click=stop_and_shutdown)

        with ui.page_sticky(position="top-right", x_offset=20, y_offset=20):
            ui.button(icon="menu", on_click=lambda: right_drawer.toggle())

        # 3. Prevent memory leaks by removing handler on disconnect
        ui.context.client.on_disconnect(lambda: logger.removeHandler(handler))

        update_hk_display()


# TODO! Show status of PSU connection
# TODO! Create a monitoring thread
# TODO! Add a mechanism interface
# TODO! Add a sci acquisition interface
