"""Regression tests: EB faults must still trigger MMS while INST_VOLTAGE_TEST masks are active.

INST_VOLTAGE_TEST runs without an OB attached, so it masks the OB limit checks,
OB_UNRESPONSIVE and the RS485 error flags. These tests run the real script with
hardware calls stubbed, inject faulted HK at the script's pause point (when the
masks are live) and assert that every EB out-of-bounds condition and every
unmasked EB error still produces an MMS trigger.
"""

import asyncio
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from core_modules import constants as const
from core_modules import tmstruct
from scripts_modules import INST_VOLTAGE_TEST as ivt
from widget_modules import monitoring_limits
from widget_modules import ui_runtime_controller as urc

MMS_LIMITS = monitoring_limits.mms_alarm_limits()

# Nominal EB readings, all comfortably inside the MMS alarm limits.
NOMINAL_EB = {
    "EB_MEAS_MAIN_12V": 12.0,
    "EB_MEAS_MAIN_NEG12V": -12.0,
    "EB_MEAS_5V": 5.0,
    "EB_MEAS_3V3": 3.3,
    "EB_MCU_INTERNAL_TEMP": 25.0,
    "EB_INTERNAL_TRP_TEMP": 25.0,
    "EB_PSU_BOARD_TEMP": 25.0,
    "EB_MEAS_TEC_RAIL": 1.0,
}

# With no OB attached every OB channel reads out of limits.
NO_OB_READINGS = {
    "OB_3V3_VOLTAGE": 0.0,
    "OB_1V5_VOLTAGE": 0.0,
    "OB_DIGITAL_TRP": 999.0,
    "OB_DETECTOR_TRP": 999.0,
    "OB_MECHANISM_TRP": 999.0,
    "OB_MOTOR_TRP": 999.0,
}

INST_VOLTAGE_MASKED_FLAGS = {"OB_UNRESPONSIVE", "RS485_RECEIVE_ERROR", "RS485_TRANSMIT_ERROR"}
ALL_EB_ERROR_FLAGS = [name for name, _ in tmstruct.eb_warning_flags if name != "RESERVED"]
UNMASKED_EB_ERROR_FLAGS = [name for name in ALL_EB_ERROR_FLAGS if name not in INST_VOLTAGE_MASKED_FLAGS]

EB_MMS_FIELDS = [
    (label, field, limit_key) for label, field, limit_key, _tec in urc._MMS_FIELDS if not label.startswith("OB ")
]


def _eb_out_of_bounds_cases() -> list[Any]:
    cases = []
    for label, field, limit_key in EB_MMS_FIELDS:
        low, high = MMS_LIMITS[limit_key]
        if low is not None:
            cases.append(pytest.param(label, field, low - 0.1, id=f"{field}-below"))
        if high is not None:
            cases.append(pytest.param(label, field, high + 0.1, id=f"{field}-above"))
    return cases


def _hk(
    readings: dict[str, float] | None = None,
    error_flags: set[str] | None = None,
    post_error_flags: int = 0,
) -> SimpleNamespace:
    active = set(error_flags or ())
    bits = SimpleNamespace(**{name: int(name in active) for name, _ in tmstruct.eb_warning_flags})
    return SimpleNamespace(
        # OB 5V enabled and not SAFE, so only the explicit mask can suppress OB checks.
        INSTRUMENT_STATUS_FLAGS=(1 << 10),
        CURRENT_OPERATING_STATE=0x04,
        POST_ERROR_FLAGS=post_error_flags,
        ERROR_FLAGS=int(bool(active)),
        ERROR_FLAGS_BITS=bits,
        ERRORS=None,
        MTR_ERRORS=None,
        OB_LAST_ERROR=0,
        OB_MOTOR_ERROR=0,
        _readings={**NOMINAL_EB, **NO_OB_READINGS, **(readings or {})},
    )


@pytest.fixture
def inst_voltage_harness(monkeypatch):
    """Run INST_VOLTAGE_TEST with stubbed hardware; ``on_pause`` runs while its masks are live."""
    monkeypatch.setattr(urc, "decoded", lambda packet, field: packet._readings.get(field))
    # Pin the global masks to their defaults so the script is the only thing changing them.
    monkeypatch.setattr(const, "MMS_MASK_OB_GENERAL_ERROR", False)
    monkeypatch.setattr(const, "MMS_EB_ONLY_TEST_MODE", False)
    monkeypatch.setattr(const, "MMS_MASK_OB_LIMIT_CHECKS", False)
    monkeypatch.setattr(const, "MMS_MASK_OB_UNRESPONSIVE", False)
    monkeypatch.setattr(const, "MMS_MASK_RS485_ERRORS", False)

    monkeypatch.setattr(ivt.eb_interface, "get_egse_interface", lambda: object())
    for name in ("standby", "ret", "hk_request", "safe"):
        monkeypatch.setattr(ivt.ebtcs, name, lambda *_args, **_kwargs: "OK")
    monkeypatch.setattr(ivt, "switch_psu", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ivt.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(urc, "notify_script_done", lambda: None)

    def _run(on_pause: Callable[[], Any]) -> list[Any]:
        results: list[Any] = []

        def _pause(*_args, **_kwargs) -> None:
            assert const.MMS_MASK_OB_LIMIT_CHECKS is True
            assert const.MMS_MASK_OB_UNRESPONSIVE is True
            assert const.MMS_MASK_RS485_ERRORS is True
            results.append(on_pause())

        monkeypatch.setattr(urc, "request_force_pause", _pause)
        ivt.run_inst_voltage_test(psu_port=object(), psu_lock=None)
        assert results, "INST_VOLTAGE_TEST never reached a pause point"
        return results

    return _run


def _reasons_during_test(harness, hk: SimpleNamespace) -> list[str]:
    reasons, _tec, _ob5v = harness(lambda: urc.mms_reasons(hk, MMS_LIMITS))[0]
    return reasons


def test_nominal_eb_without_ob_does_not_trigger_mms(inst_voltage_harness) -> None:
    hk = _hk(error_flags=INST_VOLTAGE_MASKED_FLAGS)

    assert _reasons_during_test(inst_voltage_harness, hk) == []


def test_masks_are_restored_after_test(inst_voltage_harness) -> None:
    hk = _hk(error_flags=INST_VOLTAGE_MASKED_FLAGS)
    inst_voltage_harness(lambda: None)

    assert const.MMS_MASK_OB_LIMIT_CHECKS is False
    assert const.MMS_MASK_OB_UNRESPONSIVE is False
    assert const.MMS_MASK_RS485_ERRORS is False
    reasons, _tec, ob5v_pre_action = urc.mms_reasons(hk, MMS_LIMITS)
    assert any(reason.startswith("OB ") for reason in reasons)
    assert any("OB_UNRESPONSIVE" in reason for reason in reasons)
    assert ob5v_pre_action is True


@pytest.mark.parametrize("raise_error", [False, True])
def test_script_mask_context_preserves_previous_masks_and_session_mode(monkeypatch, raise_error) -> None:
    monkeypatch.setattr(const, "MMS_EB_ONLY_TEST_MODE", True)
    monkeypatch.setattr(const, "MMS_MASK_OB_LIMIT_CHECKS", True)
    monkeypatch.setattr(const, "MMS_MASK_OB_UNRESPONSIVE", False)
    monkeypatch.setattr(const, "MMS_MASK_RS485_ERRORS", True)

    def _enter():
        with ivt.inst_voltage_mms_masks():
            assert const.MMS_MASK_OB_UNRESPONSIVE is True
            if raise_error:
                raise RuntimeError("test abort")

    if raise_error:
        with pytest.raises(RuntimeError, match="test abort"):
            _enter()
    else:
        _enter()

    assert const.MMS_EB_ONLY_TEST_MODE is True
    assert const.MMS_MASK_OB_LIMIT_CHECKS is True
    assert const.MMS_MASK_OB_UNRESPONSIVE is False
    assert const.MMS_MASK_RS485_ERRORS is True


@pytest.mark.parametrize(("label", "field", "value"), _eb_out_of_bounds_cases())
def test_eb_out_of_bounds_still_triggers_mms(inst_voltage_harness, label, field, value) -> None:
    hk = _hk(readings={field: value}, error_flags=INST_VOLTAGE_MASKED_FLAGS)

    reasons = _reasons_during_test(inst_voltage_harness, hk)

    assert len(reasons) == 1
    assert reasons[0].startswith(f"{label} out of limits: value={value}")


def test_eb_tec_rail_out_of_bounds_requests_tec_pre_action(inst_voltage_harness) -> None:
    _low, high = MMS_LIMITS["eb_tec_rail_v"]
    hk = _hk(readings={"EB_MEAS_TEC_RAIL": high + 0.1})

    reasons, tec_pre_action, ob5v_pre_action = inst_voltage_harness(lambda: urc.mms_reasons(hk, MMS_LIMITS))[0]

    assert reasons and reasons[0].startswith("EB TEC rail out of limits")
    assert tec_pre_action is True
    assert ob5v_pre_action is False


@pytest.mark.parametrize("flag", UNMASKED_EB_ERROR_FLAGS)
def test_unmasked_eb_error_flag_still_triggers_mms(inst_voltage_harness, flag) -> None:
    hk = _hk(error_flags=INST_VOLTAGE_MASKED_FLAGS | {flag})

    reasons = _reasons_during_test(inst_voltage_harness, hk)

    assert reasons == [f"HK Error Flags asserted: {flag}"]


@pytest.mark.parametrize("flag", sorted(INST_VOLTAGE_MASKED_FLAGS))
def test_masked_flags_alone_do_not_trigger_mms(inst_voltage_harness, flag) -> None:
    hk = _hk(error_flags={flag})

    assert _reasons_during_test(inst_voltage_harness, hk) == []


def test_post_error_flags_still_trigger_mms(inst_voltage_harness) -> None:
    hk = _hk(error_flags=INST_VOLTAGE_MASKED_FLAGS, post_error_flags=0x0001)

    assert _reasons_during_test(inst_voltage_harness, hk) == ["POST Error Flags asserted"]


def test_eb_fault_during_test_aborts_script_and_shuts_down_psu(inst_voltage_harness, monkeypatch) -> None:
    calls = {"abort": 0, "safe": 0, "ret": 0, "shutdown": 0, "ob5v": 0}

    class _Interface:
        def wait_for_safe_state(self, *_args, **_kwargs) -> bool:
            return True

    async def _io_bound(func):
        return func()

    def _count(name: str, result: Any = None) -> Callable[..., Any]:
        def _call(*_args, **_kwargs) -> Any:
            calls[name] += 1
            return result

        return _call

    monkeypatch.setattr(urc.run, "io_bound", _io_bound)
    monkeypatch.setattr(urc.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(urc, "is_script_running", lambda: True)
    monkeypatch.setattr(urc, "request_abort", _count("abort"))
    monkeypatch.setattr(urc, "clear_pause", lambda: None)
    monkeypatch.setattr(urc, "clear_force_pause", lambda: None)
    monkeypatch.setattr(urc, "disable_ob5v", _count("ob5v"))
    monkeypatch.setattr(urc.eb_interface, "get_egse_interface", lambda: _Interface())
    monkeypatch.setattr(urc.ebtcs, "safe", _count("safe", "OK"))
    monkeypatch.setattr(urc.ebtcs, "ret", _count("ret", "OK"))
    monkeypatch.setattr(urc.psu, "shutdown_psu_outputs", _count("shutdown"))

    _low, high = MMS_LIMITS["eb_12v"]
    hk = _hk(readings={"EB_MEAS_MAIN_12V": high + 0.1}, error_flags=INST_VOLTAGE_MASKED_FLAGS | {"GENERAL_ERROR"})
    state = {"mode": "EB", "psu_port": object(), "mms": {"enabled": True}}
    app = SimpleNamespace(state=SimpleNamespace(eb_interface=SimpleNamespace(rs422_log_path=None)))

    def _trigger_mms() -> tuple[list[str], dict[str, int]]:
        reasons, tec_pre_action, ob5v_pre_action = urc.mms_reasons(hk, MMS_LIMITS)
        before = dict(calls)
        asyncio.run(urc.mms(app, state, _Logger(), hk, reasons, tec_pre_action, ob5v_pre_action))
        # The script shares ebtcs with MMS, so only count calls made by MMS itself.
        return reasons, {name: calls[name] - before[name] for name in calls}

    reasons, mms_calls = inst_voltage_harness(_trigger_mms)[0]

    assert any(reason.startswith("EB +12V out of limits") for reason in reasons)
    assert "HK Error Flags asserted: GENERAL_ERROR" in reasons
    assert mms_calls == {"abort": 1, "safe": 1, "ret": 1, "shutdown": 1, "ob5v": 0}
    assert state["mms"]["latched"] is True
    assert state["mms"]["reasons"] == reasons


class _Logger:
    def warning(self, *_args, **_kwargs) -> None:
        pass

    info = error = exception = warning
