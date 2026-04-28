from __future__ import annotations

# Std library
from dataclasses import dataclass
from typing import Any, Callable
from datetime import datetime
import numbers
from matplotlib.ticker import FormatStrFormatter

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
    """
    _HEIGHT_SCALE = {"h-40": ("h-60", (14, 4.5)), "h-60": ("h-96", (14, 5.25))}
    if plot_height_class in _HEIGHT_SCALE:
        plot_height_class, _figsize = _HEIGHT_SCALE[plot_height_class]
    else:
        _figsize = (14, 5.25)
    n_series = len(series)

    with ui.card().classes("w-full flex-1"):
        title_label = ui.label(title).classes("text-sm font-bold")
        if not show_title:
            title_label.classes(add="hidden")

        checkboxes: list[Any] = []
        if show_toggles:
            with ui.row().classes("w-full flex-wrap gap-x-4 gap-y-1"):
                for cfg in series:
                    checkboxes.append(
                        ui.checkbox(cfg.label, value=cfg.visible)
                        .props(
                            f'checked-icon="radio_button_checked" unchecked-icon="radio_button_unchecked" keep-color color="{cfg.color}"'
                        )
                        .style(f"color: {cfg.color}")
                        .classes("text-xs")
                    )

        plot = (
            ui.line_plot(n=n_series, limit=limit, figsize=_figsize)
            .classes(f"w-full {plot_height_class}")
            .style("width: 100%; min-width: 100%; max-width: none; padding: 0;")
        )

    ax = plot.fig.axes[0]
    # Format x-axis as seconds with 2 decimal places
    ax.xaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.tick_params(labelsize=22)
    ax.grid(True, alpha=1, linewidth = 3)

    lines = list(ax.lines)
    for line, cfg in zip(lines, series):
        line.set_color(cfg.color)
        line.set_visible(cfg.visible)
        line.set_marker("*")
        line.set_markersize(8)

    legend_visible = (n_series > 1) if show_legend is None else bool(show_legend)
    series_labels = [cfg.label for cfg in series]

    def _redraw_plot() -> None:
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
        frame.set_facecolor(palette.get("plot_bg", "white"))
        frame.set_edgecolor(palette.get("plot_spine", "black"))
        for text in legend.get_texts():
            text.set_color(palette.get("plot_legend", "black"))

    def _refresh_legend() -> None:
        legend = ax.get_legend()
        if legend is not None:
            legend.remove()

        if legend_visible:
            for idx, line in enumerate(lines):
                label = series_labels[idx] if idx < len(series_labels) else line.get_label()
                line.set_label(label if line.get_visible() else "_nolegend_")

            if any(line.get_visible() for line in lines):
                ax.legend(loc="upper left", fontsize=15)
                _style_legend()

        _redraw_plot()

    def _set_legend(labels: list[str]) -> None:
        nonlocal series_labels
        series_labels = list(labels)
        _refresh_legend()

    stream_enabled = True
    # Track the first time sample seen for this plot (used to compute seconds offset)
    first_time: datetime | float | None = None

    def _reset_series() -> None:
        for line in lines:
            line.set_data([], [])
        ax.relim()
        ax.autoscale_view(scalex=True, scaley=False)
        _redraw_plot()

    _set_legend(series_labels)
    if y_limits is not None:
        ax.set_ylim(*y_limits)
    top = 0.92 if show_title else 0.98
    plot.fig.subplots_adjust(left=0.06, right=0.998, top=top, bottom=0.10)

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
            ax.set_title(f"{title} ({mode})", fontsize=22)
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
        if not (stream_enabled and time_points):
            return

        nonlocal first_time

        converted_x: list[float] = []
        for tp in time_points:
            # datetime -> seconds since first_time
            if isinstance(tp, datetime):
                if first_time is None or isinstance(first_time, float):
                    first_time = tp
                delta = (tp - first_time).total_seconds()
                converted_x.append(float(delta))
            # numeric types -> seconds since first_time
            elif isinstance(tp, numbers.Number):
                if first_time is None or isinstance(first_time, datetime):
                    first_time = float(tp)
                converted_x.append(float(tp - float(first_time)))
            else:
                # try parsing ISO-format datetime string then fallback to float
                try:
                    parsed = datetime.fromisoformat(str(tp))
                    if first_time is None or isinstance(first_time, float):
                        first_time = parsed
                    converted_x.append((parsed - first_time).total_seconds())
                except Exception:
                    try:
                        f = float(tp)
                        if first_time is None or isinstance(first_time, datetime):
                            first_time = f
                        converted_x.append(float(f - float(first_time)))
                    except Exception:
                        converted_x.append(0.0)

        plot.push(converted_x, series_values)

    return PlotCardController(
        plot=plot,
        set_mode=set_mode,
        push=push,
        set_series_labels=_set_legend,
        set_stream_enabled=set_stream_enabled,
    )
