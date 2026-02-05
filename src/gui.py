import logging
from contextlib import nullcontext
from pathlib import Path
from nicegui import app, ui
from matplotlib import dates as mdates
from matplotlib.ticker import FuncFormatter


import constants as const
import tc

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


def build_ui(ob_port, port_lock=None) -> None:
    rsrc_dir = Path(__file__).resolve().parent.parent / "rsrc"
    app.add_static_files("/rsrc", rsrc_dir)
    labels: dict[str, ui.label] = {}
    status: dict[str, int] = {"pwr": 0}
    lock_ctx = port_lock if port_lock is not None else nullcontext()

    def guarded_tc(func, *args, **kwargs):
        with lock_ctx:
            return func(ob_port, *args, **kwargs)

    def update_hk_display() -> None:
        def poll_latest_hk() -> None:
            if not const.hk_queue.empty():
                hk = const.hk_queue.get()

                labels["plot_3v3"].push(
                    [hk.TIME],
                    [[hk.HK_V_3V3]],
                    y_limits=(
                        hk.HK_V_3V3 - 20 if hk.HK_V_3V3 < 1400 else 1400,
                        hk.HK_V_3V3 + 20 if hk.HK_V_3V3 > 1900 else 1900,
                    ),
                )

                labels["plot_1v5"].push(
                    [hk.TIME],
                    [[hk.HK_V_1V5]],
                    y_limits=(
                        hk.HK_V_1V5 - 20 if hk.HK_V_1V5 < 1330 else 1330,
                        hk.HK_V_1V5 + 20 if hk.HK_V_1V5 > 1670 else 1670,
                    ),
                )

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

        ui.timer(0.2, poll_latest_hk)

    # Decorator needed to allow nicegui to properly route to the index page
    @ui.page("/")
    def index() -> None:
        ui.button("Request HK", on_click=lambda: guarded_tc(tc.hk_request))

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
            ui.image("/rsrc/Enfys_logo.jpg")
            ui.markdown("**Enfys OB EGSE GUI v0.3**")

            with ui.row(align_items="center"):
                with ui.card():
                    ui.markdown("**CMD CNT**")
                    labels["cmd_cnt"] = ui.label("---")

                with ui.card():
                    ui.markdown("**3V3**")
                    labels["3v3"] = ui.label("---")

                with ui.card():
                    ui.markdown("**1V5**")
                    labels["1v5"] = ui.label("---")

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

            ui.markdown("**HEATER STATUS**")

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
                ui.button("Display Log Terminal", on_click=footer.toggle)

        labels["plot_3v3"] = ui.line_plot(n=1, limit=20, figsize=(10, 2), update_every=1)
        plot_ax = labels["plot_3v3"].fig.axes[0]
        plot_ax.lines[0].set_marker("2")
        plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)
        plot_ax.axhline(const.WLIM_3V3_ADU[0], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.WLIM_3V3_ADU[1], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_3V3_ADU[0], color="red", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_3V3_ADU[1], color="red", linewidth=1.0, linestyle="--")

        labels["plot_1v5"] = ui.line_plot(n=1, limit=20, figsize=(10, 2), update_every=1)
        plot_ax = labels["plot_1v5"].fig.axes[0]
        plot_ax.lines[0].set_marker("2")
        plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)
        plot_ax.axhline(const.WLIM_1V5_ADU[0], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.WLIM_1V5_ADU[1], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_1V5_ADU[0], color="red", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_1V5_ADU[1], color="red", linewidth=1.0, linestyle="--")

        ui.button("Enable Mech HTR", on_click=lambda: guarded_tc(tc.heater_control, htr_mech_man=True))

        ui.button("Move Motor 1000 steps", on_click=lambda: guarded_tc(tc.mtr_mov_pos, 1000))

        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            ui.button("shutdown", on_click=app.shutdown)

        # 3. Prevent memory leaks by removing handler on disconnect
        ui.context.client.on_disconnect(lambda: logger.removeHandler(handler))

        update_hk_display()


# TODO! Show status of PSU connection
# TODO! Plot of temperatures
# TODO! Create a monitoring thread
# TODO! Add a mechanism interface
# TODO! Add a sci acquisition interface
