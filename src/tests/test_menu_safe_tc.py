import asyncio
import logging
import threading

import pytest

from widget_modules import menu_widget


@pytest.mark.parametrize("visible", [False, True])
def test_mms_live_script_visibility_uses_config_flag(monkeypatch, visible) -> None:
    monkeypatch.setattr(menu_widget.config, "SHOW_MMS_TEST_TOOLS", visible)

    scripts = menu_widget._discover_eb_scripts()

    assert ("mms_mask_live_test" in scripts) is visible
    assert "inst_voltage_test" in scripts


@pytest.mark.parametrize("result", [None, "ERROR"])
def test_manual_safe_runs_off_ui_thread_and_reports_result(monkeypatch, result) -> None:
    ui_thread = threading.get_ident()
    send_threads: list[int] = []
    notifications: list[tuple[str, str]] = []
    interface = object()

    def safe(actual_interface, source):
        assert actual_interface is interface
        assert source == 0
        send_threads.append(threading.get_ident())
        return result

    monkeypatch.setattr(menu_widget.eb_interface, "get_egse_interface", lambda: interface)
    monkeypatch.setattr(menu_widget.ebtcs, "safe", safe)
    monkeypatch.setattr(menu_widget.run, "io_bound", asyncio.to_thread)
    monkeypatch.setattr(
        menu_widget.ui, "notify", lambda message, *, type: notifications.append((message, type))
    )

    asyncio.run(menu_widget._send_safe_tc({"logger": logging.getLogger(__name__)}))

    assert len(send_threads) == 1
    assert send_threads[0] != ui_thread
    assert notifications == (
        [("Failed to send SAFE TC", "negative")] if result == "ERROR" else [("SAFE TC sent", "positive")]
    )


def test_manual_safe_reports_exception(monkeypatch, caplog) -> None:
    notifications: list[str] = []

    def get_interface():
        raise RuntimeError("CmdTool unavailable")

    monkeypatch.setattr(menu_widget.eb_interface, "get_egse_interface", get_interface)
    monkeypatch.setattr(menu_widget.run, "io_bound", asyncio.to_thread)
    monkeypatch.setattr(menu_widget.ui, "notify", lambda message, **_kwargs: notifications.append(message))

    asyncio.run(menu_widget._send_safe_tc({"logger": logging.getLogger(__name__)}))

    assert notifications == ["Failed to send SAFE TC"]
    assert "CmdTool unavailable" in caplog.text
