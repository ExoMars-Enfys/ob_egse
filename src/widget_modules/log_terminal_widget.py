from __future__ import annotations

import logging

# Std library
from dataclasses import dataclass
from typing import Any

# Added packages
from nicegui import ui


@dataclass
class LogTerminalController:
    log: Any
    handler: LogElementHandler

    def set_level(self, level: int) -> None:
        self.handler.setLevel(level)


class LogElementHandler(logging.Handler):
    LEVEL_OPTIONS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    LEVEL_COLORS = {
        "DEBUG": "grey",
        "INFO": "blue",
        "WARNING": "orange",
        "ERROR": "red",
        "CRITICAL": "red",
    }

    def __init__(self, element: Any, level: int = logging.INFO) -> None:
        super().__init__(level)
        self.element = element
        self.level_radio: Any | None = None

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the ui.log element."""
        # Prevent re-entrant logging from causing recursion (e.g., when the
        # NiceGUI client has been deleted and client.check_existence() logs).
        if getattr(self, "_in_emit", False):
            try:
                msg = self.format(record)
            except Exception:
                try:
                    msg = f"{record.levelname}: {record.getMessage().classes('egse-text')}"
                except Exception:
                    msg = "<log format error>"
            try:
                print(msg)
            except Exception:
                pass
            return

        # Format message first (this should not touch UI)
        try:
            msg = self.format(record)
        except Exception:
            # If formatting itself fails, fallback to a simple representation
            try:
                msg = f"{record.levelname}: {record.getMessage()}"
            except Exception:
                msg = "<log format error>"

        # ``ui.log.push`` accepts only the message in several NiceGUI versions.
        # Passing a ``classes`` keyword raises TypeError; the previous handler
        # swallowed that exception and silently lost every UI log record.
        self._in_emit = True
        try:
            self.element.push(msg)
        except Exception:
            # Other configured handlers still retain the record. Avoid recursive
            # logging from inside a logging handler.
            pass
        finally:
            self._in_emit = False

    def bind_level_radio(self, radio: Any) -> None:
        """Bind the log level radio button to this handler for dynamic level changes."""
        self.level_radio = radio

    def on_level_change(self, event: Any) -> None:
        """Update logger level and selected radio color based on level selection."""
        selection = str(event.value)
        if selection in self.LEVEL_OPTIONS:
            self.setLevel(self.LEVEL_OPTIONS[selection])
        if self.level_radio is not None:
            self.level_radio.props(f"color={self.LEVEL_COLORS.get(selection, 'blue')}")


def create_log_terminal(
    logger: logging.Logger,
    *,
    level: int = logging.INFO,
    max_lines: int = 200,
) -> LogTerminalController:
    """Creates a log terminal using ui.log and a custom logging.Handler to display logs in the UI."""
    level_options = LogElementHandler.LEVEL_OPTIONS
    level_colors = LogElementHandler.LEVEL_COLORS
    default_selection = next((name for name, value in level_options.items() if value == level), "INFO")

    handler: LogElementHandler | None = None

    def on_level_change(event: Any) -> None:
        if handler is not None:
            handler.on_level_change(event)

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center"):
            ui.label("Logs").classes("font-bold egse-title")
            radio = ui.radio(
                list(level_options.keys()),
                value=default_selection,
                on_change=on_level_change,
            )
            radio.props(f"inline dense color={level_colors.get(default_selection, 'blue')}")
            radio.classes("egse-metric-label")
        log = log = ui.log(max_lines=max_lines).classes("w-full h-45 egse-log-terminal")

    # Reuse an existing LogElementHandler on the logger if present (prevents
    # multiple UI handlers being attached during reloads). If found, update
    # its UI element reference and radio binding; otherwise create and attach
    # a new one.
    existing_handler: LogElementHandler | None = None
    for h in logger.handlers:
        if isinstance(h, LogElementHandler):
            existing_handler = h
            break

    if existing_handler is not None:
        handler = existing_handler
        handler.element = log
        handler.bind_level_radio(radio)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    else:
        handler = LogElementHandler(log, level=level)
        handler.bind_level_radio(radio)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    return LogTerminalController(log=log, handler=handler)


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
