from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from datetime import datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import eb_sniffer
from scripts.analysis import _extract_packet_timestamp, _read_all_packets, _read_psu_log


PSU_OVERRIDE_BY_RUN_KEY = {
    "SFT1": Path(
        r"C:\Users\GK\OneDrive - University College London\General - Enfys - Shared\Test\EM-EQM Thermal Test\SFT 1 - +25 oC Complete\SFT 1 MSSL EGSE LOGS\20260213T152537_PSU.log"
    ),
    "SFT2": Path(
        r"C:\Users\GK\OneDrive - University College London\General - Enfys - Shared\Test\EM-EQM Thermal Test\SFT 2 - 0oC Complete\SFT 2 MSSL EGSE LOGS\20260218T113203_PSU.log"
    ),
}


def _extract_temperature_label(path: Path) -> str:
    text = str(path.parent)
    matches = re.findall(r"(-?\d+)\s*oC", text, flags=re.IGNORECASE)
    if matches:
        return f"{matches[-1]}C"
    return "UNKNOWN"


def _convert_eb_rails(hk) -> dict[str, float]:
    return {
        "eb_12v": hk.EB_MEAS_MAIN_12V * 0.000400543,
        "eb_neg12v": hk.EB_MEAS_MAIN_NEG12V * -0.00038147,
        "eb_5v": hk.EB_MEAS_5V * 0.000152829,
        "eb_3v3": hk.EB_MEAS_3V3 * 0.0000763,
        "eb_tec_v": hk.EB_MEAS_TEC_RAIL * 0.0000763,
    }


def _convert_eb_temps(hk) -> dict[str, float]:
    return {
        "eb_mcu_c": hk.EB_MCU_INTERNAL_TEMP * 0.01637198 - 273,
        "eb_peltier_c": hk.EB_PELTIER_TEMP * -0.001830011 + 51.27039922,
        "eb_internal_trp_c": eb_sniffer.thermistor_adu_to_temp(hk.EB_INTERNAL_TRP_TEMP),
        "eb_psu_board_c": eb_sniffer.thermistor_adu_to_temp(hk.EB_PSU_BOARD_TEMP),
    }


def _convert_ob_temps(hk) -> dict[str, float]:
    return {
        "ob_digital_trp_c": eb_sniffer.decode_ob_trps(hk.OB_DIGITAL_TRP),
        "ob_detector_trp_c": eb_sniffer.decode_ob_trps(hk.OB_DETECTOR_TRP),
        "ob_mechanism_trp_c": eb_sniffer.decode_ob_trps(hk.OB_MECHANISM_TRP),
        "ob_motor_trp_c": eb_sniffer.decode_ob_trps(hk.OB_MOTOR_TRP),
    }


def _convert_ob_rails(hk) -> dict[str, float]:
    return {
        "ob_3v3": (hk.OB_3V3_VOLTAGE * 2) / 1000,
        "ob_1v5": hk.OB_1V5_VOLTAGE / 1000,
    }


def _find_ob_switch_on_index(hk_packets: list) -> int:
    if not hk_packets:
        return -1

    previous_power = int(getattr(hk_packets[0], "OB_POWER_STATUS", 0))
    previous_5v = bool(getattr(getattr(hk_packets[0], "INSTR_STATUS_FLAGS", None), "OB_5V_ENABLED", 0))

    for idx, hk in enumerate(hk_packets[1:], start=1):
        current_power = int(getattr(hk, "OB_POWER_STATUS", 0))
        current_5v = bool(getattr(getattr(hk, "INSTR_STATUS_FLAGS", None), "OB_5V_ENABLED", 0))

        if (previous_power == 0 and current_power > 0) or (not previous_5v and current_5v):
            return idx

        previous_power = current_power
        previous_5v = current_5v

    for idx, hk in enumerate(hk_packets):
        if int(getattr(hk, "OB_POWER_STATUS", 0)) > 0:
            return idx

    return 0


def _is_valid_switch_sample(hk) -> bool:
    eb_5v_raw = int(getattr(hk, "EB_MEAS_5V", 0))
    ob_3v3_raw = int(getattr(hk, "OB_3V3_VOLTAGE", 0))
    ob_1v5_raw = int(getattr(hk, "OB_1V5_VOLTAGE", 0))
    return eb_5v_raw > 0 and (ob_3v3_raw > 0 or ob_1v5_raw > 0)


def _first_valid_sample_after_index(hk_packets: list, start_idx: int) -> int:
    for idx in range(start_idx, len(hk_packets)):
        if _is_valid_switch_sample(hk_packets[idx]):
            return idx
    return start_idx


def _first_valid_sample_before_index(hk_packets: list, start_idx: int) -> int:
    for idx in range(start_idx, -1, -1):
        if _is_valid_switch_sample(hk_packets[idx]):
            return idx
    return max(0, start_idx)


def _nearest_non_nan(psu_data: dict, key: str, t: datetime) -> float | None:
    pairs: list[tuple[datetime, float]] = []
    for tv, val in zip(psu_data.get("times", []), psu_data.get(key, []), strict=False):
        if val is None:
            continue
        if isinstance(val, float) and math.isnan(val):
            continue
        pairs.append((tv, float(val)))
    if not pairs:
        return None
    return min(pairs, key=lambda pair: abs((pair[0] - t).total_seconds()))[1]


def _read_science_packets(rs422_log: Path) -> list[tuple[datetime | None, object]]:
    with open(rs422_log, "r", encoding="utf-8") as handle:
        all_lines = [line.strip() for line in handle]

    packets: list[tuple[datetime | None, object]] = []
    first_timestamp_date = None

    tm_indices = [i for i, line in enumerate(all_lines) if "Telemetry Data:" in line]
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
                sci = eb_sniffer.decode_cscience_data(byte_array)
            else:
                sci = eb_sniffer.decode_ncscience_data(byte_array)
        except Exception:
            continue

        ts = _extract_packet_timestamp(all_lines, tm_index, first_timestamp_date=first_timestamp_date)
        if ts is not None and first_timestamp_date is None:
            first_timestamp_date = ts.date()
        packets.append((ts, sci))

    return packets


def _find_preferred_rs422_logs(root: Path) -> list[Path]:
    all_logs = sorted(
        [
            path
            for path in root.rglob("*.log")
            if "RS422" in path.name.upper() and path.is_file()
        ]
    )

    grouped: dict[Path, list[Path]] = {}
    for path in all_logs:
        grouped.setdefault(path.parent, []).append(path)

    selected: list[Path] = []
    for _, group in sorted(grouped.items(), key=lambda item: str(item[0])):
        ranked = sorted(group, key=_rs422_rank)
        selected.append(ranked[0])
    return selected


def _rs422_rank(path: Path) -> tuple[int, int, str]:
    name = path.name.upper()
    if name.startswith("RS422IF_"):
        return (0, len(path.name), path.name)
    if "RS422 LOG" in name:
        return (1, len(path.name), path.name)
    return (2, len(path.name), path.name)


def _extract_run_key(path: Path) -> str:
    match = re.search(r"SFT\s*\d+", path.parent.name, flags=re.IGNORECASE)
    if match:
        return re.sub(r"\s+", "", match.group(0).upper())
    return re.sub(r"\W+", "", path.parent.name.upper())


def _iter_psu_candidates(search_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for item in search_root.rglob("*"):
        if not item.is_file():
            continue
        if item.suffix.lower() != ".log":
            continue
        if "PSU" not in item.name.upper():
            continue
        if item.stat().st_size <= 0:
            continue
        candidates.append(item)
    return candidates


def _rank_psu_candidate(candidate: Path, rs422_log: Path, run_key: str) -> tuple[int, int, int, str]:
    try:
        in_dataset = candidate.is_relative_to(rs422_log.parent)
    except ValueError:
        in_dataset = False
    try:
        in_parent = candidate.is_relative_to(rs422_log.parent.parent)
    except ValueError:
        in_parent = False

    location_rank = 0 if in_dataset else (1 if in_parent else 2)
    key_rank = 0 if run_key in re.sub(r"\W+", "", str(candidate).upper()) else 1
    size_rank = -candidate.stat().st_size
    return (location_rank, key_rank, size_rank, str(candidate))


def _find_psu_logs_for_rs422(rs422_log: Path, root: Path | None = None) -> list[Path]:
    search_roots = [rs422_log.parent]
    if rs422_log.parent.parent != rs422_log.parent:
        search_roots.append(rs422_log.parent.parent)
    if root is not None:
        search_roots.append(root)

    run_key = _extract_run_key(rs422_log)
    dedup: dict[str, Path] = {}

    override_path = PSU_OVERRIDE_BY_RUN_KEY.get(run_key)
    if override_path is not None and override_path.exists() and override_path.is_file():
        dedup[str(override_path)] = override_path

    for search_root in search_roots:
        if not search_root.exists():
            continue
        for candidate in _iter_psu_candidates(search_root):
            dedup[str(candidate)] = candidate

    all_candidates = list(dedup.values())
    key_matched_candidates = [
        path
        for path in all_candidates
        if run_key in re.sub(r"\W+", "", str(path).upper())
    ]
    candidates = key_matched_candidates if key_matched_candidates else all_candidates
    return sorted(candidates, key=lambda path: _rank_psu_candidate(path, rs422_log, run_key))


def _fmt(value: float | int | str | None) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        if math.isnan(value):
            return "N/A"
        return f"{value:.4f}"
    return str(value)


def _summarize_log(rs422_log: Path, root: Path | None = None) -> dict[str, str] | None:
    packets = _read_all_packets(rs422_log)
    hk_packets = [pkt for pkt_type, pkt in packets if pkt_type == "HK"]
    hk_packets = [pkt for pkt in hk_packets if getattr(pkt, "TIME", None) is not None]
    if not hk_packets:
        return None

    switch_idx = _find_ob_switch_on_index(hk_packets)
    switch_idx = _first_valid_sample_after_index(hk_packets, switch_idx)
    switch_pkt = hk_packets[switch_idx]
    switch_time = switch_pkt.TIME
    before_idx = _first_valid_sample_before_index(hk_packets, max(0, switch_idx - 1))
    before_pkt = hk_packets[before_idx]

    first_time = hk_packets[0].TIME
    dwell_sec = (switch_time - first_time).total_seconds()

    eb_rails_before = _convert_eb_rails(before_pkt)
    eb_rails_switch = _convert_eb_rails(switch_pkt)
    if eb_rails_before["eb_5v"] <= 0:
        eb_rails_before["eb_5v"] = eb_rails_switch["eb_5v"]
    eb_temps = _convert_eb_temps(switch_pkt)
    ob_temps = _convert_ob_temps(switch_pkt)
    ob_rails_switch = _convert_ob_rails(switch_pkt)

    hk_packets_post_switch = hk_packets[switch_idx:]
    ob_3v3_series = [_convert_ob_rails(pkt)["ob_3v3"] for pkt in hk_packets_post_switch]
    ob_1v5_series = [_convert_ob_rails(pkt)["ob_1v5"] for pkt in hk_packets_post_switch]

    psu_log: Path | None = None
    psu_data = {"times": []}
    for candidate in _find_psu_logs_for_rs422(rs422_log, root=root):
        try:
            candidate_data = _read_psu_log(candidate)
        except OSError:
            continue
        if candidate_data.get("times"):
            psu_log = candidate
            psu_data = candidate_data
            break
        if psu_log is None:
            psu_log = candidate
    ch4_i = _nearest_non_nan(psu_data, "ch4_i", switch_time)

    sci_packets = _read_science_packets(rs422_log)
    sci_after = [pkt for pkt in sci_packets if pkt[0] is not None and pkt[0] >= switch_time]
    sci_ref = sci_after[0][1] if sci_after else (sci_packets[0][1] if sci_packets else None)

    sci_heatsink_start = getattr(sci_ref, "HEATSINK_START_TEMP", None) if sci_ref is not None else None
    sci_heatsink_end = getattr(sci_ref, "HEATSINK_END_TEMP", None) if sci_ref is not None else None
    sci_swir_start = getattr(sci_ref, "SWIR_START_TEMP", None) if sci_ref is not None else None
    sci_swir_end = getattr(sci_ref, "SWIR_END_TEMP", None) if sci_ref is not None else None
    sci_mwir_start = getattr(sci_ref, "MWIR_START_TEMP", None) if sci_ref is not None else None
    sci_mwir_end = getattr(sci_ref, "MWIR_END_TEMP", None) if sci_ref is not None else None

    return {
        "temperature_label (°C)": _extract_temperature_label(rs422_log),
        "run": str(rs422_log.parent.name),
        "eb_facility_reported_temp (°C)": "N/A (not present in RS422/PSU/SCI logs)",
        "ob_facility_reported_temp_incl_rover_tp1000 (°C)": "N/A (not present in RS422/PSU/SCI logs)",
        "psu_current_ch4_at_ob_switch (A)": _fmt(ch4_i),
        "eb_5v_before_ob_switch (V)": _fmt(eb_rails_before["eb_5v"]),
        "eb_5v_at_ob_switch (V)": _fmt(eb_rails_switch["eb_5v"]),
        "eb_temp_mcu_at_ob_switch (°C)": _fmt(eb_temps["eb_mcu_c"]),
        "eb_temp_peltier_at_ob_switch (°C)": _fmt(eb_temps["eb_peltier_c"]),
        "eb_temp_internal_trp_at_ob_switch (°C)": _fmt(eb_temps["eb_internal_trp_c"]),
        "eb_temp_psu_board_at_ob_switch (°C)": _fmt(eb_temps["eb_psu_board_c"]),
        "eb_dwell_time_prior_to_switch (s)": _fmt(dwell_sec),
        "eb_12v_at_ob_switch (V)": _fmt(eb_rails_switch["eb_12v"]),
        "eb_neg12v_at_ob_switch (V)": _fmt(eb_rails_switch["eb_neg12v"]),
        "eb_3v3_at_ob_switch (V)": _fmt(eb_rails_switch["eb_3v3"]),
        "eb_tec_rail_at_ob_switch (V)": _fmt(eb_rails_switch["eb_tec_v"]),
        "ob_temp_digital_trp_at_ob_switch (°C)": _fmt(ob_temps["ob_digital_trp_c"]),
        "ob_temp_detector_trp_at_ob_switch (°C)": _fmt(ob_temps["ob_detector_trp_c"]),
        "ob_temp_mechanism_trp_at_ob_switch (°C)": _fmt(ob_temps["ob_mechanism_trp_c"]),
        "ob_temp_motor_trp_at_ob_switch (°C)": _fmt(ob_temps["ob_motor_trp_c"]),
        "ob_dwell_time_prior_to_switch (s)": _fmt(dwell_sec),
        "ob_3v3_at_switch (V)": _fmt(ob_rails_switch["ob_3v3"]),
        "ob_1v5_at_switch (V)": _fmt(ob_rails_switch["ob_1v5"]),
        "ob_3v3_min_post_switch (V)": _fmt(min(ob_3v3_series)),
        "ob_3v3_max_post_switch (V)": _fmt(max(ob_3v3_series)),
        "ob_1v5_min_post_switch (V)": _fmt(min(ob_1v5_series)),
        "ob_1v5_max_post_switch (V)": _fmt(max(ob_1v5_series)),
        "sci_packets_in_rs422 (#)": str(len(sci_packets)),
        "sci_heatsink_start_temp (adu)": _fmt(sci_heatsink_start),
        "sci_heatsink_end_temp (adu)": _fmt(sci_heatsink_end),
        "sci_swir_start_temp (adu)": _fmt(sci_swir_start),
        "sci_swir_end_temp (adu)": _fmt(sci_swir_end),
        "sci_mwir_start_temp (adu)": _fmt(sci_mwir_start),
        "sci_mwir_end_temp (adu)": _fmt(sci_mwir_end),
    }


def build_table(root: Path, output_csv: Path) -> int:
    rs422_logs = _find_preferred_rs422_logs(root)
    rows: list[dict[str, str]] = []

    for rs422_log in rs422_logs:
        row = _summarize_log(rs422_log, root=root)
        if row is not None:
            rows.append(row)

    if not rows:
        return 0

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(output_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build EM thermal summary table from RS422 + PSU + SCI packet logs")
    parser.add_argument("--root", required=True, help="Root folder containing thermal test logs")
    parser.add_argument("--out", required=True, help="Output CSV path")
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    count = build_table(Path(args.root), Path(args.out))
    if count == 0:
        print("No valid RS422 datasets found")
    else:
        print(f"Wrote summary rows: {count}")
