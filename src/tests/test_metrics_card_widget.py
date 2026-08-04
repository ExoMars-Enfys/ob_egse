from __future__ import annotations

from types import SimpleNamespace

import pytest

from utility_modules.eb_packet_utility import adu_to_temp
from widget_modules import metrics_card_widget as mcw


@pytest.mark.parametrize(
    ("spec_key", "packet", "expected"),
    [
        ("3v3", SimpleNamespace(OB_3V3_VOLTAGE=1500), pytest.approx(3.0)),
        ("1v5", SimpleNamespace(OB_1V5_VOLTAGE=1500), pytest.approx(1.5)),
        ("dig", SimpleNamespace(OB_DIGITAL_TRP=1000), pytest.approx(adu_to_temp(1000))),
    ],
)
def test_ob_metrics_fallback_to_embedded_eb_fields(spec_key: str, packet: SimpleNamespace, expected: object) -> None:
    specs = {spec.key: spec for spec in mcw._ob_hk_specs()}
    assert specs[spec_key].getter(packet) == expected


@pytest.mark.parametrize(
    ("spec_key", "packet", "expected"),
    [
        ("ob_steps", SimpleNamespace(OB_MOTOR_ABS_STEPS=1234), 1234),
        ("mtr_rel_steps", SimpleNamespace(OB_MOTOR_REL_STEPS=-12), -12),
        ("mtr_current", SimpleNamespace(OB_MOTOR_CURRENT=31), "0x1F"),
        ("guard_select", SimpleNamespace(OB_MOTOR_SPISPSEL=2), "0x02"),
        ("mtr_chop", SimpleNamespace(OB_MOTOR_PWM_DUTY=170), "0xAA"),
        ("mtr_speed", SimpleNamespace(OB_SPEED=11), "0x0B"),
        ("cmd_cnt", SimpleNamespace(OB_COMMAND_COUNT=44), 44),
        ("hk_samples", SimpleNamespace(HK_NUMBER_OF_SAMPLES=7), 7),
        ("hk_mech_cur", SimpleNamespace(OB_MECH_CURRENT=512), 512),
    ],
)
def test_ob_metrics_fallback_to_embedded_motor_and_counter_fields(
    spec_key: str,
    packet: SimpleNamespace,
    expected: object,
) -> None:
    specs = {spec.key: spec for spec in mcw._ob_hk_specs()}
    assert specs[spec_key].getter(packet) == expected


def test_ob_direction_reports_dir_bit_even_when_stationary() -> None:
    specs = {spec.key: spec for spec in mcw._ob_hk_specs()}
    packet = SimpleNamespace(MTR_FLAGS=SimpleNamespace(DIR=1, MOVING=0))
    assert specs["ob_direction"].getter(packet) == "TO OUTER"


@pytest.mark.parametrize(
    "raw_setpoint",
    [0, 4095],
)
def test_ob_thermal_setpoint_endpoint_adu_returns_none(raw_setpoint: int) -> None:
    specs = {spec.key: spec for spec in mcw._ob_hk_specs()}
    packet = SimpleNamespace(OB_THERMAL_MECH_MIN=raw_setpoint)
    assert specs["mech_htr_min_sp"].getter(packet) is None


@pytest.mark.parametrize(
    ("spec_key", "packet", "expected"),
    [
        ("swir_offset", SimpleNamespace(OB_SWIR_OFFSET=321), 321),
        ("mwir_offset", SimpleNamespace(OB_MWIR_OFFSET=654), 654),
    ],
)
def test_ob_offsets_fallback_to_embedded_eb_hk_offsets(
    spec_key: str,
    packet: SimpleNamespace,
    expected: int,
) -> None:
    specs = {spec.key: spec for spec in mcw._ob_hk_specs()}
    assert specs[spec_key].getter(packet) == expected
