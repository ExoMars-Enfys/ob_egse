from __future__ import annotations

from types import SimpleNamespace

import pytest

from utility_modules import hk_conversions


@pytest.mark.parametrize("field_name", sorted(hk_conversions.CONVERSIONS))
def test_decode_field_uses_registered_conversion(field_name: str) -> None:
    raw = 2000
    packet = SimpleNamespace(**{field_name: raw})
    expected = float(hk_conversions.CONVERSIONS[field_name].convert(raw))

    result = hk_conversions.decode_field(packet, field_name)

    if expected != expected:  # NaN-safe comparison
        assert result != result
    else:
        assert result == pytest.approx(expected)


def test_decode_field_accepts_numeric_strings() -> None:
    packet = SimpleNamespace(OB_1V5_VOLTAGE="1500")

    assert hk_conversions.decode_field(packet, "OB_1V5_VOLTAGE") == pytest.approx(1.5)


@pytest.mark.parametrize(
    ("packet", "field_name"),
    [
        (SimpleNamespace(), "OB_1V5_VOLTAGE"),
        (SimpleNamespace(OB_1V5_VOLTAGE=None), "OB_1V5_VOLTAGE"),
        (SimpleNamespace(OB_1V5_VOLTAGE="not-numeric"), "OB_1V5_VOLTAGE"),
        (SimpleNamespace(UNKNOWN=123), "UNKNOWN"),
    ],
)
def test_decode_field_returns_none_for_unknown_missing_or_invalid_values(
    packet: SimpleNamespace,
    field_name: str,
) -> None:
    assert hk_conversions.decode_field(packet, field_name) is None


@pytest.mark.parametrize(
    "exc",
    [
        TypeError("bad type"),
        ValueError("bad value"),
        ZeroDivisionError("bad divisor"),
    ],
)
def test_decode_field_returns_none_when_conversion_rejects_value(
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> None:
    def _raise(_raw: int) -> float:
        raise exc

    monkeypatch.setitem(
        hk_conversions.CONVERSIONS,
        "BROKEN_FIELD",
        hk_conversions.FieldConversion("V", _raise),
    )

    assert hk_conversions.decode_field(SimpleNamespace(BROKEN_FIELD=1), "BROKEN_FIELD") is None
