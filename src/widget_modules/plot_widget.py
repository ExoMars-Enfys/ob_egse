from __future__ import annotations

import datetime as dt
import weakref

# Std library
from dataclasses import dataclass
from typing import Any, Callable

import matplotlib.pyplot as plt
from matplotlib import dates as mdates
from matplotlib import ticker
from matplotlib.collections import LineCollection

# Added packages
from nicegui import app, ui


@dataclass
class SeriesConfig:
    """Configuration for a single plotted series.

    ``modes`` restricts the series to selected EGSE modes. ``None`` means the
    series is available in both OB and EB.
    """

    label: str
    color: str
    visible: bool = True
    modes: tuple[str, ...] | None = None


@dataclass(frozen=True)
class LimitBandConfig:
    """Warning/alarm bounds rendered as horizontal dashed reference lines.

    ``warning_limits`` and ``alarm_limits`` are nested mappings of
    ``EGSE mode -> display mode -> (low, high)``.  Use ``"*"`` as the EGSE
    mode key when the same limits apply in both OB and EB modes.
    """

    label: str
    warning_limits: dict[str, dict[str, tuple[float, float]]]
    alarm_limits: dict[str, dict[str, tuple[float, float]]]
    warning_color: str = "#f59e0b"
    alarm_color: str = "#ef4444"
    visible: bool = True


@dataclass
class PlotCardController:
    card: Any
    plot: Any
    set_mode: Callable[[str], None]
    set_display_mode: Callable[[str], None]
    push: Callable[[list[Any], list[list[float]]], None]
    set_series_labels: Callable[[list[str]], None]
    set_stream_enabled: Callable[[bool], None]
    close: Callable[[], None]


def create_plot_card(
    title: str,
    *,
    series: list[SeriesConfig],
    y_label: str = "",
    y_limits: tuple[float, float] | None = None,
    mode_limits: dict[str, tuple[float, float]] | None = None,
    display_limits: dict[str, tuple[float, float]] | None = None,
    limit_bands: list[LimitBandConfig] | None = None,
    limit: int = 240,
    show_toggles: bool = False,
    show_title: bool = True,
    plot_height_class: str = "h-60",
    show_legend: bool | None = None,
    use_card_wrapper: bool = True,
) -> PlotCardController:
    """Create a generic plot card.

    Args:
        title: Card title.
        series: One entry per plotted line, each with a label and colour.
        y_label: Y-axis label (e.g. "mA", "°C", "V").
        y_limits: Fixed (ymin, ymax) applied at creation.  Ignored when
            *mode_limits* provides a value for the current mode.
        mode_limits: Optional per-mode (ymin, ymax) updated by set_mode().
        display_limits: Optional REAL/ADU axis limits updated by
            set_display_mode(). These take priority over mode_limits.
        limit_bands: Warning/alarm bands rendered as horizontal dashed lines.
        limit: Number of x-points to keep in the rolling window.
        show_toggles: When True, renders a per-series checkbox row inside the
            card so individual series can be shown or hidden at runtime.
        show_title: When False, suppresses both card and axis titles.
        plot_height_class: Tailwind height class for the plot area.
        show_legend: Force legend visibility. Defaults to visible when
            there is more than one series.
    n_series = len(series)

    """
    # Keep requested card height class unchanged; only tune figure size.
    _DEFAULT_FIG_HEIGHT = 4.2
    _DEFAULT_FIG_HEIGHT_H40 = 3.2

    n_series = len(series)
    series_user_visible = [bool(cfg.visible) for cfg in series]
    series_modes: list[set[str] | None] = []
    for cfg in series:
        if cfg.modes is None:
            series_modes.append(None)
            continue
        normalized = {str(mode).upper() for mode in cfg.modes if str(mode).upper() in {"OB", "EB"}}
        series_modes.append(normalized)

    # Theme-aware sizes helper (use centralized helpers)
    from utility_modules import app_theme

    palette = getattr(app.state, "theme_palette", None)
    plot_font_pt = app_theme.font_size_px(palette.get("plot_font_size") if isinstance(palette, dict) else None)
    plot_tick_pt = app_theme.font_size_px(palette.get("plot_tick_size") if isinstance(palette, dict) else None)
    plot_footer_pt = app_theme.font_size_px(palette.get("plot_footer_size") if isinstance(palette, dict) else None)

    def _palette_float(key: str, default: float) -> float:
        if not isinstance(palette, dict):
            return default
        raw = palette.get(key)
        try:
            return float(raw) if raw is not None else default
        except (TypeError, ValueError):
            return default

    fig_height_h40 = _palette_float("plot_fig_height_h40", _DEFAULT_FIG_HEIGHT_H40)
    fig_height_h60 = _palette_float("plot_fig_height_h60", _DEFAULT_FIG_HEIGHT)
    _FIGSIZE_BY_HEIGHT = {
        "h-40": (14.0, fig_height_h40),
        "h-60": (14.0, fig_height_h60),
    }
    _figsize = _FIGSIZE_BY_HEIGHT.get(plot_height_class, (14.0, fig_height_h60))
    try:
        raw_linewidth = palette.get("plot_linewidth") if isinstance(palette, dict) else None
        plot_linewidth = float(raw_linewidth) if raw_linewidth is not None else 1.0
    except (TypeError, ValueError):
        plot_linewidth = 1.0

    container_factory = ui.card if use_card_wrapper else ui.column
    container_classes = "w-full flex-1 min-w-0"
    if use_card_wrapper:
        container_classes += " egse-plot-card"
    with container_factory().classes(container_classes) as card:
        title_label: Any | None = None
        if show_title:
            title_label = ui.label(title)
            title_label.classes("font-bold pl-3 egse-title")

        checkboxes: list[Any] = []
        if show_toggles:
            with ui.row().classes("w-full flex-wrap gap-x-4 gap-y-1"):
                for cfg in series:
                    cb = ui.checkbox(cfg.label, value=cfg.visible).props(
                        f'checked-icon="radio_button_checked" unchecked-icon="radio_button_unchecked" keep-color color="{cfg.color}"'
                    )
                    cb.classes("egse-text")
                    cb.style(f"color: {cfg.color}")
                    checkboxes.append(cb)

        plot = (
            ui.line_plot(n=n_series, limit=limit, figsize=_figsize)
            .classes("w-full self-start")
            .style("width: 100%; min-width: 0; max-width: 100%; height: auto;")
        )

    # access matplotlib axes/figure
    ax = plot.fig.axes[0]
    fig = plot.fig

    closed_state = {"done": False}

    def close_plot() -> None:
        if closed_state["done"]:
            return
        closed_state["done"] = True
        try:
            plt.close(fig)
        except Exception:
            pass

    weakref.finalize(plot, close_plot)

    # X-axis: show minutes:seconds:milliseconds on ticks
    def _fmt_x_tick(x, pos):
        try:
            dt = mdates.num2date(x)
            return f"{dt.strftime('%M:%S')}"
        except Exception:
            return ""

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_x_tick))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    # let the global theme control grid color/width/alpha
    ax.grid(True, which="major")
    ax.tick_params(labelsize=(plot_tick_pt or 11))

    current_mode = str(getattr(app.state, "egse_mode", "EB") or "EB").upper()
    if current_mode not in {"OB", "EB"}:
        current_mode = "EB"

    lines = list(ax.lines)
    for index, (line, cfg) in enumerate(zip(lines, series)):
        line.set_color(cfg.color)
        allowed_modes = series_modes[index]
        allowed = allowed_modes is None or current_mode in allowed_modes
        line.set_visible(series_user_visible[index] and allowed)
        line.set_linewidth(plot_linewidth)
        line.set_marker("*")
        line.set_markersize(8)

    current_display_mode = str(getattr(app.state, "hk_display_mode", "REAL") or "REAL").upper()
    if current_display_mode not in {"REAL", "ADU"}:
        current_display_mode = "REAL"

    def _resolve_limit_bounds(
        mapping: dict[str, dict[str, tuple[float, float]]],
        mode: str,
        display_mode: str,
    ) -> tuple[float, float] | None:
        by_display = mapping.get(mode) or mapping.get("*")
        if not by_display:
            return None
        bounds = by_display.get(display_mode) or by_display.get("*")
        if bounds is None or len(bounds) != 2:
            return None
        try:
            return float(bounds[0]), float(bounds[1])
        except (TypeError, ValueError):
            return None

    # Keep limit artists separate from ``ax.lines``. NiceGUI's line plot owns
    # those entries as its live telemetry series, so reference artists are added
    # as LineCollections instead of normal lines.
    def _make_reference_line(*, color: str, linewidth: float, alpha: float) -> LineCollection:
        artist = LineCollection(
            [[(0.0, 0.0), (1.0, 0.0)]],
            transform=ax.get_yaxis_transform(),
            colors=[color],
            linestyles=["--"],
            linewidths=[linewidth],
            alpha=alpha,
            zorder=1,
        )
        ax.add_collection(artist, autolim=False)
        return artist

    limit_line_groups: list[dict[str, Any]] = []
    for band in limit_bands or []:
        warning_low = _make_reference_line(
            color=band.warning_color,
            linewidth=max(1.0, plot_linewidth),
            alpha=0.9,
        )
        warning_high = _make_reference_line(
            color=band.warning_color,
            linewidth=max(1.0, plot_linewidth),
            alpha=0.9,
        )
        alarm_low = _make_reference_line(
            color=band.alarm_color,
            linewidth=max(1.3, plot_linewidth + 0.3),
            alpha=0.95,
        )
        alarm_high = _make_reference_line(
            color=band.alarm_color,
            linewidth=max(1.3, plot_linewidth + 0.3),
            alpha=0.95,
        )
        for artist in (warning_low, warning_high, alarm_low, alarm_high):
            artist.set_visible(False)
        limit_line_groups.append(
            {
                "config": band,
                "warning": (warning_low, warning_high),
                "alarm": (alarm_low, alarm_high),
            }
        )

    def _selected_y_limits() -> tuple[float, float] | None:
        if display_limits is not None and current_display_mode in display_limits:
            return display_limits[current_display_mode]
        if mode_limits is not None and current_mode in mode_limits:
            return mode_limits[current_mode]
        return y_limits

    active_y_limits = _selected_y_limits()

    def _update_limit_lines() -> None:
        for group in limit_line_groups:
            band: LimitBandConfig = group["config"]
            warning_bounds = _resolve_limit_bounds(band.warning_limits, current_mode, current_display_mode)
            alarm_bounds = _resolve_limit_bounds(band.alarm_limits, current_mode, current_display_mode)

            for severity, bounds in (("warning", warning_bounds), ("alarm", alarm_bounds)):
                low_line, high_line = group[severity]
                visible = bool(band.visible and bounds is not None)
                low_line.set_visible(visible)
                high_line.set_visible(visible)
                if not visible or bounds is None:
                    continue
                low, high = bounds
                low_line.set_segments([[(0.0, low), (1.0, low)]])
                high_line.set_segments([[(0.0, high), (1.0, high)]])

    def _series_allowed(index: int) -> bool:
        allowed_modes = series_modes[index]
        return allowed_modes is None or current_mode in allowed_modes

    def _apply_series_visibility() -> None:
        for index, line in enumerate(lines):
            allowed = _series_allowed(index)
            line.set_visible(series_user_visible[index] and allowed)
            if index < len(checkboxes):
                checkbox = checkboxes[index]
                set_visibility = getattr(checkbox, "set_visibility", None)
                if callable(set_visibility):
                    set_visibility(allowed)

    legend_visible = (n_series > 1) if show_legend is None else bool(show_legend)
    series_labels = [cfg.label for cfg in series]

    def _apply_footer_style() -> None:
        """Apply theme-aware color and size to the footer text."""
        try:
            palette = getattr(app.state, "theme_palette", None)
            # determine color
            color = None
            size = None
            if isinstance(palette, dict):
                color = palette.get("plot_footer") or palette.get("plot_legend")
                size = palette.get("plot_footer_size")

            if size is None:
                # derive from axis tick label size if available
                try:
                    ticks = ax.xaxis.get_ticklabels()
                    if ticks:
                        size = ticks[0].get_fontsize()
                    else:
                        size = 12
                except Exception:
                    size = 12
            if color is not None:
                footer_text_right.set_color(color)
            # Use centralized parser to get numeric pt value for matplotlib
            numeric = app_theme.font_size_px(size)
            if numeric is not None:
                try:
                    footer_text_right.set_fontsize(numeric)
                except Exception:
                    pass
        except Exception:
            # ignore styling errors
            pass

    def _redraw_plot() -> None:
        ax.yaxis.set_major_locator(ticker.MaxNLocator(6))

        # redraw grid using theme-controlled styling
        ax.grid(True, which="major")
        _apply_footer_style()
        _update_footer_time()
        plot.fig.canvas.draw_idle()
        plot.fig.canvas.draw()
        convert = getattr(plot, "_convert_to_html", None)
        if callable(convert):
            convert()
        plot.update()

    def _style_legend() -> None:
        legend = ax.get_legend()
        palette = getattr(app.state, "theme_palette", None)
        if legend is None or not isinstance(palette, dict):
            return
        frame = legend.get_frame()
        frame.set_facecolor(palette.get("plot_bg"))
        frame.set_edgecolor(palette.get("plot_spine"))
        legend_color = palette.get("plot_legend")
        if isinstance(legend_color, str):
            for text in legend.get_texts():
                text.set_color(legend_color)

    def _refresh_legend() -> None:
        legend = ax.get_legend()
        if legend is not None:
            legend.remove()

        if legend_visible:
            handles: list[Any] = []
            labels: list[str] = []
            for idx, line in enumerate(lines):
                if not line.get_visible():
                    continue
                handles.append(line)
                labels.append(series_labels[idx] if idx < len(series_labels) else line.get_label())

            # One legend entry per warning/alarm pair; the low and high dashed
            # artists deliberately share that single description.
            for group in limit_line_groups:
                band: LimitBandConfig = group["config"]
                warning_high = group["warning"][1]
                alarm_high = group["alarm"][1]
                if warning_high.get_visible():
                    handles.append(warning_high)
                    labels.append(f"{band.label} warning")
                if alarm_high.get_visible():
                    handles.append(alarm_high)
                    labels.append(f"{band.label} alarm")

            if handles:
                ax.legend(handles, labels, loc="upper left", fontsize=(plot_font_pt or 11))
                _style_legend()

        _redraw_plot()

    def _set_legend(labels: list[str]) -> None:
        nonlocal series_labels
        series_labels = list(labels)
        _refresh_legend()

    stream_enabled = True

    def _reset_series() -> None:
        for line in lines:
            line.set_data([], [])
        ax.relim()
        ax.autoscale_view(scalex=True, scaley=False)
        _redraw_plot()

    if active_y_limits is not None:
        ax.set_ylim(*active_y_limits)
    ax.set_ylabel("ADU" if current_display_mode == "ADU" else y_label)
    _update_limit_lines()
    top = 0.92 if show_title else 0.98
    # Keep a little bottom room for footer timestamp while maximizing plot area.
    fig.subplots_adjust(left=0.01, right=0.999, top=top, bottom=0.12)
    footer_text_right = fig.text(
        0.992,
        0.02,
        "",
        ha="right",
        va="bottom",
        fontsize=(plot_footer_pt or plot_font_pt or 10),
        color="white",
    )
    # expose footer on the figure so global theming can style it
    try:
        setattr(fig, "_footer_text_right", footer_text_right)
    except Exception:
        pass

    def _format_footer_dt(dt_obj: dt.datetime) -> str:
        return dt_obj.strftime("%Y:%m:%d - %H")

    def _update_footer_time() -> None:
        try:
            # Prefer the last sample x-value from plotted lines
            max_x = None
            for ln in lines:
                xd = getattr(ln, "get_xdata", None)
                if callable(xd):
                    data: Any = ln.get_xdata()
                    try:
                        candidate = data[-1]
                    except Exception:
                        continue
                    try:
                        xval = float(candidate)
                    except (TypeError, ValueError):
                        continue
                    if max_x is None or xval > max_x:
                        max_x = xval

            if max_x is None:
                # Fall back to right axis limit
                max_x = ax.get_xlim()[1]

            dt_last = mdates.num2date(max_x)
            footer_text_right.set_text(f"{_format_footer_dt(dt_last)}")

            # Position footer just below the axes bbox to avoid overlap.
            try:
                ax_pos = ax.get_position()  # Bbox in figure coordinates
                footer_y = ax_pos.y0 - 0.01
                if footer_y < 0.005:
                    footer_y = 0.005
                footer_text_right.set_y(footer_y)
            except Exception:
                # fallback: keep existing position
                pass
        except Exception:
            footer_text_right.set_text("")

    # Now that footer helpers exist, initialize legend (which triggers redraw)
    _set_legend(series_labels)

    if show_toggles:

        def _make_handler(index: int) -> Callable[[Any], None]:
            def _handler(e: Any) -> None:
                series_user_visible[index] = bool(e.value)
                _apply_series_visibility()
                _refresh_legend()

            return _handler

        for index, cb in enumerate(checkboxes):
            cb.on_value_change(_make_handler(index))

    _apply_series_visibility()

    def _apply_display_configuration() -> None:
        nonlocal active_y_limits
        active_y_limits = _selected_y_limits()
        if active_y_limits is not None:
            ax.set_ylim(*active_y_limits)
        ax.set_ylabel("ADU" if current_display_mode == "ADU" else y_label)
        _update_limit_lines()

    def set_mode(mode: str) -> None:
        """Set the EGSE mode and refresh mode-specific limits/reference lines."""
        nonlocal current_mode
        mode_upper = str(mode or "EB").upper()
        if mode_upper not in {"EB", "OB"}:
            return
        current_mode = mode_upper
        _apply_series_visibility()
        _apply_display_configuration()
        if show_title:
            ax.set_title(f"{title} ({current_mode})", fontsize=(plot_font_pt or 14))
            if title_label is not None:
                title_label.set_text(f"{title} [{current_mode}]")
        else:
            ax.set_title("")
        _refresh_legend()

    def set_display_mode(display_mode: str) -> None:
        """Switch between engineering units and raw ADU reference limits."""
        nonlocal current_display_mode
        display_upper = str(display_mode or "REAL").upper()
        if display_upper not in {"REAL", "ADU"}:
            display_upper = "REAL"
        current_display_mode = display_upper
        _apply_display_configuration()
        _refresh_legend()

    def set_stream_enabled(enabled: bool) -> None:
        nonlocal stream_enabled
        enabled = bool(enabled)
        if stream_enabled == enabled:
            return
        stream_enabled = enabled
        _reset_series()

    def push(time_points: list[Any], series_values: list[list[float]]) -> None:
        """Push one sample per series.  series_values[i] is the list of y-values
        for series i at the corresponding time_points."""
        if stream_enabled and time_points:
            plot.push(
                time_points,
                series_values,
                y_limits=active_y_limits if active_y_limits is not None else "auto",
            )

    return PlotCardController(
        card=card,
        plot=plot,
        set_mode=set_mode,
        set_display_mode=set_display_mode,
        push=push,
        set_series_labels=_set_legend,
        set_stream_enabled=set_stream_enabled,
        close=close_plot,
    )
