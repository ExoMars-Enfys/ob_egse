from __future__ import annotations

# Std library
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import time

# Added packages
from nicegui import ui

# Local modules
# core
from core_modules import constants as const
from core_modules import tmstruct

# utilities
from utility_modules import hk_conversions

# widgets
from widget_modules import popup_widget


ValueGetter = Callable[[Any], Any]


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    getter: ValueGetter
    unit: str = ""
    bounds: tuple[float, float] | None = None
    decimals: int = 2
    render: str = "value"
    chip_text: str | None = None
    true_text: str = "YES"
    false_text: str = "NO"
    true_color: str = "green"
    false_color: str = "grey"
    color_map: dict[str, str] | None = None
    popup_attr: str | None = None
    popup_title: str | None = None
    popup_names: list[str] | None = None


@dataclass
class MetricPill:
    spec: MetricSpec
    chip: Any


@dataclass
class MetricsCardController:
    title: str
    pills: list[MetricPill]
    card: Any
    last_packet: Any = None

    def set_visible(self, visible: bool) -> None:
        if visible:
            self.card.classes(remove="hidden")
            return
        self.card.classes(add="hidden")

    def set_no_data(self) -> None:
        for pill in self.pills:
            pill.chip.set_text("---")
            pill.chip.set_background_color("grey")

    def update_from_packet(self, packet: Any) -> None:
        self.last_packet = packet
        for pill in self.pills:
            value = _safe_get_value(pill.spec.getter, packet)

            if pill.spec.render == "bool_status":
                active = _coerce_bool(value)
                if active is None:
                    pill.chip.set_text("---")
                    pill.chip.set_background_color("grey")
                else:
                    pill.chip.set_text(pill.spec.true_text if active else pill.spec.false_text)
                    pill.chip.set_background_color(pill.spec.true_color if active else pill.spec.false_color)
                continue

            if pill.spec.render == "error_chip":
                active = _coerce_bool(value)
                pill.chip.set_text(pill.spec.chip_text or pill.spec.label)
                if active is None:
                    pill.chip.set_background_color("grey")
                else:
                    pill.chip.set_background_color("red" if active else "grey")
                continue

            if pill.spec.render == "state_chip":
                active = _coerce_bool(value)
                pill.chip.set_text(pill.spec.chip_text or pill.spec.label)
                if active is None:
                    pill.chip.set_background_color("grey")
                else:
                    pill.chip.set_background_color("green" if active else "grey")
                continue

            if pill.spec.render == "status_light":
                active = _coerce_bool(value)
                pill.chip.set_text("●")
                if active is None:
                    pill.chip.set_background_color("grey")
                else:
                    pill.chip.set_background_color("green" if active else "red")
                continue

            if value is None:
                pill.chip.set_text("---")
                pill.chip.set_background_color("grey")
                continue

            label = _format_value(value, pill.spec.decimals, pill.spec.unit)
            pill.chip.set_text(label)

            if pill.spec.bounds is None:
                if pill.spec.color_map is not None:
                    mapped_color = pill.spec.color_map.get(str(value), pill.spec.color_map.get("_default", "grey"))
                    pill.chip.set_background_color(mapped_color)
                else:
                    pill.chip.set_background_color("grey")
                continue

            numeric = _coerce_float(value)
            if numeric is None:
                pill.chip.set_background_color("grey")
                continue

            low, high = pill.spec.bounds
            in_bounds = low <= numeric <= high
            pill.chip.set_background_color("green" if in_bounds else "red")


@dataclass
class PacketMetricsCardController:
    state: dict[str, Any]
    cards: dict[str, Any]
    chips: dict[str, Any]

    def set_no_data(self) -> None:
        for chip in self.chips.values():
            chip.set_text("---")
            chip.set_background_color("grey")

    def set_mode(self, mode: str) -> None:
        eb_mode = mode == "EB"
        if "tc_rejected" in self.cards:
            self.cards["tc_rejected"].classes(remove="hidden" if eb_mode else None)
            if not eb_mode:
                self.cards["tc_rejected"].classes(add="hidden")
        if "post_packets" in self.cards:
            self.cards["post_packets"].classes(remove="hidden" if eb_mode else None)
            if not eb_mode:
                self.cards["post_packets"].classes(add="hidden")

    def refresh(self) -> None:
        packet_state = self.state.get("packet_counts", {})
        telemetry_last = packet_state.get("telemetry_last", {})
        eb_hk = telemetry_last.get("EB_HK", {})

        hk_time = eb_hk.get("TIME")
        if hk_time is None:
            hk_time_text = "---"
        elif isinstance(hk_time, datetime):
            delta = datetime.now() - hk_time
            total_seconds = int(delta.total_seconds())
            # Format elapsed time as HH:MM:SS
            hk_time_text = time.strftime("%H:%M:%S", time.gmtime(total_seconds))
        else:
            # Fallback for numeric timestamps (epoch seconds or monotonic floats)
            try:
                hk_time_val = float(hk_time)
                # Prefer epoch-based difference where plausible
                now_epoch = time.time()
                delta_seconds = int(now_epoch - hk_time_val)
                if delta_seconds < 0:
                    # If negative, try monotonic-based difference
                    delta_seconds = int(time.monotonic() - hk_time_val)
                hk_time_text = time.strftime("%H:%M:%S", time.gmtime(max(delta_seconds, 0)))
            except Exception:
                hk_time_text = str(hk_time)

        values = {
            "tc_rejected": eb_hk.get("TCS_REJECTED", "---"),
            "hk_time": hk_time_text,
            "hk_packets": packet_state.get("hk", 0),
            "post_packets": packet_state.get("post", 0),
            "sci_packets": packet_state.get("sci", 0),
        }

        for key, chip in self.chips.items():
            value = values.get(key, "---")
            chip.set_text(str(value))
            chip.set_background_color("grey")


def _safe_get_value(getter: ValueGetter, packet: Any) -> Any:
    try:
        return getter(packet)
    except Exception:
        return None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _format_value(value: Any, decimals: int, unit: str) -> str:
    if isinstance(value, bool):
        text = "YES" if value else "NO"
    elif isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        text = f"{value:.{decimals}f}"
    else:
        text = str(value)

    return f"{text} {unit}".strip()


def _flag_true(packet: Any, attr_name: str, bit_name: str) -> bool | None:
    namespace = getattr(packet, attr_name, None)
    if namespace is None:
        return None
    bit = getattr(namespace, bit_name, None)
    if bit is None:
        return None
    return bool(bit)


def _has_any_asserted(packet: Any, attr_name: str, fields: list[str]) -> bool | None:
    namespace = getattr(packet, attr_name, None)
    if namespace is None:
        return None
    return any(bool(getattr(namespace, field, 0)) for field in fields)


def _decoded(packet: Any, field_name: str) -> float | None:
    return hk_conversions.decode_field(packet, field_name)


def _tec_temp(packet: Any) -> float | None:
    raw = getattr(packet, "EB_PELTIER_TEMP", None)
    if raw is None:
        return None
    return float(raw) * -0.001830011 + 51.27039922


def _state_name(packet: Any) -> str | None:
    value = getattr(packet, "CURRENT_OPERATING_STATE", None)
    if value is None:
        return None
    return {0x00: "INITIALISING", 0x02: "SAFE", 0x04: "STANDBY", 0x08: "ACQ"}.get(int(value), str(value))


def _ob_warm(packet: Any) -> bool | None:
    det = _flag_true(packet, "INSTR_STATUS_FLAGS", "DETECTOR_WARM")
    mech = _flag_true(packet, "INSTR_STATUS_FLAGS", "MECHANISM_WARM")
    if det is None or mech is None:
        return None
    return bool(det and mech)


def _parked(packet: Any) -> bool | None:
    parked_flag = _flag_true(packet, "INSTR_STATUS_FLAGS", "MECHANISM_PARKED")
    if parked_flag is None:
        return None
    return not parked_flag


def _direction(packet: Any) -> str | None:
    namespace = getattr(packet, "MTR_FLAGS", None)
    if namespace is None or not hasattr(namespace, "DIR"):
        return None
    moving = _flag_true(packet, "MTR_FLAGS", "MOVING")
    if moving is not True:
        return None
    return "TO BASE" if int(getattr(namespace, "DIR", 0)) == 0 else "TO OUTER"


def _stop(packet: Any) -> str | None:
    namespace = getattr(packet, "MTR_FLAGS", None)
    if namespace is None:
        return None
    if bool(getattr(namespace, "BASE", 0)):
        return "BASE"
    if bool(getattr(namespace, "OUTER", 0)):
        return "OUTER"
    return "Not At Stop"


def _ns_bool(packet: Any, attr_name: str, bit_name: str) -> bool | None:
    namespace = getattr(packet, attr_name, None)
    if namespace is None or not hasattr(namespace, bit_name):
        return None
    return bool(getattr(namespace, bit_name))


def _eb_hk_specs() -> list[MetricSpec]:
    warning_names = [name for name, _ in tmstruct.eb_warning_flags]
    fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]

    return [
        MetricSpec(
            key="eb_operating_state",
            label="OP",
            getter=_state_name,
            color_map={"INITIALISING": "grey", "SAFE": "blue", "STANDBY": "green", "ACQ": "purple", "_default": "grey"},
        ),
        MetricSpec(
            key="eb_has_errors",
            label="ERRORS",
            getter=lambda hk: bool(getattr(hk, "ERROR_FLAGS", 0)),
            render="bool_status",
            true_text="ALARM",
            false_text="OK",
            true_color="red",
            false_color="green",
            popup_attr="ERROR_FLAGS_BITS",
            popup_title="Error Flags Bitmap",
            popup_names=warning_names,
        ),
        MetricSpec(
            key="eb_has_warnings",
            label="WARNS",
            getter=lambda hk: bool(getattr(hk, "WARNING_FLAGS", 0)),
            render="bool_status",
            true_text="ALARM",
            false_text="OK",
            true_color="red",
            false_color="green",
            popup_attr="WARNING_FLAGS_BITS",
            popup_title="Warning Flags Bitmap",
            popup_names=warning_names,
        ),
        MetricSpec(
            key="eb_fdir_alarm",
            label="FDIR ALM",
            getter=lambda hk: bool(getattr(hk, "FDIR_ALARM_FLAGS", 0)),
            render="bool_status",
            true_text="ALARM",
            false_text="OK",
            true_color="red",
            false_color="green",
            popup_attr="FDIR_ALARM_FLAGS_BITS",
            popup_title="FDIR Alarm Flags Bitmap",
            popup_names=fdir_names,
        ),
        MetricSpec(
            key="eb_fdir_warning",
            label="FDIR WRN",
            getter=lambda hk: bool(getattr(hk, "FDIR_WARNING_FLAGS", 0)),
            render="bool_status",
            true_text="ALARM",
            false_text="OK",
            true_color="red",
            false_color="green",
            popup_attr="FDIR_WARNING_FLAGS_BITS",
            popup_title="FDIR Warning Flags Bitmap",
            popup_names=fdir_names,
        ),
        MetricSpec(
            key="eb_12v",
            label="+12V",
            getter=lambda hk: _decoded(hk, "EB_MEAS_MAIN_12V"),
            unit="V",
            bounds=(11.0, 13.0),
        ),
        MetricSpec(
            key="eb_neg12v",
            label="-12V",
            getter=lambda hk: _decoded(hk, "EB_MEAS_MAIN_NEG12V"),
            unit="V",
            bounds=(-13.0, -11.0),
        ),
        MetricSpec(key="eb_5v", label="+5V", getter=lambda hk: _decoded(hk, "EB_MEAS_5V"), unit="V", bounds=(4.5, 5.5)),
        MetricSpec(
            key="eb_3v3", label="+3V3", getter=lambda hk: _decoded(hk, "EB_MEAS_3V3"), unit="V", bounds=(2.8, 3.8)
        ),
        MetricSpec(
            key="eb_mcu_temp",
            label="MCU TEMP",
            getter=lambda hk: _decoded(hk, "EB_MCU_INTERNAL_TEMP"),
            unit="°C",
            bounds=const.WLIM_TPR,
        ),
        MetricSpec(
            key="eb_internal_temp",
            label="INTERNAL TEMP",
            getter=lambda hk: _decoded(hk, "EB_INTERNAL_TRP_TEMP"),
            unit="°C",
            bounds=const.WLIM_TPR,
        ),
        MetricSpec(
            key="eb_psu_temp",
            label="PSU TEMP",
            getter=lambda hk: _decoded(hk, "EB_PSU_BOARD_TEMP"),
            unit="°C",
            bounds=const.WLIM_TPR,
        ),
        MetricSpec(key="tec_setpoint", label="TEC_SETPOINT", getter=lambda hk: getattr(hk, "TEC_SETPOINT", None)),
        MetricSpec(
            key="tec_drive_i",
            label="TEC Drive I",
            getter=lambda hk: (float(getattr(hk, "EB_TEC_DRIVE_CURRENT", 0)) * 0.0000162),
            unit="A",
            decimals=4,
        ),
        MetricSpec(key="tec_temp", label="TEC TEMP", getter=_tec_temp, unit="°C"),
        MetricSpec(key="tec_dac", label="TEC DAC OUT", getter=lambda hk: getattr(hk, "EB_TEC_DAC_OUTPUT", None)),
        MetricSpec(
            key="eb_tec_at_setpoint",
            label="TEC At Set",
            getter=lambda hk: _flag_true(hk, "INSTR_STATUS_FLAGS", "TEC_AT_SETPOINT"),
            render="bool_status",
            true_text="YES",
            false_text="NO",
            true_color="green",
            false_color="grey",
        ),
    ]


def _ob_hk_specs() -> list[MetricSpec]:
    return [
        MetricSpec(
            key="ob_3v3",
            label="OB+3.3V",
            getter=lambda hk: _decoded(hk, "OB_3V3_VOLTAGE"),
            unit="V",
            bounds=const.WLIM_3V3,
        ),
        MetricSpec(
            key="ob_1v5",
            label="OB+1.5V",
            getter=lambda hk: _decoded(hk, "OB_1V5_VOLTAGE"),
            unit="V",
            bounds=const.WLIM_1V5,
        ),
        MetricSpec(
            key="ob_dig",
            label="DIG:",
            getter=lambda hk: _decoded(hk, "OB_DIGITAL_TRP"),
            unit="°C",
            bounds=const.WLIM_TPR,
        ),
        MetricSpec(
            key="ob_det",
            label="DET:",
            getter=lambda hk: _decoded(hk, "OB_DETECTOR_TRP"),
            unit="°C",
            bounds=const.WLIM_TPR,
        ),
        MetricSpec(
            key="ob_mech",
            label="MECH:",
            getter=lambda hk: _decoded(hk, "OB_MECHANISM_TRP"),
            unit="°C",
            bounds=const.WLIM_TPR,
        ),
        MetricSpec(
            key="ob_mtr",
            label="MTR",
            getter=lambda hk: _decoded(hk, "OB_MOTOR_TRP"),
            unit="°C",
            bounds=const.WLIM_TPR,
        ),
        MetricSpec(key="cmd_cnt", label="CMD CNT", getter=lambda hk: getattr(hk, "OB_COMMAND_COUNT", None)),
        MetricSpec(
            key="ob_enabled",
            label="OB ENBLD",
            getter=lambda hk: _flag_true(hk, "INSTR_STATUS_FLAGS", "OB_5V_ENABLED"),
            render="bool_status",
            true_text="ON",
            false_text="OFF",
            true_color="green",
            false_color="red",
        ),
        MetricSpec(
            key="ob_home",
            label="HOME",
            getter=lambda hk: _flag_true(hk, "INSTR_STATUS_FLAGS", "HOMING_COMPLETE"),
            render="bool_status",
        ),
        MetricSpec(
            key="ob_parked",
            label="PARKED",
            getter=_parked,
            render="bool_status",
            true_text="YES",
            false_text="NO",
            true_color="orange",
            false_color="grey",
        ),
        MetricSpec(
            key="ob_warm",
            label="OB WARM",
            getter=_ob_warm,
            render="bool_status",
        ),
        MetricSpec(
            key="ob_mech_pwr",
            label="MECH PWR",
            getter=lambda hk: _flag_true(hk, "INSTR_STATUS_FLAGS", "OB_MECHANISM_BOARD_ENABLED"),
            render="bool_status",
            true_text="ON",
            false_text="OFF",
            true_color="green",
            false_color="red",
        ),
        MetricSpec(
            key="ob_det_pwr",
            label="DET PWR",
            getter=lambda hk: _flag_true(hk, "INSTR_STATUS_FLAGS", "OB_DETECTOR_BOARD_ENABLED"),
            render="bool_status",
            true_text="ON",
            false_text="OFF",
            true_color="green",
            false_color="red",
        ),
        MetricSpec(
            key="ob_motor_moving",
            label="MOVING",
            getter=lambda hk: _flag_true(hk, "MTR_FLAGS", "MOVING"),
            render="bool_status",
            true_text="Moving",
            false_text="STATIONARY",
            true_color="green",
            false_color="grey",
        ),
        MetricSpec(
            key="ob_direction",
            label="DIRECTION",
            getter=_direction,
            color_map={"TO BASE": "purple", "TO OUTER": "blue", "_default": "grey"},
        ),
        MetricSpec(
            key="ob_stop",
            label="STOP",
            getter=_stop,
            color_map={"BASE": "purple", "OUTER": "blue", "Not At Stop": "grey", "_default": "grey"},
        ),
        MetricSpec(key="ob_steps", label="STEPS", getter=lambda hk: getattr(hk, "OB_MOTOR_ABS_STEPS", None)),
        MetricSpec(
            key="ob_mech_cal",
            label="MECH CAL",
            getter=lambda hk: _flag_true(hk, "MTR_FLAGS", "CAL"),
            render="state_chip",
            chip_text="CAL",
        ),
        MetricSpec(
            key="mech_htr_status",
            label="MECH HTR STATUS",
            getter=lambda hk: _ns_bool(hk, "THRM_STATUS", "HMS"),
            render="status_light",
        ),
        MetricSpec(
            key="mech_manual",
            label="MANUAL",
            getter=lambda hk: _ns_bool(hk, "THRM_STATUS", "MM"),
            render="state_chip",
            chip_text="MAN",
        ),
        MetricSpec(
            key="mech_auto",
            label="AUTO",
            getter=lambda hk: _ns_bool(hk, "THRM_STATUS", "MA"),
            render="state_chip",
            chip_text="AUTO",
        ),
        MetricSpec(
            key="det_htr_status",
            label="DET HTR STATUS",
            getter=lambda hk: _ns_bool(hk, "THRM_STATUS", "HDS"),
            render="status_light",
        ),
        MetricSpec(
            key="det_manual",
            label="MANUAL",
            getter=lambda hk: _ns_bool(hk, "THRM_STATUS", "DM"),
            render="state_chip",
            chip_text="MAN",
        ),
        MetricSpec(
            key="det_auto",
            label="AUTO",
            getter=lambda hk: _ns_bool(hk, "THRM_STATUS", "DA"),
            render="state_chip",
            chip_text="AUTO",
        ),
        MetricSpec(
            key="det_sci",
            label="SCI",
            getter=lambda hk: _ns_bool(hk, "THRM_STATUS", "S"),
            render="bool_status",
            true_text="ON",
            false_text="OFF",
            true_color="green",
            false_color="grey",
        ),
        MetricSpec(key="err_ipi", label="IPI", getter=lambda hk: _ns_bool(hk, "ERRORS", "IPI"), render="error_chip"),
        MetricSpec(key="err_ios", label="IOS", getter=lambda hk: _ns_bool(hk, "ERRORS", "IOS"), render="error_chip"),
        MetricSpec(key="err_icr", label="ICR", getter=lambda hk: _ns_bool(hk, "ERRORS", "ICR"), render="error_chip"),
        MetricSpec(key="err_mor", label="MOR", getter=lambda hk: _ns_bool(hk, "ERRORS", "MOR"), render="error_chip"),
        MetricSpec(key="err_tmo", label="TMO", getter=lambda hk: _ns_bool(hk, "ERRORS", "TMO"), render="error_chip"),
        MetricSpec(key="err_ipa", label="IPA", getter=lambda hk: _ns_bool(hk, "ERRORS", "IPA"), render="error_chip"),
        MetricSpec(key="mtr_cd", label="CD", getter=lambda hk: _ns_bool(hk, "MTR_ERRORS", "CD"), render="error_chip"),
        MetricSpec(key="mtr_ab", label="AB", getter=lambda hk: _ns_bool(hk, "MTR_ERRORS", "AB"), render="error_chip"),
        MetricSpec(
            key="mtr_abs", label="ABS", getter=lambda hk: _ns_bool(hk, "MTR_ERRORS", "ABS"), render="error_chip"
        ),
        MetricSpec(
            key="mtr_dse", label="DSE", getter=lambda hk: _ns_bool(hk, "MTR_ERRORS", "DSE"), render="error_chip"
        ),
    ]


def _render_metric_grid(*, specs: list[MetricSpec], columns: int, pills: list[MetricPill]) -> None:
    with ui.grid(columns=columns).classes("w-full gap-2"):
        for spec in specs:
            if spec.render == "error_chip":
                chip = ui.chip(spec.chip_text or spec.label, color="grey").props("dense").classes("w-fit")
                pills.append(MetricPill(spec=spec, chip=chip))
            else:
                with ui.column().classes("items-center gap-0"):
                    ui.label(spec.label).classes("text-xs")
                    chip = ui.chip("---", color="grey").props("dense").classes("w-fit")
                    pills.append(MetricPill(spec=spec, chip=chip))


def _bind_metric_popups(controller: MetricsCardController) -> None:
    for pill in controller.pills:
        spec = pill.spec
        if not spec.popup_attr:
            continue
        pill.chip.props("clickable")
        pill.chip.classes(add="cursor-pointer")

        def _show_popup(_: Any = None, pill_spec: MetricSpec = spec) -> None:
            popup_widget.show_flag_popup(
                title=pill_spec.popup_title or pill_spec.label,
                packet=controller.last_packet,
                attr_name=pill_spec.popup_attr or "",
                ordered_names=pill_spec.popup_names,
            )

        pill.chip.on("click", _show_popup)


def create_metrics_card(title: str, specs: list[MetricSpec]) -> MetricsCardController:
    pills: list[MetricPill] = []

    with ui.card().classes("w-full") as card:
        ui.label(title).classes("text-sm font-bold")
        _render_metric_grid(specs=specs, columns=5, pills=pills)

    controller = MetricsCardController(title=title, pills=pills, card=card)
    controller.set_no_data()
    return controller


def create_default_eb_metrics_card() -> MetricsCardController:
    specs = _eb_hk_specs()
    spec_map = {spec.key: spec for spec in specs}
    pills: list[MetricPill] = []

    with ui.card().classes("w-full") as card:
        ui.label("EB STATUS").classes("text-sm font-bold")
        _render_metric_grid(
            specs=[
                spec_map[k]
                for k in ("eb_operating_state", "eb_has_errors", "eb_has_warnings", "eb_fdir_alarm", "eb_fdir_warning")
            ],
            columns=5,
            pills=pills,
        )
        _render_metric_grid(
            specs=[spec_map[k] for k in ("eb_12v", "eb_neg12v", "eb_5v", "eb_3v3")],
            columns=4,
            pills=pills,
        )
        _render_metric_grid(
            specs=[spec_map[k] for k in ("eb_mcu_temp", "eb_internal_temp", "eb_psu_temp")],
            columns=3,
            pills=pills,
        )

        ui.space()
        ui.label("TEC STATUS").classes("text-sm font-bold")
        _render_metric_grid(
            specs=[spec_map[k] for k in ("tec_setpoint", "tec_drive_i", "tec_temp", "tec_dac", "eb_tec_at_setpoint")],
            columns=5,
            pills=pills,
        )

    controller = MetricsCardController(title="EB STATUS", pills=pills, card=card)
    controller.set_no_data()
    _bind_metric_popups(controller)
    return controller


def create_default_ob_metrics_card() -> MetricsCardController:
    specs = _ob_hk_specs()
    spec_map = {spec.key: spec for spec in specs}
    pills: list[MetricPill] = []

    with ui.card().classes("w-full") as card:
        ui.label("OB STATUS").classes("text-sm font-bold")
        _render_metric_grid(
            specs=[spec_map[k] for k in ("ob_3v3", "ob_1v5", "ob_dig", "ob_det", "ob_mech", "ob_mtr")],
            columns=6,
            pills=pills,
        )
        _render_metric_grid(
            specs=[spec_map[k] for k in ("cmd_cnt", "ob_enabled", "ob_home", "ob_parked")],
            columns=4,
            pills=pills,
        )
        _render_metric_grid(
            specs=[spec_map[k] for k in ("ob_warm", "ob_mech_pwr", "ob_det_pwr")],
            columns=3,
            pills=pills,
        )
        ui.space()
        ui.label("MOTOR STATUS").classes("text-sm font-bold")
        _render_metric_grid(
            specs=[spec_map[k] for k in ("ob_motor_moving", "ob_direction", "ob_stop", "ob_steps", "ob_mech_cal")],
            columns=5,
            pills=pills,
        )
        ui.space()
        ui.label("HEATER STATUS").classes("text-sm font-bold")
        _render_metric_grid(
            specs=[spec_map[k] for k in ("mech_htr_status", "mech_manual", "mech_auto")],
            columns=3,
            pills=pills,
        )

        _render_metric_grid(
            specs=[spec_map[k] for k in ("det_htr_status", "det_manual", "det_auto", "det_sci")],
            columns=4,
            pills=pills,
        )
        ui.space()
        ui.label("OB ERRORS").classes("text-sm font-bold")
        _render_metric_grid(
            specs=[spec_map[k] for k in ("err_ipi", "err_ios", "err_icr", "err_mor", "err_tmo", "err_ipa")],
            columns=6,
            pills=pills,
        )
        _render_metric_grid(
            specs=[spec_map[k] for k in ("mtr_cd", "mtr_ab", "mtr_abs", "mtr_dse")],
            columns=4,
            pills=pills,
        )

    controller = MetricsCardController(title="OB STATUS", pills=pills, card=card)
    controller.set_no_data()
    return controller


def create_packet_metrics_card(state: dict[str, Any]) -> PacketMetricsCardController:
    cards: dict[str, Any] = {}
    chips: dict[str, Any] = {}

    with ui.card().classes("w-full"):
        ui.label("PACKET METRICS").classes("text-sm font-bold")
        with ui.row().classes("w-full gap-2"):
            fields = [
                ("tc_rejected", "TCs RJCTD"),
                ("hk_time", "HKTime"),
                ("hk_packets", "HK"),
                ("post_packets", "POST"),
                ("sci_packets", "SCI"),
            ]
            for key, label in fields:
                with ui.column().classes("flex-1 items-start gap-0") as card_col:
                    ui.label(label).classes("text-xs self-start")
                    chips[key] = (
                        ui.chip("---", color="grey")
                        .props("dense")
                        .classes("w-fit")
                        .style("justify-content: flex-start;")
                    )
                cards[key] = card_col

    controller = PacketMetricsCardController(state=state, cards=cards, chips=chips)
    controller.set_no_data()
    controller.set_mode(state.get("mode", "EB"))
    return controller
