from typing import Any

from widget_modules import psu_widget


def test_should_send_ret_tc_for_eb_enable() -> None:
    assert psu_widget.should_send_ret_tc_for_eb_enable("EB", True, 3) is True
    assert psu_widget.should_send_ret_tc_for_eb_enable("EB", True, 4) is True
    assert psu_widget.should_send_ret_tc_for_eb_enable("EB", False, 3) is False
    assert psu_widget.should_send_ret_tc_for_eb_enable("OB", True, 3) is False
    assert psu_widget.should_send_ret_tc_for_eb_enable("EB", True, 1) is False


def test_emit_eb_ret_tc_for_psu_toggle_sends_ret(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    class DummyInterface:
        def send_command_to_cmdtool(self, *args, **kwargs):
            calls["cmd"] = args[0]
            return True

    monkeypatch.setattr(psu_widget.eb_interface, "get_egse_interface", lambda: DummyInterface())

    def fake_ret(interface, *args):
        calls["ret_args"] = (interface, args)
        return "OK"

    monkeypatch.setattr(psu_widget.ebtcs, "ret", fake_ret)

    psu_widget.emit_eb_ret_tc_for_psu_toggle({"mode": "EB"}, enabled=True, physical_channel=4)

    assert calls["ret_args"][1] == (0, 0, 0, 0, 0, 0)


def test_emit_eb_ret_tc_uses_psu_mode_state_when_mode_missing(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    class DummyInterface:
        pass

    monkeypatch.setattr(psu_widget.eb_interface, "get_egse_interface", lambda: DummyInterface())

    def fake_ret(interface, *args):
        calls["ret_args"] = (interface, args)
        return "OK"

    monkeypatch.setattr(psu_widget.ebtcs, "ret", fake_ret)

    psu_widget.emit_eb_ret_tc_for_psu_toggle({"psu_mode_state": {"ebmode": True}}, enabled=True, physical_channel=3)

    assert calls["ret_args"][1] == (0, 0, 0, 0, 0, 0)


def test_emit_eb_ret_tc_for_psu_toggle_skips_non_enable(monkeypatch) -> None:
    called = {"ret": False}

    monkeypatch.setattr(psu_widget.eb_interface, "get_egse_interface", lambda: object())

    def fake_ret(*_args, **_kwargs):
        called["ret"] = True
        return "OK"

    monkeypatch.setattr(psu_widget.ebtcs, "ret", fake_ret)

    psu_widget.emit_eb_ret_tc_for_psu_toggle({"mode": "EB"}, enabled=False, physical_channel=4)

    assert called["ret"] is False
