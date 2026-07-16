from __future__ import annotations

# Std library
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Added packages
from nicegui import app, ui

# Local utilities
@dataclass
class PacketListController:
    """Controller for the packet list viewer."""

    rows: list[Any]
    state: dict[str, Any]
    packet_viewer_controllers: dict[str, Any]
    packet_storage: dict[str, tuple[str, Any]] = None  # Maps row_key -> (packet_type, packet_data)
    table: Any = None
    dialog: Any = None

    def __post_init__(self) -> None:
        """Initialize packet storage if not provided."""
        if self.packet_storage is None:
            self.packet_storage = {}

    def add_packet(
        self,
        packet_type: str,
        packet_data: dict[str, Any],
        label: str = "",
    ) -> None:
        """Add a packet to the list. Keeps the list at max length."""
        timestamp = packet_data.get("TIME", datetime.now())
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        else:
            time_str = str(timestamp)

        packet_id = packet_data.get("PACKET_NUMBER", packet_data.get("ID", ""))
        label_text = label or packet_type

        # Use a unique row key that combines timestamp and type
        row_key = f"{time_str}_{packet_type}_{len(self.packet_storage)}"

        row = {
            "timestamp": time_str,
            "packet_id": str(packet_id),
            "label": label_text,
            "packet_key": row_key,  # Store the key for lookup
        }

        # Store packet data separately to avoid serialization issues with large integers
        self.packet_storage[row_key] = (packet_type, packet_data)
        self.rows.insert(0, row)

        # Keep max 500 packets in memory
        max_packets = self.state.get("packet_list_max", 500)
        if len(self.rows) > max_packets:
            self.rows = self.rows[:max_packets]
            # Prune old storage entries
            stored_keys = list(self.packet_storage.keys())
            for old_key in stored_keys[max_packets:]:
                del self.packet_storage[old_key]

        # Update table
        self._update_table()

    def _update_table(self) -> None:
        """Refresh the table display with current rows."""
        if self.table is not None:
            self.table.rows = self.rows

    def show_popup(self) -> None:
        """Show the packet list popup dialog."""
        if self.dialog is None:
            self._create_popup()
        self.dialog.open()

    def _create_popup(self) -> None:
        """Lazily create the popup dialog on first use."""
        # Match packet list table typography/colour to app label styling.
        ui.add_head_html(
            f"""
            <style>
            .packet-list-table {{
                color: var(--text-primary) !important;
            }}
            .packet-list-table * {{
                color: var(--text-primary) !important;
                font-size: var(--metric-label-size) !important;
            }}
            .packet-list-table .q-table__title {{
                color: var(--accent_color) !important;
                font-size: var(--metric-label-size) !important;
                font-weight: 600 !important;
            }}
            .packet-list-table .q-table thead th,
            .packet-list-table .q-table thead tr th {{
                color: var(--accent_color) !important;
                font-size: var(--metric-label-size) !important;
                font-weight: 600 !important;
                background: var(--primary-bg) !important;
            }}
            .packet-list-table .q-table tbody td,
            .packet-list-table .q-table tbody tr td {{
                color: var(--text-primary) !important;
                font-size: var(--metric-label-size) !important;
                background: var(--secondary-bg) !important;
            }}
            .packet-list-table .q-table__bottom,
            .packet-list-table .q-table__bottom *,
            .packet-list-table .q-field__native,
            .packet-list-table .q-select__dropdown-icon,
            .packet-list-table .q-select__dropdown-icon *,
            .packet-list-table .q-btn,
            .packet-list-table .q-icon {{
                color: var(--text-primary) !important;
                font-size: var(--metric-label-size) !important;
            }}
            </style>
            """,
            shared=True,
        )

        self.dialog = ui.dialog()

        with self.dialog, ui.card().classes("w-full").style("background: var(--primary-bg);"):
            # Header with title and close button
            with ui.row().classes("w-full items-center justify-between"):
                title = ui.label("Packet List").classes("font-bold egse-title")
                title.style("color: var(--accent_color);")
                close_btn = ui.button(icon="close").props("flat dense").style("color: var(--accent_color);")
                close_btn.on_click(lambda: self.dialog.close())

            columns = [
                {"name": "timestamp", "label": "Datetime", "field": "timestamp", "align": "left"},
                {"name": "packet_id", "label": "Pkt Id", "field": "packet_id", "align": "center"},
                {"name": "label", "label": "Label", "field": "label", "align": "left"},
            ]

            self.table = (
                ui.table(
                    title="Packet List",
                    columns=columns,
                    rows=self.rows,
                    row_key="packet_key",  # Use packet_key as the unique row identifier
                )
                .classes("w-full packet-list-table")
                .style("background: var(--secondary-bg);")
            )

            # Style the table for full expansion
            self.table.props("flat bordered dense")
            self.table.props("dark")
            self.table.props("rows-per-page-options=[50, 100, 250, 500]")

            # Add row selection handler
            def on_row_click(e: Any) -> None:
                try:
                    # NiceGUI table event structure: [event_obj, row_data, row_index]
                    if isinstance(e.args, list) and len(e.args) >= 2:
                        row_data = e.args[1]
                        packet_key = row_data.get("packet_key") if isinstance(row_data, dict) else None
                    else:
                        packet_key = None

                    if packet_key and packet_key in self.packet_storage:
                        packet_type, packet_data = self.packet_storage[packet_key]
                        # Get label from row data
                        label_text = row_data.get("label", packet_type) if isinstance(row_data, dict) else packet_type

                        # Update viewer if available
                        if packet_type in self.packet_viewer_controllers:
                            pv_controller = self.packet_viewer_controllers[packet_type]
                            pv_controller.update_from_packet(packet_type, packet_data)

                        # Show packet details popup
                        self._show_packet_popup(packet_type, label_text, packet_data)
                    else:
                        ui.notify("Packet data not found", color="warning")
                except Exception as ex:
                    import traceback

                    print(f"ERROR in on_row_click: {ex}")
                    traceback.print_exc()
                    ui.notify(f"Error: {ex}", color="negative")

            self.table.on("rowClick", on_row_click)

    def _show_packet_popup(self, packet_type: str, label: str, packet_data: dict[str, Any]) -> None:
        """Show a popup displaying the selected packet details."""
        packet_dialog = ui.dialog()

        with packet_dialog, ui.card().classes("w-full max-w-2xl").style("background: var(--primary-bg);"):
            # Header
            with ui.row().classes("w-full items-center justify-between"):
                title = ui.label(f"Packet: {label}").classes("font-bold egse-title")
                title.style("color: var(--accent_color);")
                close_btn = ui.button(icon="close").props("flat dense").style("color: var(--accent_color);")
                close_btn.on_click(lambda: packet_dialog.close())

            # Packet data as a scrollable column
            with ui.scroll_area().classes("w-full h-96").style("background: var(--secondary-bg);"):
                with ui.column().classes("w-full gap-2 p-2"):
                    for key, value in packet_data.items():
                        with ui.row().classes("w-full items-start gap-2"):
                            label_widget = ui.label(str(key)).classes("font-semibold min-w-40 egse-metric-label")
                            label_widget.style("color: var(--accent_color);")
                            value_str = str(value)[:200]  # Truncate very long values
                            val_label = ui.label(value_str).classes("break-words egse-metric-label")
                            val_label.style("color: var(--text-secondary);")

        packet_dialog.open()


def create_packet_list(
    state: dict[str, Any],
    packet_viewer_controllers: dict[str, Any],
) -> PacketListController:
    """Creates a packet list controller with a popup button.

    Args:
        state: Application state dict.
        packet_viewer_controllers: Dict of packet viewer controllers to update on selection.

    Returns:
        PacketListController for external packet updates.
    """
    rows: list[Any] = []
    packet_storage: dict[str, tuple[str, Any]] = {}

    # Create controller
    controller = PacketListController(
        rows=rows,
        state=state,
        packet_viewer_controllers=packet_viewer_controllers,
        packet_storage=packet_storage,
    )

    # Create button to open popup
    btn = ui.button("Packet List", icon="list").props("flat dense")
    btn.style("color: var(--accent_color);")
    btn.on_click(lambda: controller.show_popup())

    return controller
