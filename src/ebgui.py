import logging
import re
from datetime import datetime
from contextlib import nullcontext
from pathlib import Path
from nicegui import app, ui
from matplotlib import dates as mdates
from matplotlib.ticker import FuncFormatter
import time
import os


import constants as const
import eb_interface
import eb_sniffer
import psu
import tc
import tmstruct

logger = logging.getLogger("info_log")
level_options = {"INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}


# Define a custom handler for the GUI
class LogElementHandler(logging.Handler):
    """A logging handler that emits messages to a ui.log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:
        self.element = element
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Map log levels to Tailwind text color classes
            color_map = {
                logging.DEBUG: "text-grey",
                logging.INFO: "text-blue",
                logging.WARNING: "text-orange",
                logging.ERROR: "text-red",
                logging.CRITICAL: "text-red font-bold",
            }
            # Get the class for the current level, default to no class
            log_class = color_map.get(record.levelno, "")
            self.element.push(msg, classes=log_class)  # Push with styling
        except Exception:
            self.handleError(record)


def build_ui(psu_port, port_lock=None, stop_event=None) -> None:
    rsrc_dir = Path(__file__).resolve().parent.parent / "rsrc"
    app.add_static_files("/rsrc", rsrc_dir)
    gui_css_path = rsrc_dir / "guimasterconfig.css"
    gui_css_text = gui_css_path.read_text(encoding="utf-8")

    def _parse_css_vars(css_text: str) -> dict[str, str]:
        vars_map: dict[str, str] = {}
        for line in css_text.splitlines():
            match = re.match(r"\s*--([\w-]+)\s*:\s*([^;]+);", line)
            if match:
                vars_map[match.group(1)] = match.group(2).strip()
        return vars_map

    gui_vars = _parse_css_vars(gui_css_text)
    theme_state = {"value": gui_vars.get("theme-default", "dark")}
    logo_light_src = gui_vars.get("logo-light-src", "/rsrc/Enfys_logo.png")
    logo_dark_src = gui_vars.get("logo-dark-src", "/rsrc/Enfys_logo_-_FINAL_-_WHITE.png")
    labels: dict[str, ui.label] = {}
    status: dict[str, int] = {"pwr": 0, "psu": 0}
    last_hk = {"value": None}
    last_post = {"value": None}
    hk_summary_manual_only = True
    logo_images: list[ui.image] = []
    temp_series_order = ["DIG", "DET", "MECH", "MOT"]
    temp_visibility = {key: True for key in temp_series_order}
    plot_keys = ["plot_psu_rov_htr", "plot_psu_eb", "plot_3v3", "plot_1v5", "plot_temps"]
    alarm_history: dict[str, list[dict[str, object]]] = {"ob": [], "eb": []}
    alarm_current: dict[str, dict[str, object] | None] = {"ob": None, "eb": None}
    alarm_pending: dict[str, dict[str, object] | None] = {"ob": None, "eb": None}
    alarm_last_signature: dict[str, str | None] = {"ob": None, "eb": None}
    alarm_last_active: dict[str, bool] = {"ob": False, "eb": False}
    alarm_acknowledged_signatures: dict[str, set[str]] = {"ob": set(), "eb": set()}
    alarm_history_max = 50
    snapshot_state: dict[str, datetime | None] = {"last_post_logged_time": None}
    last_psu_readings: dict[str, float | int | None] = {
        "status": None,
        "PSU_ROV_HTR_V": None,
        "PSU_ROV_HTR_I": None,
        "PSU_EB_V": None,
        "PSU_EB_I": None,
    }
    temperature_units = {"value": "Metric"}  # "Metric" or "ADU"
    lock_ctx = port_lock if port_lock is not None else nullcontext()

    def set_chip_state(chip: ui.chip, text: str, state: str) -> None:
        chip.set_text(text)
        if state == "ok":
            chip.set_background_color("green")
            chip.set_icon("check_circle")
        elif state == "warning":
            chip.set_background_color("orange")
            chip.set_icon("warning")
        elif state == "alarm":
            chip.set_background_color("red")
            chip.set_icon("error")
        else:
            chip.set_background_color("grey")
            chip.set_icon("")

    def set_chip_color(chip: ui.chip, text: str, color: str, icon: str = "fiber_manual_record") -> None:
        chip.set_text(text)
        chip.set_background_color(color)
        chip.set_icon(icon)

    def _any_flag(ns) -> bool:
        if ns is None:
            return False
        return any(bool(v) for v in ns.__dict__.values())

    def set_status_light(light, ok: bool) -> None:
        if ok:
            light.classes(remove="alarm", add="ok")
        else:
            light.classes(remove="ok", add="alarm")

    def eval_limit_state(
        value: float,
        wlim: tuple[float, float] | None = None,
        alim: tuple[float, float] | None = None,
        ok_range: tuple[float, float] | None = None,
    ) -> str:
        if wlim is not None and alim is not None:
            if value < alim[0] or value > alim[1]:
                return "alarm"
            if value < wlim[0] or value > wlim[1]:
                return "warning"
            return "ok"
        if ok_range is not None:
            return "ok" if ok_range[0] <= value <= ok_range[1] else "alarm"
        return "unknown"

    def _active_flag_names(flag_ns, ordered_names: list[str]) -> list[str]:
        if flag_ns is None:
            return []
        return [
            name
            for name in ordered_names
            if not name.startswith("UNUSED")
            and not name.startswith("RESERVED")
            and getattr(flag_ns, name, 0)
        ]

    def _check_ob_fdir_alarm(hk) -> bool:
        """Check if OB has FDIR alarm or specific warning conditions"""
        if hk is None:
            return False
        
        # Get warning flag names
        warning_names = [name for name, _ in tmstruct.eb_warning_flags]
        fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]
        
        # Get active flags from warning bits
        warning_bits = _active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)
        fdir_alarm_bits = _active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
        fdir_warning_bits = _active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)
        
        # OB-specific warning flags
        ob_warning_flags = [
            "OB_FDIR_ALARM",
            "OB_GENERAL_ERROR",
            "OB_MOTOR_ERROR",
            "OB_UNRESPONSIVE",
            "OB_STEP_COUNT_MISMATCH",
        ]
        
        # OB-related FDIR flags
        ob_fdir_flags = [
            "FPGA_IO_POWER_SUPPLY",
            "FPGA_CORE_POWER_SUPPLY",
            "DIGITAL_BOARD_TRP",
            "DETECTOR_BOARD_TRP",
            "MECH_BOARD_TRP",
            "MOTOR_TRP",
        ]
        
        # Check if any OB warning flags are active
        if any(flag in warning_bits for flag in ob_warning_flags):
            return True
        
        # Check if any OB FDIR flags are active
        if any(flag in fdir_alarm_bits for flag in ob_fdir_flags):
            return True
        if any(flag in fdir_warning_bits for flag in ob_fdir_flags):
            return True
        
        # Check for OB errors
        if _any_flag(getattr(hk, "ERRORS", None)):
            return True
        if _any_flag(getattr(hk, "MTR_ERRORS", None)):
            return True
        
        return False

    def _check_eb_fdir_alarm(hk) -> bool:
        """Check if EB has specific error, warning, or FDIR alarm conditions"""
        if hk is None:
            return False
        
        # Check TCS rejected
        if hasattr(hk, 'TCS_REJECTED') and hk.TCS_REJECTED != 0:
            return True
        
        # Get flag names
        warning_names = [name for name, _ in tmstruct.eb_warning_flags]
        fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]
        
        # Get active flags from bits
        warning_bits = _active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)
        fdir_alarm_bits = _active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
        fdir_warning_bits = _active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)
        
        # EB-specific warning flags to check
        eb_warning_flags = [
            "GENERAL_ERROR",
            "EB_FDIR_ALARM",
            "WATCHDOG_TIMEOUT_DETECTED",
            "NO_RET_RECEIVED",
            "NO_HEALTHY_ASW_IMAGE",
            "PATCH_WRITING_ERROR",
            "RS422_RECEIVE_ERROR",
            "RS422_TRANSMIT_ERROR",
            "RS485_RECEIVE_ERROR",
            "RS485_TRANSMIT_ERROR",
        ]
        
        # EB-specific FDIR flags to check
        eb_fdir_flags = [
            "EB_PLUS_12V_SUPPLY",
            "EB_MINUS_12V_SUPPLY",
            "EB_PLUS_5V_SUPPLY",
            "EB_PLUS_3V3_SUPPLY",
            "PROCESSOR_INTERNAL_TEMPERATURE",
            "INTERNAL_TRP_TEMPERATURE",
            "PSU_BOARD_TEMPERATURE",
        ]
        
        # Check if any EB warning flags are active
        if any(flag in warning_bits for flag in eb_warning_flags):
            return True
        
        # Check if any EB FDIR flags are active
        if any(flag in fdir_alarm_bits for flag in eb_fdir_flags):
            return True
        if any(flag in fdir_warning_bits for flag in eb_fdir_flags):
            return True
        
        return False

    def _format_temperature(value_celsius: float, value_adu: int) -> str:
        """Format temperature based on current unit setting"""
        if temperature_units["value"] == "ADU":
            return f"{value_adu}"
        else:
            return f"{value_celsius:.1f} °C"

    def _format_voltage(value_volts: float, value_adu: int, precision: int = 2) -> str:
        """Format voltage based on current unit setting"""
        if temperature_units["value"] == "ADU":
            return f"{value_adu}"
        return f"{value_volts:.{precision}f} V"

    def _format_alarm_details(kind: str, hk) -> list[str]:
        if hk is None:
            return ["No HK data yet."]
        if kind == "ob":
            details = []
            
            # OB ERRORS
            error_names = [name for name, _ in tmstruct.error_struct]
            errors = _active_flag_names(getattr(hk, "ERRORS", None), error_names)
            for error in errors:
                details.append(f"OB Error: {error}")
            
            # OB MOTOR ERRORS
            mtr_error_names = [name for name, _ in tmstruct.mtr_error_struct]
            mtr_errors = _active_flag_names(getattr(hk, "MTR_ERRORS", None), mtr_error_names)
            for error in mtr_errors:
                details.append(f"OB Motor Error: {error}")
            
            # OB warning flags (from WARNING_FLAGS_BITS)
            warning_names = [name for name, _ in tmstruct.eb_warning_flags]
            warning_bits = _active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)
            ob_warning_flags = [
                "OB_FDIR_ALARM",
                "OB_GENERAL_ERROR",
                "OB_MOTOR_ERROR",
                "OB_UNRESPONSIVE",
                "OB_STEP_COUNT_MISMATCH",
            ]
            for flag in warning_bits:
                if flag in ob_warning_flags:
                    details.append(f"OB Warning: {flag}")
            
            # OB FDIR flags
            fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]
            ob_fdir_flags = [
                "FPGA_IO_POWER_SUPPLY",
                "FPGA_CORE_POWER_SUPPLY",
                "DIGITAL_BOARD_TRP",
                "DETECTOR_BOARD_TRP",
                "MECH_BOARD_TRP",
                "MOTOR_TRP",
            ]
            
            fdir_alarm_bits = _active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
            for flag in fdir_alarm_bits:
                if flag in ob_fdir_flags:
                    details.append(f"OB FDIR Alarm: {flag}")
            
            fdir_warning_bits = _active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)
            for flag in fdir_warning_bits:
                if flag in ob_fdir_flags:
                    details.append(f"OB FDIR Warning: {flag}")
            
            return details if details else ["No OB alarms"]

        if kind == "eb":
            details = []
            
            # Check TCS rejected
            if hasattr(hk, 'TCS_REJECTED') and hk.TCS_REJECTED != 0:
                details.append("TCS Rejected")
            
            # EB-specific warning flags
            warning_names = [name for name, _ in tmstruct.eb_warning_flags]
            warning_bits = _active_flag_names(getattr(hk, "WARNING_FLAGS_BITS", None), warning_names)
            
            eb_warning_flags = [
                "GENERAL_ERROR",
                "EB_FDIR_ALARM",
                "WATCHDOG_TIMEOUT_DETECTED",
                "NO_RET_RECEIVED",
                "NO_HEALTHY_ASW_IMAGE",
                "PATCH_WRITING_ERROR",
                "RS422_RECEIVE_ERROR",
                "RS422_TRANSMIT_ERROR",
                "RS485_RECEIVE_ERROR",
                "RS485_TRANSMIT_ERROR",
            ]
            
            for flag in warning_bits:
                if flag in eb_warning_flags:
                    details.append(f"EB Warning: {flag}")
            
            # EB-specific FDIR flags
            fdir_names = [name for name, _ in tmstruct.eb_fdir_flags]
            fdir_alarm_bits = _active_flag_names(getattr(hk, "FDIR_ALARM_FLAGS_BITS", None), fdir_names)
            fdir_warning_bits = _active_flag_names(getattr(hk, "FDIR_WARNING_FLAGS_BITS", None), fdir_names)
            
            eb_fdir_flags = [
                "EB_PLUS_12V_SUPPLY",
                "EB_MINUS_12V_SUPPLY",
                "EB_PLUS_5V_SUPPLY",
                "EB_PLUS_3V3_SUPPLY",
                "PROCESSOR_INTERNAL_TEMPERATURE",
                "INTERNAL_TRP_TEMPERATURE",
                "PSU_BOARD_TEMPERATURE",
            ]
            
            for flag in fdir_alarm_bits:
                if flag in eb_fdir_flags:
                    details.append(f"EB FDIR Alarm: {flag}")
            
            for flag in fdir_warning_bits:
                if flag in eb_fdir_flags:
                    details.append(f"EB FDIR Warning: {flag}")
            
            return details if details else ["No EB alarms"]

        return ["Unknown alarm type."]

    def _alarm_signature(kind: str, hk) -> str:
        return "|".join(_format_alarm_details(kind, hk))

    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _record_alarm(kind: str, hk, is_active: bool) -> None:
        details = _format_alarm_details(kind, hk)
        signature = "|".join(details)
        
        # Check if any detail is already acknowledged (suppressed)
        any_acknowledged = any(detail in alarm_acknowledged_signatures[kind] for detail in details)
        
        if is_active and any_acknowledged:
            alarm_last_active[kind] = True
            alarm_last_signature[kind] = signature
            return
        if is_active:
            if not alarm_last_active[kind] or signature != alarm_last_signature[kind]:
                # New alarm: move current to pending (don't archive yet)
                if alarm_current[kind] is not None:
                    alarm_pending[kind] = alarm_current[kind]
                alarm_current[kind] = {"time": datetime.now(), "details": details}
                alarm_last_signature[kind] = signature
            alarm_last_active[kind] = True
        else:
            # Alarm cleared: archive pending and current to history
            if alarm_pending[kind] is not None:
                alarm_pending[kind].setdefault("cleared_at", datetime.now())
                alarm_history[kind].append(alarm_pending[kind])
                if len(alarm_history[kind]) > alarm_history_max:
                    alarm_history[kind].pop(0)
                alarm_pending[kind] = None
            if alarm_last_active[kind] and alarm_current[kind] is not None:
                alarm_current[kind].setdefault("cleared_at", datetime.now())
                alarm_history[kind].append(alarm_current[kind])
                if len(alarm_history[kind]) > alarm_history_max:
                    alarm_history[kind].pop(0)
                alarm_current[kind] = None
            alarm_last_active[kind] = False

    def _format_alarm_entry(entry: dict[str, object]) -> str:
        timestamp = entry.get("time")
        cleared_at = entry.get("cleared_at")
        details = entry.get("details", [])
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "Unknown time"
        lines = [f"{_escape_html(time_str)}"]
        for item in details if isinstance(details, list) else []:
            lines.append(f"- {_escape_html(str(item))}")
        if isinstance(cleared_at, datetime):
            cleared_text = cleared_at.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(
                "<span style=\"font-weight: 700; color: #f0a500;\">"
                f"Condition cleared at: {cleared_text}"
                "</span>"
            )
        return "<br>".join(lines)

    def _get_theme_palette(theme: str) -> dict[str, str]:
        prefix = f"{theme}-"

        def _get(name: str, fallback: str = "") -> str:
            return gui_vars.get(prefix + name) or gui_vars.get(name) or fallback

        return {
            "primary_bg": _get("primary-bg", "#ffffff"),
            "secondary_bg": _get("secondary-bg", "#f0f0f0"),
            "heading_color": _get("heading-color", "#000000"),
            "text_color": _get("text-color", "#000000"),
            "accent_color": _get("accent_color", "#1f78b4"),
            "plot_bg": _get("plot-bg", _get("primary-bg", "#ffffff")),
            "plot_grid": _get("plot-grid", "#cfcfcf"),
            "plot_axis": _get("plot-axis", _get("text-color", "#000000")),
            "plot_legend": _get("plot-legend", _get("text-color", "#000000")),
            "plot_spine": _get("plot-spine", _get("text-color", "#000000")),
            "plot_tick": _get("plot-tick", _get("text-color", "#000000")),
        }

    def _apply_plot_theme(ax, palette: dict[str, str]) -> None:
        ax.set_facecolor(palette["plot_bg"])
        ax.figure.set_facecolor(palette["plot_bg"])
        ax.figure.patch.set_facecolor(palette["plot_bg"])
        ax.figure.patch.set_edgecolor(palette["plot_spine"])
        ax.tick_params(colors=palette["plot_tick"])
        ax.title.set_color(palette["plot_axis"])
        ax.xaxis.label.set_color(palette["plot_axis"])
        ax.yaxis.label.set_color(palette["plot_axis"])
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            tick.set_color(palette["plot_tick"])
        for spine in ax.spines.values():
            spine.set_color(palette["plot_spine"])
        ax.grid(True, color=palette["plot_grid"], alpha=0.6, linewidth=0.6)
        legend = ax.get_legend()
        if legend is not None:
            frame = legend.get_frame()
            frame.set_facecolor(palette["plot_bg"])
            frame.set_edgecolor(palette["plot_spine"])
            for text in legend.get_texts():
                text.set_color(palette["plot_legend"])

    def _apply_theme_to_plots(palette: dict[str, str]) -> None:
        for key in plot_keys:
            plot = labels.get(key)
            if plot is None:
                continue
            ax = plot.fig.axes[0]
            _apply_plot_theme(ax, palette)
            plot.fig.canvas.draw_idle()
            plot.fig.canvas.draw()
            convert = getattr(plot, "_convert_to_html", None)
            if callable(convert):
                convert()
            update = getattr(plot, "update", None)
            if callable(update):
                update()

    def _set_logo_sources(src: str) -> None:
        for logo in logo_images:
            logo.props(f"src={src}")
            update = getattr(logo, "update", None)
            if callable(update):
                update()

    def apply_theme(theme: str) -> None:
        palette = _get_theme_palette(theme)
        ui.colors(
            primary=palette["accent_color"],
            accent=palette["accent_color"],
            accent_color=palette["accent_color"],
            secondary=palette["secondary_bg"],
            dark=palette["primary_bg"],
        )
        ui.run_javascript(
            "document.body.classList.remove('theme-dark','theme-light');"
            f"document.body.classList.add('theme-{theme}');"
        )
        logo_src = logo_dark_src if theme == "dark" else logo_light_src
        _set_logo_sources(logo_src)
        _apply_theme_to_plots(palette)

    def toggle_theme() -> None:
        theme_state["value"] = "light" if theme_state["value"] == "dark" else "dark"
        apply_theme(theme_state["value"])

    def _update_unit_dependent_plots() -> None:
        is_adu = temperature_units["value"] == "ADU"

        if "plot_3v3" in labels:
            ax_3v3 = labels["plot_3v3"].fig.axes[0]
            ax_3v3.set_title(f"3V3 Voltage ({'ADU' if is_adu else 'V'})")
            while len(ax_3v3.lines) > 1:
                ax_3v3.lines[-1].remove()
            wlim_3v3 = const.WLIM_3V3_ADU if is_adu else const.WLIM_3V3
            alim_3v3 = const.ALIM_3V3_ADU if is_adu else const.ALIM_3V3
            ax_3v3.axhline(wlim_3v3[0], color="orange", linewidth=1.0, linestyle="--")
            ax_3v3.axhline(wlim_3v3[1], color="orange", linewidth=1.0, linestyle="--")
            ax_3v3.axhline(alim_3v3[0], color="red", linewidth=1.0, linestyle="--")
            ax_3v3.axhline(alim_3v3[1], color="red", linewidth=1.0, linestyle="--")
            labels["plot_3v3"].update()

        if "plot_1v5" in labels:
            ax_1v5 = labels["plot_1v5"].fig.axes[0]
            ax_1v5.set_title(f"1V5 Voltage ({'ADU' if is_adu else 'V'})")
            while len(ax_1v5.lines) > 1:
                ax_1v5.lines[-1].remove()
            wlim_1v5 = const.WLIM_1V5_ADU if is_adu else const.WLIM_1V5
            alim_1v5 = const.ALIM_1V5_ADU if is_adu else const.ALIM_1V5
            ax_1v5.axhline(wlim_1v5[0], color="orange", linewidth=1.0, linestyle="--")
            ax_1v5.axhline(wlim_1v5[1], color="orange", linewidth=1.0, linestyle="--")
            ax_1v5.axhline(alim_1v5[0], color="red", linewidth=1.0, linestyle="--")
            ax_1v5.axhline(alim_1v5[1], color="red", linewidth=1.0, linestyle="--")
            labels["plot_1v5"].update()

        if "plot_temps" in labels:
            ax_temps = labels["plot_temps"].fig.axes[0]
            ax_temps.set_ylabel(f"Temperature ({'ADU' if is_adu else '°C'})")
            while len(ax_temps.lines) > 4:
                ax_temps.lines[-1].remove()
            wlim_tpr = const.WLIM_TPR_ADU if is_adu else const.WLIM_TPR
            alim_tpr = const.ALIM_TPR_ADU if is_adu else const.ALIM_TPR
            ax_temps.axhline(wlim_tpr[0], color="orange", linewidth=1.0, linestyle="--")
            ax_temps.axhline(wlim_tpr[1], color="orange", linewidth=1.0, linestyle="--")
            ax_temps.axhline(alim_tpr[0], color="red", linewidth=1.0, linestyle="--")
            ax_temps.axhline(alim_tpr[1], color="red", linewidth=1.0, linestyle="--")
            labels["plot_temps"].update()

    def toggle_temperature_units() -> None:
        temperature_units["value"] = "ADU" if temperature_units["value"] == "Metric" else "Metric"
        if "unit_toggle_btn" in labels:
            labels["unit_toggle_btn"].set_text(f"Unit Toggle : {temperature_units['value']}")
        _update_unit_dependent_plots()

    def check_hk_manually() -> None:
        """Manually trigger HK packet validation"""
        if last_hk["value"] is not None:
            hk = last_hk["value"]

            eb_12v = hk.EB_MEAS_MAIN_12V * 0.000400543
            eb_neg12v = hk.EB_MEAS_MAIN_NEG12V * -0.00038147
            eb_5v = hk.EB_MEAS_5V * 0.000152829
            eb_3v3 = hk.EB_MEAS_3V3 * 0.0000763
            eb_tec_v = hk.EB_MEAS_TEC_RAIL * 0.0000763
            eb_0v = hk.EB_0V_ADC_READING * 0.0000763
            eb_tec_i = hk.EB_TEC_DRIVE_CURRENT * 0.0000162
            eb_mcu_temp_adu = hk.EB_MCU_INTERNAL_TEMP
            eb_mcu_temp = eb_mcu_temp_adu * 0.01637198 - 273
            eb_peltier_temp_adu = hk.EB_PELTIER_TEMP
            eb_peltier_temp = eb_peltier_temp_adu * -0.001830011 + 51.27039922
            eb_internal_trp_adu = hk.EB_INTERNAL_TRP_TEMP
            eb_internal_trp = eb_sniffer.thermistor_adu_to_temp(eb_internal_trp_adu)
            eb_psu_board_temp_adu = hk.EB_PSU_BOARD_TEMP
            eb_psu_board_temp = eb_sniffer.thermistor_adu_to_temp(eb_psu_board_temp_adu)

            labels["hk_tcs_accepted"].set_text(f"{hk.TCS_ACCEPTED}")
            labels["hk_tcs_accepted"].set_background_color("green" if hk.TCS_ACCEPTED == 2 else "red")
            labels["hk_tcs_accepted"].set_icon("check_circle" if hk.TCS_ACCEPTED == 2 else "error")

            labels["hk_tcs_rejected"].set_text(f"{hk.TCS_REJECTED}")
            labels["hk_tcs_rejected"].set_background_color("green" if hk.TCS_REJECTED == 0 else "red")
            labels["hk_tcs_rejected"].set_icon("check_circle" if hk.TCS_REJECTED == 0 else "error")

            labels["hk_instr_status_flags"].set_text(f"{hk.INSTRUMENT_STATUS_FLAGS}")
            labels["hk_instr_status_flags"].set_background_color("green" if hk.INSTRUMENT_STATUS_FLAGS == 6 else "red")
            labels["hk_instr_status_flags"].set_icon("check_circle" if hk.INSTRUMENT_STATUS_FLAGS == 6 else "error")

            labels["hk_error_flags"].set_text(f"{hk.ERROR_FLAGS}")
            labels["hk_error_flags"].set_background_color("green" if hk.ERROR_FLAGS == 0 else "red")
            labels["hk_error_flags"].set_icon("check_circle" if hk.ERROR_FLAGS == 0 else "error")

            labels["hk_warning_flags"].set_text(f"{hk.WARNING_FLAGS}")
            labels["hk_warning_flags"].set_background_color("green" if hk.WARNING_FLAGS == 0 else "red")
            labels["hk_warning_flags"].set_icon("check_circle" if hk.WARNING_FLAGS == 0 else "error")

            labels["hk_fdir_alarms"].set_text(f"{hk.FDIR_ALARM_FLAGS}")
            labels["hk_fdir_alarms"].set_background_color("green" if hk.FDIR_ALARM_FLAGS == 0 else "red")
            labels["hk_fdir_alarms"].set_icon("check_circle" if hk.FDIR_ALARM_FLAGS == 0 else "error")

            labels["hk_fdir_warnings"].set_text(f"{hk.FDIR_WARNING_FLAGS}")
            labels["hk_fdir_warnings"].set_background_color("green" if hk.FDIR_WARNING_FLAGS == 0 else "red")
            labels["hk_fdir_warnings"].set_icon("check_circle" if hk.FDIR_WARNING_FLAGS == 0 else "error")

            labels["hk_eb_12v"].set_text(_format_voltage(eb_12v, hk.EB_MEAS_MAIN_12V))
            labels["hk_eb_12v"].set_background_color("green" if 11.0 <= eb_12v <= 13.0 else "red")
            labels["hk_eb_12v"].set_icon("check_circle" if 11.0 <= eb_12v <= 13.0 else "error")

            labels["hk_eb_neg12v"].set_text(_format_voltage(eb_neg12v, hk.EB_MEAS_MAIN_NEG12V))
            labels["hk_eb_neg12v"].set_background_color("green" if -13.0 <= eb_neg12v <= -11.0 else "red")
            labels["hk_eb_neg12v"].set_icon("check_circle" if -13.0 <= eb_neg12v <= -11.0 else "error")

            labels["hk_eb_5v"].set_text(_format_voltage(eb_5v, hk.EB_MEAS_5V))
            labels["hk_eb_5v"].set_background_color("green" if 4.5 <= eb_5v <= 5.5 else "red")
            labels["hk_eb_5v"].set_icon("check_circle" if 4.5 <= eb_5v <= 5.5 else "error")

            labels["hk_eb_3v3"].set_text(_format_voltage(eb_3v3, hk.EB_MEAS_3V3))
            labels["hk_eb_3v3"].set_background_color("green" if 2.8 <= eb_3v3 <= 3.8 else "red")
            labels["hk_eb_3v3"].set_icon("check_circle" if 2.8 <= eb_3v3 <= 3.8 else "error")

            labels["hk_eb_tec_v"].set_text(_format_voltage(eb_tec_v, hk.EB_MEAS_TEC_RAIL))
            labels["hk_eb_tec_v"].set_background_color("green" if -0.5 <= eb_tec_v <= 0.5 else "red")
            labels["hk_eb_tec_v"].set_icon("check_circle" if -0.5 <= eb_tec_v <= 0.5 else "error")

            labels["hk_eb_0v"].set_text(_format_voltage(eb_0v, hk.EB_0V_ADC_READING))
            labels["hk_eb_0v"].set_background_color("green" if -0.5 <= eb_0v <= 0.5 else "red")
            labels["hk_eb_0v"].set_icon("check_circle" if -0.5 <= eb_0v <= 0.5 else "error")

            labels["hk_eb_mcu_temp"].set_text(_format_temperature(eb_mcu_temp, eb_mcu_temp_adu))
            labels["hk_eb_mcu_temp"].set_background_color("green" if 18.0 <= eb_mcu_temp <= 43.0 else "red")
            labels["hk_eb_mcu_temp"].set_icon("check_circle" if 18.0 <= eb_mcu_temp <= 43.0 else "error")

            labels["hk_eb_peltier_temp"].set_text(_format_temperature(eb_peltier_temp, eb_peltier_temp_adu))
            labels["hk_eb_peltier_temp"].set_background_color("green" if 18.0 <= eb_peltier_temp <= 43.0 else "red")
            labels["hk_eb_peltier_temp"].set_icon("check_circle" if 18.0 <= eb_peltier_temp <= 43.0 else "error")

            labels["hk_eb_internal_trp"].set_text(_format_temperature(eb_internal_trp, eb_internal_trp_adu))
            labels["hk_eb_internal_trp"].set_background_color("green" if 18.0 <= eb_internal_trp <= 43.0 else "red")
            labels["hk_eb_internal_trp"].set_icon("check_circle" if 18.0 <= eb_internal_trp <= 43.0 else "error")

            labels["hk_eb_psu_board_temp"].set_text(_format_temperature(eb_psu_board_temp, eb_psu_board_temp_adu))
            labels["hk_eb_psu_board_temp"].set_background_color("green" if 18.0 <= eb_psu_board_temp <= 43.0 else "red")
            labels["hk_eb_psu_board_temp"].set_icon("check_circle" if 18.0 <= eb_psu_board_temp <= 43.0 else "error")

            labels["hk_eb_tec_drive_i"].set_text(f"{eb_tec_i:.4f} A")
            labels["hk_eb_tec_drive_i"].set_background_color("green" if -0.1 <= eb_tec_i <= 0.1 else "red")
            labels["hk_eb_tec_drive_i"].set_icon("check_circle" if -0.1 <= eb_tec_i <= 0.1 else "error")

            ui.notify("HK validation complete", type="positive")
        else:
            ui.notify("No HK data available yet", type="warning")

    def check_post_manually() -> None:
        """Manually trigger POST packet validation"""
        if last_post["value"] is not None:
            post = last_post["value"]

            set_chip_state(
                labels["post_warning_flags"],
                f"{post.POST_WARNING_FLAGS}",
                "ok" if post.POST_WARNING_FLAGS == 0 else "alarm",
            )
            set_chip_state(
                labels["post_error_flags"],
                f"{post.POST_ERROR_FLAGS}",
                "ok" if post.POST_ERROR_FLAGS == 0 else "alarm",
            )
            set_chip_state(
                labels["post_bad_flash"],
                f"{post.NUM_BAD_FLASH_BLOCKS}",
                "ok" if post.NUM_BAD_FLASH_BLOCKS == 0 else "alarm",
            )
            set_chip_state(
                labels["post_bad_sram"],
                f"{post.NUM_BAD_SRAM_BLOCKS}",
                "ok" if post.NUM_BAD_SRAM_BLOCKS == 0 else "alarm",
            )
            set_chip_state(
                labels["post_asw1_crc"],
                f"0x{post.ASW_IMAGE_1_CRC:04X}",
                "ok" if post.ASW_IMAGE_1_CRC == 0xBAF7 else "alarm",
            )
            set_chip_state(
                labels["post_asw2_crc"],
                f"0x{post.ASW_IMAGE_2_CRC:04X}",
                "ok" if post.ASW_IMAGE_2_CRC == 0x5C55 else "alarm",
            )
            set_chip_state(
                labels["post_asw3_crc"],
                f"0x{post.ASW_IMAGE_3_CRC:04X}",
                "ok" if post.ASW_IMAGE_3_CRC == 0x01CB else "alarm",
            )
            set_chip_state(
                labels["post_asw4_crc"],
                f"0x{post.ASW_IMAGE_4_CRC:04X}",
                "ok" if post.ASW_IMAGE_4_CRC == 0x5318 else "alarm",
            )
            set_chip_state(
                labels["post_asw5_crc"],
                f"0x{post.ASW_IMAGE_5_CRC:04X}",
                "ok" if post.ASW_IMAGE_5_CRC == 0xDCAE else "alarm",
            )
            set_chip_state(
                labels["post_bsw_crc"],
                f"0x{post.BSW_IMAGE_CRC:04X}",
                "ok" if post.BSW_IMAGE_CRC == 0xD2D7 else "alarm",
            )
            set_chip_state(
                labels["post_meas_table_crc"],
                f"0x{post.MEASUREMENT_TABLE_CRC:04X}",
                "ok" if post.MEASUREMENT_TABLE_CRC == 0x9D9B else "alarm",
            )

            all_post_passed = (
                post.POST_WARNING_FLAGS == 0
                and post.POST_ERROR_FLAGS == 0
                and post.NUM_BAD_FLASH_BLOCKS == 0
                and post.NUM_BAD_SRAM_BLOCKS == 0
                and post.ASW_IMAGE_1_CRC == 0xBAF7
                and post.ASW_IMAGE_2_CRC == 0x5C55
                and post.ASW_IMAGE_3_CRC == 0x01CB
                and post.ASW_IMAGE_4_CRC == 0x5318
                and post.ASW_IMAGE_5_CRC == 0xDCAE
                and post.BSW_IMAGE_CRC == 0xD2D7
                and post.MEASUREMENT_TABLE_CRC == 0x9D9B
            )
            if all_post_passed:
                labels["post_status"].set_text("✅ POST TEST PASSED")
                labels["post_status"].style("color: green; font-weight: bold;")
            else:
                labels["post_status"].set_text("❌ POST TEST FAILED")
                labels["post_status"].style("color: red; font-weight: bold;")

            ui.notify("POST validation complete", type="positive")
        else:
            ui.notify("No POST data available yet", type="warning")

    log_search_state = {"enabled": False}

    def update_hk_display() -> None:
        def set_label_color(label: ui.label, color: str) -> None:
            label.style(f"color: {color}")

        def apply_temp_visibility() -> None:
            if "plot_temps" not in labels:
                return
            plot_ax = labels["plot_temps"].fig.axes[0]
            for idx, key in enumerate(temp_series_order):
                plot_ax.lines[idx].set_visible(temp_visibility[key])

        def get_temp_y_limits(hk) -> tuple[float, float]:
            temp_values = {
                "DIG": hk.DIGITAL_TRP,
                "DET": hk.DETEC_TRP,
                "MECH": hk.MECH_TRP,
                "MOT": hk.MOTOR_TRP,
            }
            selected_values = [temp_values[key] for key in temp_series_order if temp_visibility[key]]
            if selected_values:
                min_val = min(selected_values) - 20
                max_val = max(selected_values) + 20
            else:
                min_val = const.WLIM_TPR_ADU[0] - 20
                max_val = const.WLIM_TPR_ADU[1] + 20
            return (min_val, max_val)

        def poll_latest_hk() -> None:
            # Only read new log data if log search is enabled; always process queued packets
            if log_search_state["enabled"]:
                rs422_log = eb_interface.locate_latest_rs422_log()
                if eb_interface.rs422_log_changed(rs422_log) and rs422_log is not None:
                    try:
                        eb_sniffer.read_pkt(rs422_log, latest_only=True)
                    except Exception as exc:
                        logger.error(f"[ERROR] Failed to read RS422if log: {exc}")

            if not const.hk_queue.empty():
                hk = const.hk_queue.get()

                if not hasattr(hk, "TIME"):
                    hk.TIME = datetime.now()

                last_hk["value"] = hk

                eb_12v = hk.EB_MEAS_MAIN_12V * 0.000400543
                eb_neg12v = hk.EB_MEAS_MAIN_NEG12V * -0.00038147
                eb_5v = hk.EB_MEAS_5V * 0.000152829
                eb_3v3 = hk.EB_MEAS_3V3 * 0.0000763
                eb_tec_v = hk.EB_MEAS_TEC_RAIL * 0.0000763
                eb_0v = hk.EB_0V_ADC_READING * 0.0000763
                eb_1v5 = hk.OB_1V5_VOLTAGE / 1000
                eb_tec_i = hk.EB_TEC_DRIVE_CURRENT * 0.0000162
                eb_mcu_temp_adu = hk.EB_MCU_INTERNAL_TEMP
                eb_mcu_temp = eb_mcu_temp_adu * 0.01637198 - 273
                eb_peltier_temp_adu = hk.EB_PELTIER_TEMP
                eb_peltier_temp = eb_peltier_temp_adu * -0.001830011 + 51.27039922
                eb_internal_trp_adu = hk.EB_INTERNAL_TRP_TEMP
                eb_internal_trp = eb_sniffer.thermistor_adu_to_temp(eb_internal_trp_adu)
                eb_psu_board_temp_adu = hk.EB_PSU_BOARD_TEMP
                eb_psu_board_temp = eb_sniffer.thermistor_adu_to_temp(eb_psu_board_temp_adu)

                ob_alarm = _check_ob_fdir_alarm(hk)
                eb_alarm = _check_eb_fdir_alarm(hk)
                ob_details = _format_alarm_details("ob", hk) if ob_alarm else []
                eb_details = _format_alarm_details("eb", hk) if eb_alarm else []
                ob_any_acknowledged = any(detail in alarm_acknowledged_signatures["ob"] for detail in ob_details)
                eb_any_acknowledged = any(detail in alarm_acknowledged_signatures["eb"] for detail in eb_details)
                ob_display_alarm = ob_alarm and not ob_any_acknowledged
                eb_display_alarm = eb_alarm and not eb_any_acknowledged
                if "ob_warning_light" in labels:
                    set_status_light(labels["ob_warning_light"], ok=not ob_display_alarm)
                if "eb_warning_light" in labels:
                    set_status_light(labels["eb_warning_light"], ok=not eb_display_alarm)

                _record_alarm("ob", hk, ob_alarm)
                _record_alarm("eb", hk, eb_alarm)

                op_state_map = {0x00: "INITIALISING", 0x02: "SAFE", 0x04: "STANDBY", 0x08: "ACQ"}
                op_state_label = op_state_map.get(hk.CURRENT_OPERATING_STATE, str(hk.CURRENT_OPERATING_STATE))
                op_state_color_map = {
                    0x00: "grey",
                    0x02: "blue",
                    0x04: "green",
                    0x08: "purple",
                }
                op_state_color = op_state_color_map.get(hk.CURRENT_OPERATING_STATE, "grey")
                op_state_icon = "fiber_manual_record" if hk.CURRENT_OPERATING_STATE in op_state_color_map else "help_outline"
                if not hk_summary_manual_only:
                    labels["hk_tcs_accepted"].set_text(f"{hk.TCS_ACCEPTED}")
                    labels["hk_tcs_accepted"].set_background_color("green" if hk.TCS_ACCEPTED == 2 else "red")
                    labels["hk_tcs_accepted"].set_icon("check_circle" if hk.TCS_ACCEPTED == 2 else "error")

                    labels["hk_tcs_rejected"].set_text(f"{hk.TCS_REJECTED}")
                    labels["hk_tcs_rejected"].set_background_color("green" if hk.TCS_REJECTED == 0 else "red")
                    labels["hk_tcs_rejected"].set_icon("check_circle" if hk.TCS_REJECTED == 0 else "error")

                    labels["hk_instr_status_flags"].set_text(f"{hk.INSTRUMENT_STATUS_FLAGS}")
                    labels["hk_instr_status_flags"].set_background_color("green" if hk.INSTRUMENT_STATUS_FLAGS == 6 else "red")
                    labels["hk_instr_status_flags"].set_icon("check_circle" if hk.INSTRUMENT_STATUS_FLAGS == 6 else "error")

                    set_chip_color(labels["hk_op_state"], op_state_label, op_state_color, op_state_icon)

                    labels["hk_error_flags"].set_text(f"{hk.ERROR_FLAGS}")
                    labels["hk_error_flags"].set_background_color("green" if hk.ERROR_FLAGS == 0 else "red")
                    labels["hk_error_flags"].set_icon("check_circle" if hk.ERROR_FLAGS == 0 else "error")

                    labels["hk_warning_flags"].set_text(f"{hk.WARNING_FLAGS}")
                    labels["hk_warning_flags"].set_background_color("green" if hk.WARNING_FLAGS == 0 else "red")
                    labels["hk_warning_flags"].set_icon("check_circle" if hk.WARNING_FLAGS == 0 else "error")

                    labels["hk_fdir_alarms"].set_text(f"{hk.FDIR_ALARM_FLAGS}")
                    labels["hk_fdir_alarms"].set_background_color("green" if hk.FDIR_ALARM_FLAGS == 0 else "red")
                    labels["hk_fdir_alarms"].set_icon("check_circle" if hk.FDIR_ALARM_FLAGS == 0 else "error")

                    labels["hk_fdir_warnings"].set_text(f"{hk.FDIR_WARNING_FLAGS}")
                    labels["hk_fdir_warnings"].set_background_color("green" if hk.FDIR_WARNING_FLAGS == 0 else "red")
                    labels["hk_fdir_warnings"].set_icon("check_circle" if hk.FDIR_WARNING_FLAGS == 0 else "error")

                    labels["hk_eb_12v"].set_text(_format_voltage(eb_12v, hk.EB_MEAS_MAIN_12V))
                    labels["hk_eb_12v"].set_background_color("green" if 11.0 <= eb_12v <= 13.0 else "red")
                    labels["hk_eb_12v"].set_icon("check_circle" if 11.0 <= eb_12v <= 13.0 else "error")

                    labels["hk_eb_neg12v"].set_text(_format_voltage(eb_neg12v, hk.EB_MEAS_MAIN_NEG12V))
                    labels["hk_eb_neg12v"].set_background_color("green" if -13.0 <= eb_neg12v <= -11.0 else "red")
                    labels["hk_eb_neg12v"].set_icon("check_circle" if -13.0 <= eb_neg12v <= -11.0 else "error")

                    labels["hk_eb_5v"].set_text(_format_voltage(eb_5v, hk.EB_MEAS_5V))
                    labels["hk_eb_5v"].set_background_color("green" if 4.5 <= eb_5v <= 5.5 else "red")
                    labels["hk_eb_5v"].set_icon("check_circle" if 4.5 <= eb_5v <= 5.5 else "error")

                    labels["hk_eb_3v3"].set_text(_format_voltage(eb_3v3, hk.EB_MEAS_3V3))
                    labels["hk_eb_3v3"].set_background_color("green" if 2.8 <= eb_3v3 <= 3.8 else "red")
                    labels["hk_eb_3v3"].set_icon("check_circle" if 2.8 <= eb_3v3 <= 3.8 else "error")

                    labels["hk_eb_tec_v"].set_text(_format_voltage(eb_tec_v, hk.EB_MEAS_TEC_RAIL))
                    labels["hk_eb_tec_v"].set_background_color("green" if -0.5 <= eb_tec_v <= 0.5 else "red")
                    labels["hk_eb_tec_v"].set_icon("check_circle" if -0.5 <= eb_tec_v <= 0.5 else "error")

                    labels["hk_eb_0v"].set_text(_format_voltage(eb_0v, hk.EB_0V_ADC_READING))
                    labels["hk_eb_0v"].set_background_color("green" if -0.5 <= eb_0v <= 0.5 else "red")
                    labels["hk_eb_0v"].set_icon("check_circle" if -0.5 <= eb_0v <= 0.5 else "error")

                    labels["hk_eb_mcu_temp"].set_text(_format_temperature(eb_mcu_temp, eb_mcu_temp_adu))
                    labels["hk_eb_mcu_temp"].set_background_color("green" if 18.0 <= eb_mcu_temp <= 43.0 else "red")
                    labels["hk_eb_mcu_temp"].set_icon("check_circle" if 18.0 <= eb_mcu_temp <= 43.0 else "error")

                    labels["hk_eb_peltier_temp"].set_text(_format_temperature(eb_peltier_temp, eb_peltier_temp_adu))
                    labels["hk_eb_peltier_temp"].set_background_color("green" if 18.0 <= eb_peltier_temp <= 43.0 else "red")
                    labels["hk_eb_peltier_temp"].set_icon("check_circle" if 18.0 <= eb_peltier_temp <= 43.0 else "error")

                    labels["hk_eb_internal_trp"].set_text(_format_temperature(eb_internal_trp, eb_internal_trp_adu))
                    labels["hk_eb_internal_trp"].set_background_color("green" if 18.0 <= eb_internal_trp <= 43.0 else "red")
                    labels["hk_eb_internal_trp"].set_icon("check_circle" if 18.0 <= eb_internal_trp <= 43.0 else "error")

                    labels["hk_eb_psu_board_temp"].set_text(_format_temperature(eb_psu_board_temp, eb_psu_board_temp_adu))
                    labels["hk_eb_psu_board_temp"].set_background_color("green" if 18.0 <= eb_psu_board_temp <= 43.0 else "red")
                    labels["hk_eb_psu_board_temp"].set_icon("check_circle" if 18.0 <= eb_psu_board_temp <= 43.0 else "error")

                    labels["hk_eb_tec_drive_i"].set_text(f"{eb_tec_i:.4f} A")
                    labels["hk_eb_tec_drive_i"].set_background_color("green" if -0.1 <= eb_tec_i <= 0.1 else "red")
                    labels["hk_eb_tec_drive_i"].set_icon("check_circle" if -0.1 <= eb_tec_i <= 0.1 else "error")

                v3v3 = (hk.OB_3V3_VOLTAGE *2) / 1000
                v1v5 = hk.OB_1V5_VOLTAGE / 1000
                dig_trp_adu = hk.OB_DIGITAL_TRP
                dig_trp = eb_sniffer.decode_ob_trps(dig_trp_adu)
                det_trp_adu = hk.OB_DETECTOR_TRP
                det_trp = eb_sniffer.decode_ob_trps(det_trp_adu)
                mech_trp_adu = hk.OB_MECHANISM_TRP
                mech_trp = eb_sniffer.decode_ob_trps(mech_trp_adu)
                mot_trp_adu = hk.OB_MOTOR_TRP
                mot_trp = eb_sniffer.decode_ob_trps(mot_trp_adu)

                set_chip_state(
                    labels["error_flags"],
                    f"{hk.ERROR_FLAGS}",
                    "ok" if hk.ERROR_FLAGS == 0 else "alarm",
                )
                set_chip_state(
                    labels["warning_flags"],
                    f"{hk.WARNING_FLAGS}",
                    "ok" if hk.WARNING_FLAGS == 0 else "alarm",
                )
                set_chip_color(
                    labels["op_state"],
                    f"{op_state_map.get(hk.CURRENT_OPERATING_STATE, str(hk.CURRENT_OPERATING_STATE))}",
                    op_state_color,
                    op_state_icon,
                )
                set_chip_state(
                    labels["fdir_alarms"],
                    f"{hk.FDIR_ALARM_FLAGS}",
                    "ok" if hk.FDIR_ALARM_FLAGS == 0 else "alarm",
                )
                set_chip_state(
                    labels["fdir_warnings"],
                    f"{hk.FDIR_WARNING_FLAGS}",
                    "ok" if hk.FDIR_WARNING_FLAGS == 0 else "alarm",
                )

                # Update left drawer voltage labels
                set_chip_state(
                    labels["eb_12v"],
                    _format_voltage(eb_12v, hk.EB_MEAS_MAIN_12V),
                    eval_limit_state(eb_12v, wlim=(11.0, 13.0), alim=(10.5, 13.5)),
                )
                set_chip_state(
                    labels["eb_neg12v"],
                    _format_voltage(eb_neg12v, hk.EB_MEAS_MAIN_NEG12V),
                    eval_limit_state(eb_neg12v, wlim=(-13.0, -11.0), alim=(-13.5, -10.5)),
                )
                set_chip_state(
                    labels["eb_5v"],
                    _format_voltage(eb_5v, hk.EB_MEAS_5V),
                    eval_limit_state(eb_5v, wlim=(4.5, 5.5), alim=(4.0, 6.0)),
                )
                set_chip_state(
                    labels["eb_3v3"],
                    _format_voltage(eb_3v3, hk.EB_MEAS_3V3),
                    eval_limit_state(eb_3v3, wlim=(2.8, 3.8), alim=(3.0, 3.5)),
                )
                set_chip_state(
                    labels["eb_1v5"],
                    _format_voltage(eb_1v5, hk.OB_1V5_VOLTAGE),
                    eval_limit_state(eb_1v5, const.WLIM_1V5, const.ALIM_1V5),
                )

                set_chip_state(
                    labels["eb_mcu_temp"],
                    _format_temperature(eb_mcu_temp, eb_mcu_temp_adu),
                    eval_limit_state(eb_mcu_temp, ok_range=(18.0, 43.0)),
                )
                set_chip_state(
                    labels["eb_internal_temp"],
                    _format_temperature(eb_internal_trp, eb_internal_trp_adu),
                    eval_limit_state(eb_internal_trp, ok_range=(18.0, 43.0)),
                )
                set_chip_state(
                    labels["eb_psu_temp"],
                    _format_temperature(eb_psu_board_temp, eb_psu_board_temp_adu),
                    eval_limit_state(eb_psu_board_temp, ok_range=(18.0, 43.0)),
                )

                set_chip_state(
                    labels["tec_setpoint"],
                    f"{hk.TEC_SETPOINT}",
                    "unknown",
                )
                set_chip_state(
                    labels["eb_tec_i"],
                    f"{eb_tec_i:.4f} A",
                    "unknown",
                )
                set_chip_state(
                    labels["eb_peltier_temp"],
                    _format_temperature(eb_peltier_temp, eb_peltier_temp_adu),
                    "unknown",
                )
                set_chip_state(
                    labels["eb_tec_dac_out"],
                    f"{hk.EB_TEC_DAC_OUTPUT}",
                    "unknown",
                )

                
                is_adu_mode = temperature_units["value"] == "ADU"
                plot_3v3_value = hk.OB_3V3_VOLTAGE if is_adu_mode else v3v3
                plot_1v5_value = hk.OB_1V5_VOLTAGE if is_adu_mode else v1v5
                plot_3v3_limits = const.ALIM_3V3_ADU if is_adu_mode else const.ALIM_3V3
                plot_1v5_limits = const.ALIM_1V5_ADU if is_adu_mode else const.ALIM_1V5

                labels["plot_3v3"].push([hk.TIME], [[plot_3v3_value]], y_limits=plot_3v3_limits)

                labels["plot_1v5"].push([hk.TIME], [[plot_1v5_value]], y_limits=plot_1v5_limits)

                apply_temp_visibility()
                if is_adu_mode:
                    temp_series_values = [[dig_trp_adu], [det_trp_adu], [mech_trp_adu], [mot_trp_adu]]
                    temp_values_map = {"DIG": dig_trp_adu, "DET": det_trp_adu, "MECH": mech_trp_adu, "MOT": mot_trp_adu}
                    temp_default_limits = const.WLIM_TPR_ADU
                else:
                    temp_series_values = [[dig_trp], [det_trp], [mech_trp], [mot_trp]]
                    temp_values_map = {"DIG": dig_trp, "DET": det_trp, "MECH": mech_trp, "MOT": mot_trp}
                    temp_default_limits = const.WLIM_TPR
                selected_temp_values = [temp_values_map[key] for key in temp_series_order if temp_visibility[key]]
                if selected_temp_values:
                    temp_y_limits = (min(selected_temp_values) - 20, max(selected_temp_values) + 20)
                else:
                    temp_y_limits = (temp_default_limits[0] - 20, temp_default_limits[1] + 20)
                labels["plot_temps"].push([hk.TIME], temp_series_values, y_limits=temp_y_limits)

                

                if "cmd_cnt" in labels:
                    labels["cmd_cnt"].set_text(f"{hk.OB_COMMAND_COUNT}")
                
                # Always display voltage and temperature values
                if "3v3" in labels:
                    if hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01:
                        set_chip_state(
                            labels["3v3"],
                            _format_voltage(v3v3, hk.OB_3V3_VOLTAGE, precision=3),
                            eval_limit_state(v3v3, const.WLIM_3V3, const.ALIM_3V3),
                        )
                    else:
                        labels["3v3"].set_text(_format_voltage(v3v3, hk.OB_3V3_VOLTAGE, precision=3))
                        labels["3v3"].set_background_color("grey")
                
                if "1v5" in labels:
                    if hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01:
                        set_chip_state(
                            labels["1v5"],
                            _format_voltage(v1v5, hk.OB_1V5_VOLTAGE, precision=3),
                            eval_limit_state(v1v5, const.WLIM_1V5, const.ALIM_1V5),
                        )
                    else:
                        labels["1v5"].set_text(_format_voltage(v1v5, hk.OB_1V5_VOLTAGE, precision=3))
                        labels["1v5"].set_background_color("grey")

                # Always display temperature values
                if "DIG" in labels:
                    if hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01:
                        set_chip_state(
                            labels["DIG"],
                            _format_temperature(dig_trp, dig_trp_adu),
                            eval_limit_state(dig_trp, const.WLIM_TPR, const.ALIM_TPR),
                        )
                    else:
                        labels["DIG"].set_text(_format_temperature(dig_trp, dig_trp_adu))
                        labels["DIG"].set_background_color("grey")
                
                if "DET" in labels:
                    if hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01:
                        set_chip_state(
                            labels["DET"],
                            _format_temperature(det_trp, det_trp_adu),
                            eval_limit_state(det_trp, const.WLIM_TPR, const.ALIM_TPR),
                        )
                    else:
                        labels["DET"].set_text(_format_temperature(det_trp, det_trp_adu))
                        labels["DET"].set_background_color("grey")
                
                if "MECH" in labels:
                    if hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01:
                        set_chip_state(
                            labels["MECH"],
                            _format_temperature(mech_trp, mech_trp_adu),
                            eval_limit_state(mech_trp, const.WLIM_TPR, const.ALIM_TPR),
                        )
                    else:
                        labels["MECH"].set_text(_format_temperature(mech_trp, mech_trp_adu))
                        labels["MECH"].set_background_color("grey")
                
                if "MTR" in labels:
                    if hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01:
                        set_chip_state(
                            labels["MTR"],
                            _format_temperature(mot_trp, mot_trp_adu),
                            eval_limit_state(mot_trp, const.WLIM_TPR, const.ALIM_TPR),
                        )
                    else:
                        labels["MTR"].set_text(_format_temperature(mot_trp, mot_trp_adu))
                        labels["MTR"].set_background_color("grey")
                
                # Always show OB enabled state
                ob_enabled = bool(hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01)
                labels["OB_ENBLD"].set_text("ON" if ob_enabled else "OFF")
                labels["OB_ENBLD"].set_background_color("green" if ob_enabled else "red")
                labels["OB_ENBLD"].set_icon("check_circle_outline" if ob_enabled else "highlight_off")

                labels["HOME"].set_text("YES" if hk.INSTR_STATUS_FLAGS.HOMING_COMPLETE & 0x01 else "NO")
                labels["HOME"].set_background_color("green" if hk.INSTR_STATUS_FLAGS.HOMING_COMPLETE & 0x01 else "grey")
                labels["HOME"].set_icon("check_circle_outline" if hk.INSTR_STATUS_FLAGS.HOMING_COMPLETE & 0x01 else "highlight_off")

                labels["OB_WARM"].set_text("YES" if (hk.INSTR_STATUS_FLAGS.DETECTOR_WARM & hk.INSTR_STATUS_FLAGS.MECHANISM_WARM & 0x01) else "NO")
                labels["OB_WARM"].set_background_color("green" if (hk.INSTR_STATUS_FLAGS.DETECTOR_WARM & hk.INSTR_STATUS_FLAGS.MECHANISM_WARM & 0x01) else "grey")
                labels["OB_WARM"].set_icon("check_circle_outline" if (hk.INSTR_STATUS_FLAGS.DETECTOR_WARM & hk.INSTR_STATUS_FLAGS.MECHANISM_WARM & 0x01) else "highlight_off")



                # Always update MECH_PWR and DET_PWR with actual power state
                # Use INSTRUMENT_STATUS_FLAGS for power board enables
                mech_pwr_on = bool(hk.INSTR_STATUS_FLAGS.OB_MECHANISM_BOARD_ENABLED & 0x01)
                det_pwr_on = bool(hk.INSTR_STATUS_FLAGS.OB_DETECTOR_BOARD_ENABLED & 0x01)
                
                labels["MECH_PWR"].set_text("ON" if mech_pwr_on else "OFF")
                labels["MECH_PWR"].set_background_color("green" if mech_pwr_on else "red")
                labels["MECH_PWR"].set_icon("check_circle_outline" if mech_pwr_on else "highlight_off")

                labels["DET_PWR"].set_text("ON" if det_pwr_on else "OFF")
                labels["DET_PWR"].set_background_color("green" if det_pwr_on else "red")
                labels["DET_PWR"].set_icon("check_circle_outline" if det_pwr_on else "highlight_off")

                # Only update remaining OB Status checks if OB_5V_ENABLED is set
                if ob_enabled:
                    set_chip_state(
                        labels["ob_3v3"],
                        _format_voltage(v3v3, hk.OB_3V3_VOLTAGE, precision=3),
                        eval_limit_state(v3v3, const.WLIM_3V3, const.ALIM_3V3),
                    )
                    set_chip_state(
                        labels["ob_1v5"],
                        _format_voltage(v1v5, hk.OB_1V5_VOLTAGE, precision=3),
                        eval_limit_state(v1v5, const.WLIM_1V5, const.ALIM_1V5),
                    )

                    labels["MTR_MOV"].set_text(("Moving" if (hk.MTR_FLAGS.MOVING & 0x01) else "STATIONARY"))
                    labels["MTR_MOV"].set_background_color("green" if (hk.MTR_FLAGS.MOVING & 0x01) else "grey")
                    labels["MTR_MOV"].set_icon("rotate_right" if (hk.MTR_FLAGS.MOVING & 0x01) else "do_not_disturb_on")

                    labels["DIRECTION"].set_text(("TO BASE" if (hk.MTR_FLAGS.DIR == 0x0) else "TO OUTER"))
                    labels["DIRECTION"].set_background_color("purple" if (hk.MTR_FLAGS.DIR == 0x0) else ("blue" if (hk.MTR_FLAGS.DIR == 0x01) else "grey"))
                    labels["DIRECTION"].set_icon("keyboard_double_arrow_left" if (hk.MTR_FLAGS.DIR == 0x0) else ("keyboard_double_arrow_right" if (hk.MTR_FLAGS.DIR == 0x01) else "do_not_disturb_on"))
                    
                    labels["STOP"].set_text(("BASE" if (hk.MTR_FLAGS.BASE & 0x01) else ("OUTER" if (hk.MTR_FLAGS.OUTER & 0x01) else "Not At Stop")))
                    labels["STOP"].set_background_color("purple" if (hk.MTR_FLAGS.BASE & 0x01) else ("blue" if (hk.MTR_FLAGS.OUTER & 0x01) else "grey"))
                    labels["STOP"].set_icon("first_page" if (hk.MTR_FLAGS.BASE & 0x01) else ("last_page" if (hk.MTR_FLAGS.OUTER & 0x01) else "do_not_disturb_on"))

                    labels["ABS_STEPS"].set_text(f"{hk.OB_MOTOR_ABS_STEPS}")

                    labels["MECH_CAL"].set_text("CALIBRATED" if hk.MTR_FLAGS.CAL&0x01 else "--")
                    labels["MECH_CAL"].set_background_color("green" if hk.THRM_STATUS.MA else "grey")
                    labels["MECH_CAL"].set_icon("check_circle_outline" if hk.THRM_STATUS.MA else "highlight_off")


                    labels["MECH_HTR_STAT"].set_text_color("green" if hk.THRM_STATUS.HMS else "red")
                    labels["MECH_HTR_MAN"].set_text("ON" if hk.THRM_STATUS.MM else "OFF")
                    labels["MECH_HTR_MAN"].set_background_color("green" if hk.THRM_STATUS.MM else "grey")
                    labels["MECH_HTR_MAN"].set_icon("check_circle_outline" if hk.THRM_STATUS.MM else "highlight_off")
                    labels["MECH_HTR_AUTO"].set_text("ON" if hk.THRM_STATUS.MA else "OFF")
                    labels["MECH_HTR_AUTO"].set_background_color("green" if hk.THRM_STATUS.MA else "grey")
                    labels["MECH_HTR_AUTO"].set_icon("check_circle_outline" if hk.THRM_STATUS.MA else "highlight_off")

                    labels["DET_HTR_STAT"].set_text_color("green" if hk.THRM_STATUS.HDS else "red")
                    labels["DET_HTR_MAN"].set_text("ON" if hk.THRM_STATUS.DM else "OFF")
                    labels["DET_HTR_MAN"].set_background_color("green" if hk.THRM_STATUS.DM else "grey")
                    labels["DET_HTR_MAN"].set_icon("check_circle_outline" if hk.THRM_STATUS.DM else "highlight_off")
                    labels["DET_HTR_AUTO"].set_text("ON" if hk.THRM_STATUS.DA else "OFF")
                    labels["DET_HTR_AUTO"].set_background_color("green" if hk.THRM_STATUS.DA else "grey")
                    labels["DET_HTR_AUTO"].set_icon("check_circle_outline" if hk.THRM_STATUS.DA else "highlight_off")
                    labels["HTR_SCI"].set_text("ON" if hk.THRM_STATUS.S else "OFF")
                    labels["HTR_SCI"].set_background_color("green" if hk.THRM_STATUS.S else "grey")
                    labels["HTR_SCI"].set_icon("check_circle_outline" if hk.THRM_STATUS.S else "highlight_off")
                else:
                    # Reset OB Status chips when OB_5V_ENABLED is 0, but keep MECH_PWR/DET_PWR greyed with their values

                    for label in ["ob_3v3", "ob_1v5", "MTR_MOV", "DIRECTION", "MECH_PWR","DET_PWR","STOP", "ABS_STEPS", "MECH_HTR_STAT", "MECH_HTR_MAN", "MECH_HTR_AUTO", "DET_HTR_STAT", "DET_HTR_MAN", "DET_HTR_AUTO", "HTR_SCI"]:
                        if label in labels:
                            if hasattr(labels[label], 'set_background_color'):
                                labels[label].set_background_color("grey")
                            if hasattr(labels[label], 'set_text'):
                                labels[label].set_text("---")

                labels["ERR_IPI"].set_background_color("red" if hk.ERRORS.IPI else "grey")
                labels["ERR_IOS"].set_background_color("red" if hk.ERRORS.IOS else "grey")
                labels["ERR_ICR"].set_background_color("red" if hk.ERRORS.ICR else "grey")
                labels["ERR_MOR"].set_background_color("red" if hk.ERRORS.MOR else "grey")
                labels["ERR_TMO"].set_background_color("red" if hk.ERRORS.TMO else "grey")
                labels["ERR_IPA"].set_background_color("red" if hk.ERRORS.IPA else "grey")

                labels["ERR_CD"].set_background_color("red" if hk.MTR_ERRORS.CD else "grey")
                labels["ERR_AB"].set_background_color("red" if hk.MTR_ERRORS.AB else "grey")
                labels["ERR_ABS"].set_background_color("red" if hk.MTR_ERRORS.ABS else "grey")
                labels["ERR_DSE"].set_background_color("red" if hk.MTR_ERRORS.DSE else "grey")

            if not const.eb_post_queue.empty():
                post = const.eb_post_queue.get()
                last_post["value"] = post

                # Update POST summary chips
                set_chip_state(
                    labels["post_warning_flags"],
                    f"{post.POST_WARNING_FLAGS}",
                    "ok" if post.POST_WARNING_FLAGS == 0 else "alarm",
                )
                set_chip_state(
                    labels["post_error_flags"],
                    f"{post.POST_ERROR_FLAGS}",
                    "ok" if post.POST_ERROR_FLAGS == 0 else "alarm",
                )
                set_chip_state(
                    labels["post_bad_flash"],
                    f"{post.NUM_BAD_FLASH_BLOCKS}",
                    "ok" if post.NUM_BAD_FLASH_BLOCKS == 0 else "alarm",
                )
                set_chip_state(
                    labels["post_bad_sram"],
                    f"{post.NUM_BAD_SRAM_BLOCKS}",
                    "ok" if post.NUM_BAD_SRAM_BLOCKS == 0 else "alarm",
                )
                set_chip_state(
                    labels["post_asw1_crc"],
                    f"0x{post.ASW_IMAGE_1_CRC:04X}",
                    "ok" if post.ASW_IMAGE_1_CRC == 0xBAF7 else "alarm",
                )
                set_chip_state(
                    labels["post_asw2_crc"],
                    f"0x{post.ASW_IMAGE_2_CRC:04X}",
                    "ok" if post.ASW_IMAGE_2_CRC == 0x5C55 else "alarm",
                )
                set_chip_state(
                    labels["post_asw3_crc"],
                    f"0x{post.ASW_IMAGE_3_CRC:04X}",
                    "ok" if post.ASW_IMAGE_3_CRC == 0x01CB else "alarm",
                )
                set_chip_state(
                    labels["post_asw4_crc"],
                    f"0x{post.ASW_IMAGE_4_CRC:04X}",
                    "ok" if post.ASW_IMAGE_4_CRC == 0x5318 else "alarm",
                )
                set_chip_state(
                    labels["post_asw5_crc"],
                    f"0x{post.ASW_IMAGE_5_CRC:04X}",
                    "ok" if post.ASW_IMAGE_5_CRC == 0xDCAE else "alarm",
                )
                set_chip_state(
                    labels["post_bsw_crc"],
                    f"0x{post.BSW_IMAGE_CRC:04X}",
                    "ok" if post.BSW_IMAGE_CRC == 0xD2D7 else "alarm",
                )
                set_chip_state(
                    labels["post_meas_table_crc"],
                    f"0x{post.MEASUREMENT_TABLE_CRC:04X}",
                    "ok" if post.MEASUREMENT_TABLE_CRC == 0x9D9B else "alarm",
                )

                # Update overall POST status
                all_post_passed = (
                    post.POST_WARNING_FLAGS == 0 and
                    post.POST_ERROR_FLAGS == 0 and
                    post.NUM_BAD_FLASH_BLOCKS == 0 and
                    post.NUM_BAD_SRAM_BLOCKS == 0 and
                    post.ASW_IMAGE_1_CRC == 0xBAF7 and
                    post.ASW_IMAGE_2_CRC == 0x5C55 and
                    post.ASW_IMAGE_3_CRC == 0x01CB and
                    post.ASW_IMAGE_4_CRC == 0x5318 and
                    post.ASW_IMAGE_5_CRC == 0xDCAE and
                    post.BSW_IMAGE_CRC == 0xD2D7 and
                    post.MEASUREMENT_TABLE_CRC == 0x9D9B
                )
                if all_post_passed:
                    labels["post_status"].set_text("✅ POST TEST PASSED")
                    labels["post_status"].style("color: green; font-weight: bold;")
                else:
                    labels["post_status"].set_text("❌ POST TEST FAILED")
                    labels["post_status"].style("color: red; font-weight: bold;")

            if not const.psu_queue.empty():
                psu_times: list[datetime] = []
                rov_currents_ma: list[float] = []
                eb_currents_ma: list[float] = []
                last_psu = None

                while not const.psu_queue.empty():
                    psu = const.psu_queue.get()
                    last_psu = psu
                    psu_times.append(psu["TIME"])
                    rov_currents_ma.append(psu["PSU_ROV_HTR_I"] * 1000)
                    eb_currents_ma.append(psu["PSU_EB_I"] * 1000)

                if last_psu is not None:
                    status["psu"] = last_psu["STATUS"]
                    last_psu_readings["status"] = last_psu["STATUS"]
                    last_psu_readings["PSU_ROV_HTR_V"] = last_psu["PSU_ROV_HTR_V"]
                    last_psu_readings["PSU_ROV_HTR_I"] = last_psu["PSU_ROV_HTR_I"]
                    last_psu_readings["PSU_EB_V"] = last_psu["PSU_EB_V"]
                    last_psu_readings["PSU_EB_I"] = last_psu["PSU_EB_I"]
                    labels["PSU_ROV_HTR_V"].set_text(f"V: {last_psu['PSU_ROV_HTR_V']:.2f}")
                    labels["PSU_ROV_HTR_I"].set_text(f"mA: {last_psu['PSU_ROV_HTR_I'] * 1000:.1f}")
                    labels["PSU_EB_V"].set_text(f"V: {last_psu['PSU_EB_V']:.2f}")
                    labels["PSU_EB_I"].set_text(f"mA: {last_psu['PSU_EB_I'] * 1000:.1f}")

                if psu_times:
                    labels["plot_psu_rov_htr"].push(
                        psu_times,
                        [rov_currents_ma],
                    )
                    labels["plot_psu_eb"].push(
                        psu_times,
                        [eb_currents_ma],
                    )

        ui.timer(0.2, poll_latest_hk)

    # Decorator needed to allow nicegui to properly route to the index page
    @ui.page("/")
    def index() -> None:
        ui.add_css(gui_css_text, shared=True)
        apply_theme(theme_state["value"])


        def stop_and_shutdown() -> None:
            if stop_event is not None:
                stop_event.set()
            app.shutdown()

        def set_temp_visibility(series_key: str, enabled: bool) -> None:
            temp_visibility[series_key] = enabled

        def start_tools_handler() -> None:
            log_search_state["enabled"] = True
            eb_interface.start_egse_tools(logger)

        def stop_tools_handler() -> None:
            log_search_state["enabled"] = False
            eb_interface.stop_egse_tools(logger)

        def select_log_handler() -> None:
            log_search_state["enabled"] = True
            eb_interface.select_rs422_log(logger)

        def _log_psu_snapshot() -> None:
            status_value = last_psu_readings["status"]
            if status_value is None:
                logger.info("PSU status: no PSU readings available yet")
                return

            rov_v = last_psu_readings["PSU_ROV_HTR_V"]
            rov_i = last_psu_readings["PSU_ROV_HTR_I"]
            eb_v = last_psu_readings["PSU_EB_V"]
            eb_i = last_psu_readings["PSU_EB_I"]

            logger.info(
                "PSU status: STATUS=%s | ROV_HTR: V=%.2f, I=%.1f mA | EB: V=%.2f, I=%.1f mA",
                status_value,
                float(rov_v) if rov_v is not None else float("nan"),
                (float(rov_i) * 1000) if rov_i is not None else float("nan"),
                float(eb_v) if eb_v is not None else float("nan"),
                (float(eb_i) * 1000) if eb_i is not None else float("nan"),
            )

        def _log_hk_snapshot() -> None:
            hk = last_hk["value"]
            if hk is None:
                logger.info("HK checks: no HK data available yet")
                return

            hk_checks = [
                ("TCS_ACCEPTED", hk.TCS_ACCEPTED, hk.TCS_ACCEPTED == 2),
                ("TCS_REJECTED", hk.TCS_REJECTED, hk.TCS_REJECTED == 0),
                ("INSTRUMENT_STATUS_FLAGS", hk.INSTRUMENT_STATUS_FLAGS, hk.INSTRUMENT_STATUS_FLAGS == 6),
                ("ERROR_FLAGS", hk.ERROR_FLAGS, hk.ERROR_FLAGS == 0),
                ("WARNING_FLAGS", hk.WARNING_FLAGS, hk.WARNING_FLAGS == 0),
                ("FDIR_ALARM_FLAGS", hk.FDIR_ALARM_FLAGS, hk.FDIR_ALARM_FLAGS == 0),
                ("FDIR_WARNING_FLAGS", hk.FDIR_WARNING_FLAGS, hk.FDIR_WARNING_FLAGS == 0),
            ]

            logger.info("HK checks:")
            for name, value, passed in hk_checks:
                logger.info("  - %s=%s (%s)", name, value, "PASS" if passed else "FAIL")

        def _log_post_snapshot_if_updated() -> None:
            post = last_post["value"]
            if post is None:
                logger.info("POST HK: no POST HK available yet")
                return

            post_time = getattr(post, "TIME", None)
            if not isinstance(post_time, datetime):
                logger.info("POST HK: available but timestamp missing; skipping update check")
                return

            if snapshot_state["last_post_logged_time"] == post_time:
                logger.info("POST HK: not updated since last snapshot")
                return

            snapshot_state["last_post_logged_time"] = post_time
            logger.info(
                "POST HK update at %s | WARN=%s ERR=%s BAD_FLASH=%s BAD_SRAM=%s",
                post_time.strftime("%Y-%m-%d %H:%M:%S"),
                post.POST_WARNING_FLAGS,
                post.POST_ERROR_FLAGS,
                post.NUM_BAD_FLASH_BLOCKS,
                post.NUM_BAD_SRAM_BLOCKS,
            )

        def log_snapshot_handler() -> None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info('Log Snapshot at "%s"', timestamp)
            _log_psu_snapshot()
            _log_hk_snapshot()
            _log_post_snapshot_if_updated()

        def log_psu_snapshot_handler() -> None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info('Log Snapshot at "%s"', timestamp)
            _log_psu_snapshot()

        # Splash screen
        with ui.dialog().props('persistent') as splash_dialog:
            with ui.card().classes('items-center').style('min-width: 400px; padding: 2rem;'):
                logo_images.append(ui.image(logo_light_src).props("contain").classes("w-64 brand-logo"))
                ui.markdown("# EB EGSE v0.5").classes("text-center mt-4")
                ui.button(
                    "Complete Form to Continue",
                    on_click=lambda: (
                        ui.run_javascript('window.open("https://forms.office.com/e/gbzkXdQvCE", "_blank")'),
                        splash_dialog.close()
                    )
                ).classes("mt-6").props("color=accent_color size=lg")
                ui.label("Skip").classes("mt-4 underline text-xs cursor-pointer").style("color: var(--text-color)").on("click", lambda: splash_dialog.close())

        splash_dialog.open()

        fullscreen = ui.fullscreen()

        # Display logger in UI as well, add first so that we can toggle visibility in the left_drawer
        log_max_lines = 200
        log_mode = "WARNING"

        def refresh_egse_log(force: bool = False) -> None:
            if log_mode != "EB EGSE":
                return

            changed, header, lines, error = eb_interface.get_egse_log_snapshot(
                log_max_lines,
                force=force,
            )
            if not changed:
                return

            log.clear()
            if error:
                log.push(error)
                return
            if header:
                log.push(header)
            for line in lines:
                log.push(line)

        def set_log_display(selection: str) -> None:
            nonlocal log_mode
            log_mode = selection
            if selection in level_options:
                handler.setLevel(level_options[selection])
                return

            handler.setLevel(logging.CRITICAL + 1)
            refresh_egse_log(force=True)

        with ui.footer(value=True).style("background-color: var(--secondary-bg)") as footer:
            with ui.row(align_items="center"):
                ui.label("Log display in window").classes("text-black")
                ui.radio(
                    list(level_options.keys()) + ["EB EGSE"],
                    value="WARNING",
                    on_change=lambda event: set_log_display(event.value),
                ).props("inline").classes("text-black")

            log = ui.log(max_lines=log_max_lines).classes("w-full h-64 border")

            handler = LogElementHandler(log, level=logging.WARNING)
            # Set formatting for the UI Log
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            logger.addHandler(handler)

        ui.timer(1.0, refresh_egse_log)

        with ui.right_drawer(top_corner=True, bottom_corner=True).style("background-color: var(--secondary-bg)").props("width=550 bordered") as right_drawer:
            with ui.row().classes("w-full items-center justify-between mb-2"):
                logo_images.append(ui.image(logo_light_src).props("contain").classes("w-64 brand-logo"))
                with ui.row().classes("items-center gap-6"):
                    with ui.column().classes("items-center gap-1 cursor-pointer").on(
                        "click",
                        lambda: show_alarm_dialog("OB", "ob"),
                    ):
                        ui.label("OB").classes("text-xs")
                        labels["ob_warning_light"] = ui.element("div").classes("status-light status-light-lg ok")
                    with ui.column().classes("items-center gap-1 cursor-pointer").on(
                        "click",
                        lambda: show_alarm_dialog("EB", "eb"),
                    ):
                        ui.label("EB").classes("text-xs")
                        labels["eb_warning_light"] = ui.element("div").classes("status-light status-light-lg ok")
            ui.markdown("**EB STATUS**").classes("gap-0")
            with ui.grid(columns=5).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**OP**").classes("text-xs")
                    labels["op_state"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0 cursor-pointer").on(
                    "click",
                    lambda: show_flags_dialog("Error Flags Bitmap", "ERROR_FLAGS_BITS"),
                ):
                    ui.markdown("**ERRORS**").classes("text-xs")
                    labels["error_flags"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0 cursor-pointer").on(
                    "click",
                    lambda: show_flags_dialog("Warning Flags Bitmap", "WARNING_FLAGS_BITS"),
                ):
                    ui.markdown("**WARNS**").classes("text-xs")
                    labels["warning_flags"] = ui.chip("---", color="grey", icon="help_outline").props("dense")
                
                with ui.column().classes("items-center w-full gap-0 cursor-pointer").on(
                    "click",
                    lambda: show_flags_dialog("FDIR Alarm Flags Bitmap", "FDIR_ALARM_FLAGS_BITS"),
                ):
                    ui.markdown("**FDIR ALM**").classes("text-xs")
                    labels["fdir_alarms"] = ui.chip("---", color="grey", icon="help_outline").props("dense")
                
                with ui.column().classes("items-center w-full gap-0 cursor-pointer").on(
                    "click",
                    lambda: show_flags_dialog("FDIR Warning Flags Bitmap", "FDIR_WARNING_FLAGS_BITS"),
                ):
                    ui.markdown("**FDIR WRN**").classes("text-xs")
                    labels["fdir_warnings"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

            with ui.grid(columns=5).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**+12V**")
                    labels["eb_12v"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**-12V**")
                    labels["eb_neg12v"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**+5V**")
                    labels["eb_5v"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**+3V3**")
                    labels["eb_3v3"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**+1V5**")
                    labels["eb_1v5"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

            with ui.grid(columns=3).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MCU TEMP**")
                    labels["eb_mcu_temp"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**INTERNAL TEMP**")
                    labels["eb_internal_temp"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**PSU TEMP**")
                    labels["eb_psu_temp"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

            with ui.grid(columns=4).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**TEC_SETPOINT**")
                    labels["tec_setpoint"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**TEC Drive I**")
                    labels["eb_tec_i"] = ui.chip("---", color="grey", icon="help_outline").props("dense")                

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**PELTIER TEMP**")
                    labels["eb_peltier_temp"] = ui.chip("---", color="grey", icon="help_outline").props("dense")
                
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**TEC DAC OUT**")
                    labels["eb_tec_dac_out"] = ui.chip("---", color="grey", icon="help_outline").props("dense")


            ui.separator()
            ui.markdown("**OB STATUS**").classes("gap-0")
            with ui.grid(columns=6).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**OB+3.3V**")
                    labels["ob_3v3"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**OB+1.5V**")
                    labels["ob_1v5"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**DIG:**")
                    labels["DIG"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**DET:**")
                    labels["DET"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MECH:**")
                    labels["MECH"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MTR**")
                    labels["MTR"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

            with ui.grid(columns=6).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**CMD CNT**")
                    labels["cmd_cnt"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**OB ENBLD**")
                    labels["OB_ENBLD"] = ui.chip("OB_ENBLD", selectable=False, icon="highlight_off", color="grey")
                
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**HOME**")
                    labels["HOME"] = ui.chip("---", selectable=False, icon="highlight_off", color="grey")
                
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**OB WARM**")
                    labels["OB_WARM"] = ui.chip("---", selectable=False, icon="highlight_off", color="grey")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MECH PWR**")
                    labels["MECH_PWR"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**DET PWR**")
                    labels["DET_PWR"] = ui.chip("---", color="grey", icon="help_outline").props("dense")

            with ui.grid(columns=5).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MOVING**").classes("text-xs")
                    labels["MTR_MOV"] = ui.chip(selectable=False, icon="block", color="grey")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**DIRECTION**").classes("text-xs")
                    labels["DIRECTION"] = ui.chip(selectable=False, icon="highlight_off", color="grey")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**STOP**").classes("text-xs")
                    labels["STOP"] = ui.chip(selectable=False, icon="highlight_off", color="grey")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**STEPS**").classes("text-xs")
                    labels["ABS_STEPS"] = ui.chip("---", color="grey", icon="help_outline").props("dense")                
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MECH CAL**").classes("text-xs")
                    labels["MECH_CAL"] = ui.chip("CAL", selectable=False, icon="highlight_off", color="grey")

            ui.markdown("**MECH HEATER STATUS**")
            with ui.grid(columns = 3).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**STATUS**").classes("text-xs")
                    labels["MECH_HTR_STAT"] = ui.icon("fiber_manual_record", size="2em").classes("text-red")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MANUAL**").classes("text-xs")
                    labels["MECH_HTR_MAN"] = ui.chip("MAN", selectable=False, icon="highlight_off", color="grey")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**AUTO**").classes("text-xs")
                    labels["MECH_HTR_AUTO"] = ui.chip("AUTO", selectable=False, icon="highlight_off", color="grey")

            ui.markdown("**DET HEATER STATUS**")
            with ui.grid(columns = 4).classes("w-full gap-2"):
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**STATUS**").classes("text-xs")
                    labels["DET_HTR_STAT"] = ui.icon("fiber_manual_record", size="2em").classes("text-red")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**MANUAL**").classes("text-xs")
                    labels["DET_HTR_MAN"] = ui.chip("MAN", selectable=False, color="grey")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**AUTO**").classes("text-xs")
                    labels["DET_HTR_AUTO"] = ui.chip("AUTO", selectable=False, icon="highlight_off", color="grey")
                with ui.column().classes("items-center w-full gap-0"):
                    ui.markdown("**SCI**").classes("text-xs")
                    labels["HTR_SCI"] = ui.chip("SCI TOGGLE", selectable=False, icon="highlight_off", color="grey")

            ui.separator()
            ui.markdown("**OB ERRORS**")
            with ui.grid(columns=6).classes("w-full gap-x-1 gap-y-4 p-0"):
                labels["ERR_IPI"] = ui.chip("IPI", color="grey").classes("m-0 w-full")
                labels["ERR_IOS"] = ui.chip("IOS", color="grey").classes("m-0 w-full")
                labels["ERR_ICR"] = ui.chip("ICR", color="grey").classes("m-0 w-full")
                labels["ERR_MOR"] = ui.chip("MOR", color="grey").classes("m-0 w-full")
                labels["ERR_TMO"] = ui.chip("TMO", color="grey").classes("m-0 w-full")
                labels["ERR_IPA"] = ui.chip("IPA", color="grey").classes("m-0 w-full")

                
                labels["ERR_CD"] = ui.chip("CD", color="grey").classes("m-0 w-full")                
                labels["ERR_AB"] = ui.chip("AB", color="grey").classes("m-0 w-full")
                labels["ERR_ABS"] = ui.chip("ABS", color="grey").classes("m-0 w-full")
                labels["ERR_DSE"] = ui.chip("DSE", color="grey").classes("m-0 w-full")

            with ui.row(align_items="center").classes("w-full justify-center"):
                ui.separator()
                pill_btn_props = "color=accent_color size=sm dense"
                pill_btn_style = "padding: 2px 12px; min-height: 26px; border-radius: 0;"
                with ui.button_group().style("border-radius: 9999px; overflow: hidden;"):
                    ui.button("Display Log Terminal", on_click=footer.toggle).props(pill_btn_props).style(pill_btn_style)
                    ui.button("Toggle Fullscreen", on_click=fullscreen.toggle).props(pill_btn_props).style(pill_btn_style)
                    ui.button("Toggle Theme", on_click=toggle_theme).props(pill_btn_props).style(pill_btn_style)
                    labels["unit_toggle_btn"] = ui.button(
                        f"Unit Toggle : {temperature_units['value']}",
                        on_click=toggle_temperature_units,
                    ).props(pill_btn_props).style(pill_btn_style)

        with ui.left_drawer(fixed=True).style("background-color: var(--secondary-bg)").props("width=350 bordered") as left_drawer:
            with ui.row(align_items="center").classes("w-full justify-between"):
                ui.markdown("**MENU**").classes("text-xs")
                ui.button(icon="close", on_click=lambda: left_drawer.toggle()).props("color=accent_color dense flat")
            with ui.row(align_items="center").classes("w-full justify-center pr-16"):
                with ui.grid(columns=2).classes("w-full gap-x-2 gap-y-2"):
                    ui.button("Start Tools", on_click=start_tools_handler).props("color=accent_color size=sm dense").classes("col-span-1 text-xs")
                    ui.button("Stop Tools", on_click=stop_tools_handler).props("color=accent_color size=sm dense").classes("col-span-1 text-xs")
                    ui.button("Select Folder", on_click=lambda: eb_interface.select_egse_folder(logger)).props("color=accent_color size=sm dense").classes("col-span-1 text-xs")
                    ui.button("Select Script", on_click=lambda: eb_interface.select_egse_script(logger)).props("color=accent_color size=sm dense").classes("col-span-1 text-xs")
                    ui.button("Select Log", on_click=select_log_handler).props("color=accent_color size=sm dense").classes("col-span-1 text-xs")
            with ui.expansion('EB HK').classes('w-full overflow-x-hidden'):
                with ui.tabs().props("dense align=justify").classes("w-full text-xs") as tabs:
                    response_tab = ui.tab("Response HK").classes("text-xs")
                    post_tab = ui.tab("POST HK").classes("text-xs")
                with ui.tab_panels(tabs, value=response_tab).classes("w-full overflow-x-hidden"):
                    with ui.tab_panel(response_tab).classes("w-full overflow-x-hidden text-xs"):
                        ui.button("Check HK Packet", on_click=check_hk_manually, icon="verified").props("color=accent_color")
                        ui.markdown("**HK Summary**")
                        with ui.grid(columns=3).classes("w-full gap-x-2 gap-y-2"):
                            ui.label("Item").classes("font-bold")
                            ui.label("Value").classes("font-bold")
                            ui.label("Expected").classes("font-bold")

                            ui.label("TCs Accepted")
                            labels["hk_tcs_accepted"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("2")

                            ui.label("TCs Rejected")
                            labels["hk_tcs_rejected"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("Instrument Status Flags")
                            labels["hk_instr_status_flags"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("6")

                            ui.label("Current Operating State")
                            labels["hk_op_state"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("SAFE")

                            ui.label("Error Flags")
                            labels["hk_error_flags"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("Warning Flags")
                            labels["hk_warning_flags"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("FDIR Alarm Flags")
                            labels["hk_fdir_alarms"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("FDIR Warning Flags")
                            labels["hk_fdir_warnings"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("EB +12V (V)")
                            labels["hk_eb_12v"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("11.0 - 13.0 V")

                            ui.label("EB -12V (V)")
                            labels["hk_eb_neg12v"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("-13.0 - -11.0 V")

                            ui.label("EB +5V (V)")
                            labels["hk_eb_5v"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("4.5 - 5.5 V")

                            ui.label("EB +3V3 (V)")
                            labels["hk_eb_3v3"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("2.8 - 3.8 V")

                            ui.label("EB TEC_V (V)")
                            labels["hk_eb_tec_v"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("-0.5 - 0.5 V")

                            ui.label("EB 0V (V)")
                            labels["hk_eb_0v"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("-0.5 - 0.5 V")

                            ui.label("EB MCU Internal Temp (raw)")
                            labels["hk_eb_mcu_temp"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("18.0 - 43.0 C")

                            ui.label("EB Peltier Temp (raw)")
                            labels["hk_eb_peltier_temp"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("18.0 - 43.0 C")

                            ui.label("EB Internal TRP Temp (raw)")
                            labels["hk_eb_internal_trp"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("18.0 - 43.0 C")

                            ui.label("EB PSU Board Temp (raw)")
                            labels["hk_eb_psu_board_temp"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("18.0 - 43.0 C")

                            ui.label("EB TEC Drive Current (A)")
                            labels["hk_eb_tec_drive_i"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("-0.1 - 0.1 A")

                    with ui.tab_panel(post_tab).classes("w-full overflow-x-hidden text-xs"):
                        ui.button("Check POST Packet", on_click=check_post_manually, icon="verified").props("color=accent_color")
                        ui.markdown("**POST Packet Parameters**")
                        labels["post_status"] = ui.label("⏳ Waiting for POST HK packet...").classes("text-lg")
                        ui.separator()
                        
                        with ui.grid(columns=3).classes("w-full gap-x-2 gap-y-2"):
                            ui.label("Parameter").classes("font-bold")
                            ui.label("Recorded").classes("font-bold")
                            ui.label("Expected").classes("font-bold")

                            ui.label("POST Warning Flags")
                            labels["post_warning_flags"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("POST Error Flags")
                            labels["post_error_flags"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("Num Bad Flash Blocks")
                            labels["post_bad_flash"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("Num Bad SRAM Blocks")
                            labels["post_bad_sram"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0")

                            ui.label("ASW Image#1 CRC")
                            labels["post_asw1_crc"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0xBAF7")

                            ui.label("ASW Image#2 CRC")
                            labels["post_asw2_crc"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0x5C55")

                            ui.label("ASW Image#3 CRC")
                            labels["post_asw3_crc"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0x01CB")

                            ui.label("ASW Image#4 CRC")
                            labels["post_asw4_crc"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0x5318")

                            ui.label("ASW Image#5 CRC")
                            labels["post_asw5_crc"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0xDCAE")

                            ui.label("BSW Image CRC")
                            labels["post_bsw_crc"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0xD2D7")

                            ui.label("Measurement Table CRC")
                            labels["post_meas_table_crc"] = ui.chip("---", color="grey", icon="help_outline").props("dense").classes("w-fit text-xs")
                            ui.label("0x9D9B")

        with ui.row(align_items="center").classes("w-full justify-start"):
            ui.button(icon="menu", on_click=lambda: left_drawer.toggle()).props("color=accent_color dense")

        with ui.grid(columns=2).classes("w-full"):        

            with ui.column().classes("tight"):
                with ui.row().classes("gap-4"):
                    ui.label("ROV HTR PSU")
                with ui.row().classes("gap-4"):
                    ui.toggle(
                        ["ON", "OFF"], value = "OFF",
                        on_change=lambda event: psu.switch_psu_channel(
                            psu_port,
                            3,
                            state=(event.value == "ON"),
                        ),
                    ).props('rounded')

                    with ui.card().classes("width-full "):
                        with ui.column().classes("items-center w-full gap-0"):
                            ui.markdown("**ROV_HTR +28V**")
                            with ui.row().classes("gap-4"):
                                labels["PSU_ROV_HTR_V"] = ui.label(f"V: --")
                                labels["PSU_ROV_HTR_I"] = ui.label(f"mA: --")

            with ui.column().classes("tight"):
                with ui.row().classes("gap-4"):
                    ui.label("EB PSU")
                with ui.row().classes("gap-4"):
                    ui.toggle(
                        ["ON", "OFF"], value = "OFF",
                        on_change=lambda event: psu.switch_psu_channel(
                            psu_port,
                            4,
                            state=(event.value == "ON"),
                        ),
                    ).props('rounded')         

                    with ui.card().classes("width-full"):
                        with ui.column().classes("items-center w-full gap-0"):
                            ui.markdown("**EB +28V**")
                            with ui.row().classes("gap-4"):
                                labels["PSU_EB_V"] = ui.label(f"V: --")
                                labels["PSU_EB_I"] = ui.label(f"mA: --")

        with ui.grid(columns=2).classes("w-full"):
            with ui.column().classes("tight"):
                labels["plot_psu_rov_htr"] = ui.line_plot(n=1, limit=40, figsize=(9, 2), update_every=1)
                plot_ax = labels["plot_psu_rov_htr"].fig.axes[0]
                plot_ax.set_title("ROV_HTR +28V Current (mA)")
                plot_ax.lines[0].set_marker("x")
                plot_ax.lines[0].set_color("#b4421f") 
                plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                plot_ax.grid(True, alpha=0.6, linewidth=0.6)
            with ui.column().classes("tight"):
                labels["plot_psu_eb"] = ui.line_plot(n=1, limit=40, figsize=(9, 2), update_every=1)
                plot_ax = labels["plot_psu_eb"].fig.axes[0]
                plot_ax.set_title("EB +28V Current (mA)")
                plot_ax.lines[0].set_marker("x")
                plot_ax.lines[0].set_color("#1f78b4") 
                plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                plot_ax.grid(True, alpha=0.6, linewidth=0.6)

            
        


        with ui.grid(columns=2).classes("w-full"):
            with ui.column().classes("tight"):
                labels["plot_3v3"] = ui.line_plot(n=1, limit=20, figsize=(9, 2), update_every=1)
                plot_ax = labels["plot_3v3"].fig.axes[0]
                plot_ax.set_title("3V3 Voltage (ADU)")
                plot_ax.lines[0].set_marker("x")
                plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                plot_ax.grid(True, alpha=0.6, linewidth=0.6)
                plot_ax.axhline(const.WLIM_3V3_ADU[0], color="orange", linewidth=1.0, linestyle="--")
                plot_ax.axhline(const.WLIM_3V3_ADU[1], color="orange", linewidth=1.0, linestyle="--")
                plot_ax.axhline(const.ALIM_3V3_ADU[0], color="red", linewidth=1.0, linestyle="--")
                plot_ax.axhline(const.ALIM_3V3_ADU[1], color="red", linewidth=1.0, linestyle="--")

            with ui.column().classes("tight"):
                labels["plot_1v5"] = ui.line_plot(n=1, limit=20, figsize=(9, 2), update_every=1)
                plot_ax = labels["plot_1v5"].fig.axes[0]
                plot_ax.set_title("1V5 Voltage (ADU)")
                plot_ax.lines[0].set_marker("x")
                plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                plot_ax.grid(True, alpha=0.6, linewidth=0.6)
                plot_ax.axhline(const.WLIM_1V5_ADU[0], color="orange", linewidth=1.0, linestyle="--")
                plot_ax.axhline(const.WLIM_1V5_ADU[1], color="orange", linewidth=1.0, linestyle="--")
                plot_ax.axhline(const.ALIM_1V5_ADU[0], color="red", linewidth=1.0, linestyle="--")
                plot_ax.axhline(const.ALIM_1V5_ADU[1], color="red", linewidth=1.0, linestyle="--")

        with ui.row(align_items="center"):
            ui.label("Temps")
            for key in temp_series_order:
                ui.checkbox(key, value=True, on_change=lambda event, k=key: set_temp_visibility(k, event.value))

        labels["plot_temps"] = ui.line_plot(n=4, limit=40, figsize=(20, 2.5), update_every=1).with_legend(
            ["DIG", "DET", "MECH", "MOT"], loc="upper right", ncol=1
        )
        plot_ax = labels["plot_temps"].fig.axes[0]
        plot_ax.set_title("Temperatures")
        plot_ax.set_ylabel(f"Temperature ({'ADU' if temperature_units['value'] == 'ADU' else '°C'})")
        plot_ax.lines[0].set_marker("o")
        plot_ax.lines[1].set_marker("^")
        plot_ax.lines[2].set_marker("2")
        plot_ax.lines[3].set_marker("x")
        plot_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plot_ax.grid(True, color="#cfcfcf", alpha=0.6, linewidth=0.6)
        plot_ax.axhline(const.WLIM_TPR_ADU[0], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.WLIM_TPR_ADU[1], color="orange", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_TPR_ADU[0], color="red", linewidth=1.0, linestyle="--")
        plot_ax.axhline(const.ALIM_TPR_ADU[1], color="red", linewidth=1.0, linestyle="--")

        _update_unit_dependent_plots()

        apply_theme(theme_state["value"])

        def format_flag_snapshot(flag_ns, keys: list[str] | None) -> str:
            if flag_ns is None:
                return "No data"
            if keys is None:
                keys = list(flag_ns.__dict__.keys())
            items = [f"{key}: {getattr(flag_ns, key)}" for key in keys if hasattr(flag_ns, key)]
            return "\n".join(items) if items else "No flags"

        with ui.dialog() as flags_dialog:
            with ui.card().classes("w-96"):
                flags_title = ui.label("Flags")
                flags_body = ui.label("---").style("white-space: pre-wrap; font-family: monospace")

        with ui.dialog() as alarm_dialog:
            with ui.card().classes("w-[36rem]"):
                alarm_title = ui.label("Alarm Details")
                ui.separator()
                ui.label("Latest alarm").classes("text-sm")
                alarm_latest_container = ui.column().classes("w-full gap-1")
                with ui.row().classes("items-center gap-2"):
                    clear_alarm_btn = ui.button("Clear last alarm")
                ui.separator()
                with ui.expansion("Previous alarms").classes("w-full") as alarm_previous_section:
                    alarm_previous = ui.html("---", sanitize=False).style("white-space: pre-wrap; font-family: monospace")
                with ui.expansion("Ignored parameters").classes("w-full") as alarm_ignored_section:
                    alarm_ignored = ui.html("---", sanitize=False).style("white-space: pre-wrap; font-family: monospace")

        def show_flags_dialog(title: str, attr_name: str) -> None:
            hk = last_hk["value"]
            if hk is None:
                details = "No HK data yet."
            else:
                order_map = {
                    "ERROR_FLAGS_BITS": [name for name, _ in tmstruct.eb_warning_flags],
                    "WARNING_FLAGS_BITS": [name for name, _ in tmstruct.eb_warning_flags],
                    "FDIR_ALARM_FLAGS_BITS": [name for name, _ in tmstruct.eb_fdir_flags],
                    "FDIR_WARNING_FLAGS_BITS": [name for name, _ in tmstruct.eb_fdir_flags],
                }
                details = format_flag_snapshot(getattr(hk, attr_name, None), order_map.get(attr_name))
            flags_title.set_text(title)
            flags_body.set_text(details)
            flags_dialog.open()

        alarm_dialog_state = {"kind": None, "checked_details": set()}

        def clear_last_alarm() -> None:
            kind = alarm_dialog_state["kind"]
            if kind is None:
                return
            current = alarm_current.get(kind)
            if current is None:
                return
            checked_details = alarm_dialog_state.get("checked_details", set())
            current_details = current.get("details", [])
            for i, detail in enumerate(current_details):
                if i in checked_details:
                    alarm_acknowledged_signatures[kind].add(detail)
            current.setdefault("cleared_at", datetime.now())
            alarm_history[kind].append(current)
            if len(alarm_history[kind]) > alarm_history_max:
                alarm_history[kind].pop(0)
            
            # Promote pending alarm to current if it exists
            if alarm_pending[kind] is not None:
                alarm_current[kind] = alarm_pending[kind]
                alarm_pending[kind] = None
                alarm_last_signature[kind] = "|".join(alarm_current[kind].get("details", []))
                alarm_last_active[kind] = True
                # Immediately update light for the promoted pending alarm
                pending_details = alarm_current[kind].get("details", [])
                pending_any_acknowledged = any(detail in alarm_acknowledged_signatures[kind] for detail in (pending_details if isinstance(pending_details, list) else []))
                pending_display = not pending_any_acknowledged
                if kind == "ob" and "ob_warning_light" in labels:
                    set_status_light(labels["ob_warning_light"], ok=not pending_display)
                if kind == "eb" and "eb_warning_light" in labels:
                    set_status_light(labels["eb_warning_light"], ok=not pending_display)
            else:
                alarm_current[kind] = None
                alarm_last_active[kind] = False
                if kind == "ob" and "ob_warning_light" in labels:
                    set_status_light(labels["ob_warning_light"], ok=True)
                if kind == "eb" and "eb_warning_light" in labels:
                    set_status_light(labels["eb_warning_light"], ok=True)
            
            alarm_dialog_state["checked_details"].clear()
            show_alarm_dialog("OB" if kind == "ob" else "EB", kind)

        clear_alarm_btn.on("click", lambda: clear_last_alarm())

        def show_alarm_dialog(title: str, kind: str) -> None:
            alarm_dialog_state["kind"] = kind
            alarm_dialog_state["checked_details"].clear()
            history = alarm_history.get(kind, [])
            current = alarm_current.get(kind)
            alarm_title.set_text(f"{title} Alarm Details")
            
            alarm_latest_container.clear()
            if current is not None:
                timestamp = current.get("time")
                if isinstance(timestamp, datetime):
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = "Unknown time"
                with alarm_latest_container:
                    ui.label(time_str).classes("text-xs text-gray-500")
                    details = current.get("details", [])
                    for i, detail in enumerate(details if isinstance(details, list) else []):
                        def on_check(checked: bool, idx: int = i):
                            if checked:
                                alarm_dialog_state["checked_details"].add(idx)
                            else:
                                alarm_dialog_state["checked_details"].discard(idx)
                        
                        ui.checkbox(detail, on_change=on_check).classes("text-sm")
            else:
                with alarm_latest_container:
                    ui.label("None")

            if history:
                alarm_previous.set_content("<br><br>".join(_format_alarm_entry(entry) for entry in reversed(history)))
                alarm_previous_section.set_value(True)
            else:
                alarm_previous.set_content("None")
                alarm_previous_section.set_value(False)
            
            # Display ignored parameters
            ignored_sigs = alarm_acknowledged_signatures.get(kind, set())
            if ignored_sigs:
                ignored_content = "<br>".join(f"• {_escape_html(sig)}" for sig in sorted(ignored_sigs))
                alarm_ignored.set_content(ignored_content)
                alarm_ignored_section.set_value(False)
            else:
                alarm_ignored.set_content("None")
                alarm_ignored_section.set_value(False)
            
            alarm_dialog.open()

        
        

        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            with ui.row().classes("items-center gap-2"):
                ui.button("shutdown", on_click=stop_and_shutdown).props("color=accent_color")
                ui.button("log snapshot", on_click=log_snapshot_handler).props("color=accent_color size=sm dense")
                ui.button("log psu", on_click=log_psu_snapshot_handler).props("color=accent_color size=sm dense")

        # 3. Prevent memory leaks by removing handler on disconnect
        ui.context.client.on_disconnect(lambda: logger.removeHandler(handler))

        update_hk_display()


# TODO! Show status of PSU connection
# TODO! Create a monitoring thread
# TODO! Add a mechanism interface
# TODO! Add a sci acquisition interface
