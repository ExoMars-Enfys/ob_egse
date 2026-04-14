from __future__ import annotations

# Std library
from datetime import datetime
from typing import Any, Mapping

# Added packages
from nicegui import ui


class AlarmLight:
    def __init__(self, *, key: str, label: str) -> None:
        """Creates an alarm light with a label. The light can be set to OK or Fault state, and clicking on it will show a dialog with details."""
        self.key = key
        self.label = label

        self.is_fault: bool = False
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
        with ui.column().classes("items-center gap-1 cursor-pointer") as container:
            ui.label(self.label).classes("text-xs")
            self.light = ui.element("div").classes("status-light status-light-lg ok")
        self.container = container

        container.on("click", lambda _=None: self.show_fault_dialog())

        with ui.dialog() as self.fault_dialog:
            with ui.card().classes("w-96"):
                self.fault_title = ui.label("Fault Details").classes("text-lg font-bold")
                ui.separator()
                self.current_faults = ui.column().classes("w-full gap-1")
                with ui.row().classes("gap-2"):
                    ui.button("Clear selected", on_click=self.clear_selected_faults).props("size=sm")
                    ui.button("Clear all", on_click=self.clear_fault).props("size=sm")
                with ui.expansion("History").classes("w-full"):
                    self.history_text = ui.label("None").classes("text-xs whitespace-pre-wrap")
                with ui.expansion("Ignored alarms").classes("w-full"):
                    self.ignored_text = ui.label("None").classes("text-xs whitespace-pre-wrap")

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

    def _refresh_light(self) -> None:
        """Refreshes the fault light's appearance based on its current state."""
        self.light.classes(remove="ok alarm")
        self.light.classes(add="alarm" if self.is_fault else "ok")

    def set_fault_state(
        self,
        ok: bool,
        details: list[str] | None = None,
    ) -> None:
        """Sets the fault state to OK or Fault, and updates the details if provided."""
        self.is_fault = not ok
        if self.is_fault:
            self.details = [str(item) for item in (details if details is not None else [f"{self.label} fault active"])]
        else:
            self.details = []
        self._refresh_light()

    def update_from_faults(self, faults: Mapping[str, bool], *, source: str = "generic") -> None:
        """Updates the fault state based on source-specific fault names and active status."""
        self._source_faults[source] = [name for name, active in faults.items() if bool(active)]
        self._refresh_from_sources(track_history=True)

    def clear_selected_faults(self) -> None:
        """Acknowledge selected details while leaving other active alarms untouched."""
        if not self._checked_details:
            self.show_fault_dialog()
            return
        for detail in self._checked_details:
            self._muted_details.add(detail)
        self._checked_details.clear()
        self._refresh_from_sources(track_history=False)
        self.show_fault_dialog()

    def clear_fault(self) -> None:
        """Clears the fault state and details."""
        if self.details:
            signature = "|".join(sorted(self.details))
            if signature:
                self._muted_signatures.add(signature)
            for detail in self.details:
                self._muted_details.add(detail)
        self._checked_details.clear()
        self.set_fault_state(True)
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
                    ).classes("text-sm")
        elif self.is_fault:
            with self.current_faults:
                ui.label(f"{self.label} currently reports a fault condition.").classes("text-sm")
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
