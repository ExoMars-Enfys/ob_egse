#!/usr/bin/env python3
"""
Plot housekeeping temperature and voltage data within a time range.
Displays OB and EB temperatures and voltages on dual subplots.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
import re

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.dates as mdates

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utility_modules.eb_packet_utility import parse_eb_hk, decode_eb_trps, adu_to_temp as decode_ob_trps


def parse_timestamp_from_log(timestamp_str):
    """Parse timestamp string in format YYYY-mm-dd_HH-MM-SS"""
    try:
        return datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
    except:
        return None


def extract_hk_packets(log_path, start_time=None, end_time=None):
    """Extract HK packets from log file, optionally filtering by time range."""
    hk_packets = []

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f]
    except Exception as e:
        print(f"Error reading log file: {e}")
        return hk_packets

    # Find all telemetry data lines
    tm_indices = [i for (i, line) in enumerate(lines) if "Telemetry Data:" in line]

    if not tm_indices:
        print("No telemetry data found in log file")
        return hk_packets

    print(f"Found {len(tm_indices)} telemetry packets in log")

    last_timestamp = None
    first_timestamp_date = None

    for tm_index in tm_indices:
        if tm_index + 1 >= len(lines):
            continue

        byte_string = lines[tm_index + 1]
        if not byte_string:
            continue

        try:
            byte_array = bytes(int(x, 16) for x in byte_string.split())
            tm_type_id = (byte_array[5] >> 2) & 0x3F

            # Extract HK packets (type 0x1 or 0x2)
            if tm_type_id not in (0x1, 0x2):
                continue

            # Parse timestamp from log lines
            packet_timestamp = None
            for search_offset in range(max(0, tm_index - 5), tm_index):
                line = lines[search_offset]
                # Look for timestamp pattern: YYYY-mm-dd_HH-MM-SS
                match = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", line)
                if match:
                    try:
                        packet_timestamp = datetime(
                            int(match.group(1)),
                            int(match.group(2)),
                            int(match.group(3)),
                            int(match.group(4)),
                            int(match.group(5)),
                            int(match.group(6)),
                        )
                        first_timestamp_date = packet_timestamp.date()
                        last_timestamp = packet_timestamp
                        break
                    except:
                        pass

            if packet_timestamp is None and last_timestamp is not None:
                packet_timestamp = last_timestamp + timedelta(seconds=0.1)
                last_timestamp = packet_timestamp
            elif packet_timestamp is None:
                continue

            # Filter by time range if specified
            if start_time is not None and end_time is not None:
                if not (start_time <= packet_timestamp <= end_time):
                    continue

            # Parse HK packet
            hk = parse_eb_hk(byte_array)
            hk.TIME = packet_timestamp
            hk_packets.append(hk)

        except Exception as e:
            continue

    return hk_packets


def extract_temperatures(hk):
    """Extract all temperature values from HK packet."""
    temps = {}

    try:
        # OB temperatures (thermistors)
        temps["OB_DIGITAL"] = decode_ob_trps(hk.OB_DIGITAL_TRP)
        temps["OB_DETECTOR"] = decode_ob_trps(hk.OB_DETECTOR_TRP)
        temps["OB_MECHANISM"] = decode_ob_trps(hk.OB_MECHANISM_TRP)
        temps["OB_MOTOR"] = decode_ob_trps(hk.OB_MOTOR_TRP)

        # EB temperatures
        temps["EB_MCU"] = hk.EB_MCU_INTERNAL_TEMP * 0.01637198 - 273.0
        temps["EB_PSU_BOARD"] = decode_eb_trps(hk.EB_PSU_BOARD_TEMP)
        temps["EB_INTERNAL_TRP"] = decode_eb_trps(hk.EB_INTERNAL_TRP_TEMP)

        # Peltier temperature if available
        try:
            temps["EB_PELTIER"] = hk.EB_PELTIER_TEMP * -0.001830011 + 51.27039922
        except:
            pass

    except Exception as e:
        print(f"Error extracting temperatures: {e}")

    return temps


def extract_voltages(hk):
    """Extract all voltage values from HK packet."""
    volts = {}

    try:
        # EB voltages
        volts["EB_12V"] = hk.EB_MEAS_MAIN_12V * 0.000400543
        volts["EB_NEG12V"] = abs(hk.EB_MEAS_MAIN_NEG12V * -0.00038147)
        volts["EB_5V"] = hk.EB_MEAS_5V * 0.000152829
        volts["EB_3V3"] = hk.EB_MEAS_3V3 * 0.0000763

        # TEC rail if available
        try:
            volts["EB_TEC_RAIL"] = hk.EB_MEAS_TEC_RAIL * 0.0000763
        except:
            pass

        # OB voltages
        volts["OB_3V3"] = (hk.OB_3V3_VOLTAGE * 2) / 1000.0
        volts["OB_1V5"] = hk.OB_1V5_VOLTAGE / 1000.0

    except Exception as e:
        print(f"Error extracting voltages: {e}")

    return volts


def plot_hk_data(hk_packets):
    """Plot HK temperatures and voltages."""

    if not hk_packets:
        print("No HK packets found in time range")
        return

    # Extract data from packets
    timestamps = [hk.TIME for hk in hk_packets]
    times_sec = [(t - timestamps[0]).total_seconds() for t in timestamps]
    start_time = timestamps[0]
    end_time = timestamps[-1]

    # Calculate inter-packet delays
    delays = []
    for i in range(1, len(timestamps)):
        delay = (timestamps[i] - timestamps[i - 1]).total_seconds()
        delays.append(delay)

    if delays:
        avg_delay = np.mean(delays)
        min_delay = np.min(delays)
        max_delay = np.max(delays)
        print(f"\nPacket timing statistics:")
        print(f"  Average delay between packets: {avg_delay:.3f} seconds ({avg_delay * 1000:.1f} ms)")
        print(f"  Min delay: {min_delay:.3f} seconds ({min_delay * 1000:.1f} ms)")
        print(f"  Max delay: {max_delay:.3f} seconds ({max_delay * 1000:.1f} ms)")
        print(f"  Total packets: {len(hk_packets)}\n")

    # Collect temperature and voltage data
    temp_data = {
        name: []
        for name in [
            "OB_DIGITAL",
            "OB_DETECTOR",
            "OB_MECHANISM",
            "OB_MOTOR",
            "EB_MCU",
            "EB_PSU_BOARD",
            "EB_INTERNAL_TRP",
            "EB_PELTIER",
        ]
    }
    volt_data = {name: [] for name in ["EB_12V", "EB_NEG12V", "EB_5V", "EB_3V3", "EB_TEC_RAIL", "OB_3V3", "OB_1V5"]}

    for hk in hk_packets:
        temps = extract_temperatures(hk)
        volts = extract_voltages(hk)

        for key in temp_data:
            temp_data[key].append(temps.get(key, np.nan))

        for key in volt_data:
            volt_data[key].append(volts.get(key, np.nan))

    # Create figure with two subplots
    fig, (ax_temp, ax_volt) = plt.subplots(2, 1, figsize=(14, 10))

    # Plot temperatures
    print(f"Plotting {len(hk_packets)} HK packets (time span: {times_sec[-1]:.1f} seconds)")

    # Temperature subplot
    ax_temp.plot(timestamps, temp_data["OB_DIGITAL"], "o-", label="OB Digital", markersize=4)
    ax_temp.plot(timestamps, temp_data["OB_DETECTOR"], "s-", label="OB Detector", markersize=4)
    ax_temp.plot(timestamps, temp_data["OB_MECHANISM"], "^-", label="OB Mechanism", markersize=4)
    ax_temp.plot(timestamps, temp_data["OB_MOTOR"], "v-", label="OB Motor", markersize=4)
    ax_temp.plot(timestamps, temp_data["EB_MCU"], "D-", label="EB MCU", markersize=4)
    ax_temp.plot(timestamps, temp_data["EB_PSU_BOARD"], "p-", label="EB PSU Board", markersize=4)
    ax_temp.plot(timestamps, temp_data["EB_INTERNAL_TRP"], "H-", label="EB Internal TRP", markersize=4)

    if any(not np.isnan(v) for v in temp_data["EB_PELTIER"]):
        ax_temp.plot(timestamps, temp_data["EB_PELTIER"], "*-", label="EB Peltier", markersize=8)

    ax_temp.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax_temp.xaxis.set_major_locator(mdates.AutoDateLocator())

    ax_temp.set_xlabel("Time (HH:MM:SS)")
    ax_temp.set_ylabel("Temperature (°C)")
    ax_temp.set_title(
        f"Housekeeping Temperatures ({start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')})"
    )
    ax_temp.legend(loc="best", fontsize=8)
    ax_temp.grid(True, alpha=0.3)

    # Voltage subplot
    ax_volt.plot(timestamps, volt_data["EB_12V"], "o-", label="EB +12V", markersize=4)
    ax_volt.plot(timestamps, volt_data["EB_NEG12V"], "s-", label="EB -12V", markersize=4)
    ax_volt.plot(timestamps, volt_data["EB_5V"], "^-", label="EB 5V", markersize=4)
    ax_volt.plot(timestamps, volt_data["EB_3V3"], "v-", label="EB 3.3V", markersize=4)

    if any(not np.isnan(v) for v in volt_data["EB_TEC_RAIL"]):
        ax_volt.plot(timestamps, volt_data["EB_TEC_RAIL"], "D-", label="EB TEC Rail", markersize=4)

    ax_volt.plot(timestamps, volt_data["OB_3V3"], "p-", label="OB 3.3V", markersize=4)
    ax_volt.plot(timestamps, volt_data["OB_1V5"], "H-", label="OB 1.5V", markersize=4)

    ax_volt.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax_volt.xaxis.set_major_locator(mdates.AutoDateLocator())

    ax_volt.set_xlabel("Time (HH:MM:SS)")
    ax_volt.set_ylabel("Voltage (V)")
    ax_volt.set_title("Housekeeping Voltages")
    ax_volt.legend(loc="best", fontsize=8)
    ax_volt.grid(True, alpha=0.3)

    # Apply date formatting to both axes
    fig.autofmt_xdate(rotation=45, ha="right")

    # Adjust layout to accommodate rotated labels
    fig.subplots_adjust(bottom=0.15)

    output_file = "hk_temps_volts.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"Saved plot to: {output_file}")

    plt.show()


def main():
    # Log file path (same as plot_sci_combined.py uses)
    log_path = Path(r"D:/emc - rs/RS422if_2026-05-14_09-10-54.log")

    print(f"Reading log file: {log_path}")
    print(f"Processing entire log file...")

    if not log_path.exists():
        print(f"Error: Log file not found at {log_path}")
        return

    # Extract all HK packets from entire log file
    hk_packets = extract_hk_packets(log_path)

    if not hk_packets:
        print("No HK packets found in time range")
        return

    print(f"Found {len(hk_packets)} HK packets in time range")

    # Plot data
    plot_hk_data(hk_packets)


if __name__ == "__main__":
    main()
