#!/usr/bin/env python3
"""
Combined analysis: HK temperatures, HK voltages, SWIR, and MWIR
on a single shared datetime x-axis.  Zooming any subplot updates all others.
"""

import argparse
import csv
import os
import re
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox

import matplotlib as mpl
import numpy as np

try:
    mpl.use("TkAgg")
except Exception:
    # Fall back to default if TkAgg is not available in this environment
    pass
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

sys.path.insert(0, str(Path(__file__).parent.parent))

from utility_modules import eb_packet_utility
from utility_modules.eb_packet_utility import adu_to_temp, decode_eb_trps, parse_eb_hk
from utility_modules.psu_log_utility import load_psu_channel_samples

# Ensure Unicode characters (e.g. box-drawing) survive PowerShell piping
_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(_reconfigure):
    _reconfigure(encoding="utf-8", errors="replace")

LOG_PATH = Path(
    r"C:\Users\GK\OneDrive - University College London\General - Enfys - Shared\Test\EMC\Logs\2nd Week\RS422if_2026-05-13_13-23-35.log"
)
RS422_TIME_OFFSET_HOURS = 1.0


def _parse_rs422_timestamp(line, offset):
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", line)
    if not match:
        return None
    try:
        y, mo, d, h, mi, s = [int(v) for v in match.groups()]
        return datetime(y, mo, d, h, mi, s) + offset
    except Exception:
        return None


def build_psu_arrays(psu_log_path):
    """Load PSU CH3/CH4 voltage and current samples for plotting."""
    samples = load_psu_channel_samples(psu_log_path)
    data = {
        "CH3": {"times": [], "v": [], "i": []},
        "CH4": {"times": [], "v": [], "i": []},
    }
    for sample in samples:
        ts = sample.get("TIME")
        channels = sample.get("CHANNELS", {})
        if ts is None:
            continue
        for ch in ("CH3", "CH4"):
            vals = channels.get(ch, {})
            v = vals.get("V")
            i = vals.get("I")
            # Keep per-channel timing independent; skip rows where neither exists.
            if v is None and i is None:
                continue
            data[ch]["times"].append(ts)
            data[ch]["v"].append(float(v) if v is not None else np.nan)
            data[ch]["i"].append(float(i) if i is not None else np.nan)
    return data


# ── HK extraction ─────────────────────────────────────────────────────────────


def extract_hk_packets(log_path, rs422_offset=timedelta(hours=RS422_TIME_OFFSET_HOURS)):
    hk_packets = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]
    except Exception as e:
        print(f"Error reading log file: {e}")
        return hk_packets

    tm_indices = [i for i, line in enumerate(lines) if "Telemetry Data:" in line]
    if not tm_indices:
        print("No telemetry data found in log file")
        return hk_packets

    last_timestamp = None
    for tm_index in tm_indices:
        if tm_index + 1 >= len(lines):
            continue
        byte_string = lines[tm_index + 1]
        if not byte_string:
            continue
        try:
            byte_array = bytes(int(x, 16) for x in byte_string.split())
            tm_type_id = (byte_array[5] >> 2) & 0x3F
            if tm_type_id not in (0x1, 0x2):
                continue

            packet_timestamp = None
            for search_offset in range(max(0, tm_index - 5), tm_index):
                packet_timestamp = _parse_rs422_timestamp(lines[search_offset], rs422_offset)
                if packet_timestamp is not None:
                    last_timestamp = packet_timestamp
                    break

            if packet_timestamp is None and last_timestamp is not None:
                packet_timestamp = last_timestamp + timedelta(seconds=0.1)
                last_timestamp = packet_timestamp
            elif packet_timestamp is None:
                continue

            hk = parse_eb_hk(byte_array)
            hk.TIME = packet_timestamp
            hk_packets.append(hk)
        except Exception:
            continue

    return hk_packets


def _extract_temperatures(hk):
    temps = {}
    try:
        temps["OB_DIGITAL"] = adu_to_temp(hk.OB_DIGITAL_TRP)
        temps["OB_DETECTOR"] = adu_to_temp(hk.OB_DETECTOR_TRP)
        temps["OB_MECHANISM"] = adu_to_temp(hk.OB_MECHANISM_TRP)
        temps["OB_MOTOR"] = adu_to_temp(hk.OB_MOTOR_TRP)
        temps["EB_MCU"] = hk.EB_MCU_INTERNAL_TEMP * 0.01637198 - 273.0
        temps["EB_PSU_BOARD"] = decode_eb_trps(hk.EB_PSU_BOARD_TEMP)
        temps["EB_INTERNAL_TRP"] = decode_eb_trps(hk.EB_INTERNAL_TRP_TEMP)
        try:
            temps["EB_PELTIER"] = hk.EB_PELTIER_TEMP * -0.001830011 + 51.27039922
        except Exception:
            pass
    except Exception as e:
        print(f"Error extracting temperatures: {e}")
    return temps


def _extract_voltages(hk):
    volts = {}
    try:
        volts["EB_12V"] = hk.EB_MEAS_MAIN_12V * 0.000400543
        volts["EB_NEG12V"] = abs(hk.EB_MEAS_MAIN_NEG12V * -0.00038147)
        volts["EB_5V"] = hk.EB_MEAS_5V * 0.000152829
        volts["EB_3V3"] = hk.EB_MEAS_3V3 * 0.0000763
        try:
            volts["EB_TEC_RAIL"] = hk.EB_MEAS_TEC_RAIL * 0.0000763
        except Exception:
            pass
        volts["OB_3V3"] = (hk.OB_3V3_VOLTAGE * 2) / 1000.0
        volts["OB_1V5"] = hk.OB_1V5_VOLTAGE / 1000.0
    except Exception as e:
        print(f"Error extracting voltages: {e}")
    return volts


def build_hk_arrays(hk_packets):
    temp_keys = [
        "OB_DIGITAL",
        "OB_DETECTOR",
        "OB_MECHANISM",
        "OB_MOTOR",
        "EB_MCU",
        "EB_PSU_BOARD",
        "EB_INTERNAL_TRP",
        "EB_PELTIER",
    ]
    volt_keys = ["EB_12V", "EB_NEG12V", "EB_5V", "EB_3V3", "EB_TEC_RAIL", "OB_3V3", "OB_1V5"]
    temp_data = {k: [] for k in temp_keys}
    volt_data = {k: [] for k in volt_keys}
    timestamps = [hk.TIME for hk in hk_packets]
    TEMP_MIN = -65.0  # values below this are treated as invalid
    for hk in hk_packets:
        temps = _extract_temperatures(hk)
        volts = _extract_voltages(hk)
        for k in temp_keys:
            v = temps.get(k, np.nan)
            if not np.isnan(v) and v < TEMP_MIN:
                v = np.nan
            temp_data[k].append(v)
        for k in volt_keys:
            volt_data[k].append(volts.get(k, np.nan))
    return timestamps, temp_data, volt_data


def list_numeric_hk_fields(hk_packets):
    """Return sorted HK field names that contain at least one numeric value."""
    names = set()
    for hk in hk_packets:
        for key, value in vars(hk).items():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float, np.number)):
                names.add(key)
    return sorted(names)


def build_hk_field_series(hk_packets, field_name):
    """Build timestamp/value arrays for one HK field, coercing missing/non-numeric to NaN."""
    ts = []
    vals = []
    for hk in hk_packets:
        ts.append(hk.TIME)
        value = getattr(hk, field_name, np.nan)
        if isinstance(value, bool):
            vals.append(np.nan)
            continue
        try:
            vals.append(float(value))
        except Exception:
            vals.append(np.nan)
    return ts, vals


# ── Acquisition window extraction ───────────────────────────────────────────

_ACQ_STATE = 0x08  # CURRENT_OPERATING_STATE value for Acquisition


def extract_acq_windows(hk_packets, gap_tolerance_s=30.0):
    """Return list of (start_dt, end_dt) covering periods where CURRENT_OPERATING_STATE == 0x08.

    Consecutive ACQUISITION HK packets separated by <= gap_tolerance_s are merged
    into a single window (accounts for the 10-s HK rate used during acquisition).
    """
    windows = []
    win_start = win_end = None
    for hk in hk_packets:
        is_acq = getattr(hk, "CURRENT_OPERATING_STATE", None) == _ACQ_STATE
        t = hk.TIME
        if is_acq:
            if win_start is None:
                win_start = win_end = t
            elif (t - win_end).total_seconds() <= gap_tolerance_s:
                win_end = t
            else:
                windows.append((win_start, win_end))
                win_start = win_end = t
        else:
            if win_start is not None:
                windows.append((win_start, win_end))
                win_start = win_end = None
    if win_start is not None:
        windows.append((win_start, win_end))
    return windows


def filter_sci_to_acq_windows(
    sci_datetimes, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high, acq_windows, margin_s=20.0
):
    """NaN-mask sci channel arrays for points that fall outside acquisition windows.

    A margin_s buffer is added around each window to account for HK reporting
    latency and the sci packet arriving slightly after acquisition ends.
    Returns masked copies of all six channel lists.
    """
    if not acq_windows or not sci_datetimes:
        return swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high

    margin = timedelta(seconds=margin_s)
    channels = [list(swir_low), list(swir_med), list(swir_high), list(mwir_low), list(mwir_med), list(mwir_high)]
    for i, dt in enumerate(sci_datetimes):
        in_window = any((s - margin) <= dt <= (e + margin) for s, e in acq_windows)
        if not in_window:
            for ch in channels:
                ch[i] = np.nan
    return tuple(channels)


# ── set_acq_configs TC parsing ───────────────────────────────────────────────

# TC identification: SET_ACQ_CONFIGS has payload-length field == 0x16 (22 bytes).
# Byte layout (0-indexed, big-endian u16s):
#   [8]       = 0x16 (payload length)
#   [9]       = Mode     (u8)  0=spectrum, 1=fixed-point
#   [13-14]   = SampleTime (u16 BE)  unit = 10 ms  (0x0064 = 100 = 1 s)
#   [15-16]   = Duration   (u16 BE)
_SET_ACQ_PAYLOAD_LEN = 0x16
_SAMPLE_TIME_UNIT_MS = 10  # 1 unit = 10 ms


def extract_acq_configs_tcs(log_path, rs422_offset=timedelta(hours=RS422_TIME_OFFSET_HOURS)):
    """Parse all set_acq_configs TCs from the RS422 log.

    Returns a list of dicts (sorted by timestamp):
        {"timestamp": datetime, "mode": int, "sample_time_raw": int,
         "duration_raw": int, "spacing_ms": float}
    """
    result = []
    with open(log_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f]

    last_timestamp = None
    for i, line in enumerate(lines):
        maybe_ts = _parse_rs422_timestamp(line, rs422_offset)
        if maybe_ts is not None:
            last_timestamp = maybe_ts

        if line != "Telecommand:" or i + 1 >= len(lines):
            continue

        byte_string = lines[i + 1]
        try:
            ba = bytes(int(x, 16) for x in byte_string.split())
        except ValueError:
            continue

        if len(ba) < 17 or ba[8] != _SET_ACQ_PAYLOAD_LEN:
            continue

        mode = ba[9]
        if mode not in (0x00, 0x01):
            continue

        sample_time_raw = (ba[13] << 8) | ba[14]  # u16 BE
        duration_raw = (ba[15] << 8) | ba[16]  # u16 BE

        # Timestamp: may appear right after the byte line
        ts = last_timestamp
        if i + 2 < len(lines):
            maybe_ts2 = _parse_rs422_timestamp(lines[i + 2], rs422_offset)
            if maybe_ts2 is not None:
                ts = maybe_ts2
                last_timestamp = ts

        if ts is None:
            continue

        spacing_ms = sample_time_raw * _SAMPLE_TIME_UNIT_MS if sample_time_raw > 0 else 0.0
        result.append(
            {
                "timestamp": ts,
                "mode": mode,
                "sample_time_raw": sample_time_raw,
                "duration_raw": duration_raw,
                "spacing_ms": spacing_ms,
            }
        )

    return result


def _find_preceding_acq_config(sci_timestamp, acq_configs_list):
    """Return the most recent set_acq_configs TC that precedes *sci_timestamp*, or None."""
    best = None
    for cfg in acq_configs_list:
        if cfg["timestamp"] <= sci_timestamp:
            if best is None or cfg["timestamp"] > best["timestamp"]:
                best = cfg
    return best


# ── Science extraction ────────────────────────────────────────────────────────


def _decode_sci_packet(byte_array, tm_type_id):
    try:
        if tm_type_id == 0x4:
            sci_pkt = eb_packet_utility.decode_dump_data(byte_array)
        elif tm_type_id == 0x5:
            sci_pkt = eb_packet_utility.decode_cscience_data(byte_array)
        elif tm_type_id == 0x6:
            sci_pkt = eb_packet_utility.decode_ncscience_data(byte_array)
        else:
            return None
        return eb_packet_utility.merge_sci_data_packet(sci_pkt)
    except Exception:
        return None


def _extract_sci_series(sci_data):
    sci_points = getattr(sci_data, "SCI_POINTS", None)
    if sci_points:
        abs_steps, swir_low, swir_med, swir_high = [], [], [], []
        mwir_low, mwir_med, mwir_high = [], [], []
        for pt in sci_points:
            abs_steps.append(int(pt.ABS_STEPS))
            swir_high.append(int(pt.SWIR_HIGH))
            swir_med.append(int(pt.SWIR_MED))
            swir_low.append(int(pt.SWIR_LOW))
            mwir_high.append(int(pt.MWIR_HIGH))
            mwir_med.append(int(pt.MWIR_MED))
            mwir_low.append(int(pt.MWIR_LOW))
        return {
            "abs_steps": abs_steps,
            "swir_low": swir_low,
            "swir_med": swir_med,
            "swir_high": swir_high,
            "mwir_low": mwir_low,
            "mwir_med": mwir_med,
            "mwir_high": mwir_high,
        }
    if not hasattr(sci_data, "ABS_STEPS"):
        return None
    return {
        "abs_steps": [int(sci_data.ABS_STEPS)],
        "swir_low": [int(sci_data.SWIR_LOW)],
        "swir_med": [int(sci_data.SWIR_MED)],
        "swir_high": [int(sci_data.SWIR_HIGH)],
        "mwir_low": [int(sci_data.MWIR_LOW)],
        "mwir_med": [int(sci_data.MWIR_MED)],
        "mwir_high": [int(sci_data.MWIR_HIGH)],
    }


def extract_sci_packets(log_path, rs422_offset=timedelta(hours=RS422_TIME_OFFSET_HOURS)):
    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = [line.strip() for line in f]

    sci_packets = []
    last_timestamp = None
    for i, line in enumerate(all_lines):
        maybe_ts = _parse_rs422_timestamp(line, rs422_offset)
        if maybe_ts is not None:
            last_timestamp = maybe_ts
        if line.startswith("Telemetry Data:") and i + 1 < len(all_lines):
            byte_string = all_lines[i + 1]
            if not byte_string:
                continue
            try:
                byte_array = bytes(int(x, 16) for x in byte_string.split())
            except ValueError:
                continue
            if len(byte_array) < 6:
                continue
            tm_type_id = (byte_array[5] >> 2) & 0x3F
            if tm_type_id not in (0x4, 0x5, 0x6):
                continue
            sci_data = _decode_sci_packet(byte_array, tm_type_id)
            if sci_data is None:
                continue
            series = _extract_sci_series(sci_data)
            if series is None:
                continue
            sci_packets.append({"timestamp": last_timestamp, "tm_type_id": tm_type_id, "series": series})

    return sci_packets


def build_sci_arrays(sci_packets, acq_configs_list=None):
    """Build combined sci arrays using real datetime objects for the x-axis.

    If *acq_configs_list* is provided, the sample spacing for each packet is
    derived from the most recent preceding set_acq_configs TC:
      - Mode 1 (fixed-point): spacing = sample_time_raw * 10 ms
      - Mode 0 (spectrum) or no TC found: derive from adjacent packet timestamps
        or fall back to 260 ms.
    """
    sci_datetimes = []
    sci_abs_steps = []
    swir_low, swir_med, swir_high = [], [], []
    mwir_low, mwir_med, mwir_high = [], [], []
    packet_boundaries = []
    packet_modes = []
    if acq_configs_list is None:
        acq_configs_list = []

    for packet_idx, packet in enumerate(sci_packets):
        packet_num = packet_idx + 1
        packet_timestamp = packet["timestamp"]
        series = packet["series"]
        num_points = len(series["abs_steps"])
        packet_type = ["dump", "critical", "noncritical"][[0x4, 0x5, 0x6].index(packet["tm_type_id"])]

        # Determine spacing from set_acq_configs if available
        spacing_source = "estimated"
        cfg = _find_preceding_acq_config(packet_timestamp, acq_configs_list) if acq_configs_list else None

        packet_mode = cfg["mode"] if cfg is not None else None
        packet_modes.append(packet_mode)

        if cfg is not None and cfg["mode"] == 0x01 and cfg["spacing_ms"] > 0:
            spacing_ms = cfg["spacing_ms"]
            spacing_source = f"Mode=1 set_acq_configs (sample_time={cfg['sample_time_raw']} × {_SAMPLE_TIME_UNIT_MS}ms)"
        elif cfg is not None and cfg["mode"] == 0x00:
            # Spectrum scan: derive from timestamps (motor-position-based spacing)
            if packet_idx > 0:
                prev_ts = sci_packets[packet_idx - 1]["timestamp"]
                time_diff = (packet_timestamp - prev_ts).total_seconds()
                spacing_ms = (time_diff * 1000) / (num_points - 1) if num_points > 1 else 260
            else:
                spacing_ms = 260
            spacing_source = "Mode=0 spectrum (estimated from timestamps)"
        elif packet_idx > 0:
            prev_ts = sci_packets[packet_idx - 1]["timestamp"]
            time_diff = (packet_timestamp - prev_ts).total_seconds()
            spacing_ms = (time_diff * 1000) / (num_points - 1) if num_points > 1 else 260
        else:
            spacing_ms = 260

        mode_label = f"Mode={cfg['mode']}" if cfg is not None else "Mode=?"
        print(
            f"  Packet {packet_num}/{len(sci_packets)}: {num_points} points, "
            f"timestamp: {packet_timestamp}, type: {packet_type}, {mode_label}, "
            f"spacing: {spacing_ms:.1f}ms ({spacing_source})"
        )

        start_idx = len(sci_datetimes)
        swir_low.extend(series["swir_low"])
        swir_med.extend(series["swir_med"])
        swir_high.extend(series["swir_high"])
        mwir_low.extend(series["mwir_low"])
        mwir_med.extend(series["mwir_med"])
        mwir_high.extend(series["mwir_high"])
        sci_abs_steps.extend(series["abs_steps"])

        for i in range(num_points):
            offset_ms = (num_points - 1 - i) * spacing_ms
            sci_datetimes.append(packet_timestamp - timedelta(milliseconds=offset_ms))

        end_idx = len(sci_datetimes) - 1
        packet_boundaries.append((start_idx, end_idx, packet_num, packet_timestamp, packet_mode))

    unique_modes = {mode for mode in packet_modes if mode in (0x00, 0x01)}
    sci_axis_mode = "abs_steps" if unique_modes == {0x00} else "time"
    if unique_modes == {0x00, 0x01}:
        print("Mixed SCI acquisition modes detected; using time baseline for combined SWIR/MWIR plots.")

    return (
        sci_datetimes,
        sci_abs_steps,
        sci_axis_mode,
        swir_low,
        swir_med,
        swir_high,
        mwir_low,
        mwir_med,
        mwir_high,
        packet_boundaries,
    )


# ── Click handler ─────────────────────────────────────────────────────────────


class ClickHandler:
    def __init__(
        self,
        sci_datetimes,
        sci_plot_x,
        sci_axis_mode,
        sci_abs_steps,
        swir_low,
        swir_med,
        swir_high,
        mwir_low,
        mwir_med,
        mwir_high,
        packet_boundaries,
        ax_swir,
        ax_mwir,
        error_events,
        click_axes,
    ):
        self.sci_datetimes = list(sci_datetimes)
        self.sci_axis_mode = sci_axis_mode
        self.sci_abs_steps = np.array(sci_abs_steps, dtype=float)
        if sci_axis_mode == "abs_steps":
            self.sci_x = np.array(sci_plot_x, dtype=float)
        else:
            self.sci_x = mdates.date2num(sci_plot_x)
        self.swir_low = np.array(swir_low)
        self.swir_med = np.array(swir_med)
        self.swir_high = np.array(swir_high)
        self.mwir_low = np.array(mwir_low)
        self.mwir_med = np.array(mwir_med)
        self.mwir_high = np.array(mwir_high)
        self.packet_boundaries = packet_boundaries
        self.ax_swir = ax_swir
        self.ax_mwir = ax_mwir
        self.error_events = list(error_events or [])
        self.click_axes = tuple(click_axes or ())

    def _show_error_popup(self, ts, eb, ob, mtr):
        title = f"Error details @ {ts.strftime('%Y-%m-%d %H:%M:%S')}"
        lines = [
            f"Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "EB Error Flags:",
            "  " + (", ".join(eb) if eb else "none"),
            "",
            "OB Errors:",
            "  " + (", ".join(ob) if ob else "none"),
            "",
            "Motor Errors:",
            "  " + (", ".join(mtr) if mtr else "none"),
        ]
        message = "\n".join(lines)
        try:
            messagebox.showinfo(title, message)
        except Exception:
            # Fallback if GUI popup is unavailable.
            print(f"\n[{title}]\n{message}")

    def _try_error_popup(self, event):
        if event.inaxes not in self.click_axes or event.xdata is None or not self.error_events:
            return False

        error_times_num = np.array([mdates.date2num(ts) for ts, _eb, _ob, _mtr in self.error_events], dtype=float)
        idx = int(np.argmin(np.abs(error_times_num - event.xdata)))
        xlim = event.inaxes.get_xlim()
        span_days = max(abs(xlim[1] - xlim[0]), 1e-12)
        tolerance_days = max(0.3 / 86400.0, span_days * 0.005)
        if abs(error_times_num[idx] - event.xdata) > tolerance_days:
            return False

        ts, eb, ob, mtr = self.error_events[idx]
        self._show_error_popup(ts, eb, ob, mtr)
        return True

    def on_click(self, event):
        if self._try_error_popup(event):
            return

        if event.inaxes not in (self.ax_swir, self.ax_mwir) or event.xdata is None:
            return
        if len(self.sci_x) == 0:
            return

        idx = int(np.argmin(np.abs(self.sci_x - event.xdata)))
        click_y = event.ydata

        # Which packet?
        packet_info = "Unknown packet"
        for start_idx, end_idx, packet_num, ts, _packet_mode in self.packet_boundaries:
            if start_idx <= idx <= end_idx:
                packet_info = f"Packet {packet_num} (received {ts})"
                break

        # Which channel?
        if event.inaxes is self.ax_swir:
            dists = [
                abs(self.swir_low[idx] - click_y),
                abs(self.swir_med[idx] - click_y),
                abs(self.swir_high[idx] - click_y),
            ]
            names = ["SWIR_LOW", "SWIR_MED", "SWIR_HIGH"]
            vals = [self.swir_low[idx], self.swir_med[idx], self.swir_high[idx]]
        else:
            dists = [
                abs(self.mwir_low[idx] - click_y),
                abs(self.mwir_med[idx] - click_y),
                abs(self.mwir_high[idx] - click_y),
            ]
            names = ["MWIR_LOW", "MWIR_MED", "MWIR_HIGH"]
            vals = [self.mwir_low[idx], self.mwir_med[idx], self.mwir_high[idx]]

        best = int(np.argmin(dists))
        ts_str = self.sci_datetimes[idx].strftime("%H:%M:%S.%f")[:-3]
        axis_str = (
            f"ABS_STEPS: {int(self.sci_abs_steps[idx])}"
            if self.sci_axis_mode == "abs_steps"
            else f"Time:      {ts_str}"
        )

        print(f"\n{'=' * 60}")
        print(f"  {packet_info}")
        if self.sci_axis_mode == "abs_steps":
            print(f"  Time:      {ts_str}")
            print(f"  {axis_str}")
        else:
            print(f"  {axis_str}")
        print(f"  Channel:   {names[best]}")
        print(f"  Intensity: {int(vals[best])}")
        print(f"{'=' * 60}")


# ── HK anomaly detection ─────────────────────────────────────────────────────

# Channels whose large swings are driven by intentional TEC on/off transitions
# and should not be flagged as temperature anomalies.
_TEMP_JUMP_EXCLUDE = {"EB_PELTIER"}

# Fields to skip when reporting error states (padding/unused bits)
_ERROR_FLAGS_SKIP = {"RESERVED"}
_OB_ERROR_SKIP = {"UNUSED1", "UNUSED2"}
_MTR_ERROR_SKIP = {"UNUSED"}


def detect_error_states(hk_packets):
    """Detect transitions in EB error flags, OB errors, and motor errors.

    Returns a list of (timestamp, eb_flags, ob_errors, mtr_errors) tuples,
    one entry per state change.  Each *_flags/*_errors is a sorted list of
    flag names whose value is 1.  An entry with all-empty lists means all
    errors cleared.
    """
    events = []
    prev_eb = frozenset()
    prev_ob = frozenset()
    prev_mtr = frozenset()

    for hk in hk_packets:
        eb_ns = getattr(hk, "ERROR_FLAGS_BITS", None)
        ob_ns = getattr(hk, "ERRORS", None)
        mtr_ns = getattr(hk, "MTR_ERRORS", None)

        eb = (
            frozenset(k for k, v in vars(eb_ns).items() if v == 1 and k not in _ERROR_FLAGS_SKIP)
            if eb_ns is not None
            else frozenset()
        )

        ob = (
            frozenset(k for k, v in vars(ob_ns).items() if v == 1 and k not in _OB_ERROR_SKIP)
            if ob_ns is not None
            else frozenset()
        )

        mtr = (
            frozenset(k for k, v in vars(mtr_ns).items() if v == 1 and k not in _MTR_ERROR_SKIP)
            if mtr_ns is not None
            else frozenset()
        )

        if eb != prev_eb or ob != prev_ob or mtr != prev_mtr:
            events.append((hk.TIME, sorted(eb), sorted(ob), sorted(mtr)))
            prev_eb, prev_ob, prev_mtr = eb, ob, mtr

    return events


def _print_error_states_section(events):
    any_set = [e for e in events if e[1] or e[2] or e[3]]
    if not any_set:
        print("  (none)")
        return
    for ts, eb, ob, mtr in events:
        parts = []
        if eb:
            parts.append(f"ERROR_FLAGS: {', '.join(eb)}")
        if ob:
            parts.append(f"OB_ERRORS: {', '.join(ob)}")
        if mtr:
            parts.append(f"MTR_ERRORS: {', '.join(mtr)}")
        if parts:
            print(f"  {ts.strftime('%H:%M:%S')}  {' | '.join(parts)}")
        else:
            print(f"  {ts.strftime('%H:%M:%S')}  → all errors cleared")


# Threshold levels to check, ordered most-strict → least-strict.
# Plot colours: 0.05 → red, 0.025 → orange.
_JUMP_FRACS = (0.05, 0.025)
_JUMP_COLOURS = {0.05: ("red", 60), 0.025: ("darkorange", 35)}


def detect_hk_anomalies(
    hk_timestamps,
    temp_data,
    volt_data,
    gap_threshold=2.0,
    jump_fracs=_JUMP_FRACS,
    exclude_temp_channels=_TEMP_JUMP_EXCLUDE,
):
    """Detect gaps > gap_threshold s and per-channel value jumps at each threshold.

    Returns:
        gaps             – list of (t_start, t_end, dt_seconds)
        temp_jumps       – {frac: {channel: [(timestamp, value, delta), ...]}}
        volt_jumps       – {frac: {channel: [(timestamp, value, delta), ...]}}
    """
    gaps = []
    for i in range(1, len(hk_timestamps)):
        dt = (hk_timestamps[i] - hk_timestamps[i - 1]).total_seconds()
        if dt > gap_threshold:
            gaps.append((hk_timestamps[i - 1], hk_timestamps[i], dt))

    def find_jumps(data_dict, timestamps, frac, exclude=()):
        result = {}
        for key, values in data_dict.items():
            if key in exclude:
                continue
            arr = np.array(values, dtype=float)
            mean_abs = np.nanmean(np.abs(arr))
            if mean_abs == 0:
                continue
            threshold = frac * mean_abs
            entries = []
            for i in range(1, len(arr)):
                if not np.isnan(arr[i]) and not np.isnan(arr[i - 1]):
                    delta = abs(arr[i] - arr[i - 1])
                    if delta > threshold:
                        entries.append((timestamps[i], arr[i], delta))
            if entries:
                result[key] = entries
        return result

    temp_jumps = {
        frac: find_jumps(temp_data, hk_timestamps, frac, exclude=exclude_temp_channels) for frac in jump_fracs
    }
    volt_jumps = {frac: find_jumps(volt_data, hk_timestamps, frac) for frac in jump_fracs}
    return gaps, temp_jumps, volt_jumps


def _fmt_pct(frac):
    return f"{frac * 100:g}%"


def _print_jump_section(label, jumps_by_frac, unit, val_fmt):
    # Collect all events, annotating which threshold(s) they breach
    # Key: (channel, timestamp) → (value, delta, set_of_fracs)
    seen: dict = {}
    for frac, ch_dict in jumps_by_frac.items():
        for ch, entries in ch_dict.items():
            for ts, val, delta in entries:
                k = (ch, ts)
                if k not in seen:
                    seen[k] = (val, delta, set())
                seen[k][2].add(frac)
    if not seen:
        print("  (none)")
        return
    for (ch, ts), (val, delta, hit_fracs) in sorted(seen.items(), key=lambda x: x[0][1]):
        tags = ", ".join(f">{_fmt_pct(f)}" for f in sorted(hit_fracs, reverse=True))
        print(f"  {ts.strftime('%H:%M:%S')}  {ch}: {val_fmt(val)}{unit}  (Δ{val_fmt(delta)}{unit})  [{tags}]")


def print_anomaly_summary(gaps, temp_jumps, volt_jumps, error_events=None):
    excl = ", ".join(sorted(_TEMP_JUMP_EXCLUDE))
    print(f"\n{'─' * 60}")
    print(f"HK ANOMALY SUMMARY  (temp excludes: {excl})")
    print(f"{'─' * 60}")
    if gaps:
        print(f"\nPacket gaps > 2s ({len(gaps)}):")
        for t_start, t_end, dt in gaps:
            print(f"  {t_start.strftime('%H:%M:%S')} → {t_end.strftime('%H:%M:%S')}  ({dt:.1f}s)")
    else:
        print("\nNo packet gaps > 2s")
    print(f"\nTemperature jumps  [thresholds: {', '.join(f'>{_fmt_pct(f)}' for f in sorted(temp_jumps))}]:")
    _print_jump_section("Temperature", temp_jumps, "°C", lambda v: f"{v:.2f}")
    print(f"\nVoltage jumps  [thresholds: {', '.join(f'>{_fmt_pct(f)}' for f in sorted(volt_jumps))}]:")
    _print_jump_section("Voltage", volt_jumps, "V", lambda v: f"{v:.3f}")
    print("\nError flag transitions (EB error flags / OB errors / MTR errors):")
    _print_error_states_section(error_events or [])
    print(f"{'─' * 60}\n")


def build_error_byte_arrays(hk_packets):
    """Build raw error/warning byte/flag arrays from HK packets."""
    ts = [hk.TIME for hk in hk_packets]

    def _get_num(hk, field):
        val = getattr(hk, field, 0)
        try:
            return float(val)
        except Exception:
            return np.nan

    data = {
        "EB_ERROR_FLAGS": [_get_num(hk, "ERROR_FLAGS") for hk in hk_packets],
        "EB_WARNING_FLAGS": [_get_num(hk, "WARNING_FLAGS") for hk in hk_packets],
        "FDIR_ALARM_FLAGS": [_get_num(hk, "FDIR_ALARM_FLAGS") for hk in hk_packets],
        "FDIR_WARNING_FLAGS": [_get_num(hk, "FDIR_WARNING_FLAGS") for hk in hk_packets],
        "OB_LAST_ERROR": [_get_num(hk, "OB_LAST_ERROR") for hk in hk_packets],
        "OB_MOTOR_ERROR": [_get_num(hk, "OB_MOTOR_ERROR") for hk in hk_packets],
    }
    return ts, data


PANEL_ORDER = ["temp", "volt", "err", "psu_ch3", "psu_ch4", "swir", "mwir"]
PANEL_LABELS = {
    "temp": "Temperatures",
    "volt": "Voltages",
    "err": "Error / Warning Bytes",
    "psu_ch3": "PSU Current CH3",
    "psu_ch4": "PSU Current CH4",
    "swir": "SWIR",
    "mwir": "MWIR",
}

TEMP_PLOT_SPECS = [
    ("OB_DIGITAL", "OB Digital", "o-", 3),
    ("OB_DETECTOR", "OB Detector", "s-", 3),
    ("OB_MECHANISM", "OB Mechanism", "^-", 3),
    ("OB_MOTOR", "OB Motor", "v-", 3),
    ("EB_MCU", "EB MCU", "D-", 3),
    ("EB_PSU_BOARD", "EB PSU Board", "p-", 3),
    ("EB_INTERNAL_TRP", "EB Int. TRP", "H-", 3),
    ("EB_PELTIER", "EB Peltier", "*-", 6),
]

VOLT_PLOT_SPECS = [
    ("EB_12V", "EB +12V", "o-", 3),
    ("EB_NEG12V", "EB -12V", "s-", 3),
    ("EB_5V", "EB 5V", "^-", 3),
    ("EB_3V3", "EB 3.3V", "v-", 3),
    ("EB_TEC_RAIL", "EB TEC Rail", "D-", 3),
    ("OB_3V3", "OB 3.3V", "p-", 3),
    ("OB_1V5", "OB 1.5V", "H-", 3),
]

ERR_PLOT_SPECS = [
    ("EB_ERROR_FLAGS", "EB ERROR_FLAGS"),
    ("EB_WARNING_FLAGS", "EB WARNING_FLAGS"),
    ("FDIR_ALARM_FLAGS", "FDIR ALARM_FLAGS"),
    ("FDIR_WARNING_FLAGS", "FDIR WARNING_FLAGS"),
    ("OB_LAST_ERROR", "OB LAST_ERROR"),
    ("OB_MOTOR_ERROR", "OB MOTOR_ERROR"),
]

SCI_PLOT_SPECS = {
    "swir": [
        ("SWIR_LOW", "SWIR_LOW"),
        ("SWIR_MED", "SWIR_MED"),
        ("SWIR_HIGH", "SWIR_HIGH"),
    ],
    "mwir": [
        ("MWIR_LOW", "MWIR_LOW"),
        ("MWIR_MED", "MWIR_MED"),
        ("MWIR_HIGH", "MWIR_HIGH"),
    ],
}

PARAM_OPTIONS = {
    "temp": [k for k, _lbl, _style, _ms in TEMP_PLOT_SPECS],
    "volt": [k for k, _lbl in [(s[0], s[1]) for s in VOLT_PLOT_SPECS]],
    "err": [k for k, _lbl in ERR_PLOT_SPECS],
    "psu_ch3": ["CH3_I"],
    "psu_ch4": ["CH4_I"],
    "swir": [k for k, _lbl in SCI_PLOT_SPECS["swir"]],
    "mwir": [k for k, _lbl in SCI_PLOT_SPECS["mwir"]],
}


# ── Drawing helper ───────────────────────────────────────────────────────────


def _draw_all_axes(
    ax_temp,
    ax_volt,
    ax_err,
    ax_psu_ch3,
    ax_psu_ch4,
    ax_swir,
    ax_mwir,
    fig,
    hk_timestamps,
    temp_data,
    volt_data,
    gaps,
    temp_jumps,
    volt_jumps,
    sci_datetimes,
    sci_abs_steps,
    sci_axis_mode,
    swir_low,
    swir_med,
    swir_high,
    mwir_low,
    mwir_med,
    mwir_high,
    packet_boundaries,
    psu_data=None,
    error_events=None,
    err_ts=None,
    err_data=None,
    panel_visibility=None,
    selected_params=None,
    custom_axes=None,
    custom_series=None,
    replay_overlay=None,
):
    """Clear and redraw all subplots in-place."""
    panel_visibility = panel_visibility or {k: True for k in PANEL_ORDER}
    selected_params = selected_params or {k: set(v) for k, v in PARAM_OPTIONS.items()}

    custom_axes = custom_axes or []
    custom_series = custom_series or {}
    replay_overlay = replay_overlay or {}

    axes = [ax_temp, ax_volt, ax_err, ax_psu_ch3, ax_psu_ch4, ax_swir, ax_mwir] + [ax for _field, ax in custom_axes]
    for ax in axes:
        ax.cla()
        ax.set_visible(True)

    panel_axes = {
        "temp": ax_temp,
        "volt": ax_volt,
        "err": ax_err,
        "psu_ch3": ax_psu_ch3,
        "psu_ch4": ax_psu_ch4,
        "swir": ax_swir,
        "mwir": ax_mwir,
    }

    for panel, ax in panel_axes.items():
        if ax is None:
            continue
        if not panel_visibility.get(panel, True):
            ax.set_visible(False)

    active_error_times = [ts for ts, eb, ob, mtr in (error_events or []) if eb or ob or mtr]

    def _selected(group):
        vals = selected_params.get(group, PARAM_OPTIONS[group])
        return set(vals)

    def _has_param(group, name):
        return name in _selected(group)

    def _show_no_params(ax, title):
        ax.set_title(title)
        ax.text(
            0.5,
            0.5,
            "No parameters selected",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color="gray",
        )
        ax.grid(True, alpha=0.3)

    # Temperatures
    if ax_temp.get_visible():
        plotted_temp = 0
        for key, label, style, ms in TEMP_PLOT_SPECS:
            if not _has_param("temp", key):
                continue
            if key not in temp_data:
                continue
            if key == "EB_PELTIER" and not any(not np.isnan(v) for v in temp_data[key]):
                continue
            ax_temp.plot(hk_timestamps, temp_data[key], style, label=label, markersize=ms)
            plotted_temp += 1
        if plotted_temp == 0:
            _show_no_params(ax_temp, "Temperatures")
        else:
            ax_temp.set_ylabel("Temperature (°C)")
            ax_temp.set_title("Temperatures")
            ax_temp.grid(True, alpha=0.3)
            for frac in sorted(temp_jumps.keys()):
                colour, sz = _JUMP_COLOURS[frac]
                for ch, entries in temp_jumps[frac].items():
                    if not _has_param("temp", ch):
                        continue
                    ax_temp.scatter(
                        [e[0] for e in entries],
                        [e[1] for e in entries],
                        marker="x",
                        color=colour,
                        s=sz,
                        linewidths=1.5,
                        zorder=5,
                    )
            for i, ts in enumerate(active_error_times):
                ax_temp.axvline(
                    ts,
                    color="crimson",
                    linestyle="--",
                    linewidth=1.0,
                    alpha=0.75,
                    label="Error" if i == 0 else None,
                )
            handles, labels = ax_temp.get_legend_handles_labels()
            if handles:
                ax_temp.legend(loc="best", fontsize=7)

    # Voltages
    if ax_volt.get_visible():
        plotted_volt = 0
        for key, label, style, ms in VOLT_PLOT_SPECS:
            if not _has_param("volt", key):
                continue
            if key not in volt_data:
                continue
            if key == "EB_TEC_RAIL" and not any(not np.isnan(v) for v in volt_data[key]):
                continue
            ax_volt.plot(hk_timestamps, volt_data[key], style, label=label, markersize=ms)
            plotted_volt += 1
        if plotted_volt == 0:
            _show_no_params(ax_volt, "Voltages")
        else:
            ax_volt.set_ylabel("Voltage (V)")
            ax_volt.set_title("Voltages")
            ax_volt.grid(True, alpha=0.3)
            for frac in sorted(volt_jumps.keys()):
                colour, sz = _JUMP_COLOURS[frac]
                for ch, entries in volt_jumps[frac].items():
                    if not _has_param("volt", ch):
                        continue
                    ax_volt.scatter(
                        [e[0] for e in entries],
                        [e[1] for e in entries],
                        marker="x",
                        color=colour,
                        s=sz,
                        linewidths=1.5,
                        zorder=5,
                    )
            for ts in active_error_times:
                ax_volt.axvline(ts, color="crimson", linestyle="--", linewidth=1.0, alpha=0.55)
            handles, labels = ax_volt.get_legend_handles_labels()
            if handles:
                ax_volt.legend(loc="best", fontsize=7)

    # Error/warning bytes
    if ax_err.get_visible():
        plotted_err = 0
        if err_ts and err_data:
            for key, label in ERR_PLOT_SPECS:
                if not _has_param("err", key):
                    continue
                ax_err.plot(err_ts, err_data[key], linewidth=1.0, label=label)
                plotted_err += 1
        if plotted_err == 0:
            _show_no_params(ax_err, "Error / Warning Bytes")
        else:
            for ts in active_error_times:
                ax_err.axvline(ts, color="crimson", linestyle="--", linewidth=1.0, alpha=0.7)
            ax_err.set_ylabel("Error Bytes")
            ax_err.set_title("Error / Warning Bytes")
            ax_err.grid(True, alpha=0.3)
            handles, labels = ax_err.get_legend_handles_labels()
            if handles:
                ax_err.legend(loc="best", fontsize=7)

    # Reflow visible base panels so hidden panels do not leave blank vertical gaps.
    base_axes = [
        ax
        for ax, panel in (
            (ax_temp, "temp"),
            (ax_volt, "volt"),
            (ax_err, "err"),
            (ax_psu_ch3, "psu_ch3"),
            (ax_psu_ch4, "psu_ch4"),
            (ax_swir, "swir"),
            (ax_mwir, "mwir"),
        )
        if ax is not None and panel_visibility.get(panel, True)
    ]
    custom_visible_axes = [ax for _field, ax in custom_axes if ax is not None]
    custom_top = max((ax.get_position().y1 for ax in custom_visible_axes), default=0.0)
    base_top = 0.88
    base_bottom = max(0.06, custom_top + 0.03)
    if base_axes and base_bottom < base_top:
        gap = 0.012
        total_h = base_top - base_bottom
        h = max(0.05, (total_h - gap * (len(base_axes) - 1)) / len(base_axes))
        y = base_top - h
        for ax in base_axes:
            ax.set_position((0.08, y, 0.86, h))
            y -= h + gap

    def _plot_psu_axis(ax_psu, panel_key, channel, title):
        if ax_psu is None or not ax_psu.get_visible():
            return

        param_name = f"{channel}_I"
        if not _has_param(panel_key, param_name):
            _show_no_params(ax_psu, title)
            return

        if psu_data is None:
            ax_psu.text(
                0.5,
                0.5,
                f"No PSU {channel} current data",
                transform=ax_psu.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="gray",
            )
            ax_psu.set_ylabel("PSU I (A)")
            ax_psu.set_title(title)
            ax_psu.grid(True, alpha=0.3)
            return

        times = psu_data[channel]["times"]
        currents = psu_data[channel]["i"]
        finite = [(t, i) for t, i in zip(times, currents) if np.isfinite(i)]
        if hk_timestamps:
            hk_start = hk_timestamps[0]
            hk_end = hk_timestamps[-1]
            finite = [(t, i) for t, i in finite if hk_start <= t <= hk_end]

        show_raw = True
        show_ma = False
        replay_ma_series = None
        if channel == "CH4" and isinstance(replay_overlay, dict):
            show_raw = bool(replay_overlay.get("show_psu_raw", True))
            show_ma = bool(replay_overlay.get("show_psu_ma", False))
            replay_ma_series = replay_overlay.get("psu_ma_series")

        if finite and show_raw:
            psu_t, psu_i = zip(*finite)
            ax_psu.plot(psu_t, [i * 1000 for i in psu_i], "o-", markersize=2, label=f"{channel} I")
        elif not finite and not (channel == "CH4" and show_ma and replay_ma_series):
            ax_psu.text(
                0.5,
                0.5,
                f"No overlapping PSU {channel} current samples",
                transform=ax_psu.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="gray",
            )

        if channel == "CH4" and show_ma and isinstance(replay_ma_series, tuple):
            ma_times, ma_vals = replay_ma_series
            finite_ma = [(t, i) for t, i in zip(ma_times, ma_vals) if np.isfinite(i)]
            if hk_timestamps:
                hk_start = hk_timestamps[0]
                hk_end = hk_timestamps[-1]
                finite_ma = [(t, i) for t, i in finite_ma if hk_start <= t <= hk_end]
            if finite_ma:
                ma_t, ma_i = zip(*finite_ma)
                ax_psu.plot(ma_t, ma_i, "-", linewidth=1.8, color="#0b6e4f", label="CH4 MA(5)")

        handles, labels = ax_psu.get_legend_handles_labels()
        if handles:
            ax_psu.legend(loc="best", fontsize=7)

        ax_psu.set_ylabel("PSU I (mA)")
        ax_psu.set_title(title)
        ax_psu.grid(True, alpha=0.3)
        for ts in active_error_times:
            ax_psu.axvline(ts, color="crimson", linestyle="--", linewidth=1.0, alpha=0.45)

        if channel == "CH4":
            replay_events = replay_overlay.get("events") if isinstance(replay_overlay, dict) else None
            if isinstance(replay_events, list):
                for event in replay_events:
                    if not isinstance(event, dict):
                        continue
                    check_start = event.get("check_start")
                    check_end = event.get("check_end")
                    acq_time = event.get("acq_time")
                    expected_min = event.get("expected_min")
                    expected_max = event.get("expected_max")
                    median_ma = event.get("median_ma")
                    result = event.get("result")
                    if isinstance(check_start, datetime) and isinstance(check_end, datetime):
                        ax_psu.axvspan(
                            check_start,
                            check_end,
                            color=("#2e7d32" if result == "PASS" else "#c62828"),
                            alpha=0.10,
                        )
                        ax_psu.axvline(check_start, color="#1565c0", linestyle="--", linewidth=1.0, alpha=0.8)
                    if isinstance(acq_time, datetime):
                        ax_psu.axvline(acq_time, color="#ff8f00", linestyle=":", linewidth=1.0, alpha=0.8)
                    if isinstance(expected_min, (int, float)) and isinstance(expected_max, (int, float)):
                        ax_psu.axhspan(expected_min, expected_max, color="#1565c0", alpha=0.06)
                    if (
                        isinstance(check_start, datetime)
                        and isinstance(check_end, datetime)
                        and isinstance(median_ma, (int, float))
                    ):
                        mid = check_start + (check_end - check_start) / 2
                        ax_psu.scatter(
                            [mid],
                            [median_ma],
                            color=("#2e7d32" if result == "PASS" else "#c62828"),
                            marker="D",
                            s=36,
                            zorder=6,
                        )

    _plot_psu_axis(ax_psu_ch3, "psu_ch3", "CH3", "PSU Current (CH3)")
    _plot_psu_axis(ax_psu_ch4, "psu_ch4", "CH4", "PSU Current (CH4)")

    sci_x = sci_abs_steps if sci_axis_mode == "abs_steps" else sci_datetimes

    # SWIR
    if ax_swir.get_visible():
        swir_map = {"SWIR_LOW": swir_low, "SWIR_MED": swir_med, "SWIR_HIGH": swir_high}
        plotted_swir = 0
        if sci_x:
            for key, label in SCI_PLOT_SPECS["swir"]:
                if not _has_param("swir", key):
                    continue
                vals = swir_map[key]
                ax_swir.scatter(sci_x, vals, s=2, label=label, alpha=0.6)
                ax_swir.plot(sci_x, vals, linewidth=0.3, alpha=0.4)
                plotted_swir += 1
            if plotted_swir > 0:
                if sci_axis_mode == "time":
                    for _start, _end, packet_num, packet_rx_ts, _packet_mode in packet_boundaries:
                        ax_swir.axvline(x=packet_rx_ts, color="red", linestyle="--", linewidth=1, alpha=0.5)
                        ax_swir.text(
                            packet_rx_ts,
                            0.95,
                            f"{packet_num}",
                            transform=ax_swir.get_xaxis_transform(),
                            rotation=90,
                            va="top",
                            ha="left",
                            fontsize=8,
                            color="red",
                            alpha=0.7,
                        )
        if plotted_swir == 0:
            _show_no_params(ax_swir, "SWIR")
        else:
            ax_swir.set_ylabel("Intensity")
            ax_swir.set_title("SWIR")
            ax_swir.grid(True, alpha=0.3)
            if sci_axis_mode == "abs_steps":
                ax_swir.set_xlabel("Absolute Motor Steps")
            for ts in active_error_times:
                if sci_axis_mode == "time":
                    ax_swir.axvline(ts, color="crimson", linestyle="--", linewidth=1.0, alpha=0.35)
            handles, labels = ax_swir.get_legend_handles_labels()
            if handles:
                ax_swir.legend(loc="upper right", fontsize=7)

    # MWIR
    if ax_mwir.get_visible():
        mwir_map = {"MWIR_LOW": mwir_low, "MWIR_MED": mwir_med, "MWIR_HIGH": mwir_high}
        plotted_mwir = 0
        if sci_x:
            for key, label in SCI_PLOT_SPECS["mwir"]:
                if not _has_param("mwir", key):
                    continue
                vals = mwir_map[key]
                ax_mwir.scatter(sci_x, vals, s=2, label=label, alpha=0.6)
                ax_mwir.plot(sci_x, vals, linewidth=0.3, alpha=0.4)
                plotted_mwir += 1
            if plotted_mwir > 0:
                if sci_axis_mode == "time":
                    for _start, _end, packet_num, packet_rx_ts, _packet_mode in packet_boundaries:
                        ax_mwir.axvline(x=packet_rx_ts, color="red", linestyle="--", linewidth=1, alpha=0.5)
                        ax_mwir.text(
                            packet_rx_ts,
                            0.95,
                            f"{packet_num}",
                            transform=ax_mwir.get_xaxis_transform(),
                            rotation=90,
                            va="top",
                            ha="left",
                            fontsize=8,
                            color="red",
                            alpha=0.7,
                        )
        if plotted_mwir == 0:
            _show_no_params(ax_mwir, "MWIR")
        else:
            ax_mwir.set_ylabel("Intensity")
            ax_mwir.set_title("MWIR")
            ax_mwir.grid(True, alpha=0.3)
            if sci_axis_mode == "abs_steps":
                ax_mwir.set_xlabel("Absolute Motor Steps")
            for ts in active_error_times:
                if sci_axis_mode == "time":
                    ax_mwir.axvline(ts, color="crimson", linestyle="--", linewidth=1.0, alpha=0.35)
            handles, labels = ax_mwir.get_legend_handles_labels()
            if handles:
                ax_mwir.legend(loc="upper right", fontsize=7)

    # Custom parameter subplots (same figure)
    for field_name, ax_custom in custom_axes:
        ts_vals = custom_series.get(field_name)
        ax_custom.cla()
        if not ts_vals:
            ax_custom.text(
                0.5,
                0.5,
                "No data",
                transform=ax_custom.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="gray",
            )
            ax_custom.set_title(f"HK Parameter: {field_name}")
            ax_custom.grid(True, alpha=0.3)
            continue

        ts, vals = ts_vals
        style = "o-"
        title = f"HK Parameter: {field_name}"
        ylabel = "Value"
        if field_name == "__REPLAY_STATE__":
            style = ".-"
            title = "Replay: CURRENT_OPERATING_STATE"
            ylabel = "State"
        elif field_name == "__REPLAY_MOVING__":
            style = ".-"
            title = "Replay: Motor MOVING / HOMING_COMPLETE"
            ylabel = "Flag"
        ax_custom.plot(ts, vals, style, markersize=2, linewidth=0.8, label=field_name)
        ax_custom.set_title(title)
        ax_custom.set_ylabel(ylabel)
        ax_custom.grid(True, alpha=0.3)
        handles, _labels = ax_custom.get_legend_handles_labels()
        if handles:
            ax_custom.legend(loc="best", fontsize=8)
        for ts_err in active_error_times:
            ax_custom.axvline(ts_err, color="crimson", linestyle="--", linewidth=1.0, alpha=0.35)

    visible_axes = [ax for ax in axes if ax is not None and ax.get_visible()]
    if visible_axes:
        bottom_ax = visible_axes[-1]
        if sci_axis_mode == "abs_steps" and bottom_ax in (ax_swir, ax_mwir):
            bottom_ax.set_xlabel("Absolute Motor Steps")
        else:
            bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            bottom_ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            bottom_ax.set_xlabel("Time (HH:MM:SS)")
    if not (sci_axis_mode == "abs_steps" and visible_axes and visible_axes[-1] in (ax_swir, ax_mwir)):
        fig.autofmt_xdate(rotation=45, ha="right")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Combined HK/SCI plot with selectable multi-RS422 and PSU")
    parser.add_argument("--rs422-log", type=Path, nargs="+", default=[LOG_PATH])
    parser.add_argument("--psu-log", type=Path, default=None)
    parser.add_argument("--rs422-offset-hours", type=float, default=RS422_TIME_OFFSET_HOURS)
    args = parser.parse_args()

    rs422_offset = timedelta(hours=args.rs422_offset_hours)

    def _title_for_logs(paths):
        names = [p.name for p in paths]
        if not names:
            return "Combined Analysis"
        if len(names) == 1:
            return f"Combined Analysis — {names[0]}"
        return f"Combined Analysis — {names[0]} + {len(names) - 1} more"

    def _analyze(log_paths, psu_log):
        valid_logs = []
        all_hk = []
        all_acq = []
        all_sci = []

        for lp in log_paths:
            if not lp.exists():
                print(f"Warning: RS422 log not found: {lp}")
                continue
            valid_logs.append(lp)
            print(f"Reading: {lp}")
            hk = extract_hk_packets(lp, rs422_offset=rs422_offset)
            acq = extract_acq_configs_tcs(lp, rs422_offset=rs422_offset)
            sci = extract_sci_packets(lp, rs422_offset=rs422_offset)
            print(f"  HK: {len(hk)}  set_acq_configs: {len(acq)}  SCI: {len(sci)}")
            all_hk.extend(hk)
            all_acq.extend(acq)
            all_sci.extend(sci)

        if not all_hk:
            print("Error: no HK packets found across selected RS422 logs")
            return None

        all_hk.sort(key=lambda hk: hk.TIME)
        all_acq.sort(key=lambda cfg: cfg["timestamp"])
        all_sci.sort(key=lambda pkt: (pkt["timestamp"] is None, pkt["timestamp"]))

        hk_timestamps, temp_data, volt_data = build_hk_arrays(all_hk)
        err_ts, err_data = build_error_byte_arrays(all_hk)
        gaps, temp_jumps, volt_jumps = detect_hk_anomalies(hk_timestamps, temp_data, volt_data)
        error_events = detect_error_states(all_hk)
        print_anomaly_summary(gaps, temp_jumps, volt_jumps, error_events)

        print(f"set_acq_configs TCs (combined): {len(all_acq)}")
        print(f"Science packets (combined): {len(all_sci)}")
        sci = build_sci_arrays(all_sci, all_acq)
        (
            sci_datetimes,
            sci_abs_steps,
            sci_axis_mode,
            swir_low,
            swir_med,
            swir_high,
            mwir_low,
            mwir_med,
            mwir_high,
            packet_boundaries,
        ) = sci

        acq_windows = extract_acq_windows(all_hk)
        if acq_windows:
            print(f"Acquisition windows ({len(acq_windows)}):")
            for ws, we in acq_windows:
                print(f"  {ws.strftime('%H:%M:%S')} → {we.strftime('%H:%M:%S')}")
        else:
            print("No acquisition windows found in HK — showing all science data")

        swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high = filter_sci_to_acq_windows(
            sci_datetimes, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high, acq_windows
        )

        psu_data = None
        if psu_log is not None:
            if psu_log.exists():
                psu_data = build_psu_arrays(psu_log)
                print(f"Loaded PSU samples from: {psu_log}")

                ch4_times = psu_data["CH4"]["times"]
                ch4_curr = psu_data["CH4"]["i"]
                finite_ch4 = [(t, i) for t, i in zip(ch4_times, ch4_curr) if np.isfinite(i)]
                if finite_ch4:
                    psu_start = finite_ch4[0][0]
                    psu_end = finite_ch4[-1][0]
                    hk_start = hk_timestamps[0]
                    hk_end = hk_timestamps[-1]
                    overlap_n = sum(1 for t, _i in finite_ch4 if hk_start <= t <= hk_end)
                    print(
                        f"PSU CH4 current samples: {len(finite_ch4)} "
                        f"({psu_start.strftime('%H:%M:%S')} → {psu_end.strftime('%H:%M:%S')}), "
                        f"overlap with HK range: {overlap_n}"
                    )
                else:
                    print("PSU CH4 current samples: 0 finite values in selected PSU log")
            else:
                print(f"Warning: PSU log not found: {psu_log}")

        hk_field_options = list_numeric_hk_fields(all_hk)

        return {
            "valid_logs": valid_logs,
            "hk_packets": all_hk,
            "hk_field_options": hk_field_options,
            "hk_timestamps": hk_timestamps,
            "temp_data": temp_data,
            "volt_data": volt_data,
            "gaps": gaps,
            "temp_jumps": temp_jumps,
            "volt_jumps": volt_jumps,
            "error_events": error_events,
            "err_ts": err_ts,
            "err_data": err_data,
            "sci_datetimes": sci_datetimes,
            "sci_abs_steps": sci_abs_steps,
            "sci_axis_mode": sci_axis_mode,
            "swir_low": swir_low,
            "swir_med": swir_med,
            "swir_high": swir_high,
            "mwir_low": mwir_low,
            "mwir_med": mwir_med,
            "mwir_high": mwir_high,
            "packet_boundaries": packet_boundaries,
            "psu_data": psu_data,
        }

    def _pick_rs422_files(current):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        start_dir = str(current[0].parent if current else LOG_PATH.parent)
        try:
            chosen = filedialog.askopenfilenames(
                title="Select one or more RS422 logs",
                initialdir=start_dir,
                filetypes=[("Log files", "*.log *.LOG *.txt"), ("All files", "*.*")],
            )
        finally:
            root.destroy()
        return [Path(p) for p in chosen] if chosen else None

    def _pick_psu_file(current):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        start_dir = str(current.parent if current is not None else LOG_PATH.parent)
        try:
            chosen = filedialog.askopenfilename(
                title="Select PSU log",
                initialdir=start_dir,
                filetypes=[("Log files", "*.log *.LOG *.txt"), ("All files", "*.*")],
            )
        finally:
            root.destroy()
        return Path(chosen) if chosen else None

    def _show_errors_popup(_event=None):
        events_obj = state.get("error_events")
        events = events_obj if isinstance(events_obj, list) else []
        active_events = [evt for evt in events if evt[1] or evt[2] or evt[3]]

        def _save_error_events():
            if not active_events:
                messagebox.showinfo("Save error transitions", "No active error transitions to save.")
                return

            save_path = filedialog.asksaveasfilename(
                title="Save error transitions",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")],
            )
            if not save_path:
                return

            try:
                if str(save_path).lower().endswith(".txt"):
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(f"Detected active error transitions: {len(active_events)}\n\n")
                        for idx, (ts, eb, ob, mtr) in enumerate(active_events, start=1):
                            f.write(f"{idx}. Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"   EB Error Flags : {', '.join(eb) if eb else 'none'}\n")
                            f.write(f"   OB Errors      : {', '.join(ob) if ob else 'none'}\n")
                            f.write(f"   Motor Errors   : {', '.join(mtr) if mtr else 'none'}\n\n")
                else:
                    with open(save_path, "w", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["index", "timestamp", "eb_error_flags", "ob_errors", "motor_errors"])
                        for idx, (ts, eb, ob, mtr) in enumerate(active_events, start=1):
                            writer.writerow(
                                [
                                    idx,
                                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                                    "; ".join(eb),
                                    "; ".join(ob),
                                    "; ".join(mtr),
                                ]
                            )
                messagebox.showinfo("Save error transitions", f"Saved: {save_path}")
            except Exception as ex:
                messagebox.showerror("Save error transitions", f"Failed to save file:\n{ex}")

        root = getattr(tk, "_default_root", None)
        owns_root = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            owns_root = True

        win = tk.Toplevel(root)
        win.title("Detected Error Transitions")
        win.geometry("920x560")

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        text = tk.Text(frame, wrap="none", font=("Consolas", 10))
        y_scroll = tk.Scrollbar(frame, orient="vertical", command=text.yview)
        x_scroll = tk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        if not active_events:
            text.insert("end", "No active error transitions detected in the current selection.\n")
        else:
            text.insert("end", f"Detected active error transitions: {len(active_events)}\n\n")
            for idx, (ts, eb, ob, mtr) in enumerate(active_events, start=1):
                text.insert("end", f"{idx}. Timestamp: {ts.strftime('%Y-%m-%d %H:%M:%S')}\n")
                text.insert("end", f"   EB Error Flags : {', '.join(eb) if eb else 'none'}\n")
                text.insert("end", f"   OB Errors      : {', '.join(ob) if ob else 'none'}\n")
                text.insert("end", f"   Motor Errors   : {', '.join(mtr) if mtr else 'none'}\n\n")

        text.configure(state="disabled")
        button_row = tk.Frame(win)
        button_row.pack(pady=(0, 10))
        tk.Button(button_row, text="Save", command=_save_error_events).pack(side="left", padx=(0, 8))
        tk.Button(button_row, text="Close", command=win.destroy).pack(side="left")

        win.lift()
        win.attributes("-topmost", True)
        win.after(250, lambda: win.attributes("-topmost", False))

        if owns_root:

            def _close_and_cleanup():
                win.destroy()
                root.destroy()

            win.protocol("WM_DELETE_WINDOW", _close_and_cleanup)
            win.mainloop()

    def _show_plot_selector(_event=None):
        root = getattr(tk, "_default_root", None)
        owns_root = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            owns_root = True

        win = tk.Toplevel(root)
        win.title("Select Visible Plots")
        win.geometry("320x320")

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        current = state.get("panel_visibility")
        if not isinstance(current, dict):
            current = {k: True for k in PANEL_ORDER}

        vars_map = {}
        for panel in PANEL_ORDER:
            var = tk.BooleanVar(value=bool(current.get(panel, True)))
            vars_map[panel] = var
            tk.Checkbutton(frame, text=PANEL_LABELS[panel], variable=var).pack(anchor="w", pady=2)

        def _apply():
            new_vis = {k: bool(v.get()) for k, v in vars_map.items()}
            if not any(new_vis.values()):
                messagebox.showwarning("Select Visible Plots", "At least one plot must remain visible.")
                return
            state["panel_visibility"] = new_vis
            last_result = state.get("last_result")
            if isinstance(last_result, dict):
                _apply_analysis(last_result)
            win.destroy()

        btn_row = tk.Frame(win)
        btn_row.pack(pady=(0, 10))
        tk.Button(btn_row, text="Apply", command=_apply).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Close", command=win.destroy).pack(side="left")

        win.lift()
        win.attributes("-topmost", True)
        win.after(250, lambda: win.attributes("-topmost", False))

        if owns_root:

            def _close_and_cleanup():
                win.destroy()
                root.destroy()

            win.protocol("WM_DELETE_WINDOW", _close_and_cleanup)
            win.mainloop()

    def _show_parameter_selector(_event=None):
        root = getattr(tk, "_default_root", None)
        owns_root = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            owns_root = True

        win = tk.Toplevel(root)
        win.title("Select Parameters To Plot")
        win.geometry("560x620")

        outer = tk.Frame(win)
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(outer, borderwidth=0)
        y_scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=y_scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")

        current_params = state.get("selected_params")
        if not isinstance(current_params, dict):
            current_params = {k: set(v) for k, v in PARAM_OPTIONS.items()}

        vars_map = {}
        for panel in PANEL_ORDER:
            group = tk.LabelFrame(body, text=PANEL_LABELS[panel])
            group.pack(fill="x", padx=4, pady=4)
            vars_map[panel] = {}
            selected = current_params.get(panel, set(PARAM_OPTIONS[panel]))
            for param in PARAM_OPTIONS[panel]:
                var = tk.BooleanVar(value=param in selected)
                vars_map[panel][param] = var
                tk.Checkbutton(group, text=param, variable=var).pack(anchor="w", padx=6, pady=1)

        def _apply():
            new_selected = {}
            for panel in PANEL_ORDER:
                chosen = {p for p, var in vars_map[panel].items() if bool(var.get())}
                if not chosen:
                    messagebox.showwarning(
                        "Select Parameters To Plot",
                        f"At least one parameter is required for {PANEL_LABELS[panel]}.",
                    )
                    return
                new_selected[panel] = chosen
            state["selected_params"] = new_selected
            last_result = state.get("last_result")
            if isinstance(last_result, dict):
                _apply_analysis(last_result)
            win.destroy()

        btn_row = tk.Frame(win)
        btn_row.pack(pady=(6, 10))
        tk.Button(btn_row, text="Apply", command=_apply).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="New Graph", command=_open_custom_parameter_plot).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Close", command=win.destroy).pack(side="left")

        win.lift()
        win.attributes("-topmost", True)
        win.after(250, lambda: win.attributes("-topmost", False))

        if owns_root:

            def _close_and_cleanup():
                win.destroy()
                root.destroy()

            win.protocol("WM_DELETE_WINDOW", _close_and_cleanup)
            win.mainloop()

    def _open_custom_parameter_plot(_event=None):
        last_result = state.get("last_result")
        if not isinstance(last_result, dict):
            messagebox.showinfo("Add Parameter", "Load data first before adding a parameter plot.")
            return

        hk_packets = last_result.get("hk_packets")
        if not isinstance(hk_packets, list) or not hk_packets:
            messagebox.showinfo("Add Parameter", "No HK packet data available for dynamic parameter plotting.")
            return

        field_options = last_result.get("hk_field_options")
        if not isinstance(field_options, list) or not field_options:
            messagebox.showinfo("Add Parameter", "No numeric HK parameters found in the current data.")
            return

        root = getattr(tk, "_default_root", None)
        owns_root = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            owns_root = True

        win = tk.Toplevel(root)
        win.title("Add Parameter Plot")
        win.geometry("420x520")

        tk.Label(win, text="Select an HK parameter to plot in a new graph:").pack(anchor="w", padx=10, pady=(10, 4))

        search_var = tk.StringVar()
        entry = tk.Entry(win, textvariable=search_var)
        entry.pack(fill="x", padx=10, pady=(0, 8))

        list_frame = tk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        listbox = tk.Listbox(list_frame, exportselection=False)
        y_scroll = tk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=y_scroll.set)
        listbox.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")

        def _refresh_list(*_args):
            q = search_var.get().strip().lower()
            listbox.delete(0, "end")
            filtered = [name for name in field_options if q in name.lower()]
            for name in filtered:
                listbox.insert("end", name)
            if filtered:
                listbox.selection_set(0)

        search_var.trace_add("write", _refresh_list)
        _refresh_list()

        def _plot_selected():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Add Parameter", "Select a parameter first.")
                return
            field_name = listbox.get(sel[0])
            ts, vals = build_hk_field_series(hk_packets, field_name)
            finite_mask = np.isfinite(np.array(vals, dtype=float))
            if not np.any(finite_mask):
                messagebox.showwarning("Add Parameter", f"Parameter {field_name} has no numeric samples.")
                return

            custom_fields = state.get("custom_fields")
            if not isinstance(custom_fields, list):
                custom_fields = []
                state["custom_fields"] = custom_fields
            if field_name not in custom_fields:
                custom_fields.append(field_name)

            _sync_custom_axes()
            last_result = state.get("last_result")
            if isinstance(last_result, dict):
                _apply_analysis(last_result)
            win.destroy()

        btn_row = tk.Frame(win)
        btn_row.pack(pady=(0, 10))
        tk.Button(btn_row, text="Plot", command=_plot_selected).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Close", command=win.destroy).pack(side="left")

        win.lift()
        win.attributes("-topmost", True)
        win.after(250, lambda: win.attributes("-topmost", False))

        if owns_root:

            def _close_and_cleanup():
                win.destroy()
                root.destroy()

            win.protocol("WM_DELETE_WINDOW", _close_and_cleanup)
            win.mainloop()

    # Fixed layout: always include dedicated CH3 and CH4 PSU subplots.
    fig, (ax_temp, ax_volt, ax_err, ax_psu_ch3, ax_psu_ch4, ax_swir, ax_mwir) = plt.subplots(
        7, 1, figsize=(16, 21), sharex=True
    )
    fig.subplots_adjust(top=0.90, hspace=0.35)

    # Keep controls on a dedicated row below the title to avoid overlap.
    ax_btn_plots = fig.add_axes((0.11, 0.92, 0.09, 0.024))
    btn_plots = Button(ax_btn_plots, "Plots", color="lavender", hovercolor="thistle")
    ax_btn_params = fig.add_axes((0.21, 0.92, 0.09, 0.024))
    btn_params = Button(ax_btn_params, "Params", color="honeydew", hovercolor="palegreen")
    ax_btn_replay = fig.add_axes((0.31, 0.92, 0.09, 0.024))
    btn_replay = Button(ax_btn_replay, "Replay", color="aliceblue", hovercolor="lightskyblue")
    ax_btn_axis = fig.add_axes((0.41, 0.92, 0.09, 0.024))
    btn_axis = Button(ax_btn_axis, "SCI: Auto", color="honeydew", hovercolor="palegreen")
    ax_btn_errors = fig.add_axes((0.51, 0.92, 0.09, 0.024))
    btn_errors = Button(ax_btn_errors, "Errors", color="mistyrose", hovercolor="lightcoral")
    ax_btn_rs422 = fig.add_axes((0.61, 0.92, 0.09, 0.024))
    btn_rs422 = Button(ax_btn_rs422, "Open RS422", color="lightgrey", hovercolor="gainsboro")
    ax_btn_psu = fig.add_axes((0.71, 0.92, 0.09, 0.024))
    btn_psu = Button(ax_btn_psu, "Open PSU", color="lightgrey", hovercolor="gainsboro")
    ax_btn_reload = fig.add_axes((0.81, 0.92, 0.09, 0.024))
    btn_reload = Button(ax_btn_reload, "\u27f3 Reload", color="lightsteelblue", hovercolor="deepskyblue")

    state: dict[str, object] = {
        "cid": None,
        "rs422_logs": list(args.rs422_log),
        "psu_log": args.psu_log,
        "error_events": [],
        "panel_visibility": {k: True for k in PANEL_ORDER},
        "selected_params": {k: set(v) for k, v in PARAM_OPTIONS.items()},
        "last_result": None,
        "custom_fields": [],
        "custom_axes": [],
        "replay_output_dir": Path("reports") / "acq_visual_replay",
        "replay_overlay": None,
        "replay_extra_fields": [],
        "replay_cursor_time": None,
        "replay_cursor_bounds": None,
        "replay_cursor_artists": [],
        "replay_timer": None,
        "sci_axis_display_mode": None,
    }

    def _update_sci_axis_button_label():
        display_mode = state.get("sci_axis_display_mode")
        if display_mode == "abs_steps":
            btn_axis.label.set_text("SCI: Steps")
        elif display_mode == "time":
            btn_axis.label.set_text("SCI: Time")
        else:
            btn_axis.label.set_text("SCI: Auto")

    def _toggle_sci_axis_mode(_event=None):
        current_mode = state.get("sci_axis_display_mode")
        next_mode = "abs_steps" if current_mode != "abs_steps" else "time"
        state["sci_axis_display_mode"] = next_mode
        _update_sci_axis_button_label()
        last_result = state.get("last_result")
        if isinstance(last_result, dict):
            _apply_analysis(last_result)

    _update_sci_axis_button_label()

    def _stop_replay_timer():
        timer = state.get("replay_timer")
        stop_timer = getattr(timer, "stop", None)
        if callable(stop_timer):
            try:
                stop_timer()
            except Exception:
                pass
        state["replay_timer"] = None

    def _clear_replay_cursor_artists():
        artists = state.get("replay_cursor_artists")
        if isinstance(artists, list):
            for artist in artists:
                try:
                    artist.remove()
                except Exception:
                    pass
        state["replay_cursor_artists"] = []

    def _install_replay_cursor(play: bool = False):
        _stop_replay_timer()
        _clear_replay_cursor_artists()
        bounds = state.get("replay_cursor_bounds")
        cursor_time = state.get("replay_cursor_time")
        if not (isinstance(bounds, tuple) and len(bounds) == 2 and isinstance(cursor_time, datetime)):
            return

        start_time, end_time = bounds
        if cursor_time < start_time:
            cursor_time = start_time
        if cursor_time > end_time:
            cursor_time = start_time
        state["replay_cursor_time"] = cursor_time

        custom_axes = state.get("custom_axes")
        if not isinstance(custom_axes, list):
            custom_axes = []
        panel_visibility = state.get("panel_visibility")
        if not isinstance(panel_visibility, dict):
            panel_visibility = {k: True for k in PANEL_ORDER}
        visible_axes = []
        for ax, panel in (
            (ax_temp, "temp"),
            (ax_volt, "volt"),
            (ax_err, "err"),
            (ax_psu_ch3, "psu_ch3"),
            (ax_psu_ch4, "psu_ch4"),
            (ax_swir, "swir"),
            (ax_mwir, "mwir"),
        ):
            if ax is not None and panel_visibility.get(panel, True):
                visible_axes.append(ax)
        visible_axes.extend([ax for _field, ax in custom_axes if ax is not None and ax.get_visible()])

        artists = []
        for ax in visible_axes:
            artists.append(ax.axvline(cursor_time, color="#6a1b9a", linewidth=1.6, alpha=0.85))
        state["replay_cursor_artists"] = artists
        fig.canvas.draw_idle()

        if not play:
            return

        timer = fig.canvas.new_timer(interval=150)

        def _tick():
            current = state.get("replay_cursor_time")
            bounds_now = state.get("replay_cursor_bounds")
            if not (isinstance(current, datetime) and isinstance(bounds_now, tuple) and len(bounds_now) == 2):
                _stop_replay_timer()
                return
            start_now, end_now = bounds_now
            next_time = current + timedelta(seconds=2)
            if next_time > end_now:
                next_time = start_now
            state["replay_cursor_time"] = next_time
            artists_now = state.get("replay_cursor_artists")
            if isinstance(artists_now, list):
                for artist in artists_now:
                    try:
                        artist.set_xdata([next_time, next_time])
                    except Exception:
                        pass
            fig.canvas.draw_idle()

        timer.add_callback(_tick)
        timer.start()
        state["replay_timer"] = timer

    def _build_inline_replay_overlay(logs_root: Path, run_filter: str = ""):
        if acq_visual_replay is None:
            raise RuntimeError("acq_visual_replay module is not available")
        try:
            events, hk_points = acq_visual_replay._collect_events_for_root(
                logs_root,
                cmd_offset_hours=1.0,
                trigger_s=150.0,
                duration_s=3.0,
            )
        except Exception as exc:
            raise RuntimeError(f"failed to collect replay events: {exc}") from exc

        if not events:
            return None

        current_psu = state.get("psu_log")
        current_psu_name = current_psu.name if isinstance(current_psu, Path) else ""
        selected = []
        for event in events:
            if (
                run_filter
                and run_filter.lower() not in event.run.lower()
                and run_filter.lower() not in event.cmd_file.lower()
            ):
                continue
            if current_psu_name and Path(event.psu_log).name != current_psu_name:
                continue
            selected.append(event)
        if not selected:
            for event in events:
                if (
                    run_filter
                    and run_filter.lower() not in event.run.lower()
                    and run_filter.lower() not in event.cmd_file.lower()
                ):
                    continue
                selected.append(event)
        if not selected:
            return None

        selected.sort(key=lambda e: e.acq_cmd_time)
        run_start = min(e.acq_cmd_time for e in selected) - timedelta(seconds=20)
        run_end = max(e.check_end for e in selected) + timedelta(seconds=20)
        hk_run = [p for p in hk_points if run_start <= p.time <= run_end]
        state_series = ([p.time for p in hk_run], [p.state if p.state is not None else -1 for p in hk_run])
        moving_series = ([p.time for p in hk_run], [p.moving + 0.1 * p.homing_complete for p in hk_run])

        return {
            "events": [
                {
                    "acq_index": e.acq_index,
                    "acq_time": e.acq_cmd_time + timedelta(hours=1),
                    "check_start": e.check_start,
                    "check_end": e.check_end,
                    "median_ma": e.median_ma,
                    "expected_min": e.expected_min_ma,
                    "expected_max": e.expected_max_ma,
                    "resolved_states": e.resolved_states,
                    "result": e.result,
                }
                for e in selected
            ],
            "state_series": state_series,
            "moving_series": moving_series,
            "psu_ma_series": acq_visual_replay._build_psu_series(current_psu)[0::2]
            if isinstance(current_psu, Path)
            else None,
            "cursor_start": run_start,
            "cursor_end": run_end,
        }

    def _guess_replay_root() -> Path | None:
        logs = state.get("rs422_logs")
        psu_log = state.get("psu_log")
        paths: list[Path] = []
        if isinstance(logs, list):
            paths.extend([p for p in logs if isinstance(p, Path)])
        if isinstance(psu_log, Path):
            paths.append(psu_log)
        if not paths:
            return None
        try:
            common = os.path.commonpath([str((p.parent if p.is_file() else p)) for p in paths])
            return Path(common)
        except Exception:
            return paths[0].parent

    def _show_replay_suite_selector(_event=None):
        replay_root = _guess_replay_root()
        if replay_root is None or not replay_root.exists():
            messagebox.showinfo("Replay Suite", "Load data first so a replay root can be inferred.")
            return

        root = getattr(tk, "_default_root", None)
        owns_root = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            owns_root = True

        win = tk.Toplevel(root)
        win.title("Replay Suite")
        win.geometry("560x420")

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(frame, text="Replay root folder:").grid(row=0, column=0, sticky="w")
        root_var = tk.StringVar(value=str(replay_root))
        tk.Entry(frame, textvariable=root_var).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        tk.Label(frame, text="Run filter (optional):").grid(row=2, column=0, sticky="w")
        run_filter_var = tk.StringVar(value="")
        tk.Entry(frame, textvariable=run_filter_var).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        tk.Label(frame, text="Animation step (s, 0 disables):").grid(row=4, column=0, sticky="w")
        animation_var = tk.StringVar(value="2")
        tk.Entry(frame, textvariable=animation_var).grid(row=5, column=0, sticky="w", pady=(0, 12))

        checks_box = tk.LabelFrame(frame, text="Replayable Checks")
        checks_box.grid(row=6, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        include_acq_var = tk.BooleanVar(value=True)
        include_homing_var = tk.BooleanVar(value=False)
        tk.Checkbutton(checks_box, text="SCI ACQ current check", variable=include_acq_var).pack(
            anchor="w", padx=6, pady=4
        )
        tk.Checkbutton(checks_box, text="Homing complete check", variable=include_homing_var).pack(
            anchor="w", padx=6, pady=4
        )

        layers_box = tk.LabelFrame(frame, text="Replay Layers")
        layers_box.grid(row=6, column=1, sticky="nsew", pady=(0, 8))
        show_state_var = tk.BooleanVar(value=True)
        show_motor_var = tk.BooleanVar(value=True)
        show_raw_var = tk.BooleanVar(value=True)
        show_ma_var = tk.BooleanVar(value=True)
        tk.Checkbutton(layers_box, text="State changes", variable=show_state_var).pack(anchor="w", padx=6, pady=4)
        tk.Checkbutton(layers_box, text="Motor movement", variable=show_motor_var).pack(anchor="w", padx=6, pady=4)
        tk.Checkbutton(layers_box, text="PSU raw trace", variable=show_raw_var).pack(anchor="w", padx=6, pady=4)
        tk.Checkbutton(layers_box, text="PSU MA(5) trace", variable=show_ma_var).pack(anchor="w", padx=6, pady=4)
        inline_only = tk.Label(frame, text="Apply to the current matplotlib plotter, not external HTML.")
        inline_only.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 6))

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        def _browse_root():
            chosen = filedialog.askdirectory(initialdir=root_var.get() or str(replay_root), title="Select Replay Root")
            if chosen:
                root_var.set(chosen)

        def _apply_inline_replay(play: bool):
            logs_root = Path(root_var.get().strip())
            if not logs_root.exists():
                messagebox.showwarning("Replay Suite", f"Replay root does not exist:\n{logs_root}")
                return

            try:
                animation_step = float(animation_var.get().strip() or "0")
            except ValueError:
                messagebox.showwarning("Replay Suite", "Animation step must be numeric.")
                return

            try:
                overlay = _build_inline_replay_overlay(logs_root, run_filter_var.get().strip())
            except Exception as exc:
                messagebox.showerror("Replay Suite", f"Failed to build replay:\n{exc}")
                return

            if not overlay:
                messagebox.showinfo("Replay Suite", "No replay data matched the current selection.")
                return

            extra_fields = []
            if bool(show_state_var.get()):
                extra_fields.append("__REPLAY_STATE__")
            if bool(show_motor_var.get()):
                extra_fields.append("__REPLAY_MOVING__")
            state["replay_extra_fields"] = extra_fields
            state["replay_overlay"] = {
                "events": overlay["events"] if bool(include_acq_var.get()) else [],
                "state_series": overlay["state_series"],
                "moving_series": overlay["moving_series"],
                "show_psu_raw": bool(show_raw_var.get()),
                "show_psu_ma": bool(show_ma_var.get()),
                "show_state": bool(show_state_var.get()),
                "show_motor": bool(show_motor_var.get()),
                "show_homing": bool(include_homing_var.get()),
            }
            state["replay_cursor_time"] = overlay["cursor_start"]
            state["replay_cursor_bounds"] = (overlay["cursor_start"], overlay["cursor_end"])

            last_result = state.get("last_result")
            if isinstance(last_result, dict):
                _apply_analysis(last_result)
                _install_replay_cursor(play=play and animation_step > 0)
            win.destroy()

        def _clear_inline_replay():
            state["replay_overlay"] = None
            state["replay_extra_fields"] = []
            state["replay_cursor_time"] = None
            state["replay_cursor_bounds"] = None
            _stop_replay_timer()
            _clear_replay_cursor_artists()
            last_result = state.get("last_result")
            if isinstance(last_result, dict):
                _apply_analysis(last_result)

        btn_row = tk.Frame(frame)
        btn_row.grid(row=8, column=0, columnspan=2, pady=(6, 0), sticky="w")
        tk.Button(btn_row, text="Browse Root", command=_browse_root).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Apply", command=lambda: _apply_inline_replay(False)).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Apply + Play", command=lambda: _apply_inline_replay(True)).pack(
            side="left", padx=(0, 8)
        )
        tk.Button(btn_row, text="Clear Replay", command=_clear_inline_replay).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Close", command=win.destroy).pack(side="left")

        win.lift()
        win.attributes("-topmost", True)
        win.after(250, lambda: win.attributes("-topmost", False))

        if owns_root:

            def _close_and_cleanup():
                win.destroy()
                root.destroy()

            win.protocol("WM_DELETE_WINDOW", _close_and_cleanup)
            win.mainloop()

    def _sync_custom_axes():
        custom_fields = state.get("custom_fields")
        if not isinstance(custom_fields, list):
            custom_fields = []
            state["custom_fields"] = custom_fields
        replay_extra_fields = state.get("replay_extra_fields")
        if not isinstance(replay_extra_fields, list):
            replay_extra_fields = []
            state["replay_extra_fields"] = replay_extra_fields
        combined_fields = [*replay_extra_fields, *custom_fields]

        existing = state.get("custom_axes")
        if isinstance(existing, list):
            for _field, ax in existing:
                try:
                    ax.remove()
                except Exception:
                    pass

        n = len(combined_fields)
        if n == 0:
            state["custom_axes"] = []
            return

        panel_h = 0.085
        gap = 0.012
        bottom_start = 0.045
        custom_axes = []
        for i, field in enumerate(combined_fields):
            y = bottom_start + (n - 1 - i) * (panel_h + gap)
            ax = fig.add_axes((0.08, y, 0.86, panel_h), sharex=ax_mwir)
            custom_axes.append((field, ax))
        state["custom_axes"] = custom_axes

    def _apply_analysis(result):
        state["last_result"] = result
        panel_visibility = state.get("panel_visibility")
        if not isinstance(panel_visibility, dict):
            panel_visibility = {k: True for k in PANEL_ORDER}
            state["panel_visibility"] = panel_visibility
        selected_params = state.get("selected_params")
        if not isinstance(selected_params, dict):
            selected_params = {k: set(v) for k, v in PARAM_OPTIONS.items()}
            state["selected_params"] = selected_params

        display_sci_axis_mode = state.get("sci_axis_display_mode")
        if display_sci_axis_mode not in ("abs_steps", "time"):
            display_sci_axis_mode = result["sci_axis_mode"]
            state["sci_axis_display_mode"] = display_sci_axis_mode
        _update_sci_axis_button_label()

        _sync_custom_axes()
        custom_axes = state.get("custom_axes")
        if not isinstance(custom_axes, list):
            custom_axes = []

        custom_series = {}
        hk_packets = result.get("hk_packets")
        if isinstance(hk_packets, list):
            for field_name, _ax in custom_axes:
                if field_name == "__REPLAY_STATE__":
                    replay_overlay = state.get("replay_overlay")
                    if isinstance(replay_overlay, dict):
                        custom_series[field_name] = replay_overlay.get("state_series")
                elif field_name == "__REPLAY_MOVING__":
                    replay_overlay = state.get("replay_overlay")
                    if isinstance(replay_overlay, dict):
                        custom_series[field_name] = replay_overlay.get("moving_series")
                else:
                    custom_series[field_name] = build_hk_field_series(hk_packets, field_name)

        _draw_all_axes(
            ax_temp,
            ax_volt,
            ax_err,
            ax_psu_ch3,
            ax_psu_ch4,
            ax_swir,
            ax_mwir,
            fig,
            result["hk_timestamps"],
            result["temp_data"],
            result["volt_data"],
            result["gaps"],
            result["temp_jumps"],
            result["volt_jumps"],
            result["sci_datetimes"],
            result["sci_abs_steps"],
            display_sci_axis_mode,
            result["swir_low"],
            result["swir_med"],
            result["swir_high"],
            result["mwir_low"],
            result["mwir_med"],
            result["mwir_high"],
            result["packet_boundaries"],
            result["psu_data"],
            result["error_events"],
            result["err_ts"],
            result["err_data"],
            panel_visibility,
            selected_params,
            custom_axes,
            custom_series,
            state.get("replay_overlay"),
        )

        cid = state.get("cid")
        if isinstance(cid, int):
            fig.canvas.mpl_disconnect(cid)
            state["cid"] = None

        popup_events = [evt for evt in result["error_events"] if evt[1] or evt[2] or evt[3]]
        state["error_events"] = result["error_events"]

        click_axes = []
        if panel_visibility.get("temp", True):
            click_axes.append(ax_temp)
        if panel_visibility.get("volt", True):
            click_axes.append(ax_volt)
        if panel_visibility.get("err", True):
            click_axes.append(ax_err)
        if panel_visibility.get("psu_ch3", True):
            click_axes.append(ax_psu_ch3)
        if panel_visibility.get("psu_ch4", True):
            click_axes.append(ax_psu_ch4)
        if panel_visibility.get("swir", True):
            click_axes.append(ax_swir)
        if panel_visibility.get("mwir", True):
            click_axes.append(ax_mwir)
        for _field, ax_custom in custom_axes:
            click_axes.append(ax_custom)

        hdlr = ClickHandler(
            result["sci_datetimes"],
            result["sci_abs_steps"] if display_sci_axis_mode == "abs_steps" else result["sci_datetimes"],
            display_sci_axis_mode,
            result["sci_abs_steps"],
            result["swir_low"],
            result["swir_med"],
            result["swir_high"],
            result["mwir_low"],
            result["mwir_med"],
            result["mwir_high"],
            result["packet_boundaries"],
            ax_swir,
            ax_mwir,
            popup_events,
            tuple(click_axes),
        )
        state["cid"] = fig.canvas.mpl_connect("button_press_event", hdlr.on_click)
        if popup_events:
            print(
                "\nClick near red error lines for popup details, use the Errors button for full list,"
                " or click SWIR/MWIR points to inspect intensity values."
            )
        elif result["sci_datetimes"]:
            print("\nUse the Errors button for full list, or click SWIR/MWIR data points to inspect intensity values.")
        else:
            print("\nUse the Errors button for full list of detected error transitions.")

        fig.suptitle(_title_for_logs(result["valid_logs"]), fontsize=13, fontweight="bold", y=0.985)
        fig.canvas.draw_idle()
        _install_replay_cursor(play=False)

    def _reload(_event=None):
        print("\n--- Reload ---")
        logs = state.get("rs422_logs")
        if not isinstance(logs, list):
            logs = [LOG_PATH]
            state["rs422_logs"] = logs
        psu_log = state.get("psu_log")
        if psu_log is not None and not isinstance(psu_log, Path):
            psu_log = None
            state["psu_log"] = None

        result = _analyze(logs, psu_log)
        if result is None:
            return
        _apply_analysis(result)

    def _open_rs422(_event=None):
        logs = state.get("rs422_logs")
        if not isinstance(logs, list):
            logs = [LOG_PATH]
        chosen = _pick_rs422_files(logs)
        if not chosen:
            return
        state["rs422_logs"] = chosen
        print("Selected RS422 logs:")
        for p in chosen:
            print(f"  - {p}")
        _reload()

    def _open_psu(_event=None):
        current = state.get("psu_log")
        if current is not None and not isinstance(current, Path):
            current = None
        chosen = _pick_psu_file(current)
        if chosen is None:
            return
        state["psu_log"] = chosen
        print(f"Selected PSU log: {chosen}")
        _reload()

    btn_plots.on_clicked(_show_plot_selector)
    btn_params.on_clicked(_show_parameter_selector)
    btn_replay.on_clicked(_show_replay_suite_selector)
    btn_axis.on_clicked(_toggle_sci_axis_mode)
    btn_errors.on_clicked(_show_errors_popup)
    btn_rs422.on_clicked(_open_rs422)
    btn_psu.on_clicked(_open_psu)
    btn_reload.on_clicked(_reload)

    # Initial load
    _reload()

    try:
        plt.show(block=True)
    except TypeError:
        plt.show()


if __name__ == "__main__":
    main()
