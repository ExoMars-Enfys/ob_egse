"""Universal ADU-to-physical conversion table for EB/OB HK telemetry fields.

Add an entry here whenever a new field needs a physical conversion.  Both the
metrics card system and plot card system consume this table so the scaling
logic lives in exactly one place.

Usage
-----
    from utility_modules import hk_conversions

    temp = hk_conversions.decode_field(hk_packet, "OB_DIGITAL_TRP")  # float | None
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from utility_modules.eb_packet_utility import decode_eb_trps, adu_to_temp as decode_ob_trps


ConvertFn = Callable[[int], float]


@dataclass(frozen=True)
class FieldConversion:
    """Conversion definition for a single HK telemetry field."""

    unit: str
    convert: ConvertFn


# ---------------------------------------------------------------------------
# Conversion table
# ---------------------------------------------------------------------------
CONVERSIONS: dict[str, FieldConversion] = {
    # ── EB Voltages ──────────────────────────────────────────────────────────
    "EB_MEAS_MAIN_12V": FieldConversion("V", lambda adu: adu * 0.000400543),
    "EB_MEAS_MAIN_NEG12V": FieldConversion("V", lambda adu: adu * -0.00038147),
    "EB_MEAS_5V": FieldConversion("V", lambda adu: adu * 0.000152829),
    "EB_MEAS_3V3": FieldConversion("V", lambda adu: adu * 0.0000763),
    # ── EB Temperatures ──────────────────────────────────────────────────────
    "EB_MCU_INTERNAL_TEMP": FieldConversion("°C", lambda adu: adu * 0.01637198 - 273.0),
    "EB_PSU_BOARD_TEMP": FieldConversion("°C", decode_eb_trps),
    "EB_INTERNAL_TRP_TEMP": FieldConversion("°C", decode_eb_trps),
    # ── OB Voltages ──────────────────────────────────────────────────────────
    "OB_3V3_VOLTAGE": FieldConversion("V", lambda adu: (adu * 2) / 1000.0),
    "OB_1V5_VOLTAGE": FieldConversion("V", lambda adu: adu / 1000.0),
    # ── OB Thermistors ───────────────────────────────────────────────────────
    "OB_DIGITAL_TRP": FieldConversion("°C", decode_ob_trps),
    "OB_DETECTOR_TRP": FieldConversion("°C", decode_ob_trps),
    "OB_MECHANISM_TRP": FieldConversion("°C", decode_ob_trps),
    "OB_MOTOR_TRP": FieldConversion("°C", decode_ob_trps),
}


def decode_field(packet: Any, field_name: str) -> float | None:
    """Convert one raw HK field to its physical value.

    Returns None when:
    - the field is not in the conversion table
    - the packet attribute is absent / None
    - the conversion raises (e.g. ADU out of range)
    """
    conv = CONVERSIONS.get(field_name)
    if conv is None:
        return None
    raw = getattr(packet, field_name, None)
    if raw is None:
        return None
    try:
        return float(conv.convert(int(raw)))
    except (TypeError, ValueError, ZeroDivisionError):
        return None
