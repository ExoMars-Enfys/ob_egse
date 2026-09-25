from __future__ import annotations

# Std library
from typing import Any

# Added packages
from nicegui import ui


def show_message(title: str, body: str) -> None:
    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-80"):
        ui.label(title).classes("font-bold egse-title")
        ui.label(body)
        ui.button("Close", on_click=dialog.close)
    dialog.open()


def show_flag_popup(
    *,
    title: str,
    packet: Any,
    attr_name: str,
    ordered_names: list[str] | None = None,
) -> None:
    """Show a popup with decoded flag bits for the selected metric."""

    def _format_flag_snapshot(flag_ns: Any, names: list[str] | None) -> str:
        if flag_ns is None:
            return "No data"

        ordered = names if names is not None else list(getattr(flag_ns, "__dict__", {}).keys())
        lines: list[str] = []
        for key in ordered:
            if key.startswith("UNUSED") or key.startswith("RESERVED"):
                continue
            if hasattr(flag_ns, key):
                value = int(bool(getattr(flag_ns, key)))
                lines.append(f"{key}: {value}")
        return "\n".join(lines) if lines else "No flags"

    body = "No HK data yet."
    if packet is not None:
        body = _format_flag_snapshot(getattr(packet, attr_name, None), ordered_names)

    with ui.dialog().props("backdrop-filter=blur(3px)") as dialog:
        with (
            ui.card()
            .classes("w-96")
            .style("background: rgba(20, 28, 38, 0.82); border: 1px solid rgba(255, 255, 255, 0.16);")
        ):
            ui.label(title).classes("font-bold egse-title")
            ui.separator()
            with ui.column().classes("w-full gap-1"):
                for line in body.splitlines() or ["No flags"]:
                    _, _, flag_value = line.partition(": ")
                    ui.chip(line, color="green" if flag_value == "1" else "grey").props("dense").classes(
                        "w-fit egse-metric-value"
                    )
            ui.button("Close", on_click=dialog.close)
    dialog.open()


def show_details_popup(*, title: str, details: list[tuple[str, Any]]) -> None:
    with ui.dialog().props("backdrop-filter=blur(3px)") as dialog:
        with (
            ui.card()
            .classes("w-96")
            .style("background: rgba(20, 28, 38, 0.82); border: 1px solid rgba(255, 255, 255, 0.16);")
        ):
            ui.label(title).classes("font-bold egse-title")
            ui.separator()
            with ui.column().classes("w-full gap-1"):
                for label, value in details:
                    if isinstance(value, bool):
                        color = "green" if value else "grey"
                        text = f"{label}: {'ON' if value else 'OFF'}"
                    else:
                        color = "grey"
                        text = f"{label}: {value}"
                    ui.chip(text, color=color).props("dense").classes("w-fit egse-metric-value")
            ui.button("Close", on_click=dialog.close)
    dialog.open()
