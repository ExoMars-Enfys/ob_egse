"""Replay an OB science log through the running UI's live SCI pipeline.

Run this module through the application's normal script runner so it shares
``const.sci_queue`` with the UI telemetry poller. Running it as a separate OS
process would create a separate in-memory queue and cannot update the UI.
"""

from __future__ import annotations

from pathlib import Path

from widget_modules import ui_runtime_controller


def run_OB_sci_replay(
    log_path: str
    | Path = r"C:\Users\GK\OneDrive - University College London\General - Enfys - Shared\Test\EM\260826 - EM OB_FFT TESTING\20260826T132729\20260826T132729_SCI.LOG",
    *,
    info_log_path: str | Path | None = None,
    point_delay_s: float = 0.02,
    label: str = "Replayed OB Science Scan",
) -> int:
    """Queue every valid measurement in an OB ``*_SCI.LOG`` for stitching.

    Args:
        log_path: Path to the OB science log to replay.
        info_log_path: Optional matching INFO log. If omitted, the matching
            ``*_INFO.log`` beside the SCI log is selected automatically.
            Completed OB SCI capture windows become separate stitched scans;
            DAC-offset readings outside those windows are excluded.
        point_delay_s: Delay between points, allowing the UI to update as if
            telemetry were arriving live. Use ``0`` for the fastest replay.
        label: Name stored on the resulting stitched scan packet.

    Returns:
        Number of science measurements written to the live SCI queue.
    """
    return ui_runtime_controller.replay_ob_sci_log(
        Path(log_path),
        info_log_path=Path(info_log_path) if info_log_path is not None else None,
        point_delay_s=point_delay_s,
        label=label,
    )


# Short alias for interactive use from the script console.
replay = run_OB_sci_replay
