from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from core_modules import constants as const
from widget_modules import monitoring_limits
from widget_modules import ui_runtime_controller as urc


class _DummyLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def _record(self, level: str, message: str, *args: Any) -> None:
        self.records.append((level, message % args if args else message))

    def debug(self, message: str, *args: Any) -> None:
        self._record("debug", message, *args)

    def info(self, message: str, *args: Any) -> None:
        self._record("info", message, *args)

    def warning(self, message: str, *args: Any) -> None:
        self._record("warning", message, *args)

    def error(self, message: str, *args: Any) -> None:
        self._record("error", message, *args)

    def exception(self, message: str, *args: Any) -> None:
        self._record("exception", message, *args)


@pytest.fixture
def fdir_actions(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Replace UI/hardware side effects while retaining FDIR logic."""
    actions: dict[str, list[Any]] = {
        "notifications": [],
        "prompts": [],
        "shutdowns": [],
    }

    monkeypatch.setattr(
        urc,
        "notify",
        lambda message, **kwargs: actions["notifications"].append((message, kwargs)),
    )
    monkeypatch.setattr(
        urc,
        "_open_ob_psu_shutdown_dialog",
        lambda _state, _logger, details: actions["prompts"].append(list(details)),
    )

    def _capture_shutdown(
        _state: dict[str, Any],
        _logger: Any,
        reasons: list[str],
        *,
        automatic: bool,
    ) -> bool:
        actions["shutdowns"].append(
            {
                "reasons": list(reasons),
                "automatic": automatic,
            }
        )
        return True

    monkeypatch.setattr(urc, "_request_ob_psu_emergency_shutdown", _capture_shutdown)
    return actions


def _parameter(flag_name: str) -> monitoring_limits.ObFdirParameter:
    return next(
        parameter
        for parameter in monitoring_limits.OB_FDIR_PARAMETERS
        if parameter.flag_name == flag_name
    )


def _midpoint(bounds: tuple[float, float]) -> int:
    low, high = bounds
    return int((low + high) // 2)


def _warning_only_value(parameter: monitoring_limits.ObFdirParameter) -> int:
    """Choose an ADU outside warning limits but still inside alarm limits."""
    warning_low, warning_high = map(int, parameter.warning_limits)
    alarm_low, alarm_high = map(int, parameter.alarm_limits)

    low_candidate = warning_low - 1
    if alarm_low <= low_candidate <= alarm_high:
        return low_candidate

    high_candidate = warning_high + 1
    if alarm_low <= high_candidate <= alarm_high:
        return high_candidate

    raise AssertionError(
        f"{parameter.flag_name} has no warning-only region between "
        f"warning={parameter.warning_limits} and alarm={parameter.alarm_limits}"
    )


def _alarm_value(parameter: monitoring_limits.ObFdirParameter) -> int:
    """Choose a valid 12-bit ADU outside the alarm limits."""
    alarm_low, alarm_high = map(int, parameter.alarm_limits)

    if alarm_high < 0x0FFF:
        return alarm_high + 1
    if alarm_low > 0:
        return alarm_low - 1

    raise AssertionError(
        f"Cannot choose an out-of-alarm 12-bit value for {parameter.flag_name}: "
        f"{parameter.alarm_limits}"
    )


def _nominal_hk(**overrides: int) -> SimpleNamespace:
    values = {
        parameter.hk_field: _midpoint(parameter.warning_limits)
        for parameter in monitoring_limits.OB_FDIR_PARAMETERS
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _messages(logger: _DummyLogger, level: str) -> list[str]:
    return [message for record_level, message in logger.records if record_level == level]


def test_ob_fdir_parameter_limits_are_sourced_from_constants() -> None:
    expected = {
        "FPGA_IO_POWER_SUPPLY": (
            const.WLIM_3V3_ADU,
            const.ALIM_3V3_ADU,
            const.WLIM_3V3,
            const.ALIM_3V3,
        ),
        "FPGA_CORE_POWER_SUPPLY": (
            const.WLIM_1V5_ADU,
            const.ALIM_1V5_ADU,
            const.WLIM_1V5,
            const.ALIM_1V5,
        ),
        "DIGITAL_BOARD_TRP": (
            const.WLIM_TPR_ADU,
            const.ALIM_TPR_ADU,
            const.WLIM_TPR,
            const.ALIM_TPR,
        ),
        "DETECTOR_BOARD_TRP": (
            const.WLIM_TPR_ADU,
            const.ALIM_TPR_ADU,
            const.WLIM_TPR,
            const.ALIM_TPR,
        ),
        "MECH_BOARD_TRP": (
            const.WLIM_TPR_ADU,
            const.ALIM_TPR_ADU,
            const.WLIM_TPR,
            const.ALIM_TPR,
        ),
        "MOTOR_TRP": (
            const.WLIM_TPR_ADU,
            const.ALIM_TPR_ADU,
            const.WLIM_TPR,
            const.ALIM_TPR,
        ),
    }

    assert {parameter.flag_name for parameter in urc.OB_FDIR_PARAMETERS} == set(expected)

    for parameter in urc.OB_FDIR_PARAMETERS:
        warning_adu, alarm_adu, warning_real, alarm_real = expected[parameter.flag_name]
        assert parameter.warning_limits == warning_adu
        assert parameter.alarm_limits == alarm_adu
        assert parameter.warning_limits_real == warning_real
        assert parameter.alarm_limits_real == alarm_real


def test_nominal_ob_values_do_not_latch_fdir(
    fdir_actions: dict[str, list[Any]],
) -> None:
    state = {"hk_display_mode": "ADU"}
    hk = _nominal_hk()
    logger = _DummyLogger()

    details = urc.simulate_ob_fdir(state, hk, logger)

    assert details == []
    assert state["ob_fdir_simulator"]["warning_latched"] == set()
    assert state["ob_fdir_simulator"]["alarm_latched"] == set()
    assert hk.FDIR_WARNING_FLAGS == 0
    assert hk.FDIR_ALARM_FLAGS == 0
    assert fdir_actions["prompts"] == []
    assert fdir_actions["shutdowns"] == []


def test_thermistor_warning_latches_once_and_prompts_once(
    fdir_actions: dict[str, list[Any]],
) -> None:
    parameter = _parameter("DIGITAL_BOARD_TRP")
    hk = _nominal_hk(**{parameter.hk_field: _warning_only_value(parameter)})
    state = {"hk_display_mode": "ADU"}
    logger = _DummyLogger()

    first_details = urc.simulate_ob_fdir(state, hk, logger)
    second_details = urc.simulate_ob_fdir(state, hk, logger)

    assert "OB FDIR Warning: DIGITAL_BOARD_TRP (simulated, latched)" in first_details
    assert second_details == first_details
    assert hk.FDIR_WARNING_FLAGS_BITS.DIGITAL_BOARD_TRP == 1
    assert hk.FDIR_ALARM_FLAGS_BITS.DIGITAL_BOARD_TRP == 0
    assert len(_messages(logger, "warning")) == 1
    assert len(fdir_actions["prompts"]) == 1
    assert "DIGITAL_BOARD_TRP" in fdir_actions["prompts"][0][0]
    assert fdir_actions["shutdowns"] == []


def test_thermistor_alarm_supersedes_its_latched_warning(
    fdir_actions: dict[str, list[Any]],
) -> None:
    parameter = _parameter("DIGITAL_BOARD_TRP")
    state = {"hk_display_mode": "ADU"}
    logger = _DummyLogger()

    warning_hk = _nominal_hk(**{parameter.hk_field: _warning_only_value(parameter)})
    urc.simulate_ob_fdir(state, warning_hk, logger)

    alarm_hk = _nominal_hk(**{parameter.hk_field: _alarm_value(parameter)})
    details = urc.simulate_ob_fdir(state, alarm_hk, logger)

    simulator = state["ob_fdir_simulator"]
    assert "DIGITAL_BOARD_TRP" not in simulator["warning_latched"]
    assert "DIGITAL_BOARD_TRP" in simulator["alarm_latched"]
    assert "OB FDIR Warning: DIGITAL_BOARD_TRP (simulated, latched)" not in details
    assert "OB FDIR Alarm: DIGITAL_BOARD_TRP (simulated, latched)" in details
    assert alarm_hk.FDIR_WARNING_FLAGS_BITS.DIGITAL_BOARD_TRP == 0
    assert alarm_hk.FDIR_ALARM_FLAGS_BITS.DIGITAL_BOARD_TRP == 1
    assert len(fdir_actions["prompts"]) == 2
    assert "OB thermistor alarm: DIGITAL_BOARD_TRP" in fdir_actions["prompts"][1][0]
    assert fdir_actions["shutdowns"] == []


def test_separate_thermistor_alarm_still_generates_a_new_prompt(
    fdir_actions: dict[str, list[Any]],
) -> None:
    digital = _parameter("DIGITAL_BOARD_TRP")
    detector = _parameter("DETECTOR_BOARD_TRP")
    state = {"hk_display_mode": "ADU"}
    logger = _DummyLogger()

    first_hk = _nominal_hk(**{digital.hk_field: _alarm_value(digital)})
    urc.simulate_ob_fdir(state, first_hk, logger)

    second_hk = _nominal_hk(
        **{
            digital.hk_field: _alarm_value(digital),
            detector.hk_field: _alarm_value(detector),
        }
    )
    details = urc.simulate_ob_fdir(state, second_hk, logger)

    assert len(fdir_actions["prompts"]) == 2
    assert any("DIGITAL_BOARD_TRP" in reason for reason in fdir_actions["prompts"][0])
    assert any("DETECTOR_BOARD_TRP" in reason for reason in fdir_actions["prompts"][1])
    assert not any("DIGITAL_BOARD_TRP" in reason for reason in fdir_actions["prompts"][1])
    assert "OB FDIR Alarm: DIGITAL_BOARD_TRP (simulated, latched)" in details
    assert "OB FDIR Alarm: DETECTOR_BOARD_TRP (simulated, latched)" in details
    assert fdir_actions["shutdowns"] == []


def test_voltage_alarm_requests_automatic_shutdown_only_on_new_latch(
    fdir_actions: dict[str, list[Any]],
) -> None:
    parameter = _parameter("FPGA_IO_POWER_SUPPLY")
    hk = _nominal_hk(**{parameter.hk_field: _alarm_value(parameter)})
    state = {"hk_display_mode": "ADU"}
    logger = _DummyLogger()

    urc.simulate_ob_fdir(state, hk, logger)
    urc.simulate_ob_fdir(state, hk, logger)

    assert len(fdir_actions["shutdowns"]) == 1
    shutdown = fdir_actions["shutdowns"][0]
    assert shutdown["automatic"] is True
    assert any("FPGA_IO_POWER_SUPPLY" in reason for reason in shutdown["reasons"])
    assert fdir_actions["prompts"] == []
    assert hk.FDIR_ALARM_FLAGS_BITS.FPGA_IO_POWER_SUPPLY == 1


@pytest.mark.parametrize(
    ("display_mode", "expected_text", "unexpected_text"),
    [
        ("ADU", " ADU", " V"),
        ("REAL", " V", " ADU"),
    ],
)
def test_ob_fdir_log_format_follows_display_mode(
    monkeypatch: pytest.MonkeyPatch,
    fdir_actions: dict[str, list[Any]],
    display_mode: str,
    expected_text: str,
    unexpected_text: str,
) -> None:
    parameter = _parameter("FPGA_IO_POWER_SUPPLY")
    hk = _nominal_hk(**{parameter.hk_field: _warning_only_value(parameter)})
    state = {"hk_display_mode": display_mode}
    logger = _DummyLogger()

    # Keep this test focused on presentation rather than conversion internals.
    monkeypatch.setattr(urc, "_ob_fdir_real_value", lambda _parameter, _adu: 3.3)

    urc.simulate_ob_fdir(state, hk, logger)

    warning_message = _messages(logger, "warning")[0]
    assert expected_text in warning_message
    assert unexpected_text not in warning_message
    assert fdir_actions["shutdowns"] == []


def test_reset_clears_ob_fdir_latches_and_allows_retrigger(
    fdir_actions: dict[str, list[Any]],
) -> None:
    parameter = _parameter("DIGITAL_BOARD_TRP")
    alarm_hk = _nominal_hk(**{parameter.hk_field: _alarm_value(parameter)})
    state = {"hk_display_mode": "ADU"}
    logger = _DummyLogger()

    urc.simulate_ob_fdir(state, alarm_hk, logger)
    assert len(fdir_actions["prompts"]) == 1

    urc.reset_ob_fdir_simulator(state, logger)

    simulator = state["ob_fdir_simulator"]
    assert simulator["warning_latched"] == set()
    assert simulator["alarm_latched"] == set()
    assert simulator["current_warning"] == set()
    assert simulator["current_alarm"] == set()
    assert simulator["latest_adu"] == {}

    # The same physical condition is a new latch after Clear_Errors/reset.
    urc.simulate_ob_fdir(state, alarm_hk, logger)
    assert len(fdir_actions["prompts"]) == 2


# ---------------------------------------------------------------------------
# Additional FDIR boundaries, state restoration, and mixed-fault priority
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "flag_name",
    [parameter.flag_name for parameter in monitoring_limits.OB_FDIR_PARAMETERS],
)
def test_warning_limit_endpoints_are_inclusive_and_remain_nominal(
    fdir_actions: dict[str, list[Any]],
    flag_name: str,
) -> None:
    parameter = _parameter(flag_name)

    for boundary in map(int, parameter.warning_limits):
        state = {"hk_display_mode": "ADU"}
        hk = _nominal_hk(**{parameter.hk_field: boundary})

        details = urc.simulate_ob_fdir(state, hk, _DummyLogger())

        assert details == []
        assert flag_name not in state["ob_fdir_simulator"]["warning_latched"]
        assert flag_name not in state["ob_fdir_simulator"]["alarm_latched"]

    assert fdir_actions["prompts"] == []
    assert fdir_actions["shutdowns"] == []


@pytest.mark.parametrize(
    "flag_name",
    ["FPGA_IO_POWER_SUPPLY", "DIGITAL_BOARD_TRP"],
)
def test_alarm_limit_endpoints_are_not_classified_as_alarm(
    fdir_actions: dict[str, list[Any]],
    flag_name: str,
) -> None:
    parameter = _parameter(flag_name)

    for boundary in map(int, parameter.alarm_limits):
        state = {"hk_display_mode": "ADU"}
        hk = _nominal_hk(**{parameter.hk_field: boundary})

        urc.simulate_ob_fdir(state, hk, _DummyLogger())

        assert flag_name not in state["ob_fdir_simulator"]["alarm_latched"]
        assert getattr(hk.FDIR_ALARM_FLAGS_BITS, flag_name) == 0

    assert fdir_actions["shutdowns"] == []


def test_disabled_ob_fdir_simulator_clears_exposed_flags_and_has_no_actions(
    fdir_actions: dict[str, list[Any]],
) -> None:
    parameter = _parameter("DIGITAL_BOARD_TRP")
    hk = _nominal_hk(**{parameter.hk_field: _alarm_value(parameter)})
    state = {
        "hk_display_mode": "ADU",
        "ob_fdir_simulator": {
            "enabled": False,
            "warning_latched": {parameter.flag_name},
            "alarm_latched": {parameter.flag_name},
        },
    }

    details = urc.simulate_ob_fdir(state, hk, _DummyLogger())

    assert details == []
    assert hk.FDIR_WARNING_FLAGS == 0
    assert hk.FDIR_ALARM_FLAGS == 0
    assert fdir_actions["notifications"] == []
    assert fdir_actions["prompts"] == []
    assert fdir_actions["shutdowns"] == []


@pytest.mark.parametrize("raw_value", [None, "not-an-adc-value"])
def test_missing_or_invalid_ob_adc_field_is_ignored_safely(
    fdir_actions: dict[str, list[Any]],
    raw_value: Any,
) -> None:
    parameter = _parameter("DIGITAL_BOARD_TRP")
    hk = _nominal_hk(**{parameter.hk_field: raw_value})
    state = {"hk_display_mode": "ADU"}

    details = urc.simulate_ob_fdir(state, hk, _DummyLogger())

    assert details == []
    assert parameter.flag_name not in state["ob_fdir_simulator"]["latest_adu"]
    assert fdir_actions["prompts"] == []
    assert fdir_actions["shutdowns"] == []


def test_left_aligned_16_bit_adc_is_normalised_before_fdir_check(
    fdir_actions: dict[str, list[Any]],
) -> None:
    parameter = _parameter("DIGITAL_BOARD_TRP")
    warning_adu = _warning_only_value(parameter)
    hk = _nominal_hk(**{parameter.hk_field: warning_adu << 4})
    state = {"hk_display_mode": "ADU"}

    urc.simulate_ob_fdir(state, hk, _DummyLogger())

    assert state["ob_fdir_simulator"]["latest_adu"][parameter.flag_name] == warning_adu
    assert parameter.flag_name in state["ob_fdir_simulator"]["warning_latched"]
    assert len(fdir_actions["prompts"]) == 1


def test_json_like_restored_fdir_state_is_normalised_to_runtime_types(
    fdir_actions: dict[str, list[Any]],
) -> None:
    state = {
        "hk_display_mode": "ADU",
        "ob_fdir_simulator": {
            "enabled": True,
            "warning_latched": ["DIGITAL_BOARD_TRP"],
            "alarm_latched": [],
            "current_warning": [],
            "current_alarm": [],
            "latest_adu": [],
        },
    }

    details = urc.simulate_ob_fdir(state, _nominal_hk(), _DummyLogger())
    simulator = state["ob_fdir_simulator"]

    assert isinstance(simulator["warning_latched"], set)
    assert isinstance(simulator["alarm_latched"], set)
    assert isinstance(simulator["current_warning"], set)
    assert isinstance(simulator["current_alarm"], set)
    assert isinstance(simulator["latest_adu"], dict)
    assert "OB FDIR Warning: DIGITAL_BOARD_TRP (simulated, latched)" in details
    assert fdir_actions["prompts"] == []


def test_simultaneous_voltage_and_thermistor_alarms_prioritise_auto_shutdown(
    fdir_actions: dict[str, list[Any]],
) -> None:
    voltage = _parameter("FPGA_IO_POWER_SUPPLY")
    thermistor = _parameter("DIGITAL_BOARD_TRP")
    hk = _nominal_hk(
        **{
            voltage.hk_field: _alarm_value(voltage),
            thermistor.hk_field: _alarm_value(thermistor),
        }
    )
    state = {"hk_display_mode": "ADU"}

    details = urc.simulate_ob_fdir(state, hk, _DummyLogger())

    assert len(fdir_actions["shutdowns"]) == 1
    assert fdir_actions["shutdowns"][0]["automatic"] is True
    assert fdir_actions["prompts"] == []
    assert "OB FDIR Alarm: FPGA_IO_POWER_SUPPLY (simulated, latched)" in details
    assert "OB FDIR Alarm: DIGITAL_BOARD_TRP (simulated, latched)" in details


def test_alarm_latch_does_not_downgrade_when_value_moves_to_warning_region(
    fdir_actions: dict[str, list[Any]],
) -> None:
    parameter = _parameter("DIGITAL_BOARD_TRP")
    state = {"hk_display_mode": "ADU"}
    logger = _DummyLogger()

    urc.simulate_ob_fdir(
        state,
        _nominal_hk(**{parameter.hk_field: _alarm_value(parameter)}),
        logger,
    )
    details = urc.simulate_ob_fdir(
        state,
        _nominal_hk(**{parameter.hk_field: _warning_only_value(parameter)}),
        logger,
    )

    simulator = state["ob_fdir_simulator"]
    assert parameter.flag_name in simulator["alarm_latched"]
    assert parameter.flag_name not in simulator["warning_latched"]
    assert "OB FDIR Alarm: DIGITAL_BOARD_TRP (simulated, latched)" in details
    assert len(fdir_actions["prompts"]) == 1


def test_ob_fdir_bitmask_matches_tmstruct_flag_ordering() -> None:
    ob_flag_names = {parameter.flag_name for parameter in monitoring_limits.OB_FDIR_PARAMETERS}

    for bit_index, flag_name in enumerate(urc._FDIR_NAMES):
        if flag_name in ob_flag_names:
            assert urc._ob_fdir_bitmask({flag_name}) == (1 << bit_index)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0x0000, 0x000),
        (0x0ABC, 0xABC),
        (0xABC0, 0xABC),
        (None, None),
        ("bad", None),
    ],
)
def test_ob_adc12_normalisation(raw: Any, expected: int | None) -> None:
    assert urc._ob_adc12(raw) == expected


def test_reset_updates_ob_alarm_light_controller(
    fdir_actions: dict[str, list[Any]],
) -> None:
    class _Light:
        def __init__(self) -> None:
            self.reset_count = 0
            self.updates: list[tuple[dict[str, Any], str]] = []

        def reset_acknowledgements(self) -> None:
            self.reset_count += 1

        def update_from_faults(self, faults: dict[str, Any], *, source: str) -> None:
            self.updates.append((faults, source))

    light = _Light()
    state = {
        "alarm_lights": {"ob": light},
        "ob_fdir_simulator": {
            "warning_latched": {"DIGITAL_BOARD_TRP"},
            "alarm_latched": set(),
            "current_warning": {"DIGITAL_BOARD_TRP"},
            "current_alarm": set(),
            "latest_adu": {"DIGITAL_BOARD_TRP": 1234},
        },
    }

    urc.reset_ob_fdir_simulator(state, _DummyLogger())

    assert light.reset_count == 1
    assert light.updates == [({}, "ob_fdir_sim")]
