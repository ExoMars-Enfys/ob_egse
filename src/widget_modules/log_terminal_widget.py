from __future__ import annotations

# Std library
from dataclasses import dataclass
import logging
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
            ui.label("Logs").classes("text-sm font-bold")
            radio = (
                ui.radio(
                    list(level_options.keys()),
                    value=default_selection,
                    on_change=on_level_change,
                )
                .props(f"inline dense size=xs color={level_colors.get(default_selection, 'blue')}")
                .classes("text-black text-xs")
            )
        log = ui.log(max_lines=max_lines).classes("w-full h-56")

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
