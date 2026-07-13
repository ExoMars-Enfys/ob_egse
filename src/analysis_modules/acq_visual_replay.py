#!/usr/bin/env python3
"""Interactive visual replay for SCI ACQ current checks.

Generates per-run Plotly HTML files that replay:
- CURRENT_OPERATING_STATE over time
- MTR_FLAGS.MOVING over time
- PSU CH4 raw current and MA(5)
- ACQ command time, t+150 s check time, and the 3 s check window
- heater-aware expected current band and measured median used by the live check
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent))

from nicegui import app as _app

from utility_modules.eb_packet_utility import parse_eb_hk
from utility_modules.psu_log_utility import load_psu_channel_samples
from widget_modules import ui_runtime_controller as urc

CMD_NAME_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}_\d{2}$")
CMD_NAME_CMDLOG_RE = re.compile(r"_CMD\.(LOG|log)$")
CMD_LINE_TS_RE = re.compile(r"^//(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
ACQ_MARKER_RE = re.compile(r"ENFYS_ACQUISITION", re.IGNORECASE)
RS_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})$")


@dataclass
class HkPoint:
    time: datetime
    state: int | None
    moving: int
    homing_complete: int
    hms: int
    hds: int
    hk: Any


@dataclass
class CheckEvent:
    root: str
    run: str
    cmd_file: str
    psu_log: str
    acq_index: int
    acq_cmd_time: datetime
    check_start: datetime
    check_end: datetime
    samples: int
    median_ma: float | None
    expected_min_ma: float | None
    expected_max_ma: float | None
    resolved_states: list[str]
    result: str
    errors: list[str]


@dataclass
class ReplayOptions:
    include_acq_check: bool = True
    include_homing_check: bool = False
    show_state_panel: bool = True
    show_motor_panel: bool = True
    show_psu_raw: bool = True
    show_psu_ma: bool = True


def _extract_acq_times(cmd_file: Path) -> list[datetime]:
    out: list[datetime] = []
    cur: datetime | None = None
    try:
        lines = cmd_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return out

    for line in lines:
        stripped = line.strip()
        match = CMD_LINE_TS_RE.match(stripped)
        if match:
            try:
                cur = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                cur = None
            continue
        if cur is None:
            continue
        upper = stripped.upper()
        if "SET_ACQ" in upper:
            continue
        if ACQ_MARKER_RE.search(stripped):
            out.append(cur)

    return out


def _is_local_pair(cmd_file: Path, psu_file: Path) -> bool:
    cmd_parent = cmd_file.parent
    psu_parent = psu_file.parent
    return (
        cmd_parent == psu_parent
        or cmd_parent.parent == psu_parent
        or psu_parent.parent == cmd_parent
        or cmd_parent.parent.parent == psu_parent
        or psu_parent.parent.parent == cmd_parent
    )


def _pick_local_psu(cmd_file: Path, psu_logs: list[Path]) -> Path | None:
    local = [p for p in psu_logs if _is_local_pair(cmd_file, p)]
    if not local:
        return None
    local.sort(key=lambda p: (0 if p.parent == cmd_file.parent else 1, len(p.parts)))
    return local[0]


def _parse_rs422_hk(root: Path, rs422_offset_hours: float) -> list[HkPoint]:
    points: list[HkPoint] = []
    offset = timedelta(hours=float(rs422_offset_hours))

    for rs422_file in sorted(root.rglob("RS422if_*.log")):
        try:
            lines = rs422_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        current_ts: datetime | None = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            match = RS_TS_RE.match(stripped)
            if match:
                try:
                    current_ts = datetime.strptime(match.group(1), "%Y-%m-%d_%H-%M-%S") + offset
                except ValueError:
                    current_ts = None
                continue

            if not stripped.startswith("Telemetry Data") or current_ts is None or i + 1 >= len(lines):
                continue

            payload = lines[i + 1].strip()
            if not payload or payload.startswith(("Telemetry Data", "Telecommand")):
                continue

            try:
                byte_array = bytes(int(x, 16) for x in payload.split())
            except Exception:
                continue

            if len(byte_array) < 6:
                continue
            tm_type_id = (byte_array[5] >> 2) & 0x3F
            if tm_type_id not in (0x1, 0x2):
                continue

            try:
                hk = parse_eb_hk(byte_array)
            except Exception:
                continue

            hk.TIME = current_ts
            thrm = getattr(hk, "THRM_STATUS", None)
            mtr = getattr(hk, "MTR_FLAGS", None)
            instr = getattr(hk, "INSTR_STATUS_FLAGS", None)
            homing_complete = 0
            if instr is not None:
                try:
                    homing_complete = int(getattr(instr, "HOMING_COMPLETE", 0) or 0)
                except Exception:
                    homing_complete = 0
            elif hasattr(hk, "INSTRUMENT_STATUS_FLAGS"):
                try:
                    homing_complete = 1 if (int(getattr(hk, "INSTRUMENT_STATUS_FLAGS", 0)) & 0x1) != 0 else 0
                except Exception:
                    homing_complete = 0
            points.append(
                HkPoint(
                    time=current_ts,
                    state=getattr(hk, "CURRENT_OPERATING_STATE", None),
                    moving=int(getattr(mtr, "MOVING", 0)) if mtr is not None else 0,
                    homing_complete=homing_complete,
                    hms=int(getattr(thrm, "HMS", 0)) if thrm is not None else 0,
                    hds=int(getattr(thrm, "HDS", 0)) if thrm is not None else 0,
                    hk=hk,
                )
            )

    points.sort(key=lambda p: p.time)
    return points


def _latest_hk_before(points: list[HkPoint], target: datetime) -> HkPoint | None:
    latest: HkPoint | None = None
    for point in points:
        if point.time <= target:
            latest = point
        else:
            break
    return latest


def _build_psu_series(psu_log: Path) -> tuple[list[datetime], list[float], list[float]]:
    samples = load_psu_channel_samples(psu_log)
    if not samples:
        return [], [], []

    times: list[datetime] = []
    raw_ma: list[float] = []
    ma5: list[float] = []
    window: deque[float] = deque(maxlen=5)

    for sample in samples:
        time_val = sample.get("TIME")
        current_a = ((sample.get("CHANNELS") or {}).get("CH4") or {}).get("I")
        if time_val is None or current_a is None:
            continue
        try:
            current_ma = float(current_a) * 1000.0
        except Exception:
            continue
        window.append(current_ma)
        times.append(time_val)
        raw_ma.append(current_ma)
        ma5.append(sum(window) / len(window))

    return times, raw_ma, ma5


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    n = len(sorted_values)
    mid = n // 2
    if n % 2:
        return float(sorted_values[mid])
    return float((sorted_values[mid - 1] + sorted_values[mid]) / 2.0)


def _homing_transition_times(points: list[HkPoint], start: datetime, end: datetime) -> list[datetime]:
    times: list[datetime] = []
    previous = 0
    for point in points:
        if point.time < start:
            previous = point.homing_complete
            continue
        if point.time > end:
            break
        if point.homing_complete == 1 and previous == 0:
            times.append(point.time)
        previous = point.homing_complete
    return times


def _collect_events_for_root(
    root: Path,
    *,
    cmd_offset_hours: float,
    trigger_s: float,
    duration_s: float,
) -> tuple[list[CheckEvent], list[HkPoint]]:
    urc._heater_state_history = {
        "Mech": {"last_expected": None, "last_trp": None, "prev_auto": False, "prev_manual": False},
        "Det": {"last_expected": None, "last_trp": None, "prev_auto": False, "prev_manual": False},
    }

    hk_points = _parse_rs422_hk(root, rs422_offset_hours=1.0)
    psu_logs = sorted([path for path in root.rglob("*_PSU.log") if path.stat().st_size > 0])
    cmd_files = sorted(
        [
            path
            for path in root.rglob("*")
            if path.is_file() and (CMD_NAME_TS_RE.match(path.stem) or CMD_NAME_CMDLOG_RE.search(path.name))
        ]
    )

    _app.state.current_model = "DEM"

    events: list[CheckEvent] = []
    seen: set[tuple[str, str, str]] = set()

    for cmd_file in cmd_files:
        acq_times = _extract_acq_times(cmd_file)
        if not acq_times:
            continue

        psu_log = _pick_local_psu(cmd_file, psu_logs)
        if psu_log is None:
            continue

        psu_times, _raw, psu_ma5 = _build_psu_series(psu_log)
        if not psu_times:
            continue

        run_name = Path(cmd_file.relative_to(root)).parts[0] if len(Path(cmd_file.relative_to(root)).parts) > 1 else "."

        for acq_index, acq_cmd_time in enumerate(acq_times, start=1):
            dedupe_key = (root.name, run_name, acq_cmd_time.isoformat(sep=" "))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            check_start = acq_cmd_time + timedelta(hours=float(cmd_offset_hours), seconds=float(trigger_s))
            check_end = check_start + timedelta(seconds=float(duration_s))
            values = [value for ts, value in zip(psu_times, psu_ma5) if check_start <= ts <= check_end]
            median_ma = _median(values)

            latest = _latest_hk_before(hk_points, check_start)
            errors: list[str] = []
            if latest is None:
                bounds = None
            else:
                bounds = urc.resolve_consumption_bounds(["State6"], errors, latest.hk)

            if bounds is None:
                resolved_states: list[str] = []
                expected_min = None
                expected_max = None
                result = "ERROR"
            else:
                resolved_states, expected_min, expected_max = bounds
                sample_ok = len(values) >= int(urc._SCI_CONSUMPTION_MIN_SAMPLES)
                median_ok = median_ma is not None and expected_min <= median_ma <= expected_max
                result = "PASS" if sample_ok and median_ok else "FAIL"
                if not sample_ok:
                    errors.append(f"too few samples: {len(values)} < {int(urc._SCI_CONSUMPTION_MIN_SAMPLES)}")
                if median_ma is None:
                    errors.append("no median (no PSU data in check window)")
                elif not median_ok:
                    errors.append(f"median {median_ma:.2f} out of [{expected_min:.1f}, {expected_max:.1f}]")

            events.append(
                CheckEvent(
                    root=root.name,
                    run=run_name,
                    cmd_file=str(cmd_file.relative_to(root)),
                    psu_log=str(psu_log.relative_to(root)),
                    acq_index=acq_index,
                    acq_cmd_time=acq_cmd_time,
                    check_start=check_start,
                    check_end=check_end,
                    samples=len(values),
                    median_ma=median_ma,
                    expected_min_ma=expected_min,
                    expected_max_ma=expected_max,
                    resolved_states=resolved_states,
                    result=result,
                    errors=errors,
                )
            )

    events.sort(key=lambda e: (e.run, e.acq_cmd_time))
    return events, hk_points


def _render_run_html(
    *,
    root: Path,
    run_name: str,
    events: list[CheckEvent],
    hk_points: list[HkPoint],
    psu_log_path: Path,
    output_html: Path,
    animation_step_s: float,
    replay_options: ReplayOptions,
) -> None:
    psu_times, psu_raw_ma, psu_ma5 = _build_psu_series(psu_log_path)
    if not psu_times:
        return

    run_start = min([psu_times[0]] + [event.acq_cmd_time for event in events]) - timedelta(seconds=20)
    run_end = max([psu_times[-1]] + [event.check_end for event in events]) + timedelta(seconds=20)

    hk_run = [point for point in hk_points if run_start <= point.time <= run_end]
    psu_indices = [i for i, ts in enumerate(psu_times) if run_start <= ts <= run_end]
    psu_plot_times = [psu_times[i] for i in psu_indices]
    psu_plot_raw = [psu_raw_ma[i] for i in psu_indices]
    psu_plot_ma5 = [psu_ma5[i] for i in psu_indices]

    state_times = [point.time for point in hk_run]
    state_vals = [point.state if point.state is not None else -1 for point in hk_run]
    moving_times = [point.time for point in hk_run]
    moving_vals = [point.moving for point in hk_run]
    heater_text = [f"HMS={point.hms}, HDS={point.hds}" for point in hk_run]
    homing_times = _homing_transition_times(hk_run, run_start, run_end) if replay_options.include_homing_check else []

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.22, 0.18, 0.60],
        subplot_titles=(
            "CURRENT_OPERATING_STATE",
            "Motor MOVING / Heater Status",
            "PSU CH4 Current with Live Check Window",
        ),
    )

    if replay_options.show_state_panel:
        fig.add_trace(
            go.Scatter(
                x=state_times,
                y=state_vals,
                mode="lines+markers",
                line_shape="hv",
                name="CURRENT_OPERATING_STATE",
                marker=dict(size=4),
            ),
            row=1,
            col=1,
        )

    if replay_options.show_motor_panel:
        fig.add_trace(
            go.Scatter(
                x=moving_times,
                y=moving_vals,
                mode="lines+markers",
                line_shape="hv",
                name="MTR_FLAGS.MOVING",
                marker=dict(size=4),
                hovertext=heater_text,
                hovertemplate="%{x}<br>MOVING=%{y}<br>%{hovertext}<extra></extra>",
            ),
            row=2,
            col=1,
        )

    if replay_options.show_psu_raw:
        fig.add_trace(
            go.Scatter(
                x=psu_plot_times,
                y=psu_plot_raw,
                mode="lines",
                line=dict(color="rgba(120,120,120,0.45)", width=1),
                name="CH4 Raw (mA)",
            ),
            row=3,
            col=1,
        )
    if replay_options.show_psu_ma:
        fig.add_trace(
            go.Scatter(
                x=psu_plot_times,
                y=psu_plot_ma5,
                mode="lines",
                line=dict(color="#0b6e4f", width=2),
                name="CH4 MA(5) (mA)",
            ),
            row=3,
            col=1,
        )

    check_x: list[datetime] = []
    check_y: list[float] = []
    check_text: list[str] = []
    check_colors: list[str] = []
    if replay_options.include_acq_check:
        check_x = [event.check_start + (event.check_end - event.check_start) / 2 for event in events if event.median_ma is not None]
        check_y = [event.median_ma for event in events if event.median_ma is not None]
        check_text = [
            (
                f"ACQ{event.acq_index}<br>cmd={event.acq_cmd_time}<br>check={event.check_start}"
                f"<br>median={event.median_ma:.2f} mA"
                f"<br>expected={event.expected_min_ma:.1f}..{event.expected_max_ma:.1f}"
                f"<br>states={'+'.join(event.resolved_states)}<br>result={event.result}"
            )
            for event in events
            if event.median_ma is not None and event.expected_min_ma is not None and event.expected_max_ma is not None
        ]
        check_colors = [
            "#2e7d32" if event.result == "PASS" else "#c62828"
            for event in events
            if event.median_ma is not None
        ]

    if replay_options.include_acq_check and check_x:
        fig.add_trace(
            go.Scatter(
                x=check_x,
                y=check_y,
                mode="markers",
                marker=dict(size=10, color=check_colors, symbol="diamond"),
                name="Check median",
                hovertemplate="%{hovertext}<extra></extra>",
                hovertext=check_text,
            ),
            row=3,
            col=1,
        )

    if replay_options.include_acq_check:
        for event in events:
            band_color = "rgba(46,125,50,0.12)" if event.result == "PASS" else "rgba(198,40,40,0.12)"
            fig.add_vrect(
                x0=event.check_start,
                x1=event.check_end,
                fillcolor=band_color,
                line_width=0,
                row=3,
                col=1,
            )
            fig.add_vline(x=event.acq_cmd_time + timedelta(hours=1), line_dash="dot", line_color="#ff8f00", row=3, col=1)
            fig.add_vline(x=event.check_start, line_dash="dash", line_color="#1565c0", row=1, col=1)
            fig.add_vline(x=event.check_start, line_dash="dash", line_color="#1565c0", row=2, col=1)
            fig.add_vline(x=event.check_start, line_dash="dash", line_color="#1565c0", row=3, col=1)
            if event.expected_min_ma is not None and event.expected_max_ma is not None:
                fig.add_hrect(
                    y0=event.expected_min_ma,
                    y1=event.expected_max_ma,
                    fillcolor="rgba(21,101,192,0.08)",
                    line_width=0,
                    row=3,
                    col=1,
                )

    if replay_options.include_homing_check and homing_times:
        for homing_time in homing_times:
            fig.add_vline(x=homing_time, line_dash="dashdot", line_color="#8e24aa", row=1, col=1)
            fig.add_vline(x=homing_time, line_dash="dashdot", line_color="#8e24aa", row=2, col=1)
            fig.add_vline(x=homing_time, line_dash="dashdot", line_color="#8e24aa", row=3, col=1)

    fig.update_yaxes(title_text="State", row=1, col=1, tickmode="array", tickvals=[0, 2, 4, 8], ticktext=["0", "SAFE", "STBY", "ACQ"])
    fig.update_yaxes(title_text="MOVING", row=2, col=1, range=[-0.1, 1.1], tickmode="array", tickvals=[0, 1])
    fig.update_yaxes(title_text="PSU CH4 (mA)", row=3, col=1)

    fig.update_layout(
        title=(
            f"SCI ACQ Replay — {root.name} / {run_name}<br>"
            f"Shows state changes, motor movement, PSU CH4, and the exact t+150 s check window"
        ),
        template="plotly_white",
        height=900,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(rangeslider_visible=True, row=3, col=1)

    if animation_step_s > 0 and run_start < run_end:
        psu_min = min(psu_plot_raw + psu_plot_ma5) if (psu_plot_raw or psu_plot_ma5) else 0.0
        psu_max = max(psu_plot_raw + psu_plot_ma5) if (psu_plot_raw or psu_plot_ma5) else 1.0
        cursor_time = run_start
        cursor_trace_start = len(fig.data)

        fig.add_trace(
            go.Scatter(x=[cursor_time, cursor_time], y=[0, 8], mode="lines", line=dict(color="#6a1b9a", width=2), name="Replay cursor", showlegend=False),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=[cursor_time, cursor_time], y=[0, 1], mode="lines", line=dict(color="#6a1b9a", width=2), showlegend=False),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=[cursor_time, cursor_time], y=[psu_min, psu_max], mode="lines", line=dict(color="#6a1b9a", width=2), showlegend=False),
            row=3,
            col=1,
        )

        frames = []
        while cursor_time <= run_end:
            frames.append(
                go.Frame(
                    name=cursor_time.isoformat(),
                    data=[
                        go.Scatter(x=[cursor_time, cursor_time], y=[0, 8]),
                        go.Scatter(x=[cursor_time, cursor_time], y=[0, 1]),
                        go.Scatter(x=[cursor_time, cursor_time], y=[psu_min, psu_max]),
                    ],
                    traces=[cursor_trace_start, cursor_trace_start + 1, cursor_trace_start + 2],
                )
            )
            cursor_time += timedelta(seconds=float(animation_step_s))

        fig.frames = frames
        fig.update_layout(
            updatemenus=[
                {
                    "type": "buttons",
                    "showactive": False,
                    "x": 1.0,
                    "xanchor": "right",
                    "y": 1.14,
                    "yanchor": "top",
                    "buttons": [
                        {
                            "label": "Play",
                            "method": "animate",
                            "args": [None, {"frame": {"duration": 150, "redraw": False}, "fromcurrent": True}],
                        },
                        {
                            "label": "Pause",
                            "method": "animate",
                            "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                        },
                    ],
                }
            ],
            sliders=[
                {
                    "currentvalue": {"prefix": "Replay time: "},
                    "steps": [
                        {
                            "method": "animate",
                            "label": frame.name[11:19],
                            "args": [[frame.name], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                        }
                        for frame in frames[:: max(1, len(frames) // 80)]
                    ],
                }
            ],
        )

    output_html.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_html, include_plotlyjs="cdn")


def generate_replay_suite(
    logs_root: Path,
    *,
    output_dir: Path | None = None,
    cmd_offset_hours: float = 1.0,
    trigger_s: float = 150.0,
    animation_step_s: float = 2.0,
    run_filter: str = "",
    replay_options: ReplayOptions | None = None,
) -> tuple[list[Path], Path]:
    if output_dir is None:
        output_dir = Path("reports") / "acq_visual_replay"
    if replay_options is None:
        replay_options = ReplayOptions()

    events, hk_points = _collect_events_for_root(
        logs_root,
        cmd_offset_hours=cmd_offset_hours,
        trigger_s=trigger_s,
        duration_s=urc._SCI_CONSUMPTION_CHECK_DURATION_S,
    )
    if not events:
        return [], output_dir / f"{logs_root.name}_replay_summary.csv"

    grouped: dict[tuple[str, str], list[CheckEvent]] = {}
    for event in events:
        if run_filter and run_filter.lower() not in event.run.lower() and run_filter.lower() not in event.cmd_file.lower():
            continue
        grouped.setdefault((event.run, event.psu_log), []).append(event)

    summary_csv = output_dir / f"{logs_root.name}_replay_summary.csv"
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "root",
                "run",
                "cmd_file",
                "psu_log",
                "acq_index",
                "acq_cmd_time",
                "check_start",
                "check_end",
                "samples",
                "median_ma",
                "expected_min_ma",
                "expected_max_ma",
                "resolved_states",
                "result",
                "errors",
            ],
        )
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "root": event.root,
                    "run": event.run,
                    "cmd_file": event.cmd_file,
                    "psu_log": event.psu_log,
                    "acq_index": event.acq_index,
                    "acq_cmd_time": event.acq_cmd_time.isoformat(sep=" "),
                    "check_start": event.check_start.isoformat(sep=" "),
                    "check_end": event.check_end.isoformat(sep=" "),
                    "samples": event.samples,
                    "median_ma": "" if event.median_ma is None else f"{event.median_ma:.2f}",
                    "expected_min_ma": "" if event.expected_min_ma is None else f"{event.expected_min_ma:.1f}",
                    "expected_max_ma": "" if event.expected_max_ma is None else f"{event.expected_max_ma:.1f}",
                    "resolved_states": "+".join(event.resolved_states),
                    "result": event.result,
                    "errors": " | ".join(event.errors),
                }
            )

    rendered_paths: list[Path] = []
    for (run_name, psu_log_rel), run_events in sorted(grouped.items(), key=lambda item: item[0][0]):
        psu_log_path = logs_root / psu_log_rel
        safe_run = re.sub(r"[^A-Za-z0-9._-]+", "_", run_name or "root").strip("_") or "root"
        output_html = output_dir / f"{logs_root.name}_{safe_run}_replay.html"
        _render_run_html(
            root=logs_root,
            run_name=run_name,
            events=sorted(run_events, key=lambda e: e.acq_cmd_time),
            hk_points=hk_points,
            psu_log_path=psu_log_path,
            output_html=output_html,
            animation_step_s=animation_step_s,
            replay_options=replay_options,
        )
        rendered_paths.append(output_html)

    return rendered_paths, summary_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate interactive visual replay HTML for SCI ACQ checks.")
    parser.add_argument("--logs-root", type=Path, required=True, help="Root FFT/log folder to replay.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports") / "acq_visual_replay",
        help="Directory where HTML replays will be written.",
    )
    parser.add_argument("--cmd-offset-hours", type=float, default=1.0, help="Command timestamp offset hours.")
    parser.add_argument("--trigger-s", type=float, default=150.0, help="Seconds after ACQ command when check runs.")
    parser.add_argument(
        "--animation-step-s",
        type=float,
        default=2.0,
        help="Replay cursor step size in seconds. Use 0 to disable animation.",
    )
    parser.add_argument(
        "--run-filter",
        type=str,
        default="",
        help="Optional substring filter to restrict which runs are rendered.",
    )
    args = parser.parse_args()

    replay_paths, summary_csv = generate_replay_suite(
        args.logs_root,
        output_dir=args.output_dir,
        cmd_offset_hours=args.cmd_offset_hours,
        trigger_s=args.trigger_s,
        animation_step_s=args.animation_step_s,
        run_filter=args.run_filter,
        replay_options=ReplayOptions(),
    )
    if not replay_paths:
        print("No acquisition events found for replay.")
        return 1
    for replay_path in replay_paths:
        print(f"Wrote replay: {replay_path}")
    print(f"Wrote summary: {summary_csv}")
    print(f"Rendered {len(replay_paths)} replay file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())