#!/usr/bin/env python3
"""Plot all science data points from a log file with 500ms time spacing."""

from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta
import re
import sys

import matplotlib.pyplot as plt
import numpy as np

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utility_modules import eb_packet_utility


def extract_timestamp_from_log_line(line: str) -> datetime | None:
    """Extract timestamp from log line like '2026-05-13_09-32-28'."""
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", line)
    if match:
        year, month, day, hour, minute, second = map(int, match.groups())
        return datetime(year, month, day, hour, minute, second)
    return None


def decode_sci_packet(byte_array: bytes, tm_type_id: int) -> SimpleNamespace | None:
    """Decode science packet from byte array."""
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


def extract_sci_series(sci_data: SimpleNamespace) -> dict | None:
    """Extract series from science data packet."""
    abs_steps: list[int] = []
    swir_low: list[int] = []
    swir_med: list[int] = []
    swir_high: list[int] = []
    mwir_low: list[int] = []
    mwir_med: list[int] = []
    mwir_high: list[int] = []

    sci_points = getattr(sci_data, "SCI_POINTS", None)
    if sci_points:
        for point in sci_points:
            abs_steps.append(int(point.ABS_STEPS))
            swir_high.append(int(point.SWIR_HIGH))
            swir_med.append(int(point.SWIR_MED))
            swir_low.append(int(point.SWIR_LOW))
            mwir_high.append(int(point.MWIR_HIGH))
            mwir_med.append(int(point.MWIR_MED))
            mwir_low.append(int(point.MWIR_LOW))
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


class ClickHandler:
    """Handle clicks on the plot to show timestamps."""

    def __init__(self, time_seconds, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high, timestamps):
        self.time_seconds = np.array(time_seconds)
        self.swir_low = np.array(swir_low)
        self.swir_med = np.array(swir_med)
        self.swir_high = np.array(swir_high)
        self.mwir_low = np.array(mwir_low)
        self.mwir_med = np.array(mwir_med)
        self.mwir_high = np.array(mwir_high)
        self.timestamps = timestamps

    def on_click(self, event):
        if event.inaxes is None:
            return

        click_x = event.xdata
        click_y = event.ydata

        # Find closest point
        distances = np.abs(self.time_seconds - click_x)
        closest_idx = np.argmin(distances)

        # Determine which line was clicked
        line_name = "Unknown"
        y_value = 0

        if event.inaxes.get_title() == "SWIR":
            swir_distances = [
                np.abs(self.swir_low[closest_idx] - click_y),
                np.abs(self.swir_med[closest_idx] - click_y),
                np.abs(self.swir_high[closest_idx] - click_y),
            ]
            min_dist = min(swir_distances)
            if swir_distances[0] == min_dist:
                line_name = "SWIR_LOW"
                y_value = self.swir_low[closest_idx]
            elif swir_distances[1] == min_dist:
                line_name = "SWIR_MED"
                y_value = self.swir_med[closest_idx]
            else:
                line_name = "SWIR_HIGH"
                y_value = self.swir_high[closest_idx]
        else:  # MWIR
            mwir_distances = [
                np.abs(self.mwir_low[closest_idx] - click_y),
                np.abs(self.mwir_med[closest_idx] - click_y),
                np.abs(self.mwir_high[closest_idx] - click_y),
            ]
            min_dist = min(mwir_distances)
            if mwir_distances[0] == min_dist:
                line_name = "MWIR_LOW"
                y_value = self.mwir_low[closest_idx]
            elif mwir_distances[1] == min_dist:
                line_name = "MWIR_MED"
                y_value = self.mwir_med[closest_idx]
            else:
                line_name = "MWIR_HIGH"
                y_value = self.mwir_high[closest_idx]

        timestamp = self.timestamps[closest_idx]
        x_value = self.time_seconds[closest_idx]

        print(f"\n{'=' * 60}")
        print(f"Clicked point:")
        print(f"  Time offset: {x_value:.1f}s")
        print(f"  Timestamp: {timestamp}")
        print(f"  Channel: {line_name}")
        print(f"  Intensity: {int(y_value)}")
        print(f"{'=' * 60}")


def main():
    log_path = Path(r"D:\emc - rs\RS422if_2026-05-13_09-54-38.log")

    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = [line.strip() for line in f]

    # Find all telemetry data indices and their timestamps
    sci_packets = []
    last_timestamp = None

    for i, line in enumerate(all_lines):
        if extract_timestamp_from_log_line(line):
            last_timestamp = extract_timestamp_from_log_line(line)

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

            sci_data = decode_sci_packet(byte_array, tm_type_id)
            if sci_data is None:
                continue

            series = extract_sci_series(sci_data)
            if series is None:
                continue

            sci_packets.append(
                {
                    "timestamp": last_timestamp,
                    "tm_type_id": tm_type_id,
                    "series": series,
                }
            )

    if len(sci_packets) == 0:
        print("No science packets found")
        return

    print(f"Total science packets found: {len(sci_packets)}")

    # Combine all packets
    all_swir_low = []
    all_swir_med = []
    all_swir_high = []
    all_mwir_low = []
    all_mwir_med = []
    all_mwir_high = []
    all_abs_steps = []
    all_time_seconds = []
    all_timestamps = []  # Store timestamps for each point

    # Start from first packet timestamp
    start_timestamp = sci_packets[0]["timestamp"]
    print(f"Start timestamp: {start_timestamp}")
    print(f"End timestamp: {sci_packets[-1]['timestamp']}")

    current_time = start_timestamp

    for packet_idx, packet in enumerate(sci_packets):
        series = packet["series"]
        num_points = len(series["abs_steps"])

        print(f"Packet {packet_idx + 1}: {num_points} data points, timestamp: {packet['timestamp']}")

        for i in range(num_points):
            all_abs_steps.append(series["abs_steps"][i])
            all_swir_low.append(series["swir_low"][i])
            all_swir_med.append(series["swir_med"][i])
            all_swir_high.append(series["swir_high"][i])
            all_mwir_low.append(series["mwir_low"][i])
            all_mwir_med.append(series["mwir_med"][i])
            all_mwir_high.append(series["mwir_high"][i])

            time_offset = (current_time - start_timestamp).total_seconds()
            all_time_seconds.append(time_offset)
            all_timestamps.append(current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])

            current_time += timedelta(milliseconds=500)

    total_points = len(all_abs_steps)
    total_duration = all_time_seconds[-1]
    print(f"\nTotal data points: {total_points}")
    print(f"Total duration: {total_duration:.1f} seconds ({total_duration / 60:.1f} minutes)")

    # Add timestamp information to be displayed
    first_timestamp_str = start_timestamp.strftime("%Y-%m-%d %H:%M:%S.000")
    last_time = start_timestamp + timedelta(seconds=all_time_seconds[-1])
    last_timestamp_str = last_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    timestamp_info = f"First: {first_timestamp_str}\nLast: {last_timestamp_str}\nDuration: {total_duration:.1f}s\nPoints: {total_points}"

    # Create plots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9))

    # Add starting timestamp information
    fig.suptitle(
        f"All Science Data Points - {log_path.stem}\n500ms spacing between data points", fontsize=12, fontweight="bold"
    )

    # SWIR plot
    ax1.scatter(all_time_seconds, all_swir_low, s=2, label="SWIR_LOW", alpha=0.7)
    ax1.plot(all_time_seconds, all_swir_low, linewidth=0.3, alpha=0.5)
    ax1.scatter(all_time_seconds, all_swir_med, s=2, label="SWIR_MED", alpha=0.7)
    ax1.plot(all_time_seconds, all_swir_med, linewidth=0.3, alpha=0.5)
    ax1.scatter(all_time_seconds, all_swir_high, s=2, label="SWIR_HIGH", alpha=0.7)
    ax1.plot(all_time_seconds, all_swir_high, linewidth=0.3, alpha=0.5)
    ax1.set_xlabel("Seconds since start")
    ax1.set_ylabel("Intensity")
    ax1.set_title("SWIR")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # MWIR plot
    ax2.scatter(all_time_seconds, all_mwir_low, s=2, label="MWIR_LOW", alpha=0.7)
    ax2.plot(all_time_seconds, all_mwir_low, linewidth=0.3, alpha=0.5)
    ax2.scatter(all_time_seconds, all_mwir_med, s=2, label="MWIR_MED", alpha=0.7)
    ax2.plot(all_time_seconds, all_mwir_med, linewidth=0.3, alpha=0.5)
    ax2.scatter(all_time_seconds, all_mwir_high, s=2, label="MWIR_HIGH", alpha=0.7)
    ax2.plot(all_time_seconds, all_mwir_high, linewidth=0.3, alpha=0.5)
    ax2.set_xlabel("Seconds since start")
    ax2.set_ylabel("Intensity")
    ax2.set_title("MWIR")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Add timestamp information box
    ax2.text(
        0.98,
        0.05,
        timestamp_info,
        transform=ax2.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        horizontalalignment="right",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        family="monospace",
    )

    plt.tight_layout()
    plt.savefig("sci_plot_all_packets.png", dpi=100, bbox_inches="tight")
    print("\nPlot saved to: sci_plot_all_packets.png")

    # Connect click handler
    handler = ClickHandler(
        all_time_seconds,
        all_swir_low,
        all_swir_med,
        all_swir_high,
        all_mwir_low,
        all_mwir_med,
        all_mwir_high,
        all_timestamps,
    )
    fig.canvas.mpl_connect("button_press_event", handler.on_click)

    print("\nClick on data points to see their timestamps!")
    plt.show()


if __name__ == "__main__":
    main()
