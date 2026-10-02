"""Tests for the live GUI MMS mask script, with the GUI HK poll loop simulated."""

from queue import Empty, Queue
from types import SimpleNamespace

import pytest

from core_modules import constants as const
from core_modules import tmstruct
from scripts_modules import MMS_MASK_LIVE_TEST as live
from widget_modules import monitoring_limits
from widget_modules import ui_runtime_controller as urc

NOMINAL = {
    "EB_MEAS_MAIN_12V": 12.0,
    "EB_MEAS_MAIN_NEG12V": -12.0,
    "EB_MEAS_5V": 5.0,
    "EB_MEAS_3V3": 3.3,
    "EB_MCU_INTERNAL_TEMP": 25.0,
    "EB_INTERNAL_TRP_TEMP": 25.0,
    "EB_PSU_BOARD_TEMP": 25.0,
    "EB_MEAS_TEC_RAIL": 1.0,
    "OB_3V3_VOLTAGE": 0.0,
    "OB_1V5_VOLTAGE": 0.0,
    "OB_DIGITAL_TRP": 999.0,
    "OB_DETECTOR_TRP": 999.0,
    "OB_MECHANISM_TRP": 999.0,
    "OB_MOTOR_TRP": 999.0,
}
CASES = live._cases()


def _live_hk() -> SimpleNamespace:
    """Nominal EB HK with no OB attached: masked flags asserted and OB readings out of limits."""
    flags = set(live.INST_VOLTAGE_MASKED_FLAGS)
    return SimpleNamespace(
        INSTRUMENT_STATUS_FLAGS=(1 << 10),
        CURRENT_OPERATING_STATE=0x04,
        POST_ERROR_FLAGS=0,
        ERROR_FLAGS=live._error_flags_value(flags),
        ERROR_FLAGS_BITS=SimpleNamespace(**{name: int(name in flags) for name, _ in tmstruct.eb_warning_flags}),
        ERRORS=None,
        MTR_ERRORS=None,
        OB_LAST_ERROR=0,
        OB_MOTOR_ERROR=0,
        _readings=dict(NOMINAL),
    )


@pytest.fixture
def gui(monkeypatch):
    """Simulated GUI: each script sleep runs one HK poll tick of the real MMS trigger logic."""
    limits = monitoring_limits.mms_alarm_limits()
    state = {
        "mode": "EB",
        "latest_hk_packet": _live_hk(),
        "mms": {"enabled": True, "latched": False, "in_progress": False, "pending": False, "limits": limits},
    }
    record = {"choice": None, "confirm": True, "notes": [], "masks_seen": []}
    queue = Queue(maxsize=100)

    def _poll_tick(*_args, **_kwargs) -> None:
        hk = state["latest_hk_packet"]  # real HK keeps arriving
        try:
            hk = queue.get_nowait()
        except Empty:
            pass
        record["masks_seen"].append(
            (const.MMS_MASK_OB_LIMIT_CHECKS, const.MMS_MASK_OB_UNRESPONSIVE, const.MMS_MASK_RS485_ERRORS)
        )
        mms_cfg = state["mms"]
        reasons, _tec, _ob5v = urc.mms_reasons(hk, mms_cfg["limits"])
        if mms_cfg["enabled"] and reasons and not mms_cfg["latched"]:
            mms_cfg.update(latched=True, reasons=reasons)

    clock = {"t": 0.0}

    def _monotonic() -> float:
        clock["t"] += live.INJECT_PERIOD_S
        return clock["t"]

    monkeypatch.setattr(urc, "decoded", lambda packet, field: packet._readings.get(field))
    monkeypatch.setattr(urc, "is_aborted", lambda: False)
    monkeypatch.setattr(const, "hk_queue", queue)
    monkeypatch.setattr(const, "MMS_MASK_OB_GENERAL_ERROR", False)
    monkeypatch.setattr(const, "MMS_EB_ONLY_TEST_MODE", True)
    monkeypatch.setattr(live.time, "sleep", _poll_tick)
    monkeypatch.setattr(live.time, "monotonic", _monotonic)
    monkeypatch.setattr(urc, "request_choice", lambda *_a, **_k: record["choice"])
    monkeypatch.setattr(urc, "request_confirmation", lambda *_a, **_k: record["confirm"])
    monkeypatch.setattr(urc, "notify", lambda msg, color="primary": record["notes"].append((color, msg)))
    return SimpleNamespace(state=state, record=record, limits=limits)


def _run(gui, case: live.Case) -> tuple[str, str]:
    gui.record["choice"] = case.title
    live.run_mms_mask_live_test(gui.state)
    return next(note for note in reversed(gui.record["notes"]) if note[0] != "warning")


@pytest.mark.parametrize("case", [c for c in CASES if c.kind != "control"], ids=lambda c: c.title)
def test_each_fault_case_triggers_mms_and_restores(gui, case) -> None:
    color, message = _run(gui, case)

    assert color == "positive", message
    assert message.startswith("PASS")
    assert any(r.startswith(case.expected_reason) for r in gui.state["mms"]["reasons"])
    assert gui.record["masks_seen"] and all(seen == (True, True, True) for seen in gui.record["masks_seen"])
    assert gui.state["mms"]["limits"] is gui.limits
    assert gui.state["mms"]["enabled"] is True
    assert const.MMS_EB_ONLY_TEST_MODE is True
    assert (const.MMS_MASK_OB_LIMIT_CHECKS, const.MMS_MASK_OB_UNRESPONSIVE, const.MMS_MASK_RS485_ERRORS) == (
        False,
        False,
        False,
    )


def test_control_case_does_not_trip(gui) -> None:
    color, message = _run(gui, next(c for c in CASES if c.kind == "control"))

    assert color == "positive", message
    assert gui.state["mms"]["latched"] is False


def test_test_mode_required_before_running(gui, monkeypatch) -> None:
    monkeypatch.setattr(const, "MMS_EB_ONLY_TEST_MODE", False)

    color, message = _run(gui, next(c for c in CASES if c.kind == "control"))

    assert color == "negative"
    assert "Select EB-only" in message
    assert gui.state["mms"]["enabled"] is True


def test_session_mode_masks_no_ob_faults_before_script_runs(gui) -> None:
    reasons, _tec, _ob5v = urc.mms_reasons(gui.state["latest_hk_packet"], gui.limits)

    assert reasons == []
    assert gui.state["mms"]["enabled"] is True


def test_limit_case_without_live_reading_is_aborted(gui) -> None:
    case = next(c for c in CASES if c.kind == "limit")
    gui.state["latest_hk_packet"]._readings[case.field] = None

    color, message = _run(gui, case)

    assert color == "negative"
    assert gui.state["mms"]["latched"] is False
    assert "no live reading" in message


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"mode": "OB"}, "EB mode"),
        ({"mms_enabled": False}, "Enable MMS"),
        ({"pending": True}, "still active"),
        ({"latched": True}, "Reset Latch"),
        ({"latest_hk_packet": None}, "No EB HK"),
    ],
)
def test_preflight_blocks_unsafe_runs(gui, change, expected) -> None:
    if "mode" in change:
        gui.state["mode"] = change["mode"]
    if "mms_enabled" in change:
        gui.state["mms"]["enabled"] = change["mms_enabled"]
    if "pending" in change:
        gui.state["mms"]["pending"] = True
    if "latched" in change:
        gui.state["mms"]["latched"] = True
    if "latest_hk_packet" in change:
        gui.state["latest_hk_packet"] = None

    color, message = _run(gui, CASES[0])

    assert color == "negative"
    assert expected in message


def test_cancelled_confirmation_changes_nothing(gui) -> None:
    gui.record["confirm"] = False

    _run(gui, CASES[0])

    assert gui.state["mms"]["latched"] is False
    assert gui.state["mms"]["limits"] is gui.limits
    assert gui.record["masks_seen"] == []


def test_mms_remains_enabled_during_selection_and_cleanup(gui, monkeypatch) -> None:
    def _choose(*_args, **_kwargs):
        assert gui.state["mms"]["enabled"] is True
        assert urc.mms_reasons(gui.state["latest_hk_packet"], gui.limits)[0] == []
        return CASES[0].title

    def _confirm(*_args, **_kwargs):
        assert gui.state["mms"]["enabled"] is True
        return True

    monkeypatch.setattr(urc, "request_choice", _choose)
    monkeypatch.setattr(urc, "request_confirmation", _confirm)

    color, message = _run(gui, CASES[0])

    assert color == "positive", message
    assert gui.state["mms"]["latched"] is True
    assert gui.state["mms"]["enabled"] is True


def test_rechecks_latch_after_selection(gui, monkeypatch) -> None:
    def _confirm(*_args, **_kwargs):
        gui.state["mms"]["latched"] = True
        return True

    monkeypatch.setattr(urc, "request_confirmation", _confirm)

    color, message = _run(gui, CASES[0])

    assert color == "negative"
    assert "Cannot arm" in message
    assert gui.state["mms"]["enabled"] is True
    assert gui.record["masks_seen"] == []


def test_existing_fault_aborts_before_inducing(gui) -> None:
    gui.state["latest_hk_packet"]._readings["EB_MEAS_MAIN_12V"] = 20.0

    color, message = _run(gui, CASES[1])

    assert color == "negative"
    assert "already present" in message
    assert gui.state["mms"]["latched"] is False


def test_turning_mode_off_restores_no_ob_triggers(gui, monkeypatch) -> None:
    monkeypatch.setattr(urc, "is_script_running", lambda: False)

    urc.set_eb_only_test_mode(gui.state, False)
    reasons, _tec, _ob5v = urc.mms_reasons(gui.state["latest_hk_packet"], gui.limits)

    assert any(r.startswith("OB FPGA") for r in reasons)
    assert any("OB_UNRESPONSIVE" in r for r in reasons)
    assert gui.state["mms"]["enabled"] is True


def test_enabling_mode_preserves_mms_and_trip_latch(gui, monkeypatch) -> None:
    monkeypatch.setattr(const, "MMS_EB_ONLY_TEST_MODE", False)
    monkeypatch.setattr(urc, "is_script_running", lambda: False)
    gui.state["mms"]["latched"] = True

    urc.set_eb_only_test_mode(gui.state, True)

    assert const.MMS_EB_ONLY_TEST_MODE is True
    assert gui.state["mms"]["enabled"] is True
    assert gui.state["mms"]["latched"] is True
    assert urc.mms_reasons(gui.state["latest_hk_packet"], gui.limits)[0] == []


@pytest.mark.parametrize("busy", ["script", "pending", "in_progress"])
def test_mode_change_blocked_during_script_or_shutdown(gui, monkeypatch, busy) -> None:
    monkeypatch.setattr(urc, "is_script_running", lambda: busy == "script")
    if busy != "script":
        gui.state["mms"][busy] = True

    with pytest.raises(RuntimeError, match="finish"):
        urc.set_eb_only_test_mode(gui.state, False)

    assert const.MMS_EB_ONLY_TEST_MODE is True


def test_cannot_enable_test_mode_in_standalone_ob_mode(gui, monkeypatch) -> None:
    monkeypatch.setattr(const, "MMS_EB_ONLY_TEST_MODE", False)
    gui.state["mode"] = "OB"

    with pytest.raises(RuntimeError, match="Select EB mode"):
        urc.set_eb_only_test_mode(gui.state, True)

    assert const.MMS_EB_ONLY_TEST_MODE is False


def test_restores_limits_after_operator_abort_without_disabling_mms(gui, monkeypatch) -> None:
    monkeypatch.setattr(urc, "is_aborted", lambda: True)

    with pytest.raises(urc.ScriptAbortRequested):
        _run(gui, CASES[0])

    assert gui.state["mms"]["limits"] is gui.limits
    assert gui.state["mms"]["enabled"] is True
    assert const.MMS_EB_ONLY_TEST_MODE is True
