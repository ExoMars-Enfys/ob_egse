# Widget Reuse Refactor Plan

Goal: move UI logic out of `ebgui.py` so each widget is reusable in any GUI instance.

## Quick Start

If you only do three things first:
1. Move log UI + log handler to `log_terminal_widget.py`.
2. Move splash/flags dialogs to `popup_widget.py`.
3. Move OB/EB alarm lights + alarm dialog/state to `traffic_light_widget.py`.

This gives a big size reduction in `ebgui.py` with low risk.

## Move Matrix (What goes where)

| Target file | Move from `ebgui.py` | Keep this widget responsible for |
|---|---|---|
| `parent_window_widget.py` | `index()` shell layout, drawers, sticky action container | Page skeleton only (containers/slots), no packet logic |
| `menu_widget.py` | Menu/action buttons (start/stop tools, select folder/script/log, toggle controls) | Button rendering + callback wiring only |
| `log_terminal_widget.py` | `LogElementHandler`, footer log area, log mode switch, EGSE log refresh | All log display behavior |
| `packet_viewer_widget.py` | HK/POST/SCI tabs, manual checks, SCI navigation helpers | Packet display and packet-level UX |
| `plot_widget.py` | Plot creation, plot theme updates, unit-dependent plot labels/limits | All plotting and plot updates |
| `psu_widget.py` | PSU toggles/cards and PSU readout updates | PSU controls + PSU status presentation |
| `traffic_light_widget.py` | OB/EB lights, alarm formatting/state/history/clear dialog | Alarm lifecycle and alarm UI |
| `popup_widget.py` | Splash dialog and generic flags/details dialogs | Reusable dialogs (except alarm dialog) |
| `file_dialog_window_widget.py` | Dialog wrappers (folder/file selection) | File/folder picker helpers |

## Exact Anchors in `ebgui.py`

Use these line anchors while extracting code:
- Alarm details/state: lines near 291, 404, 413, 467
- Plot theme + units: lines near 483, 503, 525, 548, 568
- Manual HK/POST checks: lines near 616, 721
- SCI helpers + panel + plot: lines near 843-1009
- Main polling update loop: line near 1036
- Splash dialog: lines near 1903-1918
- Log footer and refresh: lines near 1926-1956
- Right drawer status area: line near 1975
- Left drawer menu/packet tabs: lines near 2261, 2285
- PSU controls/plots: lines near 2627, 2670+
- Alarm/flags dialogs: lines near 2770, 2788, 2850
- Sticky actions: line near 2902

## What stays in `ebgui.py`

After refactor, `ebgui.py` should only do:
- app/page bootstrap
- dependency wiring (logger, ports, lock, stop event)
- queue polling orchestration (or delegate to controller)
- connect widgets together

`ebgui.py` should not build individual chips/plots/tabs directly.

## Reusability Rules (Strict)

- Widgets do not read global queues directly.
- Widgets do not call tools/process/file APIs directly.
- Widgets receive data and callbacks via constructor/build args.
- Widgets expose explicit update methods.
- Keep widget state local and minimal.

## Suggested Widget APIs (Compact)

- `build_parent_window(config, callbacks) -> ParentWindowRefs`
- `build_menu_widget(actions, state) -> MenuWidget`
- `build_log_terminal(level_options, logger) -> LogTerminalWidget`
- `build_packet_viewer(...) -> PacketViewerWidget`
- `build_plot_panel(config) -> PlotWidget`
- `build_psu_widget(on_toggle_channel) -> PsuWidget`
- `build_traffic_lights(...) -> TrafficLightWidget`
- `build_splash_dialog(...)`, `build_flags_dialog(...)`

## Migration Order (Low Risk)

1. `log_terminal_widget.py`
2. `popup_widget.py`
3. `traffic_light_widget.py`
4. `psu_widget.py`
5. `plot_widget.py`
6. `packet_viewer_widget.py`
7. `menu_widget.py`
8. `parent_window_widget.py`
9. trim `ebgui.py` to composition only

## Optional Next Improvement

Extract pure mapping/format logic into helpers:
- `view_models/hk_mapper.py`
- `view_models/post_mapper.py`
- `view_models/alarm_mapper.py`

This keeps widgets simple and highly reusable.
