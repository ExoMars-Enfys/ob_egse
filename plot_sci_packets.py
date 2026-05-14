#!/usr/bin/env python3
"""Plot each science packet on separate graphs with backwards timestamp calculation."""

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
    log_path = Path(r"D:\emc - rs\RS422if_2026-05-13_12-13-54.log")

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

    print(f"Total science packets found: {len(sci_packets)}\n")

    # Plot each packet
    for packet_idx, packet in enumerate(sci_packets):
        packet_num = packet_idx + 1
        packet_timestamp = packet["timestamp"]
        series = packet["series"]
        num_points = len(series["abs_steps"])
        packet_type = ["dump", "critical", "noncritical"][[0x4, 0x5, 0x6].index(packet["tm_type_id"])]

        # Calculate spacing based on time between this packet and previous packet
        if packet_idx > 0:
            prev_packet_timestamp = sci_packets[packet_idx - 1]["timestamp"]
            time_diff = (packet_timestamp - prev_packet_timestamp).total_seconds()
            spacing_ms = (time_diff * 1000) / (num_points - 1) if num_points > 1 else 260
        else:
            # For first packet, use previous approach or estimate
            spacing_ms = 260

        print(
            f"Packet {packet_num}/{len(sci_packets)}: {num_points} points, "
            f"timestamp: {packet_timestamp}, type: {packet_type}, spacing: {spacing_ms:.1f}ms"
        )

        # Calculate timestamps working backwards from packet received time
        timestamps = []
        time_seconds = []

        for i in range(num_points):
            # Work backwards: point 0 is oldest, point (num_points-1) is newest (at packet_timestamp)
            offset_ms = (num_points - 1 - i) * spacing_ms  # milliseconds from the last point
            point_time = packet_timestamp - timedelta(milliseconds=offset_ms)
            timestamps.append(point_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            time_seconds.append(offset_ms / 1000.0)

        # Convert time_seconds to go forward from oldest (0) to newest
        time_seconds = [max(time_seconds) - t for t in time_seconds]

        swir_low = series["swir_low"]
        swir_med = series["swir_med"]
        swir_high = series["swir_high"]
        mwir_low = series["mwir_low"]
        mwir_med = series["mwir_med"]
        mwir_high = series["mwir_high"]

        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9))

        # Add title with packet info
        fig.suptitle(
            f"Packet {packet_num} ({packet_type}) - Received: {packet_timestamp}\n"
            f"{num_points} data points, 500ms spacing backwards from reception time",
            fontsize=12,
            fontweight="bold",
        )

        # SWIR plot
        ax1.scatter(time_seconds, swir_low, s=3, label="SWIR_LOW", alpha=0.7)
        ax1.plot(time_seconds, swir_low, linewidth=0.5, alpha=0.5)
        ax1.scatter(time_seconds, swir_med, s=3, label="SWIR_MED", alpha=0.7)
        ax1.plot(time_seconds, swir_med, linewidth=0.5, alpha=0.5)
        ax1.scatter(time_seconds, swir_high, s=3, label="SWIR_HIGH", alpha=0.7)
        ax1.plot(time_seconds, swir_high, linewidth=0.5, alpha=0.5)
        ax1.set_xlabel("Timestamp")
        ax1.set_ylabel("Intensity")
        ax1.set_title("SWIR")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Set x-axis to show timestamps instead of seconds
        tick_positions = ax1.get_xticks()
        tick_labels = []
        for pos in tick_positions:
            # Find closest timestamp to this position
            idx = np.argmin(np.abs(np.array(time_seconds) - pos))
            if 0 <= idx < len(timestamps):
                tick_labels.append(timestamps[idx].split(".")[0])  # Remove milliseconds for readability
            else:
                tick_labels.append("")
        ax1.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=8)

        # MWIR plot
        ax2.scatter(time_seconds, mwir_low, s=3, label="MWIR_LOW", alpha=0.7)
        ax2.plot(time_seconds, mwir_low, linewidth=0.5, alpha=0.5)
        ax2.scatter(time_seconds, mwir_med, s=3, label="MWIR_MED", alpha=0.7)
        ax2.plot(time_seconds, mwir_med, linewidth=0.5, alpha=0.5)
        ax2.scatter(time_seconds, mwir_high, s=3, label="MWIR_HIGH", alpha=0.7)
        ax2.plot(time_seconds, mwir_high, linewidth=0.5, alpha=0.5)
        ax2.set_xlabel("Timestamp")
        ax2.set_ylabel("Intensity")
        ax2.set_title("MWIR")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Set x-axis to show timestamps instead of seconds
        tick_positions = ax2.get_xticks()
        tick_labels = []
        for pos in tick_positions:
            # Find closest timestamp to this position
            idx = np.argmin(np.abs(np.array(time_seconds) - pos))
            if 0 <= idx < len(timestamps):
                tick_labels.append(timestamps[idx].split(".")[0])  # Remove milliseconds for readability
            else:
                tick_labels.append("")
        ax2.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=8)

        # Add timestamp information box
        first_ts = timestamps[0]
        last_ts = timestamps[-1]
        duration = (num_points - 1) * (spacing_ms / 1000.0)
        timestamp_info = f"First: {first_ts}\nLast: {last_ts}\nDuration: {duration:.1f}s"
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

        # Save the figure
        output_file = f"sci_packet_{packet_num:03d}_{packet_type}.png"
        plt.savefig(output_file, dpi=100, bbox_inches="tight")
        print(f"  Saved: {output_file}")

        # Connect click handler
        handler = ClickHandler(time_seconds, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high, timestamps)
        fig.canvas.mpl_connect("button_press_event", handler.on_click)

    print(f"\nAll {len(sci_packets)} packets plotted!")
    print("Click on data points to see their timestamps!")
    plt.show()


if __name__ == "__main__":
    main()
