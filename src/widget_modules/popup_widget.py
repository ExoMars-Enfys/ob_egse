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

    with ui.dialog() as dialog:
        with ui.card().classes("w-96"):
            ui.label(title).classes("font-bold egse-title")
            ui.separator()
            ui.label(body).style("white-space: pre-wrap; font-family: monospace")
            ui.button("Close", on_click=dialog.close)
    dialog.open()
