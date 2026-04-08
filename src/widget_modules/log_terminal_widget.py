from __future__ import annotations

import logging
from typing import Any


class LogElementHandler(logging.Handler):
    """A logging handler that emits messages to a ui.log element."""

    def __init__(self, element: Any, level: int = logging.NOTSET) -> None:
        self.element = element
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the ui.log element."""
        try:
            msg = self.format(record)
            color_map = {
                logging.DEBUG: "text-grey",
                logging.INFO: "text-blue",
                logging.WARNING: "text-orange",
                logging.ERROR: "text-red",
                logging.CRITICAL: "text-red font-bold",
            }
            log_class = color_map.get(record.levelno, "")
            self.element.push(msg, classes=log_class)
        except Exception:
            self.handleError(record)


def refresh_egse_log(
    log_mode: str,
    log: Any,
    eb_interface: Any,
    log_max_lines: int,
    force: bool = False,
) -> None:
    if log_mode != "EB EGSE":
        return

    changed, header, lines, error = eb_interface.get_egse_log_snapshot(
        log_max_lines,
        force=force,
    )
    if not changed:
        return

    log.clear()
    if error:
        log.push(error)
        return
    if header:
        log.push(header)
    for line in lines:
        log.push(line)


def set_log_display(
    selection: str,
    level_options: dict[str, int],
    handler: logging.Handler,
    set_mode: Any,
    refresh_fn: Any,
) -> None:
    """Set the log display mode and logging level based on user selection."""
    set_mode(selection)
    if selection in level_options:
        handler.setLevel(level_options[selection])
        return

    handler.setLevel(logging.CRITICAL + 1)
    refresh_fn(force=True)
