from datetime import datetime
from nicegui import app, ui
from matplotlib import dates as mdates
from matplotlib.ticker import FuncFormatter


import constants as const
import tc


def build_ui(ob_port) -> None:
    labels: dict[str, ui.label] = {}

    def update_hk_display(plot_3v3) -> None:
        def poll_latest_hk() -> None:
            if const.hk_queue:
                hk = const.hk_queue.pop()
                plot_3v3.push([hk.TIME], [[hk.CMD_CNT]])

                if "cmd_cnt" in labels:
                    labels["cmd_cnt"].set_text(f"CMD_CNT: {hk.CMD_CNT}")
                if "3v3" in labels:
                    labels["3v3"].set_text(f"3V3: {hk.HK_V_3V3} V")

        ui.timer(0.2, poll_latest_hk)

    # Decorator needed to allow nicegui to properly route to the index page
    @ui.page("/")
    def index() -> None:
        ui.label("Enfys EGSE GUI v0.1")
        ui.button("shutdown", on_click=app.shutdown)
        ui.button("Request HK", on_click=lambda: tc.hk_request(ob_port))
        labels["cmd_cnt"] = ui.label("CMD_CNT: --")
        labels["3v3"] = ui.label("3V3: -- V")
        plot_3v3 = ui.line_plot(n=1, limit=20, figsize=(10, 2), update_every=1)
        plot_3v3.fig.axes[0].lines[0].set_marker("2")

        def fmt_time(x, _pos) -> str:
            dt = mdates.num2date(x)
            return dt.strftime("%M:%S.") + f"{dt.microsecond // 100000:1d}"

        plot_3v3.fig.axes[0].xaxis.set_major_formatter(FuncFormatter(fmt_time))

        update_hk_display(plot_3v3)
