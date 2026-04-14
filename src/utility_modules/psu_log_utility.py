from __future__ import annotations

# Std library
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def load_psu_channel_samples(psu_log_path: str | Path) -> list[dict[str, Any]]:
    """Parse PSU log file and return generic per-channel samples.

    Each returned record uses:
    {
      "TIME": datetime,
      "STATUS": bool,
      "CHANNELS": {
        "CH1": {"V": float | None, "I": float | None},
        "CH2": {"V": float | None, "I": float | None},
        "CH3": {"V": float | None, "I": float | None},
        "CH4": {"V": float | None, "I": float | None},
      }
    }

    Expected line format:
    - "YYYY-mm-dd HH:MM:SS,mmm - CH3_V 28V CH3_I 0.05 CH4_V 28V CH4_I 0.5"

    Channels may be partially present on each line, depending on which outputs
    were enabled at the time.
    """
    path = Path(psu_log_path)
    if not path.exists():
        return []

    timestamp_regex = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+-\s+(?P<body>.*)$")
    token_regex = re.compile(r"\bCH(?P<ch>[1-4])_(?P<kind>[VI])\s*(?P<val>[-+]?\d*\.?\d+)(?:[VA])?\b")
    # Also support compact lines like: "CH4 27.999V   0.0823A"
    compact_regex = re.compile(r"\bCH(?P<ch>[1-4])\s+(?P<v>[-+]?\d*\.?\d+)V\s+(?P<i>[-+]?\d*\.?\d+)A\b")

    def _empty_channels() -> dict[str, dict[str, float | None]]:
        return {
            "CH1": {"V": None, "I": None},
            "CH2": {"V": None, "I": None},
            "CH3": {"V": None, "I": None},
            "CH4": {"V": None, "I": None},
        }

    samples: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped_line = line.strip()

            match = timestamp_regex.search(stripped_line)
            if not match:
                continue

            try:
                ts = datetime.strptime(match.group("ts"), "%Y-%m-%d %H:%M:%S,%f")
            except ValueError:
                continue

            channels = _empty_channels()

            parsed_any = False
            for token in token_regex.finditer(match.group("body")):
                try:
                    ch = f"CH{token.group('ch')}"
                    kind = token.group("kind")
                    val = float(token.group("val"))
                except ValueError:
                    continue
                channels[ch][kind] = val
                parsed_any = True

            # Parse compact format if present on the same line.
            for token in compact_regex.finditer(match.group("body")):
                try:
                    ch = f"CH{token.group('ch')}"
                    v_val = float(token.group("v"))
                    i_val = float(token.group("i"))
                except ValueError:
                    continue
                channels[ch]["V"] = v_val
                channels[ch]["I"] = i_val
                parsed_any = True

            if not parsed_any:
                continue

            samples.append({"TIME": ts, "STATUS": True, "CHANNELS": channels})

    samples.sort(key=lambda s: s["TIME"])
    return samples
