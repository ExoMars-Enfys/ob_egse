from __future__ import annotations

# Std library
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any

# Added packages
from nicegui import ui

# Local modules
# analysis
from analysis_modules import sci_plot

# Local modules
# core
from core_modules import tmstruct

# widgets
from widget_modules import ui_runtime_controller


PACKET_PROFILE_FIELDS: dict[str, list[str]] = {
    "EB_HK": [name for name, _ in tmstruct.eb_hk],
    "EB_POST": [name for name, _ in tmstruct.post_hk],
    "EB_SCI": [name for name, _ in tmstruct.eb_sci_header],
    "OB_HK": [name for name, _ in tmstruct.eb_hk if name.startswith("OB_")],
    "OB_SCI": [name for name, _ in tmstruct.sci],
}

# Legacy counter keys mapped to reusable packet profile names.
COUNT_KEY_TO_PROFILE: dict[str, str] = {
    "hk": "EB_HK",
    "post": "EB_POST",
    "sci": "EB_SCI",
}


SCI_HEADER_FIELDS: list[str] = [
    name
    for name, _ in tmstruct.eb_sci_header
    if name not in {"PATTERN", "PACKET_ID", "LOBT_RET_TIME", "BLOCK_LENGTH"} and not name.startswith("RESERVED")
] + ["SCI_POINT_COUNT"]

SCI_POINT_FIELDS: list[str] = [name for name, _ in tmstruct.sci_data if not name.startswith("RESERVED")]


@dataclass
class PacketViewerController:
    packet_type: str | None
    packet_state: dict[str, Any]
    field_name_labels: list[Any]
    field_value_labels: list[Any]
    packet_type_label: Any
    sci_status_label: Any | None = None
    sci_packet_index_label: Any | None = None
    sci_packet_type_label: Any | None = None
    sci_point_index_label: Any | None = None
    sci_header_labels: dict[str, Any] = field(default_factory=dict)
    sci_point_labels: dict[str, Any] = field(default_factory=dict)
    sci_state: dict[str, Any] = field(default_factory=ui_runtime_controller.create_sci_navigation_state)

    def refresh(self) -> None:
        """Refresh values currently available in state."""
        if self.packet_type is None:
            return
        if self.packet_type == "EB_SCI":
            self._render_sci_panel(ui_runtime_controller.sci_current_packet(self.sci_state))
            return
        values = self.packet_state.get("telemetry_last", {}).get(self.packet_type, {})
        self._render_values(values)

    def increment(self, key: str, step: int = 1) -> None:
        """Backward-compatible counter update used by existing callers."""
        self.packet_state[key] = int(self.packet_state.get(key, 0)) + step

    def set_packet_type(self, packet_type: str) -> None:
        """Set the current packet type and refresh displayed values accordingly."""
        packet_type = packet_type.upper()
        if packet_type not in PACKET_PROFILE_FIELDS:
            return
        self.packet_type = packet_type
        self.packet_type_label.set_text(f"Telemetry Viewer: {packet_type}")
        if packet_type == "EB_SCI":
            self._render_sci_panel(ui_runtime_controller.sci_current_packet(self.sci_state))
            return
        values = self.packet_state.get("telemetry_last", {}).get(packet_type, {})
        self._render_values(values)

    def update_from_packet(
        self, packet_type: str | dict[str, Any] | Any, packet_data: dict[str, Any] | Any | None = None
    ) -> None:
        """
        Store and render one decoded TM packet.

        packet_type supports: EB_HK, EB_POST, EB_SCI, OB_HK, OB_SCI.
        packet_data can be a dict or an object with __dict__ (e.g. SimpleNamespace).
        """
        if packet_data is None:
            if self.packet_type is None:
                return
            profile = self.packet_type
            raw_packet = packet_type
        else:
            profile = str(packet_type).upper()
            raw_packet = packet_data

        if profile not in PACKET_PROFILE_FIELDS:
            return

        packet_for_display = raw_packet
        if profile == "EB_SCI":
            normalized = ui_runtime_controller.sci_add_packet(self.sci_state, raw_packet)
            if normalized is not None:
                packet_for_display = normalized
                self._render_sci_panel(ui_runtime_controller.sci_current_packet(self.sci_state))

        packet_dict = self._coerce_packet_dict(packet_for_display)

        telemetry_last = self.packet_state.setdefault("telemetry_last", {})
        telemetry_last[profile] = packet_dict

        # Keep old packet counters alive for existing UI/logic.
        for count_key, mapped_profile in COUNT_KEY_TO_PROFILE.items():
            if mapped_profile == profile:
                self.increment(count_key)
                break

        # Selection is telemetry-driven: track the latest incoming packet profile.
        self.packet_type = profile
        self.packet_type_label.set_text(f"Telemetry Viewer: {profile}")

        if profile != "EB_SCI":
            self._render_values(packet_dict)

    def shift_sci_packet(self, delta: int) -> None:
        packet = ui_runtime_controller.sci_shift_packet_index(self.sci_state, delta)
        self._render_sci_panel(packet)

    def set_sci_packet(self, packet_index: int) -> None:
        packet = ui_runtime_controller.sci_set_packet_index(self.sci_state, packet_index)
        self._render_sci_panel(packet)

    def shift_sci_point(self, delta: int) -> None:
        ui_runtime_controller.sci_shift_point_index(self.sci_state, delta)
        packet = ui_runtime_controller.sci_current_packet(self.sci_state)
        self._render_sci_panel(packet)

    def set_sci_point(self, index: int) -> None:
        ui_runtime_controller.sci_set_point_index(self.sci_state, index)
        packet = ui_runtime_controller.sci_current_packet(self.sci_state)
        self._render_sci_panel(packet)

    def plot_selected_sci_packet(self) -> None:
        packet = ui_runtime_controller.sci_current_packet(self.sci_state)
        if packet is None:
            ui.notify("No science packet selected to plot", color="warning")
            return

        packet_number = getattr(packet, "PACKET_NUMBER", "?")
        image_urls = sci_plot.render_sci_packets_data_urls(
            sci_packets=[packet],
            title_prefix=f"SCI Packet {packet_number}",
        )
        if not image_urls:
            ui.notify("Selected packet has no science data points to plot", color="warning")
            return

        with ui.dialog() as plot_dialog:
            with ui.card().classes("w-[95vw] max-w-6xl max-h-[90vh] overflow-auto"):
                with ui.row(align_items="center").classes("w-full justify-between"):
                    ui.label("Science Plot (ABS steps vs intensity)").classes("text-lg font-bold")
                    ui.button(icon="close", on_click=plot_dialog.close).props("flat dense round")
                ui.separator()
                for image_url in image_urls:
                    ui.image(image_url).props("contain").classes("w-full")
        plot_dialog.open()

    def _render_sci_panel(self, packet: Any | None) -> None:
        if self.sci_status_label is None:
            return

        if packet is None:
            self.sci_status_label.set_text("Waiting for science packet...")
            if self.sci_packet_type_label is not None:
                self.sci_packet_type_label.set_text("---")
            if self.sci_packet_index_label is not None:
                self.sci_packet_index_label.set_text("Packet 0 / 0")
            if self.sci_point_index_label is not None:
                self.sci_point_index_label.set_text("Point 0 / 0")
            for field_name in SCI_HEADER_FIELDS:
                label = self.sci_header_labels.get(field_name)
                if label is not None:
                    label.set_text("---")
            for field_name in SCI_POINT_FIELDS:
                label = self.sci_point_labels.get(field_name)
                if label is not None:
                    label.set_text("---")
            return

        packet_type = getattr(packet, "SCI_PACKET_CRITICALITY", "---")
        packet_count = len(self.sci_state.get("packets") or [])
        packet_index = int(self.sci_state.get("packet_index", 0))
        if self.sci_packet_index_label is not None:
            self.sci_packet_index_label.set_text(f"Packet {packet_index + 1} / {packet_count}")
        if self.sci_packet_type_label is not None:
            self.sci_packet_type_label.set_text(str(packet_type))
        self.sci_status_label.set_text(f"Science packet received ({packet_type})")

        for field_name in SCI_HEADER_FIELDS:
            value = getattr(packet, field_name, "---")
            label = self.sci_header_labels.get(field_name)
            if label is None:
                continue
            if field_name == "MEASUREMENT_TYPE_ID":
                label.set_text(self._format_measurement_config(value))
            elif field_name == "ACQUISITION_MODE":
                label.set_text(self._format_acquisition_mode(value))
            elif field_name == "PACKET_NUMBER":
                label.set_text(self._format_sci_packet_number(value))
            elif "TEMP" in field_name:
                label.set_text(self._format_sci_temp_value(value))
            else:
                label.set_text(str(value))

        point_count = int(getattr(packet, "SCI_POINT_COUNT", 0) or 0)
        if point_count <= 0:
            self.sci_state["point_index"] = 0
            if self.sci_point_index_label is not None:
                self.sci_point_index_label.set_text("Point 0 / 0")
            for field_name in SCI_POINT_FIELDS:
                label = self.sci_point_labels.get(field_name)
                if label is not None:
                    label.set_text("---")
            return

        point_index = ui_runtime_controller.sci_set_point_index(
            self.sci_state, int(self.sci_state.get("point_index", 0))
        )
        if self.sci_point_index_label is not None:
            self.sci_point_index_label.set_text(f"Point {point_index + 1} / {point_count}")

        point = None
        sci_points = getattr(packet, "SCI_POINTS", None)
        if sci_points and point_index < len(sci_points):
            point = sci_points[point_index]

        for field_name in SCI_POINT_FIELDS:
            label = self.sci_point_labels.get(field_name)
            if label is None:
                continue
            label.set_text(str(getattr(point, field_name, "---")) if point is not None else "---")

    @staticmethod
    def _format_measurement_config(value: Any) -> str:
        try:
            mode = int(value)
        except (TypeError, ValueError):
            return str(value)
        mode_map = {
            0b00: "0b00: Standard Scan",
            0b01: "0b01: Limited Scan",
            0b10: "0b10: Fixed Scan",
        }
        return mode_map.get(mode, str(mode))

    @staticmethod
    def _format_acquisition_mode(value: Any) -> str:
        return PacketViewerController._format_measurement_config(value)

    @staticmethod
    def _format_sci_temp_value(value: Any) -> str:
        try:
            return str(int(value) >> 4)
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _format_sci_packet_number(value: Any) -> str:
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return str(value)

    def _render_values(self, packet_dict: dict[str, Any]) -> None:
        """Render the given packet values in the UI, matching field names to labels."""
        if self.packet_type is None:
            return
        fields = PACKET_PROFILE_FIELDS.get(self.packet_type, [])
        for idx, field_name in enumerate(fields):
            if idx >= len(self.field_name_labels):
                break
            value = packet_dict.get(field_name, "-")
            self.field_name_labels[idx].set_text(field_name)
            self.field_value_labels[idx].set_text(self._format_value(field_name, value))

        # Keep the same UI structure while clearing unused rows for shorter packet profiles.
        for idx in range(len(fields), len(self.field_name_labels)):
            self.field_name_labels[idx].set_text("")
            self.field_value_labels[idx].set_text("")

    @staticmethod
    def _format_value(field_name: str, value: Any) -> str:
        """Format a telemetry field value for display, with special handling for certain types."""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, float):
            return f"{value:.3f}"
        if isinstance(value, int):
            if "CRC" in field_name:
                return f"0x{value:X}"
            return str(value)
        return str(value)

    @staticmethod
    def _coerce_packet_dict(raw_packet: Any) -> dict[str, Any]:
        """Coerce a raw packet into a dictionary for easier processing."""
        if hasattr(raw_packet, "__dict__"):
            source = dict(raw_packet.__dict__)
        elif isinstance(raw_packet, Mapping):
            source = dict(raw_packet)
        else:
            return {}
        return {str(key): value for key, value in source.items()}


def create_packet_viewer(state: dict[str, Any], packet_type: str | None = None) -> PacketViewerController:
    """Creates a packet viewer UI component and returns its controller for updates."""
    packet_state = state.setdefault("packet_counts", {"hk": 0, "post": 0, "sci": 0, "telemetry_last": {}})
    packet_state.setdefault("telemetry_last", {})

    selected_type = packet_type.upper() if packet_type else None
    if selected_type not in PACKET_PROFILE_FIELDS:
        selected_type = None

    max_rows = max(len(fields) for fields in PACKET_PROFILE_FIELDS.values())
    field_name_labels: list[Any] = []
    field_value_labels: list[Any] = []
    sci_status_label: Any | None = None
    sci_packet_index_label: Any | None = None
    sci_packet_type_label: Any | None = None
    sci_point_index_label: Any | None = None
    sci_header_labels: dict[str, Any] = {}
    sci_point_labels: dict[str, Any] = {}
    controller_ref: dict[str, PacketViewerController | None] = {"value": None}

    with ui.card().classes("w-full min-w-0"):
        initial_label = "Telemetry Viewer: waiting for telemetry"
        if selected_type is not None:
            initial_label = f"Telemetry Viewer: {selected_type}"
        packet_type_label = ui.label(initial_label).classes("text-sm font-bold")
        if selected_type != "EB_SCI":
            with ui.scroll_area().classes("w-full h-80 overflow-x-hidden"):
                with ui.column().classes("w-full gap-1"):
                    for _ in range(max_rows):
                        with ui.row().classes("w-full min-w-0 justify-between gap-3"):
                            field_name_labels.append(ui.label("").classes("text-xs font-mono break-all min-w-0"))
                            field_value_labels.append(ui.label("").classes("text-xs font-mono text-right shrink-0"))

        if selected_type == "EB_SCI":
            ui.separator()
            sci_status_label = ui.label("Waiting for science packet...").classes("text-sm")
            with ui.row(align_items="center").classes("w-full justify-between gap-2"):
                ui.button(
                    icon="skip_previous",
                    on_click=lambda: controller_ref["value"] and controller_ref["value"].set_sci_packet(0),
                ).props("dense flat")
                ui.button(
                    icon="chevron_left",
                    on_click=lambda: controller_ref["value"] and controller_ref["value"].shift_sci_packet(-1),
                ).props("dense flat")
                sci_packet_index_label = ui.label("Packet 0 / 0").classes("font-bold text-xs")
                ui.button(
                    icon="chevron_right",
                    on_click=lambda: controller_ref["value"] and controller_ref["value"].shift_sci_packet(1),
                ).props("dense flat")
                ui.button(
                    icon="skip_next",
                    on_click=lambda: controller_ref["value"]
                    and controller_ref["value"].set_sci_packet(
                        max(0, len(controller_ref["value"].sci_state.get("packets") or []) - 1)
                    ),
                ).props("dense flat")

            with ui.row(align_items="center").classes("w-full gap-2"):
                ui.label("Packet Type:").classes("font-bold text-xs")
                sci_packet_type_label = ui.label("---").classes("text-xs")

            with ui.expansion("EB SCI Header", value=False).classes("w-full"):
                with ui.grid(columns=2).classes("w-full gap-x-4 gap-y-1"):
                    for field_name in SCI_HEADER_FIELDS:
                        ui.label(field_name).classes("text-xs text-right")
                        sci_header_labels[field_name] = ui.label("---").classes("text-xs")

            with ui.expansion("Science Data Point", value=True).classes("w-full"):
                with ui.row(align_items="center").classes("w-full justify-between gap-2"):
                    ui.button(
                        icon="skip_previous",
                        on_click=lambda: controller_ref["value"] and controller_ref["value"].set_sci_point(0),
                    ).props("dense flat")
                    ui.button(
                        icon="chevron_left",
                        on_click=lambda: controller_ref["value"] and controller_ref["value"].shift_sci_point(-1),
                    ).props("dense flat")
                    sci_point_index_label = ui.label("Point 0 / 0").classes("font-bold text-xs")
                    ui.button(
                        icon="chevron_right",
                        on_click=lambda: controller_ref["value"] and controller_ref["value"].shift_sci_point(1),
                    ).props("dense flat")
                    ui.button(
                        icon="skip_next",
                        on_click=lambda: controller_ref["value"]
                        and controller_ref["value"].set_sci_point(
                            max(
                                0,
                                int(
                                    getattr(
                                        ui_runtime_controller.sci_current_packet(controller_ref["value"].sci_state),
                                        "SCI_POINT_COUNT",
                                        0,
                                    )
                                    or 0
                                )
                                - 1,
                            )
                        ),
                    ).props("dense flat")

                with ui.grid(columns=2).classes("w-full gap-x-4 gap-y-1"):
                    for field_name in SCI_POINT_FIELDS:
                        ui.label(field_name).classes("text-xs text-right")
                        sci_point_labels[field_name] = ui.label("---").classes("text-xs")

            with ui.row(align_items="center").classes("w-full justify-center"):
                ui.button(
                    "Plot Science Data",
                    icon="show_chart",
                    on_click=lambda: controller_ref["value"] and controller_ref["value"].plot_selected_sci_packet(),
                ).props("color=primary")

    controller = PacketViewerController(
        packet_type=selected_type,
        packet_state=packet_state,
        field_name_labels=field_name_labels,
        field_value_labels=field_value_labels,
        packet_type_label=packet_type_label,
        sci_status_label=sci_status_label,
        sci_packet_index_label=sci_packet_index_label,
        sci_packet_type_label=sci_packet_type_label,
        sci_point_index_label=sci_point_index_label,
        sci_header_labels=sci_header_labels,
        sci_point_labels=sci_point_labels,
    )
    controller_ref["value"] = controller

    state.setdefault("refreshers", []).append(controller.refresh)
    controller.refresh()
    if selected_type == "EB_SCI":
        controller._render_sci_panel(None)
    return controller


def create_telemetry_list(state: dict[str, Any], packet_type: str | None = None) -> PacketViewerController:
    return create_packet_viewer(state=state, packet_type=packet_type)
