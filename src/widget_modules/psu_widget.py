from __future__ import annotations

# Std library
from collections import deque
from dataclasses import dataclass
import logging
import time
from typing import Any

# Added packages
from nicegui import run, ui

# Local modules
# utilities
from utility_modules import eb_interface, ebtcs
from utility_modules import psu

# widgets
from widget_modules import plot_widget


info_log = logging.getLogger("info_log")


def _safe_get_client(element: Any) -> Any | None:
    """Return the client's object if it still exists, otherwise None."""
    if element is None:
        return None
    try:
        return getattr(element, "client")
    except Exception:
        return None


def is_ui_element_alive(element: Any) -> bool:
    """Return True only when a NiceGUI element still belongs to a live client."""
    if element is None:
        return False
    return _safe_get_client(element) is not None


def try_set_element_value(element: Any, value: Any) -> bool:
    """Attempt to set a NiceGUI value only when the element still belongs to a live client."""
    if not is_ui_element_alive(element):
        return False
    try:
        element.value = value
        return True
    except Exception:
        return False


def set_component_busy(component: Any, busy: bool) -> None:
    if component is None or not is_ui_element_alive(component):
        return
    for method_name in ("disable", "enable"):
        method = getattr(component, method_name, None)
        if callable(method):
            if (busy and method_name == "disable") or ((not busy) and method_name == "enable"):
                method()
                return
    # Fallback for components without helper methods.
    try:
        component.props("disable" if busy else "")
    except Exception:
        pass


def title_hides_plot(title: str) -> bool:
    """Return True when the PSU title indicates a ROV HTR channel."""
    normalized = "".join(ch for ch in str(title).lower() if ch.isalnum())
    return "rovhtr" in normalized


def title_shows_lisn(title: str) -> bool:
    """Return True when the PSU title indicates the +28V profile."""
    normalized = "".join(ch for ch in str(title).lower() if ch.isalnum())
    return "28v" in normalized


def _is_eb_mode(state: dict[str, Any]) -> bool:
    if str(state.get("mode", "")).upper() == "EB":
        return True
    psu_mode_state = state.get("psu_mode_state")
    return bool(isinstance(psu_mode_state, dict) and psu_mode_state.get("ebmode"))


def should_send_ret_tc_for_eb_enable(mode: str | None, enabled: bool, physical_channel: int | None) -> bool:
    """Return True when an EB-mode PSU enable should trigger an immediate RET TC."""
    return bool(str(mode).upper() == "EB" and enabled and physical_channel in {3, 4})


def emit_eb_ret_tc_for_psu_toggle(state: dict[str, Any], *, enabled: bool, physical_channel: int | None) -> None:
    """Send an immediate RET TC when enabling PSU channels in EB mode."""
    if not (_is_eb_mode(state) and bool(enabled) and physical_channel in {3, 4}):
        return

    try:
        interface = eb_interface.get_egse_interface()
    except Exception as exc:
        info_log.warning(f"Unable to resolve EGSE interface for EB RET after PSU enable: {exc}")
        return

    if interface is None:
        info_log.warning("EGSE interface unavailable for EB RET after PSU enable")
        return

    try:
        result = ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
        if result == "ERROR":
            info_log.warning("EB RET TC returned ERROR after PSU enable")
    except Exception as exc:
        info_log.warning(f"Failed to send EB RET TC after PSU enable: {exc}")
        return


@dataclass
class PsuChannelController:
    channel: dict[str, Any]
    title_label: Any
    status_dot: Any
    status_label: Any
    value_label: Any
    plot: plot_widget.PlotCardController
    card: Any
    enabled_switch: Any
    plot_container: Any | None = None
    lisn_toggle: Any | None = None
    ma_window_samples: int = 5
    ma_buffer: Any = None

    def __post_init__(self) -> None:
        self.ma_buffer = deque(maxlen=max(1, int(self.ma_window_samples)))

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
        show_enabled_toggle: bool | None = None,
        show_lisn_toggle: bool | None = None,
    ) -> None:
        self.title_label.set_text(title)
        self.plot.set_series_labels([title])
        hide_plot = title_hides_plot(title)
        show_lisn_by_title = title_shows_lisn(title)
        if self.plot_container is not None:
            if hide_plot:
                self.plot_container.classes(add="hidden")
            else:
                self.plot_container.classes(remove="hidden")
        if hide_plot:
            self.card.classes(remove="flex-1")
            self.card.classes(add="shrink-0")
        else:
            self.card.classes(remove="shrink-0")
            self.card.classes(add="flex-1")
        self.channel["live_voltage_key"] = live_voltage_key
        self.channel["live_current_key"] = live_current_key
        self.channel["replay_channel_by_mode"] = {"OB": replay_channels, "EB": replay_channels}
        self.ma_buffer.clear()
        if show_enabled_toggle is not None and self.enabled_switch is not None:
            self.enabled_switch.set_visibility(bool(show_enabled_toggle))
        if self.lisn_toggle is not None:
            if show_lisn_toggle is not None:
                self.lisn_toggle.set_visibility(bool(show_lisn_toggle) and show_lisn_by_title)
            else:
                self.lisn_toggle.set_visibility(show_lisn_by_title)
        self.set_visible(visible)

    def push_sample(self, time_value: Any, current_a: float | None) -> None:
        """Push a new sample to the channel's plot and update the value label.

        A fixed 5-sample moving average is plotted to smooth high-rate PSU current
        samples before display updates.
        """
        self.ingest_sample(current_a)
        self.push_smoothed(time_value)

    def ingest_sample(self, current_a: float | None) -> None:
        """Ingest one raw current sample into the moving-average buffer."""
        if current_a is None:
            return
        current_ma = float(current_a) * 1000.0
        self.ma_buffer.append(current_ma)
        averaged_ma = sum(self.ma_buffer) / len(self.ma_buffer)
        self.value_label.set_text(f"mA: {averaged_ma:.1f}")

    def push_smoothed(self, time_value: Any) -> None:
        """Push the current moving-average value to the plot."""
        if not self.ma_buffer:
            return
        averaged_ma = sum(self.ma_buffer) / len(self.ma_buffer)
        self.plot.push([time_value], [[averaged_ma]])

    def set_status_indicator(self, enabled: bool) -> None:
        if enabled:
            self.status_dot.style("color: var(--status-ok);")
            self.status_label.set_text("ON")
            self.status_label.style("color: var(--status-ok);")
        else:
            self.status_dot.style("color: var(--status-alarm);")
            self.status_label.set_text("OFF")
            self.status_label.style("color: var(--status-alarm);")

    def set_enabled_from_psu(self, enabled: bool) -> None:
        """Synchronize UI switch state from live PSU status without issuing commands."""
        # After a user toggle, allow hardware/readback to settle briefly before
        # accepting contradictory status samples that can cause UI bounce.
        pending_target = self.channel.get("_pending_toggle_target")
        pending_until = float(self.channel.get("_pending_toggle_until", 0.0) or 0.0)
        now = time.monotonic()
        if pending_target is not None and now < pending_until:
            if bool(enabled) != bool(pending_target):
                return

        if pending_target is not None and (now >= pending_until or bool(enabled) == bool(pending_target)):
            self.channel["_pending_toggle_target"] = None
            self.channel["_pending_toggle_until"] = 0.0

        self.channel["enabled"] = enabled
        self.set_status_indicator(bool(enabled))
        if bool(getattr(self.enabled_switch, "value", False)) == bool(enabled):
            return
        self.channel["_suppress_toggle_events"] = int(self.channel.get("_suppress_toggle_events", 0) or 0) + 1
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
    enabled_switch: Any | None = None,
    replay_channel_by_mode: dict[str, str | list[str]] | None = None,
) -> PsuChannelController:
    """Create a PSU channel card with a plot and enable switch."""
    channel = state.setdefault("channels", {}).setdefault(key, {"enabled": False})
    # Keep LISN toggle state per-card; visibility is controlled by profile title.
    channel.setdefault("lisn_check_enabled", False)
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
    channel.setdefault("_suppress_toggle_events", 0)
    channel.setdefault("_pending_toggle_target", None)
    channel.setdefault("_pending_toggle_until", 0.0)
    channel.setdefault("_toggle_in_flight", False)
    channel.setdefault("_last_requested_state", None)

    async def on_toggle(e: Any) -> None:
        enabled = bool(e.value)
        suppress_count = int(channel.get("_suppress_toggle_events", 0) or 0)
        if suppress_count > 0:
            channel["_suppress_toggle_events"] = suppress_count - 1
            return

        if channel.get("_syncing_from_psu"):
            return

        # Defensive de-duplication: if the UI fires duplicate change events for
        # the same target state while a command is already in flight, ignore it.
        if channel.get("_toggle_in_flight") and channel.get("_last_requested_state") == enabled:
            return

        channel["enabled"] = enabled
        channel["_pending_toggle_target"] = enabled
        channel["_pending_toggle_until"] = time.monotonic() + 0.8
        channel["_last_requested_state"] = enabled

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

        # Block re-enabling channels while the MMS/protection latch is active.
        if enabled and state.get("ob_psu_protection", {}).get("shutdown_latched", False):
            ui.notify("PSU is latched after a protection trip — reset the latch first.", type="warning")
            channel["_suppress_toggle_events"] = int(channel.get("_suppress_toggle_events", 0) or 0) + 1
            if enabled_switch is not None:
                enabled_switch.value = False
            return

        set_component_busy(enabled_switch, True)
        mode_state = state.get("psu_mode_state") if isinstance(state.get("psu_mode_state"), dict) else state
        psu.set_psu_command_in_flight(mode_state, True)
        channel["_toggle_in_flight"] = True

        def apply_toggle() -> None:
            from contextlib import nullcontext

            lock_ctx = psu_lock if psu_lock is not None else nullcontext()
            with lock_ctx:
                psu.switch_psu_channel(port, channel=physical_channel, state=enabled, mode_state=mode_state)

        try:
            await run.io_bound(apply_toggle)
            if should_send_ret_tc_for_eb_enable(mode, enabled, physical_channel):
                emit_eb_ret_tc_for_psu_toggle(
                    state,
                    enabled=enabled,
                    physical_channel=physical_channel,
                )
        finally:
            channel["_toggle_in_flight"] = False
            psu.set_psu_command_in_flight(mode_state, False)
            set_component_busy(enabled_switch, False)

    def on_lisn_toggle(e: Any) -> None:
        channel["lisn_check_enabled"] = bool(e.value)

    lisn_toggle: Any | None = None

    with ui.card().classes("w-full flex-1 min-w-0 egse-psu-card") as card:
        with ui.row().classes("w-full"):
            with ui.column().style("flex: 1; justify-content: flex-left;"):
                with ui.row().classes("items-center gap-2"):
                    title_label = ui.label(title).classes("font-bold egse-title")
                    title_label.style("padding-left: 0.5rem;")
                    status_dot = ui.icon("circle").classes("text-xs")
                    status_label = ui.label("OFF").classes("egse-metric-label")
                    status_dot.style("color: var(--status-alarm);")
                    status_label.style("color: var(--status-alarm);")
            with ui.column().style("flex: 1; justify-content: flex-centre;"):
                if enabled_switch is not None:
                    enabled_switch = ui.switch(
                        "Enabled",
                        value=bool(channel["enabled"]),
                        on_change=on_toggle,
                    )
            with ui.column().style("flex: 1; justify-content: flex-centre;"):
                lisn_toggle = ui.switch(
                    "LISN check",
                    value=bool(channel["lisn_check_enabled"]),
                    on_change=on_lisn_toggle,
                ).classes("ml-2")
                lisn_toggle.set_visibility(title_shows_lisn(title))
            with ui.column().style("flex: 1; justify-content: flex-end;"):
                value_label = ui.label("mA: ---").classes("self-center text-xl text-right")
        with ui.row().classes("w-full") as plot_container:
            plot = plot_widget.create_plot_card(
                title,
                series=[plot_widget.SeriesConfig(label="mA", color=color)],
                y_label="mA",
                mode_limits=mode_limits,
                show_title=False,
                plot_height_class="h-40",
                show_legend=True,
                use_card_wrapper=False,
            )

        if title_hides_plot(title):
            plot_container.classes(add="hidden")
            card.classes(remove="flex-1")
            card.classes(add="shrink-0")

    state["plot_refreshers"].append(plot.set_mode)
    plot.set_mode(state["mode"])
    return PsuChannelController(
        channel=channel,
        title_label=title_label,
        status_dot=status_dot,
        status_label=status_label,
        value_label=value_label,
        plot=plot,
        card=card,
        enabled_switch=enabled_switch,
        plot_container=plot_container,
        lisn_toggle=lisn_toggle,
    )


def create_voltage_mode_selector(
    state: dict[str, Any],
) -> Any:
    """Create a voltage mode selector (MIN/NOM/MAX) for PSU channels."""
    # Initialize voltage mode in state if not already present
    state.setdefault("voltage_mode", "NOM")

    async def on_voltage_mode_change(e: Any) -> None:
        """Handle voltage mode change and apply to PSU."""
        new_mode = e.value
        state["voltage_mode"] = new_mode
        psu_mode_state = state.get("psu_mode_state")
        if isinstance(psu_mode_state, dict):
            psu_mode_state["voltage_mode"] = new_mode

        port = state.get("psu_port")
        psu_lock = state.get("psu_lock")
        if not port:
            return

        def apply_voltage_mode() -> None:
            from contextlib import nullcontext

            lock_ctx = psu_lock if psu_lock is not None else nullcontext()
            with lock_ctx:
                psu.apply_voltage_mode(port, new_mode, state.get("mode", "OB"))

        await run.io_bound(apply_voltage_mode)

    with ui.card().classes("w-full flex-1 min-w-0") as card:
        ui.label("Bus Voltage Mode").classes("font-bold egse-title")
        voltage_selector = ui.select(
            options=["MIN", "NOM", "MAX"],
            value=state.get("voltage_mode", "NOM"),
            on_change=on_voltage_mode_change,
        ).classes("w-full")

    return {"card": card, "selector": voltage_selector}


def create_ob_master_channels_toggle(
    state: dict[str, Any],
) -> tuple[Any, Any, Any]:
    """Create OB-only master toggle for CH1-CH3 and return mode/value sync callbacks."""
    cards_ref: dict[str, tuple[PsuChannelController, PsuChannelController, PsuChannelController] | None] = {
        "cards": None
    }
    master_sync_state = {"syncing": False}

    with ui.row().classes("w-full"):
        ob_master_toggle = ui.switch(
            "OB PSU Channels (CH1-CH3)",
            value=False,
        )

    def set_visible(mode: str) -> None:
        if not is_ui_element_alive(ob_master_toggle):
            return
        ob_master_toggle.set_visibility(mode == "OB")

    def sync_value(_: Any | None = None) -> None:
        cards = cards_ref.get("cards")
        if cards is None or not is_ui_element_alive(ob_master_toggle):
            return
        enabled_all = all(bool(card.channel.get("enabled", True)) for card in cards)
        if bool(getattr(ob_master_toggle, "value", False)) == bool(enabled_all):
            return
        master_sync_state["suppress_next_event"] = True
        master_sync_state["syncing"] = True
        try:
            if not try_set_element_value(ob_master_toggle, enabled_all):
                return
        finally:
            master_sync_state["syncing"] = False

    async def on_change(e: Any) -> None:
        if master_sync_state.get("suppress_next_event"):
            master_sync_state["suppress_next_event"] = False
            return
        if master_sync_state["syncing"]:
            return
        if not is_ui_element_alive(ob_master_toggle):
            return
        cards = cards_ref.get("cards")
        if cards is None:
            return
        enabled = bool(e.value)
        enabled_all = all(bool(card.channel.get("enabled", True)) for card in cards)
        if enabled == enabled_all:
            # Programmatic sync can emit value-change events; ignore no-op transitions.
            return
        for card in cards:
            card.channel["enabled"] = enabled
            if card.enabled_switch is not None:
                current = bool(getattr(card.enabled_switch, "value", False))
                if current != enabled:
                    card.channel["_suppress_toggle_events"] = (
                        int(card.channel.get("_suppress_toggle_events", 0) or 0) + 1
                    )
                    card.channel["_syncing_from_psu"] = True
                    try:
                        if is_ui_element_alive(card.enabled_switch):
                            card.enabled_switch.value = enabled
                    except Exception:
                        pass
                    card.channel["_syncing_from_psu"] = False

        psu_port = state.get("psu_port")
        psu_lock = state.get("psu_lock")
        if not psu_port:
            return

        # Block re-enabling channels while the MMS/protection latch is active.
        if enabled and state.get("ob_psu_protection", {}).get("shutdown_latched", False):
            try:
                ui.notify("PSU is latched after a protection trip — reset the latch first.", type="warning")
            except Exception:
                pass
            if not try_set_element_value(ob_master_toggle, False):
                return
            return
        mode_state = state.get("psu_mode_state") if isinstance(state.get("psu_mode_state"), dict) else state
        psu.set_psu_command_in_flight(mode_state, True)

        def apply_master_toggle() -> None:
            from contextlib import nullcontext

            lock_ctx = psu_lock if psu_lock is not None else nullcontext()
            with lock_ctx:
                for channel_idx in (1, 2, 3):
                    psu.switch_psu_channel(psu_port, channel=channel_idx, state=enabled, mode_state=mode_state)

        try:
            await run.io_bound(apply_master_toggle)
        finally:
            psu.set_psu_command_in_flight(mode_state, False)
            set_component_busy(ob_master_toggle, False)

    def bind_cards(
        ch1_card: PsuChannelController,
        ch2_card: PsuChannelController,
        ch3_card: PsuChannelController,
    ) -> None:
        cards_ref["cards"] = (ch1_card, ch2_card, ch3_card)
        for card in cards_ref["cards"]:
            card.channel["enabled"] = False
            if card.enabled_switch is not None:
                current = bool(getattr(card.enabled_switch, "value", False))
                if current:
                    card.channel["_suppress_toggle_events"] = (
                        int(card.channel.get("_suppress_toggle_events", 0) or 0) + 1
                    )
                    card.channel["_syncing_from_psu"] = True
                    try:
                        if is_ui_element_alive(card.enabled_switch):
                            card.enabled_switch.value = False
                    except Exception:
                        pass
                    card.channel["_syncing_from_psu"] = False
        sync_value()

    ob_master_toggle.on_value_change(on_change)
    set_visible(state.get("mode", "OB"))
    return set_visible, sync_value, bind_cards
