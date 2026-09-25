from utility_modules import ebtcs, tc
from widget_modules import console_input_widget, ui_runtime_controller


def test_resolve_command_handler_prefers_ob_backend_in_ob_mode() -> None:
    handler = console_input_widget._resolve_command_handler({"mode": "OB"}, "HK_Request")

    assert handler is tc.hk_request


def test_resolve_command_handler_prefers_eb_backend_in_eb_mode() -> None:
    handler = console_input_widget._resolve_command_handler({"mode": "EB"}, "HK_Request")

    assert handler is ebtcs.hk_request


def test_parse_command_params_accepts_space_and_comma_separators() -> None:
    assert console_input_widget._parse_command_params("1 2 3") == [1, 2, 3]
    assert console_input_widget._parse_command_params("1,2,3") == [1, 2, 3]
    assert console_input_widget._parse_command_params('"hello world" 0x03 true') == ["hello world", 3, True]


def test_dispatch_ob_tc_rejects_missing_serial_handle(monkeypatch) -> None:
    notifications = []
    called = False

    def command(_port):
        nonlocal called
        called = True

    monkeypatch.setattr(
        ui_runtime_controller.ui, "notify", lambda *args, **kwargs: notifications.append((args, kwargs))
    )

    result = ui_runtime_controller.dispatch_ob_tc({"ob_port": object()}, command)

    assert result == "ERROR"
    assert called is False
    assert notifications


def test_dispatch_ob_tc_rejects_worker_with_missing_port(monkeypatch) -> None:
    notifications = []

    class Worker:
        port = None

        def submit(self, *_args, **_kwargs):
            raise AssertionError("worker should not receive command without a serial port")

    monkeypatch.setattr(
        ui_runtime_controller.ui, "notify", lambda *args, **kwargs: notifications.append((args, kwargs))
    )

    result = ui_runtime_controller.dispatch_ob_tc({"ob_port": object(), "ob_worker": Worker()}, lambda _port: None)

    assert result == "ERROR"
    assert notifications
