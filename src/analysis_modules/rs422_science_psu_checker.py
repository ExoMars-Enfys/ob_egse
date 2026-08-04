#!/usr/bin/env python3
"""Batch-check SCI acquisition PSU current from RS422 and PSU text logs.

The checker recursively scans a directory for RS422*.log and *_PSU.log files,
decodes EB HK packets using the packet layout in core_modules/tmstruct.py, finds
transitions into CURRENT_OPERATING_STATE 0x08, and checks CH4 current over the
60-second interval beginning 150 seconds after each acquisition starts.

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
import math
import os
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Iterable


TIMESTAMP_RS422 = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")
TIMESTAMP_PSU = re.compile(r"^(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-\s+")
HEX_BYTE = re.compile(r"0x[0-9a-fA-F]+")
PSU_SAMPLE = re.compile(
    r"CH3\(status=(?P<ch3_status>\d+)\)\s+"
    r"(?P<ch3_v>[-+]?\d+(?:\.\d+)?)\s+"
    r"(?P<ch3_i>[-+]?\d+(?:\.\d+)?)\s+"
    r"CH4\(status=(?P<ch4_status>\d+)\)\s+"
    r"(?P<ch4_v>[-+]?\d+(?:\.\d+)?)\s+"
    r"(?P<ch4_i>[-+]?\d+(?:\.\d+)?)"
)
FFT_RUN_MARKER = re.compile(
    r"(?:"
    r"fft\.py.{0,120}\b(?:start(?:ed|ing)?|ran|run(?:ning)?|execut(?:ed|ing)?)\b"
    r"|"
    r"\b(?:start(?:ed|ing)?|ran|run(?:ning)?|execut(?:ed|ing)?)\b.{0,120}fft\.py"
    r"|"
    r"fft\.txt.{0,120}\b(?:start(?:ed|ing)?|ran|run(?:ning)?|execut(?:ed|ing)?)\b"
    r"|"
    r"\b(?:start(?:ed|ing)?|ran|run(?:ning)?|execut(?:ed|ing)?)\b.{0,120}fft\.txt"
    r"|"
    r"typecasting\s+text\s+script\s*:\s*.*(?:[/\\])fft\.txt\b"
    r"|"
    r"text\s+script\s+completed\s*:\s*.*(?:[/\\])fft\.txt\b"
    r"|"
    r"(?:typecasting|start(?:ed|ing)?|run(?:ning)?|execut(?:ed|ing)?)"
    r"\s+python\s+script\s*:\s*.*(?:[/\\])fft\.py\b"
    r"|"
    r"python\s+script\s+(?:completed|finished|started)\s*:\s*"
    r".*(?:[/\\])fft\.py\b"
    r")",
    re.IGNORECASE,
)

# Byte/bit positions from tmstruct.eb_hk. The raw EB HK packet is 256 bytes.
HK_PACKET_BYTES = 256
HK_PACKET_TYPES = {0x17, 0x37}
CURRENT_OPERATING_STATE_BIT_OFFSET = 192
CURRENT_OPERATING_STATE_BITS = 8
SCIENCE_PACKETS_SENT_BIT_OFFSET = 856
SCIENCE_PACKETS_SENT_BITS = 16
OB_HK_ID_BIT_OFFSET = 1088
OB_HK_ID_BITS = 8
ACQUISITION_STATE = 0x08

MODEL_NAMES = {
    2: "BB2",
    4: "EM",
    5: "PFM",
}

# State 6 values from MODEL_CONSUMPTION. The source table calls the BB2 profile
# DEM; the report uses the operator-supplied BB2 name.
STATE6_CURRENT_MA = {
    2: 207.0,
    4: 200.0,
    5: 190.0,
}


@dataclass(frozen=True)
class HKRecord:
    timestamp: datetime
    state: int
    model_id: int
    science_packets_sent: int
    source: Path


@dataclass(frozen=True)
class Acquisition:
    source: Path
    start: datetime
    end: datetime | None
    model_id: int
    science_packets_start: int
    science_packets_end: int | None


@dataclass(frozen=True)
class PSUSample:
    timestamp: datetime
    current_a: float
    voltage_v: float
    enabled: bool
    source: Path


@dataclass(frozen=True)
class CheckResult:
    acquisition: Acquisition
    window_start: datetime
    window_end: datetime
    samples: tuple[PSUSample, ...]
    average_ma: float | None
    minimum_ma: float | None
    maximum_ma: float | None
    stddev_ma: float | None
    expected_ma: float | None
    lower_ma: float | None
    upper_ma: float | None
    status: str
    reason: str


class Progress:
    """Small dependency-free progress display suitable for PowerShell."""

    def __init__(self, *, quiet: bool = False) -> None:
        self.quiet = quiet
        self.started = time.monotonic()
        self._last_width = 0
        self._last_discovery_update = 0.0

    def _write(self, text: str, *, finish: bool = False) -> None:
        if self.quiet:
            return
        padded = text.ljust(self._last_width)
        self._last_width = max(self._last_width, len(text))
        print(f"\r{padded}", end="\n" if finish else "", flush=True)
        if finish:
            self._last_width = 0

    def discovery(self, directories: int, logs: int) -> None:
        elapsed = time.monotonic() - self.started
        if elapsed - self._last_discovery_update < 0.1 and directories > 1:
            return
        self._last_discovery_update = elapsed
        spinner = "|/-\\"[directories % 4]
        self._write(
            f"{spinner} Scanning directories: {directories:,} visited, {logs:,} log files found ({elapsed:.1f}s)"
        )

    def bar(self, label: str, current: int, total: int, detail: str = "") -> None:
        width = 28
        fraction = 1.0 if total <= 0 else min(max(current / total, 0.0), 1.0)
        filled = round(width * fraction)
        bar = "#" * filled + "-" * (width - filled)
        suffix = f"  {detail}" if detail else ""
        self._write(
            f"[{bar}] {fraction * 100:6.1f}%  {label} ({current}/{total}){suffix}",
            finish=current >= total,
        )

    def message(self, text: str) -> None:
        self._write(text, finish=True)


def extract_unsigned(packet: bytes, bit_offset: int, bit_count: int) -> int:
    """Extract a big-endian unsigned field from a packet."""
    total_bits = len(packet) * 8
    shift = total_bits - bit_offset - bit_count
    if shift < 0:
        raise ValueError("Field extends beyond packet")
    return (int.from_bytes(packet, "big") >> shift) & ((1 << bit_count) - 1)


def parse_rs422(path: Path, *, time_offset: timedelta = timedelta(hours=1)) -> list[HKRecord]:
    """Decode valid 256-byte EB HK telemetry records from one RS422 log."""
    records: list[HKRecord] = []
    current_timestamp: datetime | None = None
    record_kind: str | None = None

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if TIMESTAMP_RS422.fullmatch(line):
                current_timestamp = datetime.strptime(line, "%Y-%m-%d_%H-%M-%S") + time_offset
                continue
            if line == "Telemetry Data:":
                record_kind = "telemetry"
                continue
            if line == "Telecommand:":
                record_kind = "telecommand"
                continue
            if record_kind != "telemetry" or current_timestamp is None or not line.startswith("0x"):
                continue

            packet = bytes(int(token, 16) for token in HEX_BYTE.findall(line))
            if len(packet) != HK_PACKET_BYTES or len(packet) < 6 or packet[4] not in HK_PACKET_TYPES:
                continue

            state = extract_unsigned(packet, CURRENT_OPERATING_STATE_BIT_OFFSET, CURRENT_OPERATING_STATE_BITS)
            # Reject non-HK/legacy records that happen to have a supported length.
            if state not in {0x02, 0x04, ACQUISITION_STATE}:
                continue
            ob_hk_id = extract_unsigned(packet, OB_HK_ID_BIT_OFFSET, OB_HK_ID_BITS)
            model_id = (ob_hk_id >> 5) & 0x07
            science_packets = extract_unsigned(packet, SCIENCE_PACKETS_SENT_BIT_OFFSET, SCIENCE_PACKETS_SENT_BITS)
            records.append(
                HKRecord(
                    timestamp=current_timestamp,
                    state=state,
                    model_id=model_id,
                    science_packets_sent=science_packets,
                    source=path,
                )
            )

    # Critical and routine HK packets can share a timestamp. Retain one copy of
    # identical decoded state while preserving real transitions.
    unique: list[HKRecord] = []
    seen: set[tuple[datetime, int, int, int]] = set()
    for record in sorted(records, key=lambda item: item.timestamp):
        identity = (
            record.timestamp,
            record.state,
            record.model_id,
            record.science_packets_sent,
        )
        if identity not in seen:
            seen.add(identity)
            unique.append(record)
    return unique


def find_acquisitions(records: Iterable[HKRecord]) -> list[Acquisition]:
    """Find transitions into and out of EB acquisition state."""
    ordered = sorted(records, key=lambda item: item.timestamp)
    acquisitions: list[Acquisition] = []
    active: HKRecord | None = None
    last_acq: HKRecord | None = None
    previous_state: int | None = None

    for record in ordered:
        if record.state == ACQUISITION_STATE:
            last_acq = record
            if previous_state != ACQUISITION_STATE:
                active = record
        elif active is not None:
            acquisitions.append(
                Acquisition(
                    source=active.source,
                    start=active.timestamp,
                    end=record.timestamp,
                    model_id=active.model_id,
                    science_packets_start=active.science_packets_sent,
                    science_packets_end=(last_acq.science_packets_sent if last_acq is not None else None),
                )
            )
            active = None
            last_acq = None
        previous_state = record.state

    if active is not None:
        acquisitions.append(
            Acquisition(
                source=active.source,
                start=active.timestamp,
                end=None,
                model_id=active.model_id,
                science_packets_start=active.science_packets_sent,
                science_packets_end=(last_acq.science_packets_sent if last_acq is not None else None),
            )
        )
    return acquisitions


def parse_psu(path: Path) -> list[PSUSample]:
    """Parse CH4 voltage/current records from one PSU log."""
    samples: list[PSUSample] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            time_match = TIMESTAMP_PSU.match(raw_line)
            sample_match = PSU_SAMPLE.search(raw_line)
            if not time_match or not sample_match:
                continue
            samples.append(
                PSUSample(
                    timestamp=datetime.strptime(time_match.group("stamp"), "%Y-%m-%d %H:%M:%S,%f"),
                    current_a=float(sample_match.group("ch4_i")),
                    voltage_v=float(sample_match.group("ch4_v")),
                    enabled=sample_match.group("ch4_status") == "1",
                    source=path,
                )
            )
    return samples


def run_check(
    acquisition: Acquisition,
    psu_samples: list[PSUSample],
    *,
    trigger_s: float,
    window_s: float,
    tolerance_ma: float,
    min_samples: int,
) -> CheckResult:
    window_start = acquisition.start + timedelta(seconds=trigger_s)
    window_end = window_start + timedelta(seconds=window_s)
    effective_window_end = min(window_end, acquisition.end) if acquisition.end is not None else window_end
    selected = tuple(sample for sample in psu_samples if window_start <= sample.timestamp < effective_window_end)
    expected = STATE6_CURRENT_MA.get(acquisition.model_id)
    lower = expected - tolerance_ma if expected is not None else None
    upper = expected + tolerance_ma if expected is not None else None

    if acquisition.end is not None and acquisition.end <= window_start:
        return CheckResult(
            acquisition,
            window_start,
            window_end,
            selected,
            None,
            None,
            None,
            None,
            expected,
            lower,
            upper,
            "NOT CHECKED",
            f"Acquisition ended before the t+{trigger_s:g}s check window.",
        )
    if expected is None:
        return CheckResult(
            acquisition,
            window_start,
            window_end,
            selected,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "UNKNOWN MODEL",
            f"No State 6 current profile for MODEL_ID {acquisition.model_id}.",
        )
    if not selected:
        return CheckResult(
            acquisition,
            window_start,
            window_end,
            selected,
            None,
            None,
            None,
            None,
            expected,
            lower,
            upper,
            "NO DATA",
            "No CH4 PSU samples overlap the check window.",
        )

    currents = [sample.current_a * 1000.0 for sample in selected]
    average = statistics.fmean(currents)
    minimum = min(currents)
    maximum = max(currents)
    stddev = statistics.pstdev(currents) if len(currents) > 1 else 0.0
    reasons: list[str] = []
    if len(selected) < min_samples:
        reasons.append(f"Only {len(selected)} samples; at least {min_samples} required.")
    if not (lower <= average <= upper):
        reasons.append(f"Average {average:.2f} mA is outside {lower:.1f}-{upper:.1f} mA.")
    status = "PASS" if not reasons else "FAIL"
    return CheckResult(
        acquisition,
        window_start,
        window_end,
        selected,
        average,
        minimum,
        maximum,
        stddev,
        expected,
        lower,
        upper,
        status,
        "All checks passed." if not reasons else " ".join(reasons),
    )


def fmt_time(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if value else "Open/incomplete"


def fmt_number(value: float | None, places: int = 2) -> str:
    return "—" if value is None or not math.isfinite(value) else f"{value:.{places}f}"


def build_html(
    root: Path,
    rs422_files: list[Path],
    psu_files: list[Path],
    results: list[CheckResult],
    *,
    trigger_s: float,
    window_s: float,
    tolerance_ma: float,
    min_samples: int,
    rs422_time_offset_hours: float,
) -> str:
    generated = datetime.now().astimezone()
    status_counts = {
        name: sum(r.status == name for r in results)
        for name in {"PASS", "FAIL", "NO DATA", "NOT CHECKED", "UNKNOWN MODEL"}
    }

    rows: list[str] = []
    for index, result in enumerate(results, 1):
        acq = result.acquisition
        model_name = MODEL_NAMES.get(acq.model_id, f"Unknown ({acq.model_id})")
        try:
            test_folder = acq.source.parent.relative_to(root)
            test_folder_text = root.name if str(test_folder) == "." else str(test_folder)
        except ValueError:
            test_folder_text = acq.source.parent.name
        status_class = result.status.lower().replace(" ", "-")
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{escape(test_folder_text)}</td>"
            f"<td>{escape(acq.source.name)}</td>"
            f"<td>{acq.model_id} — {escape(model_name)}</td>"
            f"<td>{fmt_number(result.average_ma)}</td>"
            f"<td>{fmt_number(result.lower_ma, 1)}–{fmt_number(result.upper_ma, 1)}</td>"
            f'<td><span class="badge {status_class}">{escape(result.status)}</span></td>'
            f"<td>{escape(result.reason)}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="8">No checks with PSU data were found.</td></tr>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RS422 Science PSU Check Report</title>
<style>
:root {{ color-scheme: light; --ink:#14213d; --muted:#667085; --line:#d9e0ea;
--panel:#f7f9fc; --pass:#087443; --fail:#b42318; --warn:#9a6700; }}
* {{ box-sizing:border-box }} body {{ margin:0; font:14px/1.45 system-ui,sans-serif;
color:var(--ink); background:#eef2f7 }} main {{ max-width:1500px; margin:28px auto;
padding:0 20px }} h1 {{ margin-bottom:4px }} .subtitle {{ color:var(--muted) }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:12px; margin:20px 0 }} .card, section {{ background:white;
border:1px solid var(--line); border-radius:10px; box-shadow:0 1px 2px #10182812 }}
.card {{ padding:16px }} .card strong {{ display:block; font-size:26px }}
section {{ padding:18px; margin:16px 0; overflow:auto }} table {{ width:100%;
border-collapse:collapse; white-space:nowrap }} th,td {{ padding:9px 10px;
border-bottom:1px solid var(--line); text-align:left; vertical-align:top }}
th {{ background:var(--panel); position:sticky; top:0 }} td:last-child {{ white-space:normal;
min-width:260px }} .badge {{ display:inline-block; padding:3px 8px; border-radius:999px;
font-weight:700 }} .pass {{ background:#d8f3e6; color:var(--pass) }}
.fail {{ background:#fee4e2; color:var(--fail) }} .not-checked,.unknown-model
{{ background:#fff1c2; color:var(--warn) }} code {{ background:var(--panel); padding:2px 5px;
border-radius:4px }} ul {{ margin-top:6px }}
</style></head><body><main>
<h1>RS422 Science PSU Check Report</h1>
<div class="subtitle">Generated {escape(generated.isoformat(timespec="seconds"))} from
<code>{escape(str(root))}</code></div>
<div class="cards">
<div class="card"><span>Checks with data</span><strong>{len(results)}</strong></div>
<div class="card"><span>Passed</span><strong>{status_counts.get("PASS", 0)}</strong></div>
<div class="card"><span>Failed</span><strong>{status_counts.get("FAIL", 0)}</strong></div>
</div>
<section><h2>Configuration</h2>
<ul><li>Only test folders whose ordinary log contents indicate that
<code>fft.py</code> or <code>FFT.txt</code> was started/run are included</li>
<li>Check window: t+{trigger_s:g}s to t+{trigger_s + window_s:g}s from acquisition entry</li>
<li>RS422 timestamp correction: {rs422_time_offset_hours:+g} hour(s); PSU timestamps unchanged</li>
<li>Current: PSU CH4, reported as <code>PSU_EB_I</code></li>
<li>Pass limit: model State 6 expected current ±{tolerance_ma:g} mA</li>
<li>Minimum samples: {min_samples}</li>
<li>Model mapping: 2 = BB2 (DEM/BB2 207 mA profile), 4 = EM (200 mA),
5 = PFM (190 mA)</li></ul>
<p>Inputs: {len(rs422_files)} RS422 file(s), {len(psu_files)} PSU file(s).</p></section>
<section><h2>Check summary</h2><table><thead><tr>
<th>#</th><th>Test folder</th><th>RS422 file</th><th>Model</th><th>Average (mA)</th>
<th>Allowed (mA)</th><th>Result</th><th>Reason</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table></section>
</main></body></html>"""


def discover_files(root: Path, progress: Progress | None = None) -> tuple[list[Path], list[Path]]:
    log_files: list[Path] = []
    directory_count = 0
    for directory, _subdirectories, filenames in os.walk(root):
        directory_count += 1
        base = Path(directory)
        log_files.extend(base / filename for filename in filenames if Path(filename).suffix.lower() == ".log")
        if progress is not None:
            progress.discovery(directory_count, len(log_files))
    if progress is not None:
        progress.message(f"Scan complete: {directory_count:,} directories, {len(log_files):,} log files.")
    rs422 = sorted(path for path in log_files if "rs422" in path.name.lower())
    psu = sorted(path for path in log_files if "psu" in path.name.lower())
    return rs422, psu


def find_fft_run_marker_file(folder: Path) -> Path | None:
    """Return the ordinary log file that shows FFT was run, if one exists."""
    for path in folder.iterdir():
        lower_name = path.name.lower()
        if not path.is_file() or path.suffix.lower() != ".log" or "rs422" in lower_name or "psu" in lower_name:
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if FFT_RUN_MARKER.search(line):
                        return path
        except OSError:
            continue
    return None


def choose_psu_log(test_folder: Path, candidates: list[Path], root: Path) -> Path | None:
    """Ask which PSU log belongs to an FFT-qualified folder."""

    def distance(path: Path) -> tuple[int, str]:
        try:
            common = Path(os.path.commonpath((test_folder, path.parent)))
            steps = len(test_folder.parts) + len(path.parent.parts) - 2 * len(common.parts)
        except ValueError:
            steps = 10_000
        return steps, str(path).lower()

    ordered = sorted(candidates, key=distance)
    shown = ordered[:25]
    print(f"\nFFT test has no PSU log in its folder:\n  {test_folder}")
    if shown:
        print("Choose a PSU log by number, or paste the full path to another PSU log:")
        for number, path in enumerate(shown, 1):
            try:
                label = path.relative_to(root)
            except ValueError:
                label = path
            print(f"  {number:>2}. {label}")
        if len(ordered) > len(shown):
            print(f"  ... {len(ordered) - len(shown)} more discovered PSU log(s) not shown")
    else:
        print("No PSU logs were discovered. Paste the full path to the correct PSU log.")
    print("Press Enter to skip this test.")

    while True:
        try:
            answer = input("PSU log selection: ").strip().strip('"')
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not answer:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(shown):
            return shown[int(answer) - 1]
        selected = Path(answer).expanduser()
        if selected.is_file() and selected.suffix.lower() == ".log":
            return selected.resolve()
        print("That is not a valid listed number or .log file. Please try again.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check PSU current during every SCI acquisition in a directory of logs."
    )
    parser.add_argument("directory", type=Path, help="Directory to scan recursively")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="HTML report path (default: <directory>/science_psu_report.html)",
    )
    parser.add_argument("--trigger-seconds", type=float, default=150.0)
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=60.0,
        help="PSU averaging-window duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--rs422-time-offset-hours",
        type=float,
        default=1.0,
        help="Hours added to RS422 timestamps before PSU correlation (default: 1)",
    )
    parser.add_argument("--tolerance-ma", type=float, default=10.0)
    parser.add_argument("--min-samples", type=int, default=25)
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not ask for missing PSU logs; skip FFT folders that have none",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output except the final result")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.directory.expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    if not 5.0 <= args.window_seconds <= 300.0:
        print("error: --window-seconds must be between 5 and 300", file=sys.stderr)
        return 2
    if args.min_samples < 1:
        print("error: --min-samples must be at least 1", file=sys.stderr)
        return 2

    progress = Progress(quiet=args.quiet)
    progress.message(f"Scanning {root} ...")
    rs422_files, psu_files = discover_files(root, progress)
    if not rs422_files:
        progress.message("Warning: no RS422 log files were found.")
    if not psu_files:
        progress.message("Warning: no PSU log files were found.")

    fft_folder_cache: dict[Path, Path | None] = {}
    qualified_rs422_files: list[Path] = []
    for index, path in enumerate(rs422_files, 1):
        progress.bar("Finding FFT tests", index - 1, len(rs422_files), path.parent.name)
        if path.parent not in fft_folder_cache:
            fft_folder_cache[path.parent] = find_fft_run_marker_file(path.parent)
        marker_file = fft_folder_cache[path.parent]
        if marker_file is not None:
            qualified_rs422_files.append(path)
        progress.bar(
            "Finding FFT tests",
            index,
            len(rs422_files),
            f"included via {marker_file.name}" if marker_file is not None else "skipped",
        )
    skipped_rs422_count = len(rs422_files) - len(qualified_rs422_files)
    progress.message(f"FFT filter: {len(qualified_rs422_files)} RS422 file(s) included, {skipped_rs422_count} skipped.")
    rs422_files = qualified_rs422_files
    fft_folders = {path.parent for path in rs422_files}
    discovered_psu_files = psu_files
    psu_assignments: dict[Path, list[Path]] = {
        folder: [path for path in discovered_psu_files if path.parent == folder] for folder in fft_folders
    }
    for folder in sorted(fft_folders):
        if psu_assignments[folder]:
            continue
        progress.message(f"Warning: FFT log found but no PSU log found in {folder}")
        selected = None
        if not args.no_prompt and sys.stdin.isatty():
            selected = choose_psu_log(folder, discovered_psu_files, root)
        elif not args.no_prompt:
            progress.message(
                "Cannot ask for a PSU log because input is not interactive; rerun in a terminal or use --no-prompt."
            )
        if selected is not None:
            psu_assignments[folder].append(selected)
            progress.message(f"Using PSU log for {folder.name}: {selected}")
        else:
            progress.message(f"No PSU log selected; {folder} will have no reported checks.")

    psu_files = sorted({path for assigned_paths in psu_assignments.values() for path in assigned_paths})
    progress.message(f"PSU selection: {len(psu_files)} file(s) assigned to FFT-qualified folders.")

    rs422_time_offset = timedelta(hours=args.rs422_time_offset_hours)
    hk_by_file: dict[Path, list[HKRecord]] = {}
    for index, path in enumerate(rs422_files, 1):
        progress.bar("Decoding RS422", index - 1, len(rs422_files), path.name)
        hk_by_file[path] = parse_rs422(path, time_offset=rs422_time_offset)
        progress.bar("Decoding RS422", index, len(rs422_files), path.name)
    acquisitions = [acquisition for path in rs422_files for acquisition in find_acquisitions(hk_by_file[path])]
    acquisitions.sort(key=lambda item: item.start)
    psu_samples_by_folder: dict[Path, list[PSUSample]] = {folder: [] for folder in fft_folders}
    assigned_psu_logs = [
        (folder, path) for folder, assigned_paths in psu_assignments.items() for path in assigned_paths
    ]
    for index, (folder, path) in enumerate(assigned_psu_logs, 1):
        progress.bar("Parsing PSU logs", index - 1, len(assigned_psu_logs), path.name)
        psu_samples_by_folder[folder].extend(parse_psu(path))
        progress.bar("Parsing PSU logs", index, len(assigned_psu_logs), path.name)
    for folder_samples in psu_samples_by_folder.values():
        folder_samples.sort(key=lambda item: item.timestamp)

    results: list[CheckResult] = []
    for index, acquisition in enumerate(acquisitions, 1):
        progress.bar(
            "Checking acquisitions",
            index - 1,
            len(acquisitions),
            fmt_time(acquisition.start),
        )
        results.append(
            run_check(
                acquisition,
                psu_samples_by_folder.get(acquisition.source.parent, []),
                trigger_s=args.trigger_seconds,
                window_s=args.window_seconds,
                tolerance_ma=args.tolerance_ma,
                min_samples=args.min_samples,
            )
        )
        progress.bar(
            "Checking acquisitions",
            index,
            len(acquisitions),
            results[-1].status,
        )
    report_results = [result for result in results if result.status != "NO DATA"]
    output = args.output.expanduser().resolve() if args.output else root / "science_psu_report.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    progress.message(f"Writing HTML report: {output}")
    output.write_text(
        build_html(
            root,
            rs422_files,
            psu_files,
            report_results,
            trigger_s=args.trigger_seconds,
            window_s=args.window_seconds,
            tolerance_ma=args.tolerance_ma,
            min_samples=args.min_samples,
            rs422_time_offset_hours=args.rs422_time_offset_hours,
        ),
        encoding="utf-8",
    )
    print(
        f"Wrote {output} — {len(rs422_files)} RS422 file(s), "
        f"{len(psu_files)} PSU file(s), {len(report_results)} check(s) with data, "
        f"{sum(result.status == 'PASS' for result in report_results)} passed."
    )
    return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
