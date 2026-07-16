from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from core_modules import constants as const
from core_modules import tmstruct

from . import plot_widget

# Extract all EB_HK parameter names from tmstruct
EB_HK_PARAMETERS = [param_name for param_name, _ in tmstruct.eb_hk]


@dataclass
class HKParameterExplorerController:
    """Controller for HK parameter explorer."""

    set_mode: Any
    push_data: Any


def create_hk_parameter_explorer(state: dict[str, Any], palette: dict[str, str]) -> HKParameterExplorerController:
    """Create HK parameter explorer card with dropdown and dynamic plot spawning."""

    # Initialize state for HK parameter explorer
    hk_explorer = state.setdefault(
        "hk_parameter_explorer",
        {
            "data": defaultdict(list),
            "timestamps": [],
            "selected_params": set(),
            "plot_controllers": {},  # Map of param_name -> PlotCardController
            "max_points": 240,
            "update_counter": 0,
            "pending_updates": defaultdict(list),  # Buffer for pending plot updates
            "batch_size": 5,  # Update plots every N packets to avoid UI freeze
            "plots_container": None,
        },
    )

    with ui.card().classes("w-full"):
        with ui.column().classes("w-full gap-2"):
            # Header
            ui.label("HK Parameter Explorer").classes("font-bold egse-title")

            # Dropdown and button for adding plots
            with ui.row().classes("w-full gap-2 items-center"):
                param_select = ui.select(
                    label="Select Parameter",
                    value=None,
                    options=EB_HK_PARAMETERS,
                ).classes("flex-grow")

                add_btn = ui.button("Add Plot").props("outline dense").classes("h-12")

            # Container for plots (will be populated as user adds parameters)
            plots_container = ui.column().classes("w-full gap-2")
            hk_explorer["plots_container"] = plots_container

            def add_plot():
                """Add a new plot for the selected parameter."""
                param = param_select.value
                if param and param not in hk_explorer["selected_params"]:
                    hk_explorer["selected_params"].add(param)

                    # Create new plot card inside the plots container
                    with plots_container:
                        plot_card = plot_widget.create_plot_card(
                            f"HK: {param}",
                            series=[
                                plot_widget.SeriesConfig(param, palette.get("series_ob_3v3", "#2E7D32")),
                            ],
                            y_label="Value",
                            y_limits=(0, 100),
                            show_toggles=False,
                            limit=hk_explorer["max_points"],
                            plot_height_class="h-40",
                        )

                    hk_explorer["plot_controllers"][param] = plot_card
                    param_select.value = None

            add_btn.on_click(add_plot)

    def set_mode(mode: str) -> None:
        """Set the mode for all plots."""
        for plot_card in hk_explorer["plot_controllers"].values():
            plot_card.set_mode(mode)

    def push_data(telemetry: Any) -> None:
        """Process HK data from the dedicated queue to avoid blocking on file I/O."""
        # Skip if no plots are selected to avoid unnecessary work
        if not hk_explorer["selected_params"] or not hk_explorer["plot_controllers"]:
            return

        # Drain pending HK packets from the queue (non-blocking)
        batch_count = 0
        max_batch = 20  # Process up to 20 packets per call

        while batch_count < max_batch and not const.hk_explorer_queue.empty():
            try:
                hk_data = const.hk_explorer_queue.get_nowait()
            except Exception:
                break

            batch_count += 1

            # Record timestamp
            timestamp = getattr(hk_data, "TIME", None)
            if timestamp is None:
                continue

            # Buffer data for selected parameters
            for param in hk_explorer["selected_params"]:
                if hasattr(hk_data, param):
                    value = getattr(hk_data, param)
                    hk_explorer["data"][param].append(value)
                    # Store pending updates to batch them
                    hk_explorer["pending_updates"][param].append((timestamp, value))

            hk_explorer["timestamps"].append(timestamp)
            hk_explorer["update_counter"] += 1

            # Only flush updates every batch_size packets to avoid UI freeze
            batch_size = hk_explorer["batch_size"]
            if hk_explorer["update_counter"] % batch_size == 0:
                # Flush pending updates to plots
                for param, updates in hk_explorer["pending_updates"].items():
                    if param in hk_explorer["plot_controllers"] and updates:
                        plot_card = hk_explorer["plot_controllers"][param]
                        # Push all buffered points at once
                        times = [u[0] for u in updates]
                        values = [[u[1]] for u in updates]
                        plot_card.push(times, values)
                        updates.clear()

            # Maintain max_points limit (do this less frequently too)
            max_points = hk_explorer["max_points"]
            if hk_explorer["update_counter"] % (batch_size * 2) == 0:
                if max_points is not None and len(hk_explorer["timestamps"]) > max_points:
                    excess = len(hk_explorer["timestamps"]) - max_points
                    hk_explorer["timestamps"] = hk_explorer["timestamps"][excess:]
                    for param in hk_explorer["data"]:
                        hk_explorer["data"][param] = hk_explorer["data"][param][excess:]

    return HKParameterExplorerController(
        set_mode=set_mode,
        push_data=push_data,
    )
