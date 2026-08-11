from __future__ import annotations

# Std library
from datetime import datetime
from typing import Any, Callable, Mapping

# Added packages
from nicegui import app, ui


_ALARM_LIGHT_CSS_INSTALLED = False


def _ensure_alarm_light_css() -> None:
    global _ALARM_LIGHT_CSS_INSTALLED
    if _ALARM_LIGHT_CSS_INSTALLED:
        return
    ui.add_head_html(
        """
        <style>
        @keyframes egse-alarm-pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.18); opacity: 0.55; }
        }
        .egse-alarm-light {
            display: block;
            width: 22px;
            height: 22px;
            min-width: 22px;
            min-height: 22px;
            border-radius: 50%;
            border: 2px solid var(--color-neutral);
        }
        .egse-alarm-light.ok {
            background: var(--color-ok);
            box-shadow: 0 0 8px var(--color-ok);
            animation: none;
        }
        .egse-alarm-light.warning {
            background: var(--color-warning);
            box-shadow: 0 0 12px var(--color-warning);
            animation: egse-alarm-pulse 1.15s ease-in-out infinite;
        }
        .egse-alarm-light.alarm {
            background: var(--color-error);
            box-shadow: 0 0 14px var(--color-error);
            animation: egse-alarm-pulse .9s ease-in-out infinite;
        }
        </style>
        """,
        shared=True,
    )
    _ALARM_LIGHT_CSS_INSTALLED = True


class AlarmLight:
    def __init__(self, *, key: str, label: str) -> None:
        """Creates an alarm light with a label. The light can be set to OK or Fault state, and clicking on it will show a dialog with details."""
        self.key = key
        self.label = label
        self.on_clear: Callable[[], None] | None = None
        self.on_ignore: Callable[[set[str]], None] | None = None

        self.is_fault: bool = False
        self.severity: str = "ok"
        self.details: list[str] = []
        self._source_faults: dict[str, list[str]] = {}
        self._muted_signatures: set[str] = set()
        self._muted_details: set[str] = set()
        self._checked_details: set[str] = set()
        self._history: list[dict[str, str | list[str]]] = []
        self._last_signature: str | None = None

        self._create_fault_widget()

    def _create_fault_widget(self) -> None:
        """Creates the UI elements for the fault light and its dialog."""
        _ensure_alarm_light_css()
        with ui.column().classes("items-center gap-1 cursor-pointer") as container:
            ui.label(self.label).classes("egse-metric-label")
            self.light = ui.element("div").classes("status-light status-light-lg egse-alarm-light ok")
        self.container = container

        container.on("click", lambda _=None: self.show_fault_dialog())

        with ui.dialog() as self.fault_dialog:
            with ui.card().classes("w-96"):
                self.fault_title = ui.label("Fault Details").classes("font-bold egse-title")
                ui.separator()
                self.current_faults = ui.column().classes("w-full gap-1")
                with ui.row().classes("gap-2"):
                    ui.button("Ignore selected", on_click=self.clear_selected_faults).props("size=sm")
                    ui.button("Clear all", on_click=self.clear_fault).props("size=sm")
                with ui.expansion("History").classes("w-full"):
                    self.history_text = ui.label("None").classes("whitespace-pre-wrap egse-metric-label")
                    with ui.expansion("Ignored alarms").classes("w-full"):
                        self.ignored_text = ui.label("None").classes("whitespace-pre-wrap egse-metric-label")

    def _refresh_from_sources(self, *, track_history: bool) -> None:
        merged_details: list[str] = []
        for names in self._source_faults.values():
            for name in names:
                if name not in merged_details:
                    merged_details.append(name)

        filtered_details = [name for name in merged_details if name not in self._muted_details]
        signature = "|".join(sorted(filtered_details))

        if signature and signature in self._muted_signatures:
            self.set_fault_state(ok=True, details=[])
            return

        if filtered_details:
            if track_history and signature != self._last_signature:
                self._history.append(
                    {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "details": filtered_details,
                    }
                )
                if len(self._history) > 50:
                    self._history.pop(0)
            self._last_signature = signature
            self.set_fault_state(ok=False, details=filtered_details)
            return

        self._last_signature = None
        self.set_fault_state(ok=True, details=[])

    @staticmethod
    def _severity_from_details(details: list[str]) -> str:
        """Return alarm for alarm/error details, warning for all other active details."""
        lowered = [str(detail).lower() for detail in details]
        if any("alarm" in detail or "error" in detail for detail in lowered):
            return "alarm"
        if details:
            return "warning"
        return "ok"

    def _refresh_light(self) -> None:
        """Refresh the light as green, amber, or red from the current severity."""
        self.light.classes(remove="ok warning alarm")
        self.light.classes(add=self.severity)

    def set_fault_state(
        self,
        ok: bool,
        details: list[str] | None = None,
    ) -> None:
        """Sets the fault state to OK or Fault, and updates the details if provided."""
        self.is_fault = not ok
        if self.is_fault:
            self.details = [str(item) for item in (details if details is not None else [f"{self.label} fault active"])]
            self.severity = self._severity_from_details(self.details)
        else:
            self.details = []
            self.severity = "ok"
        self._refresh_light()

    def update_from_faults(self, faults: Mapping[str, bool], *, source: str = "generic") -> None:
        """Updates the fault state based on source-specific fault names and active status."""
        self._source_faults[source] = [name for name, active in faults.items() if bool(active)]
        self._refresh_from_sources(track_history=True)

    def reset_acknowledgements(self) -> None:
        """Forget muted alarm acknowledgements so future repeats are visible."""
        self._muted_signatures.clear()
        self._muted_details.clear()
        self._checked_details.clear()
        self._refresh_from_sources(track_history=False)

    def reset_latches(self) -> None:
        """Reset transient latch state while preserving the ignored-details list."""
        self._muted_signatures.clear()
        self._checked_details.clear()
        self._refresh_from_sources(track_history=False)

    def clear_selected_faults(self) -> None:
        """Ignore the selected details while leaving other active alarms visible."""
        if not self._checked_details:
            self.show_fault_dialog()
            return
        newly_muted = set(self._checked_details)
        for detail in newly_muted:
            self._muted_details.add(detail)
        self._checked_details.clear()
        self._refresh_from_sources(track_history=False)
        if callable(self.on_ignore):
            self.on_ignore(newly_muted)
        self.show_fault_dialog()

    def clear_fault(self) -> None:
        """Clear the currently displayed fault without adding it to the ignored list.

        The underlying source remains untouched. If it is still active, the next
        telemetry update will raise it again. Existing ignored selections are
        preserved.
        """
        self._checked_details.clear()
        self.set_fault_state(True, details=[])
        if callable(self.on_clear):
            self.on_clear()
        self.show_fault_dialog()

    def show_fault_dialog(self) -> None:
        """Shows a dialog with the current fault details."""
        self.fault_title.set_text(f"{self.label} Fault Details")
        self.current_faults.clear()
        if self.details:
            with self.current_faults:
                for detail in self.details:

                    def _on_change(event: Any, name: str = detail) -> None:
                        if bool(event.value):
                            self._checked_details.add(name)
                        else:
                            self._checked_details.discard(name)

                    ui.checkbox(
                        detail,
                        value=detail in self._checked_details,
                        on_change=_on_change,
                    ).classes("egse-metric-label")
        elif self.is_fault:
            with self.current_faults:
                ui.label(f"{self.label} currently reports a fault condition.").classes("egse-metric-label")
        else:
            with self.current_faults:
                ui.label(f"{self.label} currently reports OK.").classes("text-sm")

        if self._history:
            lines: list[str] = []
            for entry in reversed(self._history[-20:]):
                time_text = str(entry.get("time", "Unknown time"))
                lines.append(time_text)
                for detail in entry.get("details", []):
                    lines.append(f"- {detail}")
                lines.append("")
            self.history_text.set_text("\n".join(lines).strip())
        else:
            self.history_text.set_text("None")

        ignored_entries = sorted(self._muted_details)
        if ignored_entries:
            ignored_lines: list[str] = []
            for detail in ignored_entries:
                ignored_lines.append(detail)
            self.ignored_text.set_text("\n".join(ignored_lines))
        else:
            self.ignored_text.set_text("None")
        self.fault_dialog.open()

    def set_visible(self, visible: bool) -> None:
        if visible:
            self.container.classes(remove="hidden")
            return
        self.container.classes(add="hidden")


def create_traffic_lights(items: list[tuple[str, str]]) -> dict[str, AlarmLight]:
    with ui.row().classes("items-start gap-4"):
        return {key: AlarmLight(key=key, label=label) for key, label in items}
