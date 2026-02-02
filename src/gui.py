from nicegui import app, ui
import scripts.abu_sequences as abu


def build_ui(ob_port) -> None:
    @ui.page("/")
    def index() -> None:
        ui.label("Hello, NiceGUI!")
        ui.button("shutdown", on_click=app.shutdown)
        ui.button("Request HK", on_click=lambda: abu.read_hk(ob_port))
