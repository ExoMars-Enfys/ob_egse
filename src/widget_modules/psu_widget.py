from __future__ import annotations

# Std library
from dataclasses import dataclass
from typing import Any

# Added packages
from nicegui import ui

# Local modules
# utilities
from utility_modules import psu

# widgets
from widget_modules import plot_widget


@dataclass
class PsuChannelController:
    channel: dict[str, Any]
    title_label: Any
    value_label: Any
    plot: plot_widget.PlotCardController
    card: Any
    enabled_switch: Any

    def set_visible(self, visible: bool) -> None:
        if visible:
            self.card.classes(remove="hidden")
            return
        self.card.classes(add="hidden")

    def apply_profile(
        self,
        *,
        title: str,
        visible: bool,
        live_voltage_key: str,
        live_current_key: str,
        replay_channels: list[str],
    ) -> None:
        self.title_label.set_text(title)
        self.plot.set_series_labels([title])
        self.channel["live_voltage_key"] = live_voltage_key
        self.channel["live_current_key"] = live_current_key
        self.channel["replay_channel_by_mode"] = {"OB": replay_channels, "EB": replay_channels}
        self.set_visible(visible)

    def push_sample(self, time_value: Any, current_a: float | None) -> None:
        """Push a new sample to the channel's plot and update the value label."""
        if current_a is None:
            return
        current_ma = float(current_a) * 1000.0
        self.value_label.set_text(f"mA: {current_ma:.1f}")
        self.plot.push([time_value], [[current_ma]])

    def set_enabled_from_psu(self, enabled: bool) -> None:
        """Synchronize UI switch state from live PSU status without issuing commands."""
        self.channel["enabled"] = enabled
        if bool(getattr(self.enabled_switch, "value", False)) == bool(enabled):
            return
        self.channel["_syncing_from_psu"] = True
        self.enabled_switch.value = bool(enabled)
        self.channel["_syncing_from_psu"] = False


def create_psu_channel_card(
    state: dict[str, Any],
    *,
    key: str,
    title: str,
    color: str,
    mode_limits: dict[str, tuple[float, float]],
    live_voltage_key: str,
    live_current_key: str,
    replay_channel_by_mode: dict[str, str | list[str]] | None = None,
) -> PsuChannelController:
    """Create a PSU channel card with a plot and enable switch."""
    channel = state.setdefault("channels", {}).setdefault(key, {"enabled": True})
    # Refresh card-channel config from current code while preserving runtime UI state.
    channel["live_voltage_key"] = live_voltage_key
    channel["live_current_key"] = live_current_key
    channel["replay_channel_by_mode"] = replay_channel_by_mode or {"OB": "CH3", "EB": "CH3"}
    channel["status_key"] = {
        "psu_ch1": "CH1_STATUS",
        "psu_ch2": "CH2_STATUS",
        "psu_ch3": "CH3_STATUS",
        "psu_ch4": "CH4_STATUS",
    }.get(key)
    channel.setdefault("_syncing_from_psu", False)

    def _on_toggle(e: Any) -> None:
        enabled = bool(e.value)
        channel["enabled"] = enabled

        if channel.get("_syncing_from_psu"):
            return

        port = state.get("psu_port")
        psu_lock = state.get("psu_lock")
        if not port:
            return

        channel_map = {"psu_ch1": 1, "psu_ch2": 2, "psu_ch3": 3, "psu_ch4": 4}
        physical_channel = channel_map.get(key)
        if physical_channel is None:
            return

        # In EB mode, CH1/CH2 are not part of the active PSU profile.
        mode = state.get("mode")
        if mode == "EB" and physical_channel in (1, 2):
            return

        from contextlib import nullcontext

        lock_ctx = psu_lock if psu_lock is not None else nullcontext()
        with lock_ctx:
            psu.switch_psu_channel(port, channel=physical_channel, state=enabled)

    with ui.card().classes("flex-1 min-w-0") as card:
        title_label = ui.label(title).classes("text-sm font-bold")
        enabled_switch = ui.switch(
            "Enabled",
            value=bool(channel["enabled"]),
            on_change=_on_toggle,
        )
        value_label = ui.label("mA: ---")
        plot = plot_widget.create_plot_card(
            title,
            series=[plot_widget.SeriesConfig(label="mA", color=color)],
            y_label="mA",
            mode_limits=mode_limits,
            show_title=False,
            plot_height_class="h-40",
            show_legend=True,
        )

    state["plot_refreshers"].append(plot.set_mode)
    plot.set_mode(state["mode"])
    return PsuChannelController(
        channel=channel,
        title_label=title_label,
        value_label=value_label,
        plot=plot,
        card=card,
        enabled_switch=enabled_switch,
    )
