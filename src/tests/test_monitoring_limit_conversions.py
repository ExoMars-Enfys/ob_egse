from __future__ import annotations

from collections.abc import Callable

import pytest

from core_modules import constants as const
from utility_modules import hk_conversions
from utility_modules.eb_packet_utility import adu_to_temp, decode_eb_trps
from widget_modules import metrics_card_widget as mcw
from widget_modules import monitoring_limits as ml


def _assert_decoded_pair_matches_limits(
    decoder: Callable[[int], float],
    adu_bounds: tuple[int, int],
    real_bounds: tuple[float, float],
    tol: float,
) -> None:
    lo_adu, hi_adu = adu_bounds
    assert lo_adu <= hi_adu, "ADU bounds must be ordered ascending for range checks"

    decoded_lo = float(decoder(lo_adu))
    decoded_hi = float(decoder(hi_adu))

    decoded_min = min(decoded_lo, decoded_hi)
    decoded_max = max(decoded_lo, decoded_hi)

    real_lo, real_hi = real_bounds
    assert abs(decoded_min - real_lo) <= tol
    assert abs(decoded_max - real_hi) <= tol


@pytest.mark.parametrize(
    ("field", "adu_bounds", "real_bounds", "tol"),
    [
        ("EB_MEAS_MAIN_12V", const.WLIM_EB_12V_ADU, const.WLIM_EB_12V, 0.002),
        ("EB_MEAS_MAIN_12V", const.ALIM_EB_12V_ADU, const.ALIM_EB_12V, 0.002),
        ("EB_MEAS_MAIN_NEG12V", const.WLIM_EB_NEG12V_ADU, const.WLIM_EB_NEG12V, 0.002),
        ("EB_MEAS_MAIN_NEG12V", const.ALIM_EB_NEG12V_ADU, const.ALIM_EB_NEG12V, 0.002),
        ("EB_MEAS_5V", const.WLIM_EB_5V_ADU, const.WLIM_EB_5V, 0.002),
        ("EB_MEAS_5V", const.ALIM_EB_5V_ADU, const.ALIM_EB_5V, 0.002),
        ("EB_MEAS_3V3", const.WLIM_EB_3V3_ADU, const.WLIM_EB_3V3, 0.002),
        ("EB_MEAS_3V3", const.ALIM_EB_3V3_ADU, const.ALIM_EB_3V3, 0.002),
        ("OB_3V3_VOLTAGE", const.WLIM_3V3_ADU, const.WLIM_3V3, 0.002),
        ("OB_3V3_VOLTAGE", const.ALIM_3V3_ADU, const.ALIM_3V3, 0.002),
        ("OB_1V5_VOLTAGE", const.WLIM_1V5_ADU, const.WLIM_1V5, 0.002),
        ("OB_1V5_VOLTAGE", const.ALIM_1V5_ADU, const.ALIM_1V5, 0.002),
        (
            "EB_MCU_INTERNAL_TEMP",
            const.WLIM_EB_MCU_INTERNAL_TEMP_ADU,
            const.WLIM_EB_MCU_INTERNAL_TEMP,
            0.02,
        ),
        (
            "EB_MCU_INTERNAL_TEMP",
            const.ALIM_EB_MCU_INTERNAL_TEMP_ADU,
            const.ALIM_EB_MCU_INTERNAL_TEMP,
            0.02,
        ),
    ],
)
def test_linear_conversion_based_adu_limits_match_real_limits(
    field: str,
    adu_bounds: tuple[int, int],
    real_bounds: tuple[float, float],
    tol: float,
) -> None:
    conversion = hk_conversions.CONVERSIONS[field]
    _assert_decoded_pair_matches_limits(conversion.convert, adu_bounds, real_bounds, tol)


@pytest.mark.parametrize(
    ("adu_bounds", "real_bounds", "tol"),
    [
        (const.WLIM_TPR_ADU, const.WLIM_TPR, 0.2),
        (const.ALIM_TPR_ADU, const.ALIM_TPR, 0.2),
    ],
)
def test_ob_thermistor_adu_limits_match_real_limits(
    adu_bounds: tuple[int, int],
    real_bounds: tuple[float, float],
    tol: float,
) -> None:
    _assert_decoded_pair_matches_limits(adu_to_temp, adu_bounds, real_bounds, tol)


@pytest.mark.parametrize(
    ("adu_bounds", "real_bounds", "tol"),
    [
        (const.WLIM_EB_INTERNAL_TRP_TEMP_ADU, const.WLIM_EB_INTERNAL_TRP_TEMP, 0.2),
        (const.ALIM_EB_INTERNAL_TRP_TEMP_ADU, const.ALIM_EB_INTERNAL_TRP_TEMP, 0.2),
        (const.WLIM_EB_PSU_BOARD_TEMP_ADU, const.WLIM_EB_PSU_BOARD_TEMP, 0.2),
        (const.ALIM_EB_PSU_BOARD_TEMP_ADU, const.ALIM_EB_PSU_BOARD_TEMP, 0.2),
    ],
)
def test_eb_thermistor_adu_limits_match_real_limits(
    adu_bounds: tuple[int, int],
    real_bounds: tuple[float, float],
    tol: float,
) -> None:
    _assert_decoded_pair_matches_limits(decode_eb_trps, adu_bounds, real_bounds, tol)


def test_metrics_specs_are_wired_to_reference_limit_constants() -> None:
    eb_specs = {spec.key: spec for spec in mcw._eb_hk_specs()}
    ob_specs = {spec.key: spec for spec in mcw._ob_hk_specs()}

    # EB converted values
    assert eb_specs["eb_12v"].bounds == const.WLIM_EB_12V
    assert eb_specs["eb_12v"].alarm_bounds == const.ALIM_EB_12V
    assert eb_specs["eb_12v"].bounds_adu == const.WLIM_EB_12V_ADU
    assert eb_specs["eb_12v"].alarm_bounds_adu == const.ALIM_EB_12V_ADU

    assert eb_specs["eb_neg12v"].bounds == const.WLIM_EB_NEG12V
    assert eb_specs["eb_neg12v"].alarm_bounds == const.ALIM_EB_NEG12V
    assert eb_specs["eb_neg12v"].bounds_adu == const.WLIM_EB_NEG12V_ADU
    assert eb_specs["eb_neg12v"].alarm_bounds_adu == const.ALIM_EB_NEG12V_ADU

    assert eb_specs["eb_5v"].bounds == const.WLIM_EB_5V
    assert eb_specs["eb_5v"].alarm_bounds == const.ALIM_EB_5V
    assert eb_specs["eb_5v"].bounds_adu == const.WLIM_EB_5V_ADU
    assert eb_specs["eb_5v"].alarm_bounds_adu == const.ALIM_EB_5V_ADU

    assert eb_specs["eb_3v3"].bounds == const.WLIM_EB_3V3
    assert eb_specs["eb_3v3"].alarm_bounds == const.ALIM_EB_3V3
    assert eb_specs["eb_3v3"].bounds_adu == const.WLIM_EB_3V3_ADU
    assert eb_specs["eb_3v3"].alarm_bounds_adu == const.ALIM_EB_3V3_ADU

    assert eb_specs["eb_mcu_temp"].bounds == const.WLIM_EB_MCU_INTERNAL_TEMP
    assert eb_specs["eb_mcu_temp"].alarm_bounds == const.ALIM_EB_MCU_INTERNAL_TEMP
    assert eb_specs["eb_mcu_temp"].bounds_adu == const.WLIM_EB_MCU_INTERNAL_TEMP_ADU
    assert eb_specs["eb_mcu_temp"].alarm_bounds_adu == const.ALIM_EB_MCU_INTERNAL_TEMP_ADU

    assert eb_specs["eb_internal_temp"].bounds == const.WLIM_EB_INTERNAL_TRP_TEMP
    assert eb_specs["eb_internal_temp"].alarm_bounds == const.ALIM_EB_INTERNAL_TRP_TEMP
    assert eb_specs["eb_internal_temp"].bounds_adu == const.WLIM_EB_INTERNAL_TRP_TEMP_ADU
    assert eb_specs["eb_internal_temp"].alarm_bounds_adu == const.ALIM_EB_INTERNAL_TRP_TEMP_ADU

    assert eb_specs["eb_psu_temp"].bounds == const.WLIM_EB_PSU_BOARD_TEMP
    assert eb_specs["eb_psu_temp"].alarm_bounds == const.ALIM_EB_PSU_BOARD_TEMP
    assert eb_specs["eb_psu_temp"].bounds_adu == const.WLIM_EB_PSU_BOARD_TEMP_ADU
    assert eb_specs["eb_psu_temp"].alarm_bounds_adu == const.ALIM_EB_PSU_BOARD_TEMP_ADU

    # OB converted values
    assert ob_specs["3v3"].bounds == const.WLIM_3V3
    assert ob_specs["3v3"].alarm_bounds == const.ALIM_3V3
    assert ob_specs["3v3"].bounds_adu == const.WLIM_3V3_ADU
    assert ob_specs["3v3"].alarm_bounds_adu == const.ALIM_3V3_ADU

    assert ob_specs["1v5"].bounds == const.WLIM_1V5
    assert ob_specs["1v5"].alarm_bounds == const.ALIM_1V5
    assert ob_specs["1v5"].bounds_adu == const.WLIM_1V5_ADU
    assert ob_specs["1v5"].alarm_bounds_adu == const.ALIM_1V5_ADU

    for key in ("dig", "det", "mech", "mtr"):
        assert ob_specs[key].bounds == const.WLIM_TPR
        assert ob_specs[key].alarm_bounds == const.ALIM_TPR
        assert ob_specs[key].bounds_adu == const.WLIM_TPR_ADU
        assert ob_specs[key].alarm_bounds_adu == const.ALIM_TPR_ADU


# ---------------------------------------------------------------------------
# Constants-backed monitoring registry validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ((None, 5), (None, 5.0)),
        ((1, None), (1.0, None)),
        ([1, 5], (1.0, 5.0)),
    ],
)
def test_monitoring_limit_pair_accepts_open_ended_bounds(raw, expected) -> None:
    assert ml._pair(raw, "TEST_LIMIT") == expected


@pytest.mark.parametrize(
    "raw",
    [
        (1,),
        (1, 2, 3),
        "1,2",
    ],
)
def test_monitoring_limit_pair_rejects_non_pairs(raw) -> None:
    with pytest.raises(RuntimeError, match="two-value tuple"):
        ml._pair(raw, "TEST_LIMIT")


def test_monitoring_limit_pair_rejects_reversed_bounds() -> None:
    with pytest.raises(RuntimeError, match="ordered low <= high"):
        ml._pair((5, 1), "TEST_LIMIT")


@pytest.mark.parametrize("raw", [("bad", 1), (1, object())])
def test_monitoring_limit_pair_rejects_non_numeric_endpoints(raw) -> None:
    with pytest.raises(RuntimeError, match="numeric or None"):
        ml._pair(raw, "TEST_LIMIT")


def test_unknown_monitoring_limit_key_raises_clear_error() -> None:
    with pytest.raises(KeyError, match="Unknown monitoring limit key"):
        ml.get_limit("not-a-real-limit")


def test_ob_mms_limit_mapping_uses_correct_fpga_rails() -> None:
    limits = ml.mms_alarm_limits()

    assert limits["ob_fpga_core_v"] == const.ALIM_1V5
    assert limits["ob_fpga_io_v"] == const.ALIM_3V3
    assert limits["ob_digital_trp"] == const.ALIM_TPR
    assert limits["ob_detector_trp"] == const.ALIM_TPR
    assert limits["ob_mechanism_trp"] == const.ALIM_TPR
    assert limits["ob_motor_trp"] == const.ALIM_TPR


@pytest.mark.parametrize(
    ("display_mode", "alarm_pairs"),
    [
        ("REAL", (const.ALIM_3V3, const.ALIM_1V5)),
        ("ADU", (const.ALIM_3V3_ADU, const.ALIM_1V5_ADU)),
    ],
)
def test_recommended_ob_voltage_plot_limits_enclose_alarm_bounds(
    display_mode: str,
    alarm_pairs: tuple[tuple[float, float], tuple[float, float]],
) -> None:
    plot_low, plot_high = ml.recommended_plot_limits(
        ["ob_3v3", "ob_1v5"],
        display_mode,
        padding_fraction=0.10,
        minimum_padding=0.0,
    )
    expected_low = min(float(pair[0]) for pair in alarm_pairs)
    expected_high = max(float(pair[1]) for pair in alarm_pairs)

    assert plot_low <= expected_low
    assert plot_high >= expected_high
    if display_mode == "ADU":
        assert 0.0 <= plot_low <= 4095.0
        assert 0.0 <= plot_high <= 4095.0


def test_recommended_plot_limits_rejects_missing_display_bounds() -> None:
    with pytest.raises(RuntimeError, match="No ADU alarm bounds"):
        ml.recommended_plot_limits(["eb_tec_rail"], "ADU")


def test_recommended_plot_limits_rejects_open_ended_only_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        ml.MONITORING_LIMITS,
        "open_only",
        ml.MonitoringLimit(key="open_only", unit="V", alarm_real=(None, 5.0)),
    )

    with pytest.raises(RuntimeError, match="Cannot derive a finite REAL plot range"):
        ml.recommended_plot_limits(["open_only"], "REAL")


def test_metric_limit_kwargs_returns_all_four_registry_fields() -> None:
    kwargs = ml.metric_limit_kwargs("ob_3v3")

    assert kwargs == {
        "bounds": const.WLIM_3V3,
        "alarm_bounds": const.ALIM_3V3,
        "bounds_adu": const.WLIM_3V3_ADU,
        "alarm_bounds_adu": const.ALIM_3V3_ADU,
    }


# ---------------------------------------------------------------------------
# Remaining monitoring registry branches
# ---------------------------------------------------------------------------


def test_monitoring_limit_display_maps_only_include_configured_modes() -> None:
    spec = ml.MonitoringLimit(
        key="mixed",
        unit="V",
        warning_real=(1.0, 2.0),
        warning_adu=(100.0, 200.0),
        alarm_real=(0.5, 2.5),
    )

    assert spec.warning_by_display() == {
        "REAL": (1.0, 2.0),
        "ADU": (100.0, 200.0),
    }
    assert spec.alarm_by_display() == {"REAL": (0.5, 2.5)}


def test_monitoring_limit_display_maps_can_be_empty() -> None:
    spec = ml.MonitoringLimit(key="empty", unit="V")

    assert spec.warning_by_display() == {}
    assert spec.alarm_by_display() == {}


def test_const_pair_reports_missing_constant() -> None:
    with pytest.raises(RuntimeError, match="missing required monitoring limit"):
        ml._const_pair("LIMIT_THAT_DOES_NOT_EXIST")


def test_required_reports_missing_bounds() -> None:
    with pytest.raises(RuntimeError, match="has no warning REAL bounds"):
        ml._required(None, "missing", "warning REAL")


@pytest.mark.parametrize("bounds", [(None, 5.0), (1.0, None)])
def test_required_finite_rejects_open_bounds(bounds) -> None:
    with pytest.raises(RuntimeError, match="requires finite alarm ADU bounds"):
        ml._required_finite(bounds, "open", "alarm ADU")


def test_recommended_real_plot_limits_use_default_minimum_padding() -> None:
    alarm_low, alarm_high = map(float, const.ALIM_3V3)

    plot_low, plot_high = ml.recommended_plot_limits(
        ["ob_3v3"],
        "REAL",
        padding_fraction=0.0,
    )

    assert plot_low == pytest.approx(alarm_low - 0.25)
    assert plot_high == pytest.approx(alarm_high + 0.25)


def test_recommended_adu_plot_limits_use_default_padding_and_adc_clamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        ml.MONITORING_LIMITS,
        "full_adc",
        ml.MonitoringLimit(key="full_adc", unit="ADU", alarm_adu=(0.0, 4095.0)),
    )

    assert ml.recommended_plot_limits(
        ["full_adc"],
        "ADU",
        padding_fraction=0.0,
    ) == (0.0, 4095.0)
