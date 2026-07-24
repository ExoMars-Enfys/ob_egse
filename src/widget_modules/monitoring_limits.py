from __future__ import annotations

"""Constants-backed monitoring limit registry.

``core_modules.constants`` is the only source of numeric warning/alarm
thresholds.  Widgets and runtime protection code consume the typed specs in
this module so the parameter mapping is defined once and cannot drift between
plots, metric cards, logs, FDIR latching, and PSU protection.
"""

from dataclasses import dataclass
from typing import Any, Iterable

from core_modules import constants as const


LimitValue = float | None
Bounds = tuple[LimitValue, LimitValue]
FiniteBounds = tuple[float, float]


@dataclass(frozen=True)
class MonitoringLimit:
    key: str
    unit: str
    warning_real: Bounds | None = None
    alarm_real: Bounds | None = None
    warning_adu: Bounds | None = None
    alarm_adu: Bounds | None = None

    def warning_by_display(self) -> dict[str, Bounds]:
        result: dict[str, Bounds] = {}
        if self.warning_real is not None:
            result["REAL"] = self.warning_real
        if self.warning_adu is not None:
            result["ADU"] = self.warning_adu
        return result

    def alarm_by_display(self) -> dict[str, Bounds]:
        result: dict[str, Bounds] = {}
        if self.alarm_real is not None:
            result["REAL"] = self.alarm_real
        if self.alarm_adu is not None:
            result["ADU"] = self.alarm_adu
        return result


@dataclass(frozen=True)
class ObFdirParameter:
    name: str
    hk_field: str
    flag_name: str
    limit_key: str

    @property
    def limit(self) -> MonitoringLimit:
        return get_limit(self.limit_key)

    @property
    def warning_limits(self) -> FiniteBounds:
        return _required_finite(self.limit.warning_adu, self.limit_key, "warning ADU")

    @property
    def alarm_limits(self) -> FiniteBounds:
        return _required_finite(self.limit.alarm_adu, self.limit_key, "alarm ADU")

    @property
    def warning_limits_real(self) -> FiniteBounds:
        return _required_finite(self.limit.warning_real, self.limit_key, "warning REAL")

    @property
    def alarm_limits_real(self) -> FiniteBounds:
        return _required_finite(self.limit.alarm_real, self.limit_key, "alarm REAL")

    @property
    def real_unit(self) -> str:
        return self.limit.unit


def _pair(value: Any, name: str) -> Bounds:
    """Normalise a two-ended limit while preserving open ``None`` bounds.

    ``constants.py`` uses ``None`` for one-sided checks (for example the TEC
    rail alarm).  A missing lower or upper endpoint therefore means
    "unbounded" rather than invalid configuration.
    """
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise RuntimeError(f"constants.py {name} must be a two-value tuple")

    def _endpoint(raw: Any) -> LimitValue:
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"constants.py {name} endpoints must be numeric or None") from exc

    low, high = _endpoint(value[0]), _endpoint(value[1])
    if low is not None and high is not None and low > high:
        raise RuntimeError(f"constants.py {name} must be ordered low <= high")
    return (low, high)


def _const_pair(name: str) -> Bounds:
    if not hasattr(const, name):
        raise RuntimeError(f"constants.py is missing required monitoring limit {name}")
    return _pair(getattr(const, name), name)


def _required(value: Bounds | None, key: str, kind: str) -> Bounds:
    if value is None:
        raise RuntimeError(f"Monitoring limit {key!r} has no {kind} bounds")
    return value


def _required_finite(value: Bounds | None, key: str, kind: str) -> FiniteBounds:
    pair = _required(value, key, kind)
    low, high = pair
    if low is None or high is None:
        raise RuntimeError(f"Monitoring limit {key!r} requires finite {kind} bounds")
    return (float(low), float(high))


def _full_limit(key: str, unit: str, prefix: str) -> MonitoringLimit:
    return MonitoringLimit(
        key=key,
        unit=unit,
        warning_real=_const_pair(f"WLIM_{prefix}"),
        alarm_real=_const_pair(f"ALIM_{prefix}"),
        warning_adu=_const_pair(f"WLIM_{prefix}_ADU"),
        alarm_adu=_const_pair(f"ALIM_{prefix}_ADU"),
    )


MONITORING_LIMITS: dict[str, MonitoringLimit] = {
    # EB analogue housekeeping
    "eb_12v": _full_limit("eb_12v", "V", "EB_12V"),
    "eb_neg12v": _full_limit("eb_neg12v", "V", "EB_NEG12V"),
    "eb_5v": _full_limit("eb_5v", "V", "EB_5V"),
    "eb_3v3": _full_limit("eb_3v3", "V", "EB_3V3"),
    "eb_mcu_temp": _full_limit("eb_mcu_temp", "°C", "EB_MCU_INTERNAL_TEMP"),
    "eb_internal_temp": _full_limit("eb_internal_temp", "°C", "EB_INTERNAL_TRP_TEMP"),
    "eb_psu_temp": _full_limit("eb_psu_temp", "°C", "EB_PSU_BOARD_TEMP"),
    # The MMS TEC rail currently has an alarm band only.
    "eb_tec_rail": MonitoringLimit(
        key="eb_tec_rail",
        unit="V",
        alarm_real=_const_pair("ALIM_EB_TEC_RAIL"),
    ),
    # Standalone OB analogue housekeeping
    "ob_3v3": _full_limit("ob_3v3", "V", "3V3"),
    "ob_1v5": _full_limit("ob_1v5", "V", "1V5"),
    "ob_trp": _full_limit("ob_trp", "°C", "TPR"),
}


OB_FDIR_PARAMETERS: tuple[ObFdirParameter, ...] = (
    ObFdirParameter("FPGA I/O power supply", "HK_V_3V3", "FPGA_IO_POWER_SUPPLY", "ob_3v3"),
    ObFdirParameter("FPGA core power supply", "HK_V_1V5", "FPGA_CORE_POWER_SUPPLY", "ob_1v5"),
    ObFdirParameter("Digital board TRP", "DIGITAL_TRP", "DIGITAL_BOARD_TRP", "ob_trp"),
    ObFdirParameter("Detector board TRP", "DETEC_TRP", "DETECTOR_BOARD_TRP", "ob_trp"),
    ObFdirParameter("Mechanism board TRP", "MECH_TRP", "MECH_BOARD_TRP", "ob_trp"),
    ObFdirParameter("Motor TRP", "MOTOR_TRP", "MOTOR_TRP", "ob_trp"),
)


def get_limit(key: str) -> MonitoringLimit:
    try:
        return MONITORING_LIMITS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown monitoring limit key: {key}") from exc


def metric_limit_kwargs(key: str) -> dict[str, Bounds | None]:
    """Return the four ``MetricSpec`` limit fields for one constants-backed key."""
    spec = get_limit(key)
    return {
        "bounds": spec.warning_real,
        "alarm_bounds": spec.alarm_real,
        "bounds_adu": spec.warning_adu,
        "alarm_bounds_adu": spec.alarm_adu,
    }


def mms_alarm_limits() -> dict[str, Bounds]:
    """Build the MMS alarm mapping from the same constants-backed registry.

    FPGA core is the OB 1V5 rail and FPGA I/O is the OB 3V3 rail.
    """
    return {
        "eb_12v": _required(get_limit("eb_12v").alarm_real, "eb_12v", "alarm REAL"),
        "eb_neg12v": _required(get_limit("eb_neg12v").alarm_real, "eb_neg12v", "alarm REAL"),
        "eb_5v": _required(get_limit("eb_5v").alarm_real, "eb_5v", "alarm REAL"),
        "eb_3v3": _required(get_limit("eb_3v3").alarm_real, "eb_3v3", "alarm REAL"),
        "eb_mcu_temp": _required(get_limit("eb_mcu_temp").alarm_real, "eb_mcu_temp", "alarm REAL"),
        "eb_internal_trp_temp": _required(get_limit("eb_internal_temp").alarm_real, "eb_internal_temp", "alarm REAL"),
        "eb_psu_trp_temp": _required(get_limit("eb_psu_temp").alarm_real, "eb_psu_temp", "alarm REAL"),
        "eb_tec_rail_v": _required(get_limit("eb_tec_rail").alarm_real, "eb_tec_rail", "alarm REAL"),
        "ob_fpga_core_v": _required(get_limit("ob_1v5").alarm_real, "ob_1v5", "alarm REAL"),
        "ob_fpga_io_v": _required(get_limit("ob_3v3").alarm_real, "ob_3v3", "alarm REAL"),
        "ob_digital_trp": _required(get_limit("ob_trp").alarm_real, "ob_trp", "alarm REAL"),
        "ob_detector_trp": _required(get_limit("ob_trp").alarm_real, "ob_trp", "alarm REAL"),
        "ob_mechanism_trp": _required(get_limit("ob_trp").alarm_real, "ob_trp", "alarm REAL"),
        "ob_motor_trp": _required(get_limit("ob_trp").alarm_real, "ob_trp", "alarm REAL"),
    }


def recommended_plot_limits(
    keys: Iterable[str],
    display_mode: str,
    *,
    padding_fraction: float = 0.15,
    minimum_padding: float | None = None,
) -> Bounds:
    """Derive a plot y-range from constants-backed outer alarm bounds."""
    mode = str(display_mode).upper()
    bounds: list[Bounds] = []
    for key in keys:
        spec = get_limit(key)
        pair = spec.alarm_adu if mode == "ADU" else spec.alarm_real
        if pair is not None:
            bounds.append(pair)
    if not bounds:
        raise RuntimeError(f"No {mode} alarm bounds available for plot keys {tuple(keys)!r}")

    finite_lows = [float(pair[0]) for pair in bounds if pair[0] is not None]
    finite_highs = [float(pair[1]) for pair in bounds if pair[1] is not None]
    if not finite_lows or not finite_highs:
        raise RuntimeError(f"Cannot derive a finite {mode} plot range from open-ended bounds for {tuple(keys)!r}")
    low = min(finite_lows)
    high = max(finite_highs)
    span = max(high - low, 1.0)
    if minimum_padding is None:
        minimum_padding = 100.0 if mode == "ADU" else 0.25
    padding = max(span * float(padding_fraction), float(minimum_padding))
    plot_low = low - padding
    plot_high = high + padding
    if mode == "ADU":
        plot_low = max(0.0, plot_low)
        plot_high = min(4095.0, plot_high)
    return (plot_low, plot_high)
