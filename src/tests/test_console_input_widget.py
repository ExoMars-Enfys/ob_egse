from utility_modules import ebtcs, tc
from widget_modules import console_input_widget


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
