from __future__ import annotations

# Std library
from dataclasses import dataclass
from typing import Any, Callable
import datetime as dt
from matplotlib import ticker, dates as mdates
import numpy as np

# Added packages
from nicegui import app, ui


@dataclass
class SeriesConfig:
    """Configuration for a single plotted series."""

    label: str
    color: str
    visible: bool = True


@dataclass
class PlotCardController:
    plot: Any
    set_mode: Callable[[str], None]
    push: Callable[[list[Any], list[list[float]]], None]
    set_series_labels: Callable[[list[str]], None]
    set_stream_enabled: Callable[[bool], None]


def create_plot_card(
    title: str,
    *,
    series: list[SeriesConfig],
    y_label: str = "",
    y_limits: tuple[float, float] | None = None,
    mode_limits: dict[str, tuple[float, float]] | None = None,
    limit: int = 240,
    show_toggles: bool = False,
    show_title: bool = True,
    plot_height_class: str = "h-60",
    show_legend: bool | None = None,
) -> PlotCardController:
    """Create a generic plot card.

    Args:
        title: Card title.
        series: One entry per plotted line, each with a label and colour.
        y_label: Y-axis label (e.g. "mA", "°C", "V").
        y_limits: Fixed (ymin, ymax) applied at creation.  Ignored when
            *mode_limits* provides a value for the current mode.
        mode_limits: Optional per-mode (ymin, ymax) updated by set_mode().
        limit: Number of x-points to keep in the rolling window.
        show_toggles: When True, renders a per-series checkbox row inside the
            card so individual series can be shown or hidden at runtime.
        show_title: When False, suppresses both card and axis titles.
        plot_height_class: Tailwind height class for the plot area.
        show_legend: Force legend visibility. Defaults to visible when
            there is more than one series.
    n_series = len(series)

    """
    # Use a larger baseline canvas so the rendered plot fills card space.
    _HEIGHT_SCALE = {"h-40": ("h-60", (14.0, 4.5)), "h-60": ("h-96", (14.0, 5.25))}
    if plot_height_class in _HEIGHT_SCALE:
        plot_height_class, _figsize = _HEIGHT_SCALE[plot_height_class]
    else:
        _figsize = (14.0, 5.25)

    n_series = len(series)

    # Theme-aware sizes helper (use centralized helpers)
    from utility_modules import app_theme

    palette = getattr(app.state, "theme_palette", None)
    ui_sz = app_theme.ui_font_size(palette.get("heading_size") if isinstance(palette, dict) else None)
    chk_sz = app_theme.ui_font_size(palette.get("metric_label_size") if isinstance(palette, dict) else None)

    with ui.card().classes("flex-1 min-w-0"):
        title_label = ui.label(title)
        title_label.style(f"font-size: {ui_sz}")
        title_label.classes("font-bold")
        if not show_title:
            title_label.classes(add="hidden")

        checkboxes: list[Any] = []
        if show_toggles:
            with ui.row().classes("w-full flex-wrap gap-x-4 gap-y-1"):
                for cfg in series:
                    cb = ui.checkbox(cfg.label, value=cfg.visible).props(
                        f'checked-icon="radio_button_checked" unchecked-icon="radio_button_unchecked" keep-color color="{cfg.color}"'
                    )
                    cb.style(f"font-size: {chk_sz}")
                    cb.style(f"color: {cfg.color}")
                    checkboxes.append(cb)

        plot = (
            ui.line_plot(n=n_series, limit=limit, figsize=_figsize)
            .classes(f"w-full {plot_height_class}")
            .style("width: 100%; min-width: 0; max-width: 100%; padding: 0;")
        )

    # access matplotlib axes/figure
    ax = plot.fig.axes[0]
    fig = plot.fig

    # X-axis: show minutes:seconds:milliseconds on ticks
    def _fmt_x_tick(x, pos):
        try:
            dt = mdates.num2date(x)
            ms = dt.microsecond // 1000
            return f"{dt.strftime('%M:%S')}"
        except Exception:
            return ""

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt_x_tick))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    # let the global theme control grid color/width/alpha
    ax.grid(True, which="major")
    tick_size = app_theme.font_size_px(palette.get("plot_tick_size") if isinstance(palette, dict) else None)
    ax.tick_params(labelsize=(tick_size or 11))

    lines = list(ax.lines)
    for line, cfg in zip(lines, series):
        line.set_color(cfg.color)
        line.set_visible(cfg.visible)
        line.set_marker("*")
        line.set_markersize(8)

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
        for text in legend.get_texts():
            text.set_color(palette.get("plot_legend"))

    def _refresh_legend() -> None:
        legend = ax.get_legend()
        if legend is not None:
            legend.remove()

        if legend_visible:
            for idx, line in enumerate(lines):
                label = series_labels[idx] if idx < len(series_labels) else line.get_label()
                line.set_label(label if line.get_visible() else "_nolegend_")

            if any(line.get_visible() for line in lines):
                ax.legend(loc="upper left", fontsize=11)
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

    if y_limits is not None:
        ax.set_ylim(*y_limits)
    top = 0.92 if show_title else 0.98
    # Keep a little bottom room for footer timestamp while maximizing plot area.
    fig.subplots_adjust(left=0.065, right=0.995, top=top, bottom=0.19)
    footer_text_right = fig.text(0.992, 0.02, "", ha="right", va="bottom", fontsize=10, color="white")
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
                    data = ln.get_xdata()
                    if len(data) > 0:
                        xval = float(data[-1])
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

        def _make_handler(ln: Any) -> Callable[[Any], None]:
            def _handler(e: Any) -> None:
                ln.set_visible(e.value)
                _refresh_legend()

            return _handler

        for cb, ln in zip(checkboxes, lines):
            cb.on_value_change(_make_handler(ln))

    def set_mode(mode: str) -> None:
        """Set the plot mode, updating any mode-specific limits and the title."""
        if mode_limits is not None:
            ymin, ymax = mode_limits.get(mode, y_limits or (0.0, 1000.0))
            ax.set_ylim(ymin, ymax)
        if show_title:
            ax.set_title(f"{title} ({mode})", fontsize=14)
            title_label.set_text(f"{title} [{mode}]")
        else:
            ax.set_title("")
        plot.update()

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
            plot.push(time_points, series_values)

    return PlotCardController(
        plot=plot,
        set_mode=set_mode,
        push=push,
        set_series_labels=_set_legend,
        set_stream_enabled=set_stream_enabled,
    )
