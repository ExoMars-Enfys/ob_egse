from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from tkinter import Tk, filedialog

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import eb_sniffer
import constants as const
import sci_plot


_DATETIME_FORMATS = (
    "%Y-%m-%d_%H-%M-%S",
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S,%f",
    "%Y/%m/%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
)

_TIME_ONLY_FORMATS = (
    "%H:%M:%S,%f",
    "%H:%M:%S.%f",
    "%H:%M:%S",
)


def analysis(
    log: Path | None = None,
    psu_log: Path | None = None,
    outdir: Path | None = None,
    cutoff_time: str | None = None,
    sci_log: Path | None = None,
    sci_log_dir: Path | None = None,
    sci_plot_save: bool = False,
    psu_prompt: bool = True,
) -> None:
    """Analyze RS422 log file and create plots for EB and OB data."""
    
    # If no log file provided, show file picker
    if log is None:
        root = Tk()
        root.withdraw()  # Hide the root window
        
        log_file = filedialog.askopenfilename(
            title="Select RS422 Log File",
            filetypes=[
                ("RS422 Log Files", "RS422if_*.log"),
                ("All Log Files", "*.log"),
                ("All Files", "*.*")
            ]
        )
        root.destroy()
        
        if not log_file:
            print("No file selected. Exiting.")
            return
        
        log = Path(log_file)
    
    log_path = Path(log)
    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        return

    psu_data = {
        "times": [],
        "ch3_v": [],
        "ch3_i": [],
        "ch4_v": [],
        "ch4_i": [],
    }

    # If no PSU log file provided, show PSU file picker
    if psu_log is None and psu_prompt:
        root = Tk()
        root.withdraw()  # Hide the root window

        psu_log_file = filedialog.askopenfilename(
            title="Select PSU Log File",
            filetypes=[
                ("PSU Log Files", "*_PSU.log *_PSU.LOG"),
                ("All Log Files", "*.log"),
                ("All Files", "*.*")
            ]
        )
        root.destroy()

        if psu_log_file:
            psu_log = Path(psu_log_file)

    psu_log_path = Path(psu_log) if psu_log else None
    if psu_log_path is not None and not psu_log_path.exists():
        print(f"PSU log file not found: {psu_log_path}")
        return

    print(f"Analyzing log file: {log_path}")
    if psu_log_path is not None:
        print(f"Using PSU log file: {psu_log_path}")
    else:
        print("No PSU log provided. Skipping PSU analysis.")

    # Extract all packets from log
    packets = _read_all_packets(log_path)
    if not packets:
        print("No packets found in log file")
        return

    print(f"Found {len(packets)} packets")

    if psu_log_path is not None:
        psu_data = _read_psu_log(psu_log_path)
        if not psu_data["times"]:
            print(f"Unsupported or empty PSU log format: {psu_log_path}")
            print("Expected entries like 'CH4 28.000V  0.0870A' or 'CH4 Voltage: 28.000V  CH4 Current: 0.0870A'.")
            return
        print(f"Found {len(psu_data['times'])} PSU samples")

    if outdir is None:
        root = Tk()
        root.withdraw()  # Hide the root window

        selected_dir = filedialog.askdirectory(
            title="Select folder to save plot images"
        )
        root.destroy()

        if not selected_dir:
            print("No output folder selected. Exiting.")
            return

        output_dir = Path(selected_dir)
    else:
        output_dir = Path(outdir)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving plots to: {output_dir}")

    sci_logs: list[Path] = []
    if sci_log is not None:
        if sci_log.exists():
            sci_logs.append(sci_log)
        else:
            print(f"SCI log file not found: {sci_log}")
    if sci_log_dir is not None:
        if sci_log_dir.exists():
            sci_logs.extend(sorted(sci_log_dir.rglob("*_SCI.LOG")))
            sci_logs.extend(sorted(sci_log_dir.rglob("*_SCI.log")))
        else:
            print(f"SCI log folder not found: {sci_log_dir}")

    # Build time series data
    ts_data = _build_timeseries(packets)

    if cutoff_time:
        packets, ts_data, psu_data = _apply_time_cutoff(packets, ts_data, psu_data, cutoff_time)
    
    # Store packets for interactive lookups
    ts_data["packets"] = packets

    # Create plots
    _create_eb_plot(ts_data, packets, output_dir)
    _create_ob_plot(ts_data, packets, output_dir)
    _create_ob_abs_steps_plot(ts_data, output_dir)
    if psu_data["times"]:
        _create_psu_plot(ts_data, psu_data, output_dir)

    zoom_data = _build_error128_zoom_data(packets, ts_data, psu_data)
    if zoom_data is not None:
        zoom_packets, zoom_ts_data, zoom_psu_data = zoom_data
        _create_eb_plot(
            zoom_ts_data,
            zoom_packets,
            output_dir,
            file_suffix="_error128_zoom",
            title_suffix=" - Error 128 Zoom",
        )
        _create_ob_plot(
            zoom_ts_data,
            zoom_packets,
            output_dir,
            file_suffix="_error128_zoom",
            title_suffix=" - Error 128 Zoom",
        )
        _create_ob_abs_steps_plot(
            zoom_ts_data,
            output_dir,
            file_suffix="_error128_zoom",
            title_suffix=" - Error 128 Zoom",
        )
        if zoom_psu_data.get("times"):
            _create_psu_plot(
                zoom_ts_data,
                zoom_psu_data,
                output_dir,
                file_suffix="_error128_zoom",
                title_suffix=" - Error 128 Zoom",
            )
        print("Created additional Error 128 zoom plots.")

    _save_open_figures(output_dir)

    if sci_logs:
        sci_output_dir = output_dir / "sci_plots" if sci_plot_save else None
        sci_plot.plot_sci_logs(
            sci_logs=sci_logs,
            output_dir=sci_output_dir,
            save=sci_plot_save,
            show=True,
        )
    else:
        sci_output_dir = output_dir / "sci_plots"
        sci_plot.plot_sci_from_rs422(
            log_path=log_path,
            output_dir=sci_output_dir,
            save=True,
            show=True,
        )
        print(f"Saved SCI plots from RS422 to: {sci_output_dir}")

    plt.show()


def _read_all_packets(log_path: Path) -> list:
    """Read all packets from RS422 log file."""
    packets = []
    with open(log_path, "r", encoding="utf-8") as handle:
        all_lines = [line.strip() for line in handle]

    tm_indices = [i for (i, line) in enumerate(all_lines) if "Telemetry Data:" in line]

    if not tm_indices:
        return _read_hk_line_log_packets(all_lines)

    packet_index = 0
    last_timestamp = None
    first_timestamp_date = None
    for tm_index in tm_indices:
        if tm_index + 1 >= len(all_lines):
            continue
        byte_string = all_lines[tm_index + 1]
        if not byte_string:
            continue

        try:
            byte_array = bytes(int(x, 16) for x in byte_string.split())
            tm_type_id = (byte_array[5] >> 2) & 0x3F

            if tm_type_id in (0x1, 0x2):
                hk = eb_sniffer.parse_eb_hk(byte_array)
                hk = eb_sniffer.decode_warning_flags(hk)
                hk = eb_sniffer.decode_error_flags(hk)
                hk = eb_sniffer.decode_fdir_alarms(hk)
                hk = eb_sniffer.decode_fdir_warnings(hk)

                parsed_timestamp = _extract_packet_timestamp(
                    all_lines=all_lines,
                    tm_index=tm_index,
                    first_timestamp_date=first_timestamp_date,
                )

                if parsed_timestamp is not None:
                    hk.TIME = parsed_timestamp
                    last_timestamp = parsed_timestamp
                    if first_timestamp_date is None:
                        first_timestamp_date = parsed_timestamp.date()
                elif last_timestamp is not None:
                    hk.TIME = last_timestamp + timedelta(seconds=0.1)
                    last_timestamp = hk.TIME
                else:
                    # Fallback when no log timestamps are available
                    hk.TIME = datetime.fromtimestamp(packet_index * 0.1)
                    last_timestamp = hk.TIME

                packets.append(("HK", hk))
                packet_index += 1
        except Exception as e:
            print(f"Error parsing packet at line {tm_index}: {e}")
            continue

    return packets


def _read_hk_line_log_packets(all_lines: list[str]) -> list:
    """Read packets from line-based HK log format: '<timestamp> - <hex words>'."""
    packets = []
    last_timestamp = None

    for line in all_lines:
        if not line:
            continue

        split_parts = line.split(" - ", 1)
        if len(split_parts) != 2:
            continue

        timestamp_text, payload = split_parts
        timestamp = _parse_timestamp_text(timestamp_text)

        words = re.findall(r"\b[0-9A-Fa-f]{4}\b", payload)
        if not words:
            continue

        try:
            byte_array = bytes.fromhex("".join(words))
        except ValueError:
            continue

        if len(byte_array) < 6:
            continue

        tm_type_id = (byte_array[5] >> 2) & 0x3F
        if tm_type_id not in (0x1, 0x2):
            continue

        try:
            hk = eb_sniffer.parse_eb_hk(byte_array)
            hk = eb_sniffer.decode_warning_flags(hk)
            hk = eb_sniffer.decode_error_flags(hk)
            hk = eb_sniffer.decode_fdir_alarms(hk)
            hk = eb_sniffer.decode_fdir_warnings(hk)
        except Exception:
            continue

        if timestamp is not None:
            hk.TIME = timestamp
            last_timestamp = timestamp
        elif last_timestamp is not None:
            hk.TIME = last_timestamp + timedelta(seconds=0.1)
            last_timestamp = hk.TIME
        else:
            hk.TIME = datetime.fromtimestamp(len(packets) * 0.1)
            last_timestamp = hk.TIME

        packets.append(("HK", hk))

    return packets


def _parse_timestamp_text(text: str) -> datetime | None:
    """Parse a timestamp string using known datetime formats."""
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def _apply_time_cutoff(packets: list, ts_data: dict, psu_data: dict, cutoff_time: str) -> tuple[list, dict, dict]:
    """Trim EB/OB/PSU data after a given time-of-day cutoff (HH:MM[:SS])."""
    cutoff_formats = ("%H:%M:%S", "%H:%M")
    cutoff_clock = None
    for fmt in cutoff_formats:
        try:
            cutoff_clock = datetime.strptime(cutoff_time, fmt).time()
            break
        except ValueError:
            continue

    if cutoff_clock is None:
        print(f"Invalid cutoff time '{cutoff_time}'. Expected HH:MM or HH:MM:SS. Ignoring cutoff.")
        return packets, ts_data, psu_data

    packet_mask = []
    for pkt_type, pkt in packets:
        pkt_time = getattr(pkt, "TIME", None)
        keep = pkt_time is not None and pkt_time.time() <= cutoff_clock
        packet_mask.append(keep)

    filtered_packets = [pkt for pkt, keep in zip(packets, packet_mask, strict=False) if keep]

    time_mask = [time_val.time() <= cutoff_clock for time_val in ts_data["times"]]
    for key, values in ts_data.items():
        if key in ("state_changes", "error_flags"):
            continue
        if isinstance(values, list) and len(values) == len(time_mask):
            ts_data[key] = [val for val, keep in zip(values, time_mask, strict=False) if keep]

    ts_data["state_changes"] = [
        event for event in ts_data["state_changes"] if event[0].time() <= cutoff_clock
    ]
    ts_data["error_flags"] = [
        event for event in ts_data["error_flags"] if event[0].time() <= cutoff_clock
    ]

    psu_mask = [time_val.time() <= cutoff_clock for time_val in psu_data["times"]]
    for key, values in psu_data.items():
        if isinstance(values, list) and len(values) == len(psu_mask):
            psu_data[key] = [val for val, keep in zip(values, psu_mask, strict=False) if keep]

    print(f"Applied cutoff at {cutoff_clock}. Remaining HK packets: {len(filtered_packets)}, PSU samples: {len(psu_data['times'])}")
    return filtered_packets, ts_data, psu_data


def _build_error128_zoom_data(packets: list, ts_data: dict, psu_data: dict):
    """Build zoomed data from 5 samples before first Error 128 to the end."""
    if not ts_data.get("times") or not ts_data.get("error_flags"):
        return None

    error_128_event = next(
        (event for event in ts_data["error_flags"] if int(event[2]) & 128),
        None,
    )
    if error_128_event is None:
        return None

    error_time = error_128_event[0]
    times = ts_data["times"]
    error_idx = min(range(len(times)), key=lambda idx: abs((times[idx] - error_time).total_seconds()))
    start_idx = max(0, error_idx - 5)
    start_time = times[start_idx]

    zoom_ts_data = {}
    for key, values in ts_data.items():
        if key in ("state_changes", "error_flags"):
            continue
        if isinstance(values, list) and len(values) == len(times):
            zoom_ts_data[key] = values[start_idx:]
        else:
            zoom_ts_data[key] = values

    zoom_ts_data["state_changes"] = [event for event in ts_data["state_changes"] if event[0] >= start_time]
    zoom_ts_data["error_flags"] = [event for event in ts_data["error_flags"] if event[0] >= start_time]

    zoom_packets = [
        packet for packet in packets
        if getattr(packet[1], "TIME", None) is not None and packet[1].TIME >= start_time
    ]

    psu_times = psu_data.get("times", [])
    psu_mask = [time_val >= start_time for time_val in psu_times]
    zoom_psu_data = {}
    for key, values in psu_data.items():
        if isinstance(values, list) and len(values) == len(psu_mask):
            zoom_psu_data[key] = [val for val, keep in zip(values, psu_mask, strict=False) if keep]
        else:
            zoom_psu_data[key] = values

    return zoom_packets, zoom_ts_data, zoom_psu_data


def _extract_packet_timestamp(all_lines: list[str], tm_index: int, first_timestamp_date=None) -> datetime | None:
    """Extract packet timestamp from telemetry line context."""
    candidate_indices = [tm_index, tm_index - 1, tm_index - 2, tm_index - 3]
    for index in candidate_indices:
        if index < 0 or index >= len(all_lines):
            continue
        line = all_lines[index]

        direct_timestamp = _parse_timestamp_text(line)
        if direct_timestamp is not None:
            return direct_timestamp

        full_dt_match = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2}(?:[\.,]\d{1,6})?", line)
        if full_dt_match:
            dt_text = full_dt_match.group(0)
            for fmt in _DATETIME_FORMATS:
                try:
                    return datetime.strptime(dt_text, fmt)
                except ValueError:
                    continue

        time_match = re.search(r"\d{2}:\d{2}:\d{2}(?:[\.,]\d{1,6})?", line)
        if time_match and first_timestamp_date is not None:
            time_text = time_match.group(0)
            for fmt in _TIME_ONLY_FORMATS:
                try:
                    parsed_time = datetime.strptime(time_text, fmt).time()
                    return datetime.combine(first_timestamp_date, parsed_time)
                except ValueError:
                    continue

    return None


def _read_psu_log(psu_log_path: Path) -> dict:
    """Read PSU log file and extract CH3/CH4 voltage and current time series."""
    psu_data = {
        "times": [],
        "ch3_v": [],
        "ch3_i": [],
        "ch4_v": [],
        "ch4_i": [],
    }

    compact_entry_regex = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-\s+"
        r"(?P<ch>CH[34])\s+"
        r"(?P<v>[-+]?\d*\.?\d+)(?:V)?\s+"
        r"(?P<i>[-+]?\d*\.?\d+)(?:A)?"
    )

    labelled_entry_regex = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-\s+"
        r"(?P<ch>CH[34])\s+Voltage:\s*(?P<v>[-+]?\d*\.?\d+)(?:V)?\s+"
        r"CH[34]\s+Current:\s*(?P<i>[-+]?\d*\.?\d+)(?:A)?"
    )

    dual_channel_entry_regex = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-\s+"
        r"CH3\s+Voltage:\s*(?P<ch3_v>[-+]?\d*\.?\d+)(?:V)?\s+"
        r"CH3\s+Current:\s*(?P<ch3_i>[-+]?\d*\.?\d+)(?:A)?\s+"
        r"CH4\s+Voltage:\s*(?P<ch4_v>[-+]?\d*\.?\d+)(?:V)?\s+"
        r"CH4\s+Current:\s*(?P<ch4_i>[-+]?\d*\.?\d+)(?:A)?"
    )

    with open(psu_log_path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped_line = line.strip()
            dual_match = dual_channel_entry_regex.search(stripped_line)
            if dual_match:
                try:
                    time_val = datetime.strptime(dual_match.group("ts"), "%Y-%m-%d %H:%M:%S,%f")
                    ch3_v = float(dual_match.group("ch3_v"))
                    ch3_i = float(dual_match.group("ch3_i"))
                    ch4_v = float(dual_match.group("ch4_v"))
                    ch4_i = float(dual_match.group("ch4_i"))
                except ValueError:
                    continue

                psu_data["times"].append(time_val)
                psu_data["ch3_v"].append(ch3_v)
                psu_data["ch3_i"].append(ch3_i)
                psu_data["ch4_v"].append(ch4_v)
                psu_data["ch4_i"].append(ch4_i)
                continue

            match = compact_entry_regex.search(stripped_line)
            if not match:
                match = labelled_entry_regex.search(stripped_line)
            if not match:
                continue

            try:
                time_val = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S,%f")
                channel = match.group("ch")
                voltage = float(match.group("v"))
                current = float(match.group("i"))
            except ValueError:
                continue

            psu_data["times"].append(time_val)
            if channel == "CH3":
                psu_data["ch3_v"].append(voltage)
                psu_data["ch3_i"].append(current)
                psu_data["ch4_v"].append(np.nan)
                psu_data["ch4_i"].append(np.nan)
            else:
                psu_data["ch3_v"].append(np.nan)
                psu_data["ch3_i"].append(np.nan)
                psu_data["ch4_v"].append(voltage)
                psu_data["ch4_i"].append(current)

    return psu_data


def _build_timeseries(packets: list) -> dict:
    """Build time series data from packets."""
    min_valid_temp = -70.0

    def sanitize_temp(value: float) -> float:
        return value if value >= min_valid_temp else np.nan

    ts_data = {
        "times": [],
        "eb_12v": [],
        "eb_neg12v": [],
        "eb_5v": [],
        "eb_3v3": [],
        "eb_tec_v": [],
        "eb_tec_i": [],
        "eb_mcu_temp": [],
        "eb_peltier_temp": [],
        "eb_internal_trp": [],
        "eb_psu_board_temp": [],
        "ob_3v3": [],
        "ob_1v5": [],
        "ob_dig_trp": [],
        "ob_det_trp": [],
        "ob_mech_trp": [],
        "ob_mot_trp": [],
        "ob_motor_abs_steps": [],
        "state_changes": [],  # List of (time, state_code, state_name)
        "error_flags": [],  # List of (time, error_flags_bits, error_code)
        "hk_packets": [],  # List of HK packet objects for click handler
    }

    last_state = None
    last_error_state = None  # Track error state changes

    for pkt_type, pkt in packets:
        if pkt_type != "HK":
            continue

        time_val = getattr(pkt, "TIME", None)
        if time_val is None:
            continue

        ts_data["times"].append(time_val)
        ts_data["hk_packets"].append(pkt)  # Store packet for click handler
        # EB Voltages
        ts_data["eb_12v"].append(pkt.EB_MEAS_MAIN_12V * 0.000400543)
        ts_data["eb_neg12v"].append(pkt.EB_MEAS_MAIN_NEG12V * -0.00038147)
        ts_data["eb_5v"].append(pkt.EB_MEAS_5V * 0.000152829)
        ts_data["eb_3v3"].append(pkt.EB_MEAS_3V3 * 0.0000763)
        ts_data["eb_tec_v"].append(pkt.EB_MEAS_TEC_RAIL * 0.0000763)
        ts_data["eb_tec_i"].append(pkt.EB_TEC_DRIVE_CURRENT * 0.0000162)

        # EB Temperatures
        eb_mcu_temp = pkt.EB_MCU_INTERNAL_TEMP * 0.01637198 - 273
        ts_data["eb_mcu_temp"].append(sanitize_temp(eb_mcu_temp))

        eb_peltier_temp = pkt.EB_PELTIER_TEMP * -0.001830011 + 51.27039922
        ts_data["eb_peltier_temp"].append(sanitize_temp(eb_peltier_temp))

        eb_internal_trp = eb_sniffer.thermistor_adu_to_temp(pkt.EB_INTERNAL_TRP_TEMP)
        ts_data["eb_internal_trp"].append(sanitize_temp(eb_internal_trp))

        eb_psu_board_temp = eb_sniffer.thermistor_adu_to_temp(pkt.EB_PSU_BOARD_TEMP)
        ts_data["eb_psu_board_temp"].append(sanitize_temp(eb_psu_board_temp))

        # OB Voltages
        ob_3v3 = (pkt.OB_3V3_VOLTAGE * 2) / 1000
        ts_data["ob_3v3"].append(ob_3v3)

        ob_1v5 = pkt.OB_1V5_VOLTAGE / 1000
        ts_data["ob_1v5"].append(ob_1v5)

        # OB Temperatures
        ob_dig_trp = eb_sniffer.decode_ob_trps(pkt.OB_DIGITAL_TRP)
        ts_data["ob_dig_trp"].append(sanitize_temp(ob_dig_trp))

        ob_det_trp = eb_sniffer.decode_ob_trps(pkt.OB_DETECTOR_TRP)
        ts_data["ob_det_trp"].append(sanitize_temp(ob_det_trp))

        ob_mech_trp = eb_sniffer.decode_ob_trps(pkt.OB_MECHANISM_TRP)
        ts_data["ob_mech_trp"].append(sanitize_temp(ob_mech_trp))

        ob_mot_trp = eb_sniffer.decode_ob_trps(pkt.OB_MOTOR_TRP)
        ts_data["ob_mot_trp"].append(sanitize_temp(ob_mot_trp))
        ts_data["ob_motor_abs_steps"].append(float(getattr(pkt, "OB_MOTOR_ABS_STEPS", np.nan)))

        # Track state changes
        current_state = pkt.CURRENT_OPERATING_STATE
        if current_state != last_state:
            state_name = _get_state_name(current_state)
            ts_data["state_changes"].append((time_val, current_state, state_name))
            last_state = current_state

        # Track error state changes (convert bits to comparable value)
        error_flags_bits = getattr(pkt, 'ERROR_FLAGS_BITS', None)
        current_error_state = int(getattr(pkt, "ERROR_FLAGS", 0))
        if current_error_state != last_error_state:
            ts_data["error_flags"].append((time_val, error_flags_bits, current_error_state))
            last_error_state = current_error_state

    return ts_data


def _get_state_name(state_code: int) -> str:
    """Convert state code to human readable name."""
    state_map = {
        0x00: "Initialising",
        0x02: "Safe",
        0x04: "Standby",
        0x08: "Acquisition",
    }
    return state_map.get(state_code, f"Unknown({state_code:02X})")


def _get_state_color(state_code: int) -> str:
    """Convert state code to color for plotting."""
    color_map = {
        0x00: "grey",
        0x02: "blue",
        0x04: "green",
        0x08: "orange",
    }
    return color_map.get(state_code, "black")


def _error_bits_to_value(error_flags_bits) -> int:
    """Convert ERROR_FLAGS_BITS object to an integer for comparison."""
    if error_flags_bits is None:
        return 0
    
    value = 0
    bit_pos = 0
    for attr_name in dir(error_flags_bits):
        if not attr_name.startswith('_'):
            try:
                flag_val = bool(getattr(error_flags_bits, attr_name, False))
                if flag_val:
                    value |= (1 << bit_pos)
                bit_pos += 1
            except:
                pass
    return value


def _decode_error_flags(error_flags_bits) -> dict[str, bool]:
    """Extract active EB error flags from decoded ERROR_FLAGS_BITS object."""
    if error_flags_bits is None:
        return {}
    
    # Get all attributes and their boolean values
    flags = {}
    for attr_name in dir(error_flags_bits):
        if not attr_name.startswith('_'):  # Skip private attributes
            try:
                value = getattr(error_flags_bits, attr_name)
                if isinstance(value, (bool, int)):
                    flags[attr_name] = bool(value)
            except:
                pass
    return flags


def _format_error_description(error_flags_bits) -> str:
    """Format EB error description for display."""
    error_map = {
        "GENERAL_ERROR": "General Error",
        "OB_GENERAL_ERROR": "OB General Error",
        "EB_FDIR_ALARM": "EB FDIR Alarm",
        "OB_FDIR_ALARM": "OB FDIR Alarm",
        "WATCHDOG_TIMEOUT_DETECTED": "Watchdog Timeout",
        "NO_RET_RECEIVED": "No RET Received",
        "NO_HEALTHY_ASW_IMAGE": "No Healthy ASW Image",
        "OB_MOTOR_ERROR": "OB Motor Error",
        "OB_UNRESPONSIVE": "OB Unresponsive",
        "OB_STEP_COUNT_MISMATCH": "Step Count Mismatch",
        "PATCH_WRITING_ERROR": "Patch Writing Error",
        "RS422_RECEIVE_ERROR": "RS422 RX Error",
        "RS422_TRANSMIT_ERROR": "RS422 TX Error",
        "RS485_RECEIVE_ERROR": "RS485 RX Error",
        "RS485_TRANSMIT_ERROR": "RS485 TX Error",
    }
    
    errors = _decode_error_flags(error_flags_bits)
    active_errors = [f"{name} ({error_map.get(name, name)})" for name, active in errors.items() if active]
    
    if not active_errors:
        return "No EB errors"
    return "\n".join(active_errors)


def _show_error_popup(error_flags_bits) -> None:
    """Display EB error information in a popup window."""
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        
        popup = tk.Toplevel()
        popup.title("EB Error Flags Information")
        popup.geometry("500x350")
        
        text_widget = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=("Courier", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        info = "EB ERROR FLAGS\n{}\n\n".format("=" * 40)
        info += _format_error_description(error_flags_bits)
        
        text_widget.insert(tk.END, info)
        text_widget.config(state=tk.DISABLED)  # Make read-only
        
    except Exception as e:
        print(f"Error displaying error popup: {e}")


def _format_hk_data(hk) -> str:
    """Format HK packet data for display."""
    info = f"HK Packet Information\n{'='*50}\n\n"
    
    # EB Voltages
    info += "EB VOLTAGES:\n"
    info += f"  12V:        {hk.EB_MEAS_MAIN_12V * 0.000400543:.3f} V\n"
    info += f"  -12V:       {hk.EB_MEAS_MAIN_NEG12V * -0.00038147:.3f} V\n"
    info += f"  5V:         {hk.EB_MEAS_5V * 0.000152829:.3f} V\n"
    info += f"  3.3V:       {hk.EB_MEAS_3V3 * 0.0000763:.3f} V\n"
    info += f"  TEC Rail:   {hk.EB_MEAS_TEC_RAIL * 0.0000763:.3f} V\n"
    info += f"  TEC Current: {hk.EB_TEC_DRIVE_CURRENT * 0.0000162:.3f} A\n\n"
    
    # EB Temperatures
    info += "EB TEMPERATURES:\n"
    eb_mcu = hk.EB_MCU_INTERNAL_TEMP * 0.01637198 - 273
    info += f"  MCU Internal: {eb_mcu:.2f}°C (ADU: {hk.EB_MCU_INTERNAL_TEMP})\n"
    
    eb_peltier = hk.EB_PELTIER_TEMP * -0.001830011 + 51.27039922
    info += f"  Peltier:      {eb_peltier:.2f}°C (ADU: {hk.EB_PELTIER_TEMP})\n"
    
    eb_internal_trp = eb_sniffer.thermistor_adu_to_temp(hk.EB_INTERNAL_TRP_TEMP)
    info += f"  Internal TRP: {eb_internal_trp:.2f}°C (ADU: {hk.EB_INTERNAL_TRP_TEMP})\n"
    
    eb_psu_board = eb_sniffer.thermistor_adu_to_temp(hk.EB_PSU_BOARD_TEMP)
    info += f"  PSU Board:    {eb_psu_board:.2f}°C (ADU: {hk.EB_PSU_BOARD_TEMP})\n\n"
    
    # OB Voltages
    info += "OB VOLTAGES:\n"
    ob_3v3 = (hk.OB_3V3_VOLTAGE * 2) / 1000
    info += f"  3.3V:  {ob_3v3:.3f} V (ADU: {hk.OB_3V3_VOLTAGE})\n"
    
    ob_1v5 = hk.OB_1V5_VOLTAGE / 1000
    info += f"  1.5V:  {ob_1v5:.3f} V (ADU: {hk.OB_1V5_VOLTAGE})\n\n"
    
    # OB Temperatures
    info += "OB TEMPERATURES:\n"
    ob_dig = eb_sniffer.decode_ob_trps(hk.OB_DIGITAL_TRP)
    info += f"  Digital TRP:    {ob_dig:.2f}°C (ADU: {hk.OB_DIGITAL_TRP})\n"
    
    ob_det = eb_sniffer.decode_ob_trps(hk.OB_DETECTOR_TRP)
    info += f"  Detector TRP:   {ob_det:.2f}°C (ADU: {hk.OB_DETECTOR_TRP})\n"
    
    ob_mech = eb_sniffer.decode_ob_trps(hk.OB_MECHANISM_TRP)
    info += f"  Mechanism TRP:  {ob_mech:.2f}°C (ADU: {hk.OB_MECHANISM_TRP})\n"
    
    ob_mot = eb_sniffer.decode_ob_trps(hk.OB_MOTOR_TRP)
    info += f"  Motor TRP:      {ob_mot:.2f}°C (ADU: {hk.OB_MOTOR_TRP})\n\n"
    
    # State and Flags
    info += "SYSTEM STATE:\n"
    state_name = _get_state_name(hk.CURRENT_OPERATING_STATE)
    info += f"  Operating State: {state_name} (0x{hk.CURRENT_OPERATING_STATE:02X})\n"
    info += f"  EB Error Flags:  0x{hk.ERROR_FLAGS:04X}\n"
    info += f"  EB Warning Flags: 0x{hk.WARNING_FLAGS:04X}\n"

    info += "\nRAW HK FIELDS:\n"
    info += f"{'-'*50}\n"
    hk_fields = vars(hk)
    for key in sorted(hk_fields.keys()):
        value = hk_fields[key]
        if hasattr(value, "__dict__"):
            nested = vars(value)
            if nested:
                info += f"  {key}:\n"
                for nested_key, nested_val in sorted(nested.items()):
                    info += f"    {nested_key}: {nested_val}\n"
            else:
                info += f"  {key}: {value}\n"
        else:
            info += f"  {key}: {value}\n"
    
    return info


def _get_hk_packet_from_pick(event, ts_data: dict):
    """Resolve clicked sample to nearest HK packet in time."""
    if not hasattr(event.artist, "get_xdata"):
        return None

    hk_packets = ts_data.get("hk_packets", [])
    if not hk_packets:
        return None

    try:
        picked_index = int(event.ind[0])
    except Exception:
        return None

    xdata = event.artist.get_xdata()
    if xdata is None or len(xdata) == 0 or picked_index >= len(xdata):
        return None

    picked_time = xdata[picked_index]
    if picked_time is None:
        return None

    hk_times = [getattr(pkt, "TIME", None) for pkt in hk_packets]
    hk_times = [time_val for time_val in hk_times if time_val is not None]
    if not hk_times:
        return None

    nearest_index = min(
        range(len(hk_packets)),
        key=lambda idx: abs((hk_packets[idx].TIME - picked_time).total_seconds()) if getattr(hk_packets[idx], "TIME", None) else float("inf"),
    )
    return hk_packets[nearest_index]


def _show_hk_popup(hk) -> None:
    """Display HK data in a popup window."""
    try:
        import tkinter as tk
        from tkinter import scrolledtext
        
        popup = tk.Toplevel()
        popup.title("HK Packet Information")
        popup.geometry("600x700")
        
        text_widget = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=("Courier", 9))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        info = _format_hk_data(hk)
        text_widget.insert(tk.END, info)
        text_widget.config(state=tk.DISABLED)  # Make read-only
        
    except Exception as e:
        print(f"Error displaying HK popup: {e}")


def _create_eb_plot(
    ts_data: dict,
    packets: list,
    output_dir: Path,
    file_suffix: str = "",
    title_suffix: str = "",
) -> None:
    """Create EB window with voltage and temperature plots."""
    if not ts_data["times"]:
        print("No data to plot for EB")
        return

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle(f"EB System Analysis{title_suffix}", fontsize=16, fontweight="bold")

    times = np.array(ts_data["times"])
    packets = ts_data.get("packets", [])

    # EB Voltage plot
    ax_volt = axes[0]
    lines = []
    lines.append(ax_volt.plot(times, ts_data["eb_12v"], label="12V", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_volt.plot(times, ts_data["eb_neg12v"], label="-12V", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_volt.plot(times, ts_data["eb_5v"], label="5V", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_volt.plot(times, ts_data["eb_3v3"], label="3.3V", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_volt.plot(times, ts_data["eb_tec_v"], label="TEC Rail", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    
    ax_volt.set_ylabel("Voltage (V)", fontsize=12, fontweight="bold")
    ax_volt.set_title("EB Voltages", fontsize=13, fontweight="bold")
    
    # Place the voltage legend just above the top-right plot border
    leg_volt = ax_volt.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), fontsize=10, ncol=2, borderaxespad=0)
    ax_volt.add_artist(leg_volt)
    
    ax_volt.grid(True, alpha=0.3)
    ax_volt.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # EB Temperature plot
    ax_temp = axes[1]
    lines.append(ax_temp.plot(times, ts_data["eb_mcu_temp"], label="MCU Internal", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_temp.plot(times, ts_data["eb_peltier_temp"], label="Peltier", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_temp.plot(times, ts_data["eb_internal_trp"], label="Internal TRP", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_temp.plot(times, ts_data["eb_psu_board_temp"], label="PSU Board", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    
    ax_temp.set_ylabel("Temperature (°C)", fontsize=12, fontweight="bold")
    ax_temp.set_xlabel("Time", fontsize=12, fontweight="bold")
    ax_temp.set_title("EB Temperatures", fontsize=13, fontweight="bold")
    
    # Place the temperature legend just above the top-right plot border
    leg_temp = ax_temp.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), fontsize=10, ncol=2, borderaxespad=0)
    ax_temp.add_artist(leg_temp)
    
    ax_temp.grid(True, alpha=0.3)
    ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # Add state change lines
    for ax in axes:
        for time_val, state_code, state_name in ts_data["state_changes"]:
            color = _get_state_color(state_code)
            ax.axvline(time_val, color=color, linestyle="--", alpha=0.6, linewidth=2)

        # Add error flag lines with error descriptions
        for time_val, error_flags_bits, error_code in ts_data["error_flags"]:
            error_text = str(error_code)
            
            line = ax.axvline(time_val, color="red", linestyle=":", alpha=0.8, linewidth=2.5, picker=True)
            # Store error flags object for later reference
            line.error_flags_bits = error_flags_bits
            
            # Add text annotation above the line showing which errors
            y_pos = ax.get_ylim()[1] * 0.95
            ax.text(time_val, y_pos, error_text, rotation=90, fontsize=8, color="red", 
                   alpha=0.7, verticalalignment="bottom", horizontalalignment="right")

    # Add combined legend for state changes and error flags at top-left of the figure window
    if ts_data["state_changes"] or ts_data["error_flags"]:
        init_line = plt.Line2D([0], [0], color="grey", linestyle="--", linewidth=2, label="Initialising")
        safe_line = plt.Line2D([0], [0], color="blue", linestyle="--", linewidth=2, label="Safe")
        standby_line = plt.Line2D([0], [0], color="green", linestyle="--", linewidth=2, label="Standby")
        acq_line = plt.Line2D([0], [0], color="orange", linestyle="--", linewidth=2, label="Acquisition")
        error_flag_line = plt.Line2D([0], [0], color="red", linestyle=":", linewidth=2, label="Error Flag")
        fig.legend(handles=[init_line, safe_line, standby_line, acq_line, error_flag_line], 
                  loc="upper left", bbox_to_anchor=(0.01, 0.995), fontsize=9, title="System States & Events", ncol=1, borderaxespad=0)

    # Rotate x-axis labels
    for ax in axes:
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Add click handler
    def on_pick(event):
        # Check if error line was clicked
        if hasattr(event.artist, 'error_flags_bits'):
            _show_error_popup(event.artist.error_flags_bits)
        elif event.artist in lines:
            pkt = _get_hk_packet_from_pick(event, ts_data)
            if pkt is not None:
                _show_hk_popup(pkt)
    
    fig.canvas.mpl_connect('pick_event', on_pick)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(output_dir / f"eb_system_analysis{file_suffix}.png", dpi=150, bbox_inches="tight")


def _create_ob_plot(
    ts_data: dict,
    packets: list,
    output_dir: Path,
    file_suffix: str = "",
    title_suffix: str = "",
) -> None:
    """Create OB window with voltage and temperature plots."""
    if not ts_data["times"]:
        print("No data to plot for OB")
        return

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle(f"OB System Analysis{title_suffix}", fontsize=16, fontweight="bold")

    times = np.array(ts_data["times"])
    packets = ts_data.get("packets", [])

    # OB Voltage plot
    ax_volt = axes[0]
    lines = []
    lines.append(ax_volt.plot(times, ts_data["ob_3v3"], label="3.3V", linewidth=2.5, marker="o", markersize=5, picker=5)[0])
    lines.append(ax_volt.plot(times, ts_data["ob_1v5"], label="1.5V", linewidth=2.5, marker="s", markersize=5, picker=5)[0])
    
    ax_volt.set_ylabel("Voltage (V)", fontsize=12, fontweight="bold")
    ax_volt.set_title("OB Voltages", fontsize=13, fontweight="bold")
    
    # Place the voltage legend just above the top-right plot border
    leg_volt = ax_volt.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), fontsize=11, borderaxespad=0)
    ax_volt.add_artist(leg_volt)
    
    ax_volt.grid(True, alpha=0.3)
    ax_volt.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # OB Temperature plot
    ax_temp = axes[1]
    lines.append(ax_temp.plot(times, ts_data["ob_dig_trp"], label="Digital TRP", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_temp.plot(times, ts_data["ob_det_trp"], label="Detector TRP", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_temp.plot(times, ts_data["ob_mech_trp"], label="Mechanism TRP", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    lines.append(ax_temp.plot(times, ts_data["ob_mot_trp"], label="Motor TRP", linewidth=2.5, marker=".", markersize=3, picker=5)[0])
    
    ax_temp.set_ylabel("Temperature (°C)", fontsize=12, fontweight="bold")
    ax_temp.set_xlabel("Time", fontsize=12, fontweight="bold")
    ax_temp.set_title("OB Temperatures", fontsize=13, fontweight="bold")
    
    # Place the temperature legend just above the top-right plot border
    leg_temp = ax_temp.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), fontsize=10, ncol=2, borderaxespad=0)
    ax_temp.add_artist(leg_temp)
    
    ax_temp.grid(True, alpha=0.3)
    ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # Add state change lines
    for ax in axes:
        for time_val, state_code, state_name in ts_data["state_changes"]:
            color = _get_state_color(state_code)
            ax.axvline(time_val, color=color, linestyle="--", alpha=0.6, linewidth=2)

        # Add error flag lines with error descriptions
        for time_val, error_flags_bits, error_code in ts_data["error_flags"]:
            if error_flags_bits is None:
                continue
            error_text = str(error_code)
            
            line = ax.axvline(time_val, color="red", linestyle=":", alpha=0.6, linewidth=2, picker=True)
            # Store error flags object for later reference
            line.error_flags_bits = error_flags_bits
            
            # Add text annotation above the line showing which errors
            y_pos = ax.get_ylim()[1] * 0.95
            ax.text(time_val, y_pos, error_text, rotation=90, fontsize=7, color="red", 
                   alpha=0.6, verticalalignment="bottom", horizontalalignment="right")

    # Add combined legend for state changes and error flags at top-left of the figure window
    if ts_data["state_changes"] or ts_data["error_flags"]:
        init_line = plt.Line2D([0], [0], color="grey", linestyle="--", linewidth=2, label="Initialising")
        safe_line = plt.Line2D([0], [0], color="blue", linestyle="--", linewidth=2, label="Safe")
        standby_line = plt.Line2D([0], [0], color="green", linestyle="--", linewidth=2, label="Standby")
        acq_line = plt.Line2D([0], [0], color="orange", linestyle="--", linewidth=2, label="Acquisition")
        error_flag_line = plt.Line2D([0], [0], color="red", linestyle=":", linewidth=2, label="Error Flag")
        fig.legend(handles=[init_line, safe_line, standby_line, acq_line, error_flag_line], 
                  loc="upper left", bbox_to_anchor=(0.01, 0.995), fontsize=9, title="System States & Events", ncol=1, borderaxespad=0)

    # Rotate x-axis labels for OB plot
    for ax in axes:
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Add click handler
    def on_pick(event):
        # Check if error line was clicked
        if hasattr(event.artist, 'error_flags_bits'):
            _show_error_popup(event.artist.error_flags_bits)
        elif event.artist in lines:
            pkt = _get_hk_packet_from_pick(event, ts_data)
            if pkt is not None:
                _show_hk_popup(pkt)
    
    fig.canvas.mpl_connect('pick_event', on_pick)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(output_dir / f"ob_system_analysis{file_suffix}.png", dpi=150, bbox_inches="tight")


def _create_psu_plot(
    ts_data: dict,
    psu_data: dict,
    output_dir: Path,
    file_suffix: str = "",
    title_suffix: str = "",
) -> None:
    """Create PSU window with CH3/CH4 current plots."""
    fig, ax_curr = plt.subplots(1, 1, figsize=(14, 6))
    fig.suptitle(f"PSU System Analysis{title_suffix}", fontsize=16, fontweight="bold")

    times = np.array(psu_data["times"])

    if len(times) > 0:
        ax_curr.plot(times, np.array(psu_data["ch3_i"]) * 1000, label="CH3 Current", linewidth=2.5, marker=".", markersize=4)
        ax_curr.plot(times, np.array(psu_data["ch4_i"]) * 1000, label="CH4 Current", linewidth=2.5, marker=".", markersize=4)
    else:
        ax_curr.text(0.5, 0.5, "No PSU current samples", transform=ax_curr.transAxes,
                     ha="center", va="center", fontsize=11)

    ax_curr.set_ylabel("Current (mA)", fontsize=12, fontweight="bold")
    ax_curr.set_xlabel("Time", fontsize=12, fontweight="bold")
    ax_curr.set_title("PSU Currents", fontsize=13, fontweight="bold")
    leg_curr = ax_curr.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), fontsize=10, ncol=2, borderaxespad=0)
    ax_curr.add_artist(leg_curr)
    ax_curr.grid(True, alpha=0.3)
    ax_curr.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    # Add EB/OB state and error flag lines for correlation
    time_window_start = None
    time_window_end = None
    if len(times) > 0:
        time_window_start = min(times)
        time_window_end = max(times)

    filtered_state_changes = ts_data["state_changes"]
    filtered_error_flags = ts_data["error_flags"]
    if time_window_start is not None and time_window_end is not None:
        filtered_state_changes = [
            event for event in ts_data["state_changes"]
            if time_window_start <= event[0] <= time_window_end
        ]
        filtered_error_flags = [
            event for event in ts_data["error_flags"]
            if time_window_start <= event[0] <= time_window_end
        ]

        if not filtered_state_changes and ts_data["state_changes"]:
            start_tod = time_window_start.time()
            end_tod = time_window_end.time()
            filtered_state_changes = [
                event for event in ts_data["state_changes"]
                if start_tod <= event[0].time() <= end_tod
            ]
            filtered_state_changes = [
                (datetime.combine(time_window_start.date(), event[0].time()), event[1], event[2])
                for event in filtered_state_changes
            ]

    for time_val, state_code, state_name in filtered_state_changes:
        color = _get_state_color(state_code)
        ax_curr.axvline(time_val, color=color, linestyle="--", alpha=0.6, linewidth=2)
        y_pos = ax_curr.get_ylim()[1] * 0.88
        ax_curr.text(time_val, y_pos, state_name, rotation=90, fontsize=8, color=color,
                     alpha=0.7, verticalalignment="bottom", horizontalalignment="right")

    for time_val, error_flags_bits, error_code in filtered_error_flags:
        if error_flags_bits is None:
            continue
        error_text = str(error_code)

        ax_curr.axvline(time_val, color="red", linestyle=":", alpha=0.6, linewidth=2)
        y_pos = ax_curr.get_ylim()[1] * 0.95
        ax_curr.text(time_val, y_pos, error_text, rotation=90, fontsize=7, color="red",
                     alpha=0.6, verticalalignment="bottom", horizontalalignment="right")

    if filtered_state_changes or filtered_error_flags:
        init_line = plt.Line2D([0], [0], color="grey", linestyle="--", linewidth=2, label="Initialising")
        safe_line = plt.Line2D([0], [0], color="blue", linestyle="--", linewidth=2, label="Safe")
        standby_line = plt.Line2D([0], [0], color="green", linestyle="--", linewidth=2, label="Standby")
        acq_line = plt.Line2D([0], [0], color="orange", linestyle="--", linewidth=2, label="Acquisition")
        error_flag_line = plt.Line2D([0], [0], color="red", linestyle=":", linewidth=2, label="Error Flag")
        fig.legend(handles=[init_line, safe_line, standby_line, acq_line, error_flag_line],
                   loc="upper left", bbox_to_anchor=(0.01, 0.995), fontsize=9, title="System States & Events", ncol=1, borderaxespad=0)

    plt.setp(ax_curr.xaxis.get_majorticklabels(), rotation=45, ha="right")

    fig.subplots_adjust(top=0.86, bottom=0.14, left=0.08, right=0.98)
    fig.savefig(output_dir / f"psu_system_analysis{file_suffix}.png", dpi=150, bbox_inches="tight")


def _create_ob_abs_steps_plot(
    ts_data: dict,
    output_dir: Path,
    file_suffix: str = "",
    title_suffix: str = "",
) -> None:
    """Create OB absolute motor steps plot over time."""
    if not ts_data["times"]:
        print("No data to plot for OB motor ABS steps")
        return

    times = np.array(ts_data["times"])
    abs_steps = np.array(ts_data.get("ob_motor_abs_steps", []), dtype=float)
    if abs_steps.size == 0 or np.all(np.isnan(abs_steps)):
        print("No OB motor absolute steps found in HK data")
        return

    fig, ax = plt.subplots(1, 1, figsize=(14, 6))
    fig.suptitle(f"OB Motor Absolute Steps{title_suffix}", fontsize=16, fontweight="bold")

    ax.plot(
        times,
        abs_steps,
        label="OB_MOTOR_ABS_STEPS",
        linewidth=2.0,
        marker=".",
        markersize=3,
    )
    ax.set_ylabel("Absolute Steps", fontsize=12, fontweight="bold")
    ax.set_xlabel("Time", fontsize=12, fontweight="bold")
    ax.set_title("OB Motor Absolute Steps vs Time", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), fontsize=10, borderaxespad=0)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    for time_val, state_code, _state_name in ts_data["state_changes"]:
        color = _get_state_color(state_code)
        ax.axvline(time_val, color=color, linestyle="--", alpha=0.5, linewidth=1.5)

    for time_val, error_flags_bits, error_code in ts_data["error_flags"]:
        if error_flags_bits is None:
            continue
        ax.axvline(time_val, color="red", linestyle=":", alpha=0.5, linewidth=1.8)
        y_pos = ax.get_ylim()[1] * 0.97
        ax.text(
            time_val,
            y_pos,
            str(error_code),
            rotation=90,
            fontsize=7,
            color="red",
            alpha=0.6,
            verticalalignment="bottom",
            horizontalalignment="right",
        )

    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
    fig.subplots_adjust(top=0.88, bottom=0.18, left=0.08, right=0.98)
    fig.savefig(output_dir / f"ob_motor_abs_steps{file_suffix}.png", dpi=150, bbox_inches="tight")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HK analysis - Generate plots from RS422 logs")
    parser.add_argument("--log", type=str, default=None, help="Path to RS422 log file (optional - file picker will open if not provided)")
    parser.add_argument("--psu-log", type=str, default=None, help="Path to PSU log file (optional - file picker will open if not provided)")
    parser.add_argument("--outdir", type=str, default=None, help="Folder to save plot images (optional - folder picker will open if not provided)")
    parser.add_argument("--cutoff-time", type=str, default=None, help="Optional time-of-day cutoff (HH:MM or HH:MM:SS); data after this time is removed")
    parser.add_argument("--sci-log", type=str, default=None, help="Path to a single *_SCI.LOG file (optional)")
    parser.add_argument("--sci-log-dir", type=str, default=None, help="Folder to search for *_SCI.LOG files (optional)")
    parser.add_argument("--sci-plot-save", action="store_true", help="Save SCI plots into outdir/sci_plots")
    parser.add_argument("--no-psu", action="store_true", help="Skip PSU log prompt/processing")
    return parser


def _save_open_figures(output_dir: Path) -> None:
    """Save all currently open matplotlib figures (as displayed in the plotting window)."""
    for fig_num in plt.get_fignums():
        fig = plt.figure(fig_num)
        suptitle = getattr(fig, "_suptitle", None)
        if suptitle is not None and suptitle.get_text():
            file_stem = suptitle.get_text().strip().lower().replace(" ", "_")
        else:
            file_stem = f"figure_{fig_num}"
        fig.savefig(output_dir / f"window_{file_stem}.png", dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    # If --log/--psu-log/--outdir are not provided, file/folder pickers will open
    analysis(
        Path(args.log) if args.log else None,
        Path(args.psu_log) if args.psu_log else None,
        Path(args.outdir) if args.outdir else None,
        args.cutoff_time,
        Path(args.sci_log) if args.sci_log else None,
        Path(args.sci_log_dir) if args.sci_log_dir else None,
        args.sci_plot_save,
        not args.no_psu,
    )
