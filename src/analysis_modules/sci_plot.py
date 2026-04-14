from __future__ import annotations

import base64
import io
from pathlib import Path
import re
from types import SimpleNamespace
from typing import cast

import matplotlib.pyplot as plt
import numpy as np

from utility_modules import eb_packet_utility

_MANUALLY_OFFSET = {
    "20250620T123307",
    "20250620T143923",
    "20250620T144228",
    "20250620T144349",
    "20250620T144459",
    "20250620T151005",
    "20250620T151604",
    "20250620T155742",
    "20250620T155934",
    "20250620T160907",
    "20250620T161354",
    "20250620T161755",
}


def _parse_sci_log_line(line: str) -> tuple[int, int, int, int, int, int, int] | None:
    if len(line) < 86:
        return None

    try:
        swir_high = int(re.sub(" ", "", line[56:61]), 16)
        swir_med = int(re.sub(" ", "", line[61:66]), 16)
        swir_low = int(re.sub(" ", "", line[66:71]), 16)
        mwir_high = int(re.sub(" ", "", line[71:76]), 16)
        mwir_med = int(re.sub(" ", "", line[76:81]), 16)
        mwir_low = int(re.sub(" ", "", line[81:86]), 16)
        abs_steps = int(line[33:38], 16)
    except ValueError:
        return None

    return abs_steps, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high


def _remove_offset_calibration(abs_steps: np.ndarray, *series: list[int]) -> tuple[np.ndarray, list[np.ndarray]]:
    abs_steps = np.asarray(abs_steps)
    if abs_steps.size == 0:
        return abs_steps, [np.asarray(values) for values in series]

    unique_steps, first_indices = np.unique(abs_steps, return_index=True)

    # For sparse scans with very few unique motor positions, keep all points.
    # Dropping duplicates here can collapse the dataset to effectively nothing.
    if unique_steps.size < 3:
        return abs_steps, [np.asarray(values) for values in series]

    keep_indices = np.sort(first_indices)
    cleaned = [np.asarray(values)[keep_indices] for values in series]
    return abs_steps[keep_indices], cleaned


def _parse_rs422_science(
    log_path: Path,
) -> tuple[list[int], list[int], list[int], list[int], list[int], list[int], list[int]]:
    swir_low: list[int] = []
    swir_med: list[int] = []
    swir_high: list[int] = []
    mwir_low: list[int] = []
    mwir_med: list[int] = []
    mwir_high: list[int] = []
    abs_steps: list[int] = []

    with open(log_path, "r", encoding="utf-8") as handle:
        all_lines = [line.strip() for line in handle]

    tm_indices = [i for (i, line) in enumerate(all_lines) if line.startswith("Telemetry Data:")]

    for tm_index in tm_indices:
        if tm_index + 1 >= len(all_lines):
            continue
        byte_string = all_lines[tm_index + 1]
        if not byte_string:
            continue
        try:
            byte_array = bytes(int(x, 16) for x in byte_string.split())
        except ValueError:
            continue

        if len(byte_array) < 6:
            continue

        tm_type_id = (byte_array[5] >> 2) & 0x3F
        if tm_type_id not in (0x5, 0x6):
            continue

        try:
            if tm_type_id == 0x5:
                sci_pkt = eb_packet_utility.decode_cscience_data(byte_array)
            else:
                sci_pkt = eb_packet_utility.decode_ncscience_data(byte_array)
            sci_data = eb_packet_utility.merge_sci_data_packet(sci_pkt)
        except Exception:
            continue

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
            continue

        if not hasattr(sci_data, "ABS_STEPS"):
            continue

        abs_steps.append(int(sci_data.ABS_STEPS))
        swir_high.append(int(sci_data.SWIR_HIGH))
        swir_med.append(int(sci_data.SWIR_MED))
        swir_low.append(int(sci_data.SWIR_LOW))
        mwir_high.append(int(sci_data.MWIR_HIGH))
        mwir_med.append(int(sci_data.MWIR_MED))
        mwir_low.append(int(sci_data.MWIR_LOW))

    return abs_steps, swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high


def plot_sci_log_file(
    sci_log: Path,
    output_dir: Path | None = None,
    save: bool = False,
    show: bool = True,
    manual_offsets: set[str] | None = None,
) -> None:
    manual_offsets = manual_offsets or _MANUALLY_OFFSET
    sci_name = sci_log.name.removesuffix("_SCI.LOG")

    swir_low: list[int] = []
    swir_med: list[int] = []
    swir_high: list[int] = []
    mwir_low: list[int] = []
    mwir_med: list[int] = []
    mwir_high: list[int] = []
    abs_steps: list[int] = []

    with open(sci_log, "r", encoding="utf-8") as sci:
        for line in sci:
            parsed = _parse_sci_log_line(line)
            if parsed is None:
                continue
            abs_step, s_low, s_med, s_high, m_low, m_med, m_high = parsed
            abs_steps.append(abs_step)
            swir_low.append(s_low)
            swir_med.append(s_med)
            swir_high.append(s_high)
            mwir_low.append(m_low)
            mwir_med.append(m_med)
            mwir_high.append(m_high)

    if not abs_steps:
        return

    abs_steps_array = np.asarray(abs_steps)
    sample_index = np.arange(abs_steps_array.size)

    if sci_name not in manual_offsets:
        abs_steps_array, cleaned = _remove_offset_calibration(
            abs_steps_array,
            swir_low,
            swir_med,
            swir_high,
            mwir_low,
            mwir_med,
            mwir_high,
        )
        swir_low, swir_med, swir_high, mwir_low, mwir_med, mwir_high = [
            cast(list[int], values.tolist()) for values in cleaned
        ]

    plt.figure()
    plt.scatter(sample_index, swir_low, s=5, label="SWIR_LOW")
    plt.plot(sample_index, swir_low, linewidth=0.5)
    plt.scatter(sample_index, swir_med, s=5, label="SWIR_MED")
    plt.plot(sample_index, swir_med, linewidth=0.5)
    plt.scatter(sample_index, swir_high, s=5, label="SWIR_HIGH")
    plt.plot(sample_index, swir_high, linewidth=0.5)
    plt.xlabel("Science Sample Index")
    plt.ylabel("Intensity")
    plt.title(f"{sci_name} - SWIR (ABS steps in packet data)")
    plt.legend()
    if save and output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_dir / f"{sci_name}_SWIR_Plotted.png")

    plt.figure()
    plt.scatter(sample_index, mwir_low, s=5, label="MWIR_LOW")
    plt.plot(sample_index, mwir_low, linewidth=0.5)
    plt.scatter(sample_index, mwir_med, s=5, label="MWIR_MED")
    plt.plot(sample_index, mwir_med, linewidth=0.5)
    plt.scatter(sample_index, mwir_high, s=5, label="MWIR_HIGH")
    plt.plot(sample_index, mwir_high, linewidth=0.5)
    plt.ylabel("Intensity")
    plt.title(f"{sci_name} - MWIR (ABS steps in packet data)")
    plt.xlabel("Science Sample Index")
    plt.legend()
    if save and output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_dir / f"{sci_name}_MWIR_Plotted.png")

    if not show:
        plt.close("all")


def plot_sci_from_rs422(
    log_path: Path,
    output_dir: Path | None = None,
    save: bool = False,
    show: bool = True,
    manual_offsets: set[str] | None = None,
) -> None:
    sci_name = log_path.stem.replace(" ", "_")

    (
        abs_steps,
        swir_low,
        swir_med,
        swir_high,
        mwir_low,
        mwir_med,
        mwir_high,
    ) = _parse_rs422_science(log_path)

    if not abs_steps:
        return

    abs_steps_array = np.asarray(abs_steps)

    # RS422 packets can legitimately contain repeated ABS_STEPS values with
    # different detector readings. Keep all points so the packet content is
    # faithfully visualized.

    plt.figure()
    plt.scatter(abs_steps_array, swir_low, s=5, label="SWIR_LOW")
    plt.plot(abs_steps_array, swir_low, linewidth=0.5)
    plt.scatter(abs_steps_array, swir_med, s=5, label="SWIR_MED")
    plt.plot(abs_steps_array, swir_med, linewidth=0.5)
    plt.scatter(abs_steps_array, swir_high, s=5, label="SWIR_HIGH")
    plt.plot(abs_steps_array, swir_high, linewidth=0.5)
    plt.xlabel("Absolute Motor Steps")
    plt.ylabel("Intensity")
    plt.title(f"{sci_name} - SWIR")
    plt.legend()
    if save and output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_dir / f"{sci_name}_SWIR_Plotted.png")

    plt.figure()
    plt.scatter(abs_steps_array, mwir_low, s=5, label="MWIR_LOW")
    plt.plot(abs_steps_array, mwir_low, linewidth=0.5)
    plt.scatter(abs_steps_array, mwir_med, s=5, label="MWIR_MED")
    plt.plot(abs_steps_array, mwir_med, linewidth=0.5)
    plt.scatter(abs_steps_array, mwir_high, s=5, label="MWIR_HIGH")
    plt.plot(abs_steps_array, mwir_high, linewidth=0.5)
    plt.ylabel("Intensity")
    plt.title(f"{sci_name} - MWIR")
    plt.xlabel("Absolute Motor Steps")
    plt.legend()
    if save and output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_dir / f"{sci_name}_MWIR_Plotted.png")

    if not show:
        plt.close("all")


def plot_sci_packets(
    sci_packets: list[SimpleNamespace],
    title_prefix: str = "SCI Buffer",
    show: bool = True,
) -> None:
    abs_steps: list[int] = []
    swir_low: list[int] = []
    swir_med: list[int] = []
    swir_high: list[int] = []
    mwir_low: list[int] = []
    mwir_med: list[int] = []
    mwir_high: list[int] = []

    for packet in sci_packets:
        sci_points = getattr(packet, "SCI_POINTS", None)
        if sci_points:
            for point in sci_points:
                abs_steps.append(int(point.ABS_STEPS))
                swir_high.append(int(point.SWIR_HIGH))
                swir_med.append(int(point.SWIR_MED))
                swir_low.append(int(point.SWIR_LOW))
                mwir_high.append(int(point.MWIR_HIGH))
                mwir_med.append(int(point.MWIR_MED))
                mwir_low.append(int(point.MWIR_LOW))
            continue

        if not hasattr(packet, "ABS_STEPS"):
            continue

        abs_steps.append(int(packet.ABS_STEPS))
        swir_high.append(int(packet.SWIR_HIGH))
        swir_med.append(int(packet.SWIR_MED))
        swir_low.append(int(packet.SWIR_LOW))
        mwir_high.append(int(packet.MWIR_HIGH))
        mwir_med.append(int(packet.MWIR_MED))
        mwir_low.append(int(packet.MWIR_LOW))

    if not abs_steps:
        return

    abs_steps_array = np.asarray(abs_steps)

    plt.figure()
    plt.scatter(abs_steps_array, swir_low, s=5, label="SWIR_LOW")
    plt.plot(abs_steps_array, swir_low, linewidth=0.5)
    plt.scatter(abs_steps_array, swir_med, s=5, label="SWIR_MED")
    plt.plot(abs_steps_array, swir_med, linewidth=0.5)
    plt.scatter(abs_steps_array, swir_high, s=5, label="SWIR_HIGH")
    plt.plot(abs_steps_array, swir_high, linewidth=0.5)
    plt.xlabel("Absolute Motor Steps")
    plt.ylabel("Intensity")
    plt.title(f"{title_prefix} - SWIR")
    plt.legend()

    plt.figure()
    plt.scatter(abs_steps_array, mwir_low, s=5, label="MWIR_LOW")
    plt.plot(abs_steps_array, mwir_low, linewidth=0.5)
    plt.scatter(abs_steps_array, mwir_med, s=5, label="MWIR_MED")
    plt.plot(abs_steps_array, mwir_med, linewidth=0.5)
    plt.scatter(abs_steps_array, mwir_high, s=5, label="MWIR_HIGH")
    plt.plot(abs_steps_array, mwir_high, linewidth=0.5)
    plt.ylabel("Intensity")
    plt.title(f"{title_prefix} - MWIR")
    plt.xlabel("Absolute Motor Steps")
    plt.legend()

    if not show:
        plt.close("all")


def render_sci_packets_data_urls(
    sci_packets: list[SimpleNamespace],
    title_prefix: str = "SCI Buffer",
) -> list[str]:
    abs_steps: list[int] = []
    swir_low: list[int] = []
    swir_med: list[int] = []
    swir_high: list[int] = []
    mwir_low: list[int] = []
    mwir_med: list[int] = []
    mwir_high: list[int] = []

    for packet in sci_packets:
        sci_points = getattr(packet, "SCI_POINTS", None)
        if sci_points:
            for point in sci_points:
                abs_steps.append(int(point.ABS_STEPS))
                swir_high.append(int(point.SWIR_HIGH))
                swir_med.append(int(point.SWIR_MED))
                swir_low.append(int(point.SWIR_LOW))
                mwir_high.append(int(point.MWIR_HIGH))
                mwir_med.append(int(point.MWIR_MED))
                mwir_low.append(int(point.MWIR_LOW))
            continue

        if not hasattr(packet, "ABS_STEPS"):
            continue

        abs_steps.append(int(packet.ABS_STEPS))
        swir_high.append(int(packet.SWIR_HIGH))
        swir_med.append(int(packet.SWIR_MED))
        swir_low.append(int(packet.SWIR_LOW))
        mwir_high.append(int(packet.MWIR_HIGH))
        mwir_med.append(int(packet.MWIR_MED))
        mwir_low.append(int(packet.MWIR_LOW))

    if not abs_steps:
        return []

    abs_steps_array = np.asarray(abs_steps)
    sort_idx = np.argsort(abs_steps_array)
    abs_steps_sorted = abs_steps_array[sort_idx]

    def _axis_bounds(
        x_values: np.ndarray, y_values: list[np.ndarray]
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        x_min = float(np.min(x_values))
        x_max = float(np.max(x_values))
        if x_min == x_max:
            x_pad = 1.0
        else:
            x_pad = max((x_max - x_min) * 0.05, 1.0)

        y_all = np.concatenate(y_values)
        y_min = float(np.min(y_all))
        y_max = float(np.max(y_all))
        if y_min == y_max:
            y_pad = 1.0
        else:
            y_pad = max((y_max - y_min) * 0.08, 10.0)

        return (x_min - x_pad, x_max + x_pad), (y_min - y_pad, y_max + y_pad)

    image_urls: list[str] = []

    swir_low_array = np.asarray(swir_low)
    swir_med_array = np.asarray(swir_med)
    swir_high_array = np.asarray(swir_high)
    mwir_low_array = np.asarray(mwir_low)
    mwir_med_array = np.asarray(mwir_med)
    mwir_high_array = np.asarray(mwir_high)

    fig_swir, ax_swir = plt.subplots(figsize=(10, 4.5))
    ax_swir.scatter(abs_steps_array, swir_low_array, s=8, label="SWIR_LOW")
    ax_swir.plot(abs_steps_sorted, swir_low_array[sort_idx], linewidth=0.8)
    ax_swir.scatter(abs_steps_array, swir_med_array, s=8, label="SWIR_MED")
    ax_swir.plot(abs_steps_sorted, swir_med_array[sort_idx], linewidth=0.8)
    ax_swir.scatter(abs_steps_array, swir_high_array, s=8, label="SWIR_HIGH")
    ax_swir.plot(abs_steps_sorted, swir_high_array[sort_idx], linewidth=0.8)
    ax_swir.set_xlabel("Absolute Motor Steps")
    ax_swir.set_ylabel("Intensity")
    ax_swir.set_title(f"{title_prefix} - SWIR")
    (swir_x_bounds, swir_y_bounds) = _axis_bounds(abs_steps_array, [swir_low_array, swir_med_array, swir_high_array])
    ax_swir.set_xlim(*swir_x_bounds)
    ax_swir.set_ylim(*swir_y_bounds)
    ax_swir.legend(loc="upper left", bbox_to_anchor=(0.01, 0.99), framealpha=0.9, fontsize="small")
    fig_swir.tight_layout()
    swir_buffer = io.BytesIO()
    fig_swir.savefig(swir_buffer, format="png", bbox_inches="tight")
    swir_encoded = base64.b64encode(swir_buffer.getvalue()).decode("ascii")
    image_urls.append(f"data:image/png;base64,{swir_encoded}")
    plt.close(fig_swir)

    fig_mwir, ax_mwir = plt.subplots(figsize=(10, 4.5))
    ax_mwir.scatter(abs_steps_array, mwir_low_array, s=8, label="MWIR_LOW")
    ax_mwir.plot(abs_steps_sorted, mwir_low_array[sort_idx], linewidth=0.8)
    ax_mwir.scatter(abs_steps_array, mwir_med_array, s=8, label="MWIR_MED")
    ax_mwir.plot(abs_steps_sorted, mwir_med_array[sort_idx], linewidth=0.8)
    ax_mwir.scatter(abs_steps_array, mwir_high_array, s=8, label="MWIR_HIGH")
    ax_mwir.plot(abs_steps_sorted, mwir_high_array[sort_idx], linewidth=0.8)
    ax_mwir.set_ylabel("Intensity")
    ax_mwir.set_title(f"{title_prefix} - MWIR")
    ax_mwir.set_xlabel("Absolute Motor Steps")
    (mwir_x_bounds, mwir_y_bounds) = _axis_bounds(abs_steps_array, [mwir_low_array, mwir_med_array, mwir_high_array])
    ax_mwir.set_xlim(*mwir_x_bounds)
    ax_mwir.set_ylim(*mwir_y_bounds)
    ax_mwir.legend(loc="upper left", bbox_to_anchor=(0.01, 0.99), framealpha=0.9, fontsize="small")
    fig_mwir.tight_layout()
    mwir_buffer = io.BytesIO()
    fig_mwir.savefig(mwir_buffer, format="png", bbox_inches="tight")
    mwir_encoded = base64.b64encode(mwir_buffer.getvalue()).decode("ascii")
    image_urls.append(f"data:image/png;base64,{mwir_encoded}")
    plt.close(fig_mwir)

    return image_urls


def plot_sci_logs(
    sci_logs: list[Path],
    output_dir: Path | None = None,
    save: bool = False,
    show: bool = True,
    manual_offsets: set[str] | None = None,
) -> None:
    for sci_log in sci_logs:
        plot_sci_log_file(
            sci_log=sci_log,
            output_dir=output_dir,
            save=save,
            show=show,
            manual_offsets=manual_offsets,
        )
