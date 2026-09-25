#!/usr/bin/env python3
"""Desktop wrapper for the OB EGSE NiceGUI application."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC_DIR))

from main import main as run_main  # noqa: E402
from utility_modules.desktop_launcher import run_app_in_desktop  # noqa: E402


if __name__ in {"__main__", "__mp_main__"}:
    run_main(gui_runner=run_app_in_desktop)
