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

from utility_modules.eb_packet_utility import adu_to_temp as decode_ob_trps
from utility_modules.eb_packet_utility import decode_eb_trps
from utility_modules.eb_packet_utility import resistance_to_temp

ConvertFn = Callable[[int], float]
SCI_TEMPERATURE_FIELDS = (
    "SWIR_TEMP",
    "HT_SINK_TEMP",
    "HEATSINK_START_TEMP",
    "HEATSINK_END_TEMP",
    "SWIR_START_TEMP",
    "SWIR_END_TEMP",
    "MWIR_START_TEMP",
    "MWIR_END_TEMP",
)

def sci_temperature_to_c(field: str, raw: int) -> float:
    """Convert a raw SCI temperature field to degrees Celsius."""
    adc = int(raw) >> 4
    if not 0 < adc < 4096:
        return float("nan")
    resistance = 10000.0 * adc / (4096 - adc)
    return resistance_to_temp(resistance)


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
    # EB-relayed OB rail voltages pack the 12-bit ADU into the upper bits of
    # the 16-bit field, same as the native standalone OB HK log.
    "OB_3V3_VOLTAGE": FieldConversion("V", lambda raw: ((raw >> 4) * 2) / 1000.0),
    "OB_1V5_VOLTAGE": FieldConversion("V", lambda raw: (raw >> 4) / 1000.0),
    # ── OB Thermistors ───────────────────────────────────────────────────────
    # EB-relayed OB TRPs pack the 12-bit ADC value into the upper bits of the
    # 16-bit field, same as the native standalone OB HK log.
    "OB_DIGITAL_TRP": FieldConversion("°C", lambda raw: decode_ob_trps(raw >> 4)),
    "OB_DETECTOR_TRP": FieldConversion("°C", lambda raw: decode_ob_trps(raw >> 4)),
    "OB_MECHANISM_TRP": FieldConversion("°C", lambda raw: decode_ob_trps(raw >> 4)),
    "OB_MOTOR_TRP": FieldConversion("°C", lambda raw: decode_ob_trps(raw >> 4)),
    # ── OB ADC ───────────────────────────────────────────────────────
    "HK_MECH_CUR": FieldConversion("mA", lambda raw: (raw >> 4) * (0.12 / (0.2 * 10))),
    "OB_MECH_CURRENT": FieldConversion("mA", lambda raw: (raw >> 4) * (0.12 / (0.2 * 10))),
    # ── SCI temperatures (OB SCI and EB SCI header) ──────────────────────────
    **{
        field: FieldConversion("°C", lambda raw, field=field: sci_temperature_to_c(field, raw))
        for field in SCI_TEMPERATURE_FIELDS
    },
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
