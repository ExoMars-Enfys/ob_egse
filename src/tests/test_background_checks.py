import threading
from types import SimpleNamespace
from typing import Any

import pytest

from scripts_modules import sci_acq
from utility_modules.background_checks import (
    CommandChecks,
    calculate_ob_current_profile,
    check_current_profile,
    check_dark_science,
    check_hk,
    check_mechanism_current_zero,
    check_mechanism_idle,
    check_science,
    check_motor_hold_current,
    check_motor_params,
    check_ob_state,
    check_powered,
    check_thermal,
    mechanism_current_adu,
    read_psu_channels,
)


def _hk(**overrides):
    values = {
        "ERROR_BYTE": 0,
        "ERROR_MTR": 0,
        "PWR_STAT": 3,
        "THRM_STATUS": SimpleNamespace(DM=1, DA=0, MM=1, MA=0, HDS=1, HMS=1),
        "MTR_FLAGS": SimpleNamespace(MOVING=0, HOMING=0, DIR=0, OUTER=0, BASE=1),
        "MTR_ABS_STEPS": 9640,
        "MTR_REL_STEPS": 20,
        "MTR_CURRENT": 64,
        "MTR_GUARD_SELECT": 0,
        "MTR_CHOP": 60,
        "MTR_SPEED": 8,
        "HK_MECH_CUR": 0,
        "DETEC_TRP": 100,
        "MECH_TRP": 100,
        "MOTOR_TRP": 100,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_generic_hk_power_heater_and_motor_checks_pass():
    response = check_hk(_hk(), label="test")
    check_powered(response, 3)
    check_thermal(response, (False, True, False, True, False))
    check_motor_params(response)


def test_boot_motor_params_are_not_treated_as_nominal():
    response = _hk(MTR_CURRENT=64, MTR_GUARD_SELECT=0, MTR_CHOP=32, MTR_SPEED=9)
    check_motor_params(response, (64, 0, 32, 9))

    with pytest.raises(AssertionError, match=r"expected \(64, 0, 60, 8\)"):
        check_motor_params(response, (64, 0, 60, 8))


def test_check_hk_can_skip_repeat_logging(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "utility_modules.background_checks.info_log.info", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    check_hk(_hk(), label="test", log_result=False)

    assert calls == []


def test_ob_state_uses_active_motor_params():
    response = _hk(
        MTR_CURRENT=20,
        MTR_GUARD_SELECT=0,
        MTR_CHOP=60,
        MTR_SPEED=8,
        PWR_STAT=1,
        THRM_STATUS=SimpleNamespace(DM=0, DA=0, MM=0, MA=0, HDS=0, HMS=0),
    )

    assert check_ob_state(
        response,
        {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.060)},
        "Moving",
        expected_motor_params=(20, 0, 60, 8),
    ) == {"CH1": 18.0, "CH2": 129.0, "CH3": 60.0}


def _science(**overrides):
    values = {
        name: 0
        for name in (
            "MOD_ID",
            "UNUSED1",
            "CMD_ID",
            "CMD_CNT",
            "ERROR_BYTE",
            "MTR_ABS_STEPS",
            "THRM_STATUS_BYTE",
            "SWIR_OFFSET",
            "MWIR_OFFSET",
            "SCI_ADC_SAMPLES",
            "SCI_ADC_SKIP",
            "SWIR_HIGH",
            "SWIR_MED",
            "SWIR_LOW",
            "MWIR_HIGH",
            "MWIR_MED",
            "MWIR_LOW",
            "HT_SINK_TEMP",
            "SWIR_TEMP",
            "CRC",
        )
    }
    values["CMD_ID"] = 0x0F
    values.update(overrides)
    return SimpleNamespace(**values)


def test_science_check_requires_every_tmstruct_field():
    response = _science()

    assert check_science(response, label="test science") is response


def test_science_check_rejects_error_and_wrong_command():
    with pytest.raises(AssertionError, match="ERROR_BYTE=1"):
        check_science(_science(ERROR_BYTE=1, CMD_ID=0), label="test science")


def test_science_check_rejects_out_of_range_science_value():
    with pytest.raises(AssertionError, match="SWIR_HIGH=65536"):
        check_science(_science(SWIR_HIGH=65536), label="test science")


def test_mechanism_current_uses_upper_12_bit_adu_value():
    response = _hk(HK_MECH_CUR=16 * 10)

    assert mechanism_current_adu(response) == 10


def test_mechanism_current_zero_check_reports_adu():
    errors = []
    check_mechanism_current_zero(_hk(HK_MECH_CUR=16 * 6), errors)

    assert errors == ["HK_MECH_CUR not at zero: got 6 ADU, expected <= 5 ADU"]


def test_mechanism_heater_offset_is_not_subtracted_from_net_hk_reading():
    # A heater contribution of about -83 mA is represented by the clipped
    # 0 mA net reading when no positive rail current remains.
    assert mechanism_current_adu(_hk(HK_MECH_CUR=0)) == 0


def test_mechanism_idle_allows_nonzero_idle_current():
    errors = []
    check_mechanism_idle(_hk(HK_MECH_CUR=16 * 130), errors)
    assert errors == []

    errors = []
    check_mechanism_idle(_hk(HK_MECH_CUR=16 * 136), errors)
    assert errors == ["HK_MECH_CUR above idle limit: got 136 ADU, expected <= 135 ADU"]


def test_check_ob_state_uses_zero_threshold_when_mechanism_is_powered_off():
    response = _hk(
        HK_MECH_CUR=16 * 4,
        PWR_STAT=0,
        THRM_STATUS=SimpleNamespace(DM=0, DA=0, MM=0, MA=0, HDS=0, HMS=0),
    )

    assert check_ob_state(
        response,
        {"CH1": (12.0, 0.000), "CH2": (-12.0, 0.000), "CH3": (5.0, 0.060)},
        "State1",
    ) == {"CH1": 0.0, "CH2": 0.0, "CH3": 60.0}


def test_check_ob_state_uses_idle_threshold_for_state5():
    response = _hk(
        HK_MECH_CUR=16 * 128,
        PWR_STAT=3,
        THRM_STATUS=SimpleNamespace(DM=0, DA=0, MM=0, MA=0, HDS=0, HMS=0),
    )

    assert check_ob_state(
        response,
        {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.0), "CH3": (5.0, 0.060)},
        "State5",
    ) == {"CH1": 18.0, "CH2": 0.0, "CH3": 60.0}


def test_motor_hold_current_accepts_phase_dependent_nonzero_current():
    errors = []
    check_motor_hold_current(_hk(HK_MECH_CUR=16 * 6), errors, {"CH1": (12.0, 0.005)})

    assert errors == []


def test_motor_hold_current_rejects_zero_band_current():
    errors = []
    check_motor_hold_current(_hk(HK_MECH_CUR=16 * 5), errors, {"CH1": (12.0, 0.004)})

    assert errors == [
        "HK_MECH_CUR hold current too low: got 5 ADU, expected >= 6 ADU",
        "CH1 motor hold current too low: got 4.00 mA, expected > 4.00 mA",
    ]


def test_last_command_mismatch_is_reported():
    response = _hk(PWR_STAT=1)
    with pytest.raises(AssertionError, match="expected 3"):
        check_powered(response, 3)


def test_move_validates_active_state_while_moving(monkeypatch):
    states = []
    responses = iter(
        [
            _hk(MTR_FLAGS=SimpleNamespace(MOVING=1, HOMING=0, DIR=0, OUTER=0, BASE=0)),
            _hk(MTR_FLAGS=SimpleNamespace(MOVING=1, HOMING=0, DIR=0, OUTER=0, BASE=0)),
            _hk(MTR_FLAGS=SimpleNamespace(MOVING=0, HOMING=0, DIR=0, OUTER=0, BASE=1)),
        ]
    )

    monkeypatch.setattr("utility_modules.background_checks.repeat", lambda *args, **kwargs: None)

    def fake_hk(self, label, **kwargs):
        return next(responses)

    monkeypatch.setattr(CommandChecks, "hk", fake_hk)

    def fake_state(self, state_name, readings, *, response: Any = None, allow_psu_unavailable=False):
        states.append((state_name, bool(response.MTR_FLAGS.MOVING), readings))
        return {"CH1": 18.0, "CH2": 129.0, "CH3": 60.0}

    monkeypatch.setattr(CommandChecks, "state", fake_state)

    checks = CommandChecks(
        None,
        sleep=lambda _: None,
        current_reader=lambda: {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.060)},
    )
    checks.move(
        negative=False,
        steps=100,
        label="turning",
        active_state="Moving",
        expected_motor_params=(20, 0, 60, 8),
    )

    assert states[0][0] == "Moving"
    assert states[0][1] is True
    assert len(states) >= 2


def test_move_validates_all_samples_across_whole_motion(monkeypatch):
    state_calls: list[dict[str, object]] = []
    responses = iter(
        [
            _hk(MTR_FLAGS=SimpleNamespace(MOVING=1, HOMING=0, DIR=0, OUTER=0, BASE=0)),
            _hk(MTR_FLAGS=SimpleNamespace(MOVING=1, HOMING=0, DIR=0, OUTER=0, BASE=0)),
            _hk(MTR_FLAGS=SimpleNamespace(MOVING=0, HOMING=0, DIR=0, OUTER=0, BASE=1)),
        ]
    )

    monkeypatch.setattr("utility_modules.background_checks.repeat", lambda *args, **kwargs: None)

    def fake_hk(self, label, **kwargs):
        return next(responses)

    monkeypatch.setattr(CommandChecks, "hk", fake_hk)

    def fake_state(self, state_name, readings, *, response: Any = None, allow_psu_unavailable=False):
        state_calls.append(
            {"state": state_name, "moving": bool(response.MTR_FLAGS.MOVING), "readings": readings.copy()}
        )
        return {"CH1": 18.0, "CH2": 129.0, "CH3": 60.0}

    monkeypatch.setattr(CommandChecks, "state", fake_state)

    checks = CommandChecks(
        None,
        sleep=lambda _: None,
        current_reader=lambda: {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.060)},
    )
    checks.move(
        negative=False,
        steps=100,
        label="turning",
        active_state="Moving",
        expected_motor_params=(20, 0, 60, 8),
    )

    assert len(state_calls) == 2
    assert all(call["state"] == "Moving" for call in state_calls)
    assert all(call["moving"] is True for call in state_calls)


def test_move_wait_aborts_when_script_stop_is_requested(monkeypatch):
    from widget_modules import ui_runtime_controller

    started = _hk(MTR_FLAGS=SimpleNamespace(MOVING=1, HOMING=0, DIR=0, OUTER=0, BASE=0))
    monkeypatch.setattr(ui_runtime_controller, "is_aborted", lambda: True)

    checks = CommandChecks(
        None,
        sleep=lambda _: None,
        current_reader=lambda: {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.060)},
    )

    with pytest.raises(ui_runtime_controller.ScriptAbortRequested):
        checks._wait_for_stop("turning", active_state="Moving", initial_response=started)


def test_move_to_absolute_position_rejects_no_motion(monkeypatch):
    checks = CommandChecks(None)
    before = _hk(MTR_ABS_STEPS=5000)
    finished = _hk(MTR_ABS_STEPS=5000)
    monkeypatch.setattr(checks, "hk", lambda *args, **kwargs: before)
    monkeypatch.setattr(checks, "move", lambda **kwargs: finished)

    with pytest.raises(AssertionError, match="did not move"):
        checks.move_to_absolute_position(5200, label="target move")


def test_movement_speed_is_calculated_from_steps_and_time():
    assert CommandChecks._movement_speed_mm_s(320, 2.0) == pytest.approx(0.5)
    assert CommandChecks._movement_speed_mm_s(160, 2.0) == pytest.approx(0.25)


def test_movement_time_is_checked_with_two_second_tolerance():
    CommandChecks._assert_elapsed_within_tolerance("speed check", 18.0, 20.0, 2.0)

    with pytest.raises(AssertionError, match=r"outside 18.00\.\.22\.00 s"):
        CommandChecks._assert_elapsed_within_tolerance("speed check", 23.0, 20.0, 2.0)


def test_read_psu_channels_skips_when_lock_is_busy():
    class BusyLock:
        def acquire(self, blocking=True, timeout=None):
            return False

        def release(self):
            raise AssertionError("lock should not be acquired when busy")

    class FakePort:
        pass

    assert read_psu_channels(FakePort(), BusyLock()) == {}


def test_read_psu_channels_uses_latest_cached_sample_when_queue_is_empty(monkeypatch):
    from utility_modules import eb_packet_utility

    class BusyLock:
        def acquire(self, blocking=True, timeout=None):
            return False

        def release(self):
            raise AssertionError("lock should not be acquired when busy")

    class FakePort:
        pass

    snapshot = {
        "CH1_V": 12.0,
        "CH1_I": 0.018,
        "CH2_V": -12.0,
        "CH2_I": 0.129,
        "CH3_V": 5.0,
        "CH3_I": 0.060,
        "CH4_V": 0.0,
        "CH4_I": 0.0,
    }
    eb_packet_utility.set_latest_psu(snapshot)
    monkeypatch.setattr("utility_modules.background_checks.const.psu_queue", None)

    assert read_psu_channels(FakePort(), BusyLock()) == {
        "CH1": (12.0, 0.018),
        "CH2": (-12.0, 0.129),
        "CH3": (5.0, 0.060),
        "CH4": (0.0, 0.0),
    }


def test_dark_science_checks_all_configured_measurements():
    science = SimpleNamespace(
        SWIR_HIGH=10,
        SWIR_MED=11,
        SWIR_LOW=12,
        MWIR_HIGH=13,
        MWIR_MED=14,
        MWIR_LOW=15,
        SWIR_TEMP=100,
        HT_SINK_TEMP=100,
    )
    check_dark_science(_hk(), science)


def test_dark_science_rejects_missing_channel():
    science = SimpleNamespace(
        SWIR_HIGH=10,
        SWIR_MED=11,
        SWIR_LOW=12,
        MWIR_HIGH=13,
        MWIR_MED=14,
        SWIR_TEMP=100,
        HT_SINK_TEMP=100,
    )
    with pytest.raises(AssertionError, match="MWIR_LOW is missing"):
        check_dark_science(_hk(), science)


def test_dark_offset_all_zero_is_not_treated_as_failure():
    dark_science = SimpleNamespace(
        SWIR_HIGH=0,
        SWIR_MED=0,
        SWIR_LOW=0,
        MWIR_HIGH=0,
        MWIR_MED=0,
        MWIR_LOW=0,
    )
    offset_science = SimpleNamespace(
        SWIR_HIGH=0,
        SWIR_MED=0,
        SWIR_LOW=0,
        MWIR_HIGH=0,
        MWIR_MED=0,
        MWIR_LOW=0,
    )
    errors = []
    for field in ("SWIR_HIGH", "SWIR_MED", "SWIR_LOW", "MWIR_HIGH", "MWIR_MED", "MWIR_LOW"):
        initial_value = getattr(dark_science, field, None)
        offset_value = getattr(offset_science, field, None)
        if initial_value is None or offset_value is None:
            errors.append(f"{field} is unavailable for dark-offset comparison")
        elif initial_value == 0 and offset_value == 0:
            continue
        elif offset_value >= initial_value:
            errors.append(f"{field} did not decrease after offset 4095: {initial_value} -> {offset_value}")
    assert errors == []


def test_ob_state_current_checks_only_configured_rails():
    measured = check_current_profile(
        {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.080)},
        "State3",
    )
    assert measured == {"CH1": 18.0, "CH2": 129.0, "CH3": 80.0}


def test_ob_current_profile_sums_active_components():
    assert calculate_ob_current_profile("State3") == {"CH1": 17.4, "CH2": 129.7, "CH3": 70.0}


def test_ob_current_profile_includes_movement_component():
    moving_state = _hk(
        PWR_STAT=3,
        THRM_STATUS=SimpleNamespace(DM=1, DA=0, MM=1, MA=0, HDS=1, HMS=1),
        MTR_FLAGS=SimpleNamespace(MOVING=1, HOMING=0, DIR=0, OUTER=0, BASE=0),
    )
    assert calculate_ob_current_profile(moving_state) == {
        "CH1": 102.4,
        "CH2": 129.7,
        "CH3": 67.0,
    }


def test_moving_current_profile_uses_live_motor_setting():
    moving = _hk(
        MTR_CURRENT=40,
        PWR_STAT=1,
        THRM_STATUS=SimpleNamespace(DM=0, DA=0, MM=0, MA=0, HDS=0, HMS=0),
        MTR_FLAGS=SimpleNamespace(MOVING=1, HOMING=0, DIR=0, OUTER=0, BASE=0),
    )

    assert calculate_ob_current_profile(moving) == {"CH1": 60.0, "CH2": 0.0, "CH3": 67.0}


def test_component_current_profile_checks_all_ob_rails():
    response = _hk(
        PWR_STAT=0,
        THRM_STATUS=SimpleNamespace(DM=0, DA=0, MM=1, MA=0, HDS=0, HMS=1),
    )
    measured = check_current_profile(
        {"CH1": (12.0, 0.0), "CH2": (-12.0, 0.083), "CH3": (5.0, 0.060)},
        response,
    )
    assert measured == {"CH1": 0.0, "CH2": 83.0, "CH3": 60.0}


def test_ob_state_expected_ch3_includes_powered_heated_board_load():
    measured = check_current_profile(
        {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.080)},
        "State3",
    )
    assert measured == {"CH1": 18.0, "CH2": 129.0, "CH3": 80.0}

    assert calculate_ob_current_profile("State3") == {"CH1": 17.4, "CH2": 129.7, "CH3": 70.0}


def test_ob_state_current_reports_out_of_range_rail():
    with pytest.raises(AssertionError, match="CH1=40.00 mA"):
        check_current_profile(
            {"CH1": (12.0, 0.040), "CH2": (-12.0, 0.0057), "CH3": (5.0, 0.060)},
            "State5",
        )


def test_ob_state_current_can_skip_when_psu_is_disabled():
    assert check_current_profile({}, "State1", allow_unavailable=True) == {}


def test_complete_ob_state_checks_hk_and_current_together():
    measured = check_ob_state(
        _hk(),
        {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.080)},
        "State3",
    )
    assert measured["CH1"] == 18.0
    assert measured["CH2"] == 129.0
    assert measured["CH3"] == 80.0


def test_complete_ob_state_rejects_wrong_ob_state():
    with pytest.raises(AssertionError, match="Power state mismatch"):
        check_ob_state(
            _hk(PWR_STAT=0),
            {"CH1": (12.0, 0.018), "CH2": (-12.0, 0.129), "CH3": (5.0, 0.060)},
            "State3",
        )


def test_measurement_scan_can_be_started_in_background(monkeypatch):
    started = []

    def fake_measurement_scan(port, step_spacing=30, port_lock=None):
        started.append((port, step_spacing, port_lock))

    monkeypatch.setattr(sci_acq, "measurement_scan", fake_measurement_scan)

    thread = sci_acq.measurement_scan_async("port", step_spacing=50)

    assert isinstance(thread, type(threading.Thread()))
    thread.join(timeout=1)
    assert started == [("port", 50, None)]


def test_measurement_scan_async_respects_shared_port_lock(monkeypatch):
    seen = []

    class FakeLock:
        def __enter__(self):
            seen.append("entered")
            return self

        def __exit__(self, exc_type, exc, tb):
            seen.append("exited")
            return False

    def fake_measurement_scan(port, step_spacing=30, port_lock=None):
        if port_lock is not None:
            with port_lock:
                seen.append((port, step_spacing, True))
        else:
            seen.append((port, step_spacing, False))

    monkeypatch.setattr(sci_acq, "measurement_scan", fake_measurement_scan)

    thread = sci_acq.measurement_scan_async("port", step_spacing=50, port_lock=FakeLock())

    assert isinstance(thread, type(threading.Thread()))
    thread.join(timeout=1)
    assert seen == ["entered", ("port", 50, True), "exited"]
