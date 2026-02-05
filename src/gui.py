from pathlib import Path
from nicegui import app, ui
from matplotlib import dates as mdates
from matplotlib.ticker import FuncFormatter


import constants as const
import tc


def build_ui(ob_port) -> None:
    rsrc_dir = Path(__file__).resolve().parent.parent / "rsrc"
    app.add_static_files("/rsrc", rsrc_dir)
    labels: dict[str, ui.label] = {}
    status: dict[str, int] = {"pwr": 0}

    def update_hk_display(plot_3v3) -> None:
        def poll_latest_hk() -> None:
            if const.hk_queue:
                hk = const.hk_queue.pop()
                plot_3v3.push([hk.TIME], [[hk.CMD_CNT]])

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
        ui.button("shutdown", on_click=app.shutdown)
        ui.button("Request HK", on_click=lambda: tc.hk_request(ob_port))

        with ui.left_drawer(top_corner=True, bottom_corner=True).style("background-color: #d7e3f4"):
            ui.image("/rsrc/Enfys_logo.jpg")  # .style("width: 150px; margin-bottom: 20px;")
            ui.markdown("**Enfys OB EGSE GUI v0.2**")

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
                    on_click=lambda: tc.power_control(ob_port, status["pwr"] ^ 0x01),
                )
                labels["DET_PWR"] = ui.button(
                    "DET PWR", on_click=lambda: tc.power_control(ob_port, status["pwr"] ^ 0x02)
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
        plot_3v3 = ui.line_plot(n=1, limit=20, figsize=(10, 2), update_every=1)
        plot_3v3.fig.axes[0].lines[0].set_marker("2")

        def fmt_time(x, _pos) -> str:
            dt = mdates.num2date(x)
            return dt.strftime("%M:%S.") + f"{dt.microsecond // 100000:1d}"

        ui.button("Enable Mech HTR", on_click=lambda: tc.heater_control(ob_port, htr_mech_man=True))

        ui.button("Move Motor 1000 steps", on_click=lambda: tc.mtr_mov_pos(ob_port, 1000))

        plot_3v3.fig.axes[0].xaxis.set_major_formatter(FuncFormatter(fmt_time))

        update_hk_display(plot_3v3)
