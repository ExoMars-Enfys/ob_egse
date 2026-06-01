#!/usr/bin/env python3
"""
Combined analysis: HK temperatures, HK voltages, SWIR, and MWIR
on a single shared datetime x-axis.  Zooming any subplot updates all others.
"""

import sys
import re
from pathlib import Path
from datetime import datetime, timedelta

# Ensure Unicode characters (e.g. box-drawing) survive PowerShell piping
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import matplotlib as mpl

try:
    mpl.use("TkAgg")
except Exception:
    # Fall back to default if TkAgg is not available in this environment
    pass
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button

sys.path.insert(0, str(Path(__file__).parent.parent))

from utility_modules import eb_packet_utility
from utility_modules.eb_packet_utility import parse_eb_hk, decode_eb_trps, adu_to_temp

LOG_PATH = Path(
    r"C:\Users\GK\OneDrive - University College London\General - Enfys - Shared\Test\EMC\Logs\2nd Week\RS422if_2026-05-13_13-23-35.log"
)


# ── HK extraction ─────────────────────────────────────────────────────────────


def extract_hk_packets(log_path):
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
                match = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", lines[search_offset])
                if match:
                    try:
                        packet_timestamp = datetime(*map(int, match.groups()))
                        last_timestamp = packet_timestamp
                        break
                    except Exception:
                        pass

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


def extract_acq_configs_tcs(log_path):
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
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", line)
        if m:
            last_timestamp = datetime(*map(int, m.groups()))

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
            m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", lines[i + 2])
            if m2:
                ts = datetime(*map(int, m2.groups()))
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


def extract_sci_packets(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = [line.strip() for line in f]

    sci_packets = []
    last_timestamp = None
    for i, line in enumerate(all_lines):
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", line)
        if match:
            last_timestamp = datetime(*map(int, match.groups()))
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
    swir_low, swir_med, swir_high = [], [], []
    mwir_low, mwir_med, mwir_high = [], [], []
    packet_boundaries = []
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

        for i in range(num_points):
            offset_ms = (num_points - 1 - i) * spacing_ms
            sci_datetimes.append(packet_timestamp - timedelta(milliseconds=offset_ms))

        end_idx = len(sci_datetimes) - 1
        packet_boundaries.append((start_idx, end_idx, packet_num, packet_timestamp))

    return sci_datetimes, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high, packet_boundaries


# ── Click handler ─────────────────────────────────────────────────────────────


class ClickHandler:
    def __init__(
        self,
        sci_datetimes,
        swir_low,
        swir_med,
        swir_high,
        mwir_low,
        mwir_med,
        mwir_high,
        packet_boundaries,
        ax_swir,
        ax_mwir,
    ):
        # Convert datetimes to matplotlib float for fast nearest-point lookup
        self.sci_dates_num = mdates.date2num(sci_datetimes)
        self.swir_low = np.array(swir_low)
        self.swir_med = np.array(swir_med)
        self.swir_high = np.array(swir_high)
        self.mwir_low = np.array(mwir_low)
        self.mwir_med = np.array(mwir_med)
        self.mwir_high = np.array(mwir_high)
        self.packet_boundaries = packet_boundaries
        self.ax_swir = ax_swir
        self.ax_mwir = ax_mwir

    def on_click(self, event):
        if event.inaxes not in (self.ax_swir, self.ax_mwir) or event.xdata is None:
            return

        idx = int(np.argmin(np.abs(self.sci_dates_num - event.xdata)))
        click_y = event.ydata

        # Which packet?
        packet_info = "Unknown packet"
        for start_idx, end_idx, packet_num, ts in self.packet_boundaries:
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
        ts_str = mdates.num2date(self.sci_dates_num[idx]).strftime("%H:%M:%S.%f")[:-3]

        print(f"\n{'=' * 60}")
        print(f"  {packet_info}")
        print(f"  Time:      {ts_str}")
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
    fracs = sorted(jumps_by_frac.keys())  # ascending: 2.5% before 5%
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
        print(f"  (none)")
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
    print(f"\nError flag transitions (EB error flags / OB errors / MTR errors):")
    _print_error_states_section(error_events or [])
    print(f"{'─' * 60}\n")


# ── Drawing helper ───────────────────────────────────────────────────────────


def _draw_all_axes(
    ax_temp,
    ax_volt,
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
    swir_low,
    swir_med,
    swir_high,
    mwir_low,
    mwir_med,
    mwir_high,
    packet_boundaries,
):
    """Clear and redraw all four subplots in-place."""
    for ax in (ax_temp, ax_volt, ax_swir, ax_mwir):
        ax.cla()

    # Temperatures
    ax_temp.plot(hk_timestamps, temp_data["OB_DIGITAL"], "o-", label="OB Digital", markersize=3)
    ax_temp.plot(hk_timestamps, temp_data["OB_DETECTOR"], "s-", label="OB Detector", markersize=3)
    ax_temp.plot(hk_timestamps, temp_data["OB_MECHANISM"], "^-", label="OB Mechanism", markersize=3)
    ax_temp.plot(hk_timestamps, temp_data["OB_MOTOR"], "v-", label="OB Motor", markersize=3)
    ax_temp.plot(hk_timestamps, temp_data["EB_MCU"], "D-", label="EB MCU", markersize=3)
    ax_temp.plot(hk_timestamps, temp_data["EB_PSU_BOARD"], "p-", label="EB PSU Board", markersize=3)
    ax_temp.plot(hk_timestamps, temp_data["EB_INTERNAL_TRP"], "H-", label="EB Int. TRP", markersize=3)
    if any(not np.isnan(v) for v in temp_data["EB_PELTIER"]):
        ax_temp.plot(hk_timestamps, temp_data["EB_PELTIER"], "*-", label="EB Peltier", markersize=6)
    ax_temp.set_ylabel("Temperature (°C)")
    ax_temp.set_title("Temperatures")
    ax_temp.legend(loc="best", fontsize=7)
    ax_temp.grid(True, alpha=0.3)
    for t_start, t_end, _ in gaps:
        ax_temp.axvspan(t_start, t_end, color="red", alpha=0.15, zorder=0)
    for frac in sorted(temp_jumps.keys()):
        colour, sz = _JUMP_COLOURS[frac]
        for ch, entries in temp_jumps[frac].items():
            ax_temp.scatter(
                [e[0] for e in entries],
                [e[1] for e in entries],
                marker="x",
                color=colour,
                s=sz,
                linewidths=1.5,
                zorder=5,
            )

    # Voltages
    ax_volt.plot(hk_timestamps, volt_data["EB_12V"], "o-", label="EB +12V", markersize=3)
    ax_volt.plot(hk_timestamps, volt_data["EB_NEG12V"], "s-", label="EB -12V", markersize=3)
    ax_volt.plot(hk_timestamps, volt_data["EB_5V"], "^-", label="EB 5V", markersize=3)
    ax_volt.plot(hk_timestamps, volt_data["EB_3V3"], "v-", label="EB 3.3V", markersize=3)
    if any(not np.isnan(v) for v in volt_data["EB_TEC_RAIL"]):
        ax_volt.plot(hk_timestamps, volt_data["EB_TEC_RAIL"], "D-", label="EB TEC Rail", markersize=3)
    ax_volt.plot(hk_timestamps, volt_data["OB_3V3"], "p-", label="OB 3.3V", markersize=3)
    ax_volt.plot(hk_timestamps, volt_data["OB_1V5"], "H-", label="OB 1.5V", markersize=3)
    ax_volt.set_ylabel("Voltage (V)")
    ax_volt.set_title("Voltages")
    ax_volt.legend(loc="best", fontsize=7)
    ax_volt.grid(True, alpha=0.3)
    for t_start, t_end, _ in gaps:
        ax_volt.axvspan(t_start, t_end, color="red", alpha=0.15, zorder=0)
    for frac in sorted(volt_jumps.keys()):
        colour, sz = _JUMP_COLOURS[frac]
        for ch, entries in volt_jumps[frac].items():
            ax_volt.scatter(
                [e[0] for e in entries],
                [e[1] for e in entries],
                marker="x",
                color=colour,
                s=sz,
                linewidths=1.5,
                zorder=5,
            )

    # SWIR
    if sci_datetimes:
        ax_swir.scatter(sci_datetimes, swir_low, s=2, label="SWIR_LOW", alpha=0.6)
        ax_swir.plot(sci_datetimes, swir_low, linewidth=0.3, alpha=0.4)
        ax_swir.scatter(sci_datetimes, swir_med, s=2, label="SWIR_MED", alpha=0.6)
        ax_swir.plot(sci_datetimes, swir_med, linewidth=0.3, alpha=0.4)
        ax_swir.scatter(sci_datetimes, swir_high, s=2, label="SWIR_HIGH", alpha=0.6)
        ax_swir.plot(sci_datetimes, swir_high, linewidth=0.3, alpha=0.4)
        for start_idx, _end, packet_num, _ts in packet_boundaries:
            ax_swir.axvline(x=sci_datetimes[start_idx], color="red", linestyle="--", linewidth=1, alpha=0.5)
            ax_swir.text(
                sci_datetimes[start_idx],
                0.95,
                f"{packet_num}",
                transform=ax_swir.get_xaxis_transform(),
                rotation=90,
                va="top",
                ha="right",
                fontsize=8,
                color="red",
                alpha=0.7,
            )
    ax_swir.set_ylabel("Intensity")
    ax_swir.set_title("SWIR")
    ax_swir.legend(loc="upper right", fontsize=7)
    ax_swir.grid(True, alpha=0.3)

    # MWIR
    if sci_datetimes:
        ax_mwir.scatter(sci_datetimes, mwir_low, s=2, label="MWIR_LOW", alpha=0.6)
        ax_mwir.plot(sci_datetimes, mwir_low, linewidth=0.3, alpha=0.4)
        ax_mwir.scatter(sci_datetimes, mwir_med, s=2, label="MWIR_MED", alpha=0.6)
        ax_mwir.plot(sci_datetimes, mwir_med, linewidth=0.3, alpha=0.4)
        ax_mwir.scatter(sci_datetimes, mwir_high, s=2, label="MWIR_HIGH", alpha=0.6)
        ax_mwir.plot(sci_datetimes, mwir_high, linewidth=0.3, alpha=0.4)
        for start_idx, _end, packet_num, _ts in packet_boundaries:
            ax_mwir.axvline(x=sci_datetimes[start_idx], color="red", linestyle="--", linewidth=1, alpha=0.5)
            ax_mwir.text(
                sci_datetimes[start_idx],
                0.95,
                f"{packet_num}",
                transform=ax_mwir.get_xaxis_transform(),
                rotation=90,
                va="top",
                ha="right",
                fontsize=8,
                color="red",
                alpha=0.7,
            )
    ax_mwir.set_ylabel("Intensity")
    ax_mwir.set_title("MWIR")
    ax_mwir.legend(loc="upper right", fontsize=7)
    ax_mwir.grid(True, alpha=0.3)

    # x-axis formatting (shared axis — only bottom subplot needs the label)
    ax_mwir.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax_mwir.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax_mwir.set_xlabel("Time (HH:MM:SS)")
    fig.autofmt_xdate(rotation=45, ha="right")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    print(f"Reading: {LOG_PATH}")
    if not LOG_PATH.exists():
        print(f"Error: file not found: {LOG_PATH}")
        return

    # ── Initial load ──────────────────────────────────────────────────────────
    hk_packets = extract_hk_packets(LOG_PATH)
    print(f"HK packets: {len(hk_packets)}")
    hk_timestamps, temp_data, volt_data = build_hk_arrays(hk_packets)
    gaps, temp_jumps, volt_jumps = detect_hk_anomalies(hk_timestamps, temp_data, volt_data)
    error_events = detect_error_states(hk_packets)
    print_anomaly_summary(gaps, temp_jumps, volt_jumps, error_events)

    acq_configs = extract_acq_configs_tcs(LOG_PATH)
    if acq_configs:
        print(f"set_acq_configs TCs ({len(acq_configs)}):")
        for cfg in acq_configs:
            mode_name = "fixed-point" if cfg["mode"] == 0x01 else "spectrum"
            print(
                f"  {cfg['timestamp'].strftime('%H:%M:%S')}  Mode={cfg['mode']} ({mode_name}),"
                f" SampleTime={cfg['sample_time_raw']} ({cfg['spacing_ms']:.0f}ms),"
                f" Duration={cfg['duration_raw']}"
            )

    sci_packets = extract_sci_packets(LOG_PATH)
    print(f"Science packets: {len(sci_packets)}")
    (sci_datetimes, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high, packet_boundaries) = build_sci_arrays(
        sci_packets, acq_configs
    )

    acq_windows = extract_acq_windows(hk_packets)
    if acq_windows:
        print(f"Acquisition windows ({len(acq_windows)}):")
        for ws, we in acq_windows:
            print(f"  {ws.strftime('%H:%M:%S')} → {we.strftime('%H:%M:%S')}")
    else:
        print("No acquisition windows found in HK — showing all science data")
    (swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high) = filter_sci_to_acq_windows(
        sci_datetimes, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high, acq_windows
    )

    # ── Figure: 4 subplots, all sharing the same datetime x-axis ─────────────
    fig, (ax_temp, ax_volt, ax_swir, ax_mwir) = plt.subplots(4, 1, figsize=(16, 14), sharex=True)
    fig.suptitle(f"Combined Analysis — {LOG_PATH.name}", fontsize=13, fontweight="bold")
    fig.subplots_adjust(top=0.93, hspace=0.35)

    # ── Reload button ─────────────────────────────────────────────────────────
    ax_btn = fig.add_axes([0.88, 0.955, 0.09, 0.028])
    btn_reload = Button(ax_btn, "\u27f3 Reload", color="lightsteelblue", hovercolor="deepskyblue")

    # Mutable state so the closure can track and disconnect the click handler
    state = {"cid": None}

    def _reload(_event=None):
        print(f"\n--- Reload ---")
        print(f"Reading: {LOG_PATH}")

        hk_pkts = extract_hk_packets(LOG_PATH)
        print(f"HK packets: {len(hk_pkts)}")
        ts, td, vd = build_hk_arrays(hk_pkts)
        g, tj, vj = detect_hk_anomalies(ts, td, vd)
        err_evts = detect_error_states(hk_pkts)
        print_anomaly_summary(g, tj, vj, err_evts)

        acq_cfgs = extract_acq_configs_tcs(LOG_PATH)
        if acq_cfgs:
            print(f"set_acq_configs TCs ({len(acq_cfgs)}):")
            for cfg in acq_cfgs:
                mode_name = "fixed-point" if cfg["mode"] == 0x01 else "spectrum"
                print(
                    f"  {cfg['timestamp'].strftime('%H:%M:%S')}  Mode={cfg['mode']} ({mode_name}),"
                    f" SampleTime={cfg['sample_time_raw']} ({cfg['spacing_ms']:.0f}ms),"
                    f" Duration={cfg['duration_raw']}"
                )

        sp = extract_sci_packets(LOG_PATH)
        print(f"Science packets: {len(sp)}")
        sd, sl, sm, sh, ml, mm, mh, pb = build_sci_arrays(sp, acq_cfgs)

        acq_wins = extract_acq_windows(hk_pkts)
        if acq_wins:
            print(f"Acquisition windows ({len(acq_wins)}):")
            for ws, we in acq_wins:
                print(f"  {ws.strftime('%H:%M:%S')} → {we.strftime('%H:%M:%S')}")
        else:
            print("No acquisition windows found in HK — showing all science data")
        sl, sm, sh, ml, mm, mh = filter_sci_to_acq_windows(sd, sl, sm, sh, ml, mm, mh, acq_wins)

        _draw_all_axes(ax_temp, ax_volt, ax_swir, ax_mwir, fig, ts, td, vd, g, tj, vj, sd, sl, sm, sh, ml, mm, mh, pb)

        if state["cid"] is not None:
            fig.canvas.mpl_disconnect(state["cid"])
            state["cid"] = None
        if sd:
            hdlr = ClickHandler(sd, sl, sm, sh, ml, mm, mh, pb, ax_swir, ax_mwir)
            state["cid"] = fig.canvas.mpl_connect("button_press_event", hdlr.on_click)
            print("\nClick on SWIR/MWIR data points to inspect intensity values.")

        fig.canvas.draw_idle()

    btn_reload.on_clicked(_reload)

    # ── Initial draw ──────────────────────────────────────────────────────────
    _draw_all_axes(
        ax_temp,
        ax_volt,
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
        swir_low,
        swir_med,
        swir_high,
        mwir_low,
        mwir_med,
        mwir_high,
        packet_boundaries,
    )

    if sci_datetimes:
        handler = ClickHandler(
            sci_datetimes,
            swir_low,
            swir_med,
            swir_high,
            mwir_low,
            mwir_med,
            mwir_high,
            packet_boundaries,
            ax_swir,
            ax_mwir,
        )
        state["cid"] = fig.canvas.mpl_connect("button_press_event", handler.on_click)
        print("\nClick on SWIR/MWIR data points to inspect intensity values.")

    try:
        plt.show(block=True)
    except TypeError:
        # Older matplotlib versions may not accept block kwarg
        plt.show()


if __name__ == "__main__":
    main()
