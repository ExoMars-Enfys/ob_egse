from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# CSS variable parser
# ---------------------------------------------------------------------------


def _extract_block_vars(text: str, selector: str) -> dict[str, str]:
    """Return the CSS custom properties declared inside *selector* { … }."""
    pattern = re.compile(
        re.escape(selector) + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return {}
    return dict(re.findall(r"--([a-zA-Z0-9_-]+)\s*:\s*([^;]+?)\s*;", match.group(1)))


def _resolve_vars(vars_dict: dict[str, str]) -> dict[str, str]:
    """Resolve var(--x) references until all values are concrete colours."""
    resolved = dict(vars_dict)
    for _ in range(10):
        changed = False
        for key, value in resolved.items():
            m = re.fullmatch(r"var\(--([a-zA-Z0-9_-]+)\)", value.strip())
            if m:
                ref = m.group(1)
                if ref in resolved and not resolved[ref].strip().startswith("var("):
                    resolved[key] = resolved[ref]
                    changed = True
        if not changed:
            break
    return resolved


def load_css_vars(css_path: Path, theme: str = "dark") -> dict[str, str]:
    """Parse *css_path* and return a flat dict of resolved CSS variable values
    for the requested *theme* (``"dark"`` or ``"light"``).

    The dict keys are variable names **without** the leading ``--``, e.g.
    ``"primary-bg"``, ``"series-dig-trp"``.
    """
    text = css_path.read_text(encoding="utf-8")
    root_vars = _extract_block_vars(text, ":root")
    theme_vars = _extract_block_vars(text, f"body.theme-{theme}")
    merged = {**root_vars, **theme_vars}
    return _resolve_vars(merged)


def get_theme_palette(gui_vars: dict[str, str], theme: str) -> dict[str, str]:
    """Get a color palette based on the current theme and GUI variables."""

    def _get(name: str) -> str | None:
        return gui_vars.get(name)

    # Return values directly from parsed CSS variables. No Python-side
    # fallbacks or defaults: the CSS file is the single source of truth.
    return {
        "accent_color": _get("accent_color"),
        "secondary_bg": _get("secondary-bg"),
        "primary_bg": _get("primary-bg"),
        "plot_bg": _get("plot-bg"),
        "plot_text": _get("plot-axis"),
        "plot_grid": _get("plot-grid"),
        # Typography and sizes (read directly from CSS variables)
        "ui_label_size": _get("ui-label-size"),
        "metric_label_size": _get("metric-label-size"),
        "metric_value_size": _get("metric-value-size"),
        "heading_size": _get("heading-size"),
        "heading_weight": _get("heading-weight"),
        "body_font_family": _get("body-font-family"),
        # Plot controls
        "plot_font_size": _get("plot-font-size"),
        "plot_footer_size": _get("plot-footer-size"),
        "plot_linewidth": _get("plot-linewidth"),
        "plot_grid_alpha": _get("plot-grid-alpha"),
        "plot_grid_width": _get("plot-grid-width"),
        "plot_tick_size": _get("plot-tick-size"),
        "plot_fig_height_h40": _get("plot-fig-height-h40"),
        "plot_fig_height_h60": _get("plot-fig-height-h60"),
        "plot_spine": _get("plot-spine"),
        "plot_legend": _get("plot-legend"),
        # Semantic / constant colours sourced from CSS variables
        "limit_warn": _get("limit-warn"),
        "limit_alarm": _get("limit-alarm"),
        "status_ok": _get("status-ok"),
        "status_alarm": _get("status-alarm"),
        # Chart series identity colours
        "series_dig_trp": _get("series-dig-trp"),
        "series_det_trp": _get("series-det-trp"),
        "series_mech_trp": _get("series-mech-trp"),
        "series_mtr_trp": _get("series-mtr-trp"),
        "series_ob_3v3": _get("series-ob-3v3"),
        "series_eb_3v3": _get("series-eb-3v3"),
        "chart_rov_htr": _get("chart-rov-htr"),
        "chart_eb_current": _get("chart-eb-current"),
    }


def apply_plot_theme(ax: Any, palette: dict[str, str]) -> None:
    """Apply the given color palette to a matplotlib Axes object."""
    # Keep the plot interior white for readability while the outer canvas
    # (margins/card surroundings) follows the active app theme.
    fig = ax.figure
    plot_bg = palette.get("secondary_bg") or palette.get("plot_bg")
    plot_text = palette.get("plot_text")
    interior_bg = "#ffffff"

    def _is_light_text(color: Any) -> bool:
        if not isinstance(color, str):
            return False
        value = color.strip().lower()
        return value in {"#fff", "#ffffff", "white", "rgb(255,255,255)", "rgba(255,255,255,1)"}

    if plot_bg is not None:
        fig.set_facecolor(plot_bg)
        fig.patch.set_facecolor(plot_bg)
    ax.set_facecolor(interior_bg)
    if plot_text is not None:
        ax.tick_params(colors=plot_text)
        ax.xaxis.label.set_color(plot_text)
        ax.yaxis.label.set_color(plot_text)
        ax.title.set_color(plot_text)
    # Apply grid style from palette (allow numeric strings in palette)
    grid_color = palette.get("plot_grid")
    grid_alpha = palette.get("plot_grid_alpha")
    grid_width = palette.get("plot_grid_width")
    try:
        grid_alpha = float(grid_alpha) if grid_alpha is not None else None
    except Exception:
        grid_alpha = None
    try:
        grid_width = float(grid_width) if grid_width is not None else None
    except Exception:
        grid_width = None
    ax.grid(True, color=grid_color, alpha=grid_alpha, linewidth=grid_width)

    plot_spine = palette.get("plot_spine")
    if plot_spine is not None:
        for spine in ax.spines.values():
            spine.set_color(plot_spine)

    legend = ax.get_legend()
    if legend is not None:
        frame = legend.get_frame()
        frame.set_facecolor(interior_bg)
        if plot_spine is not None:
            frame.set_edgecolor(plot_spine)
        plot_legend = palette.get("plot_legend")
        # Legend sits on white interior, so keep dark text if theme legend color is light.
        if _is_light_text(plot_legend):
            plot_legend = "#111827"
        if plot_legend is not None:
            for text in legend.get_texts():
                text.set_color(plot_legend)

    # Centralized footer styling: if a footer text object was attached to the
    # figure (by the plot widget), style it here so theme switching is unified.
    try:
        footer = getattr(fig, "_footer_text_right", None)
        if footer is not None:
            footer_color = palette.get("plot_footer")
            if footer_color is not None:
                footer.set_color(footer_color)
            # fontsize may be provided as a numeric string in GUI vars
            size = palette.get("plot_footer_size")
            if size is not None:
                try:
                    footer.set_fontsize(float(size))
                except Exception:
                    try:
                        footer.set_fontsize(int(size))
                    except Exception:
                        pass
            else:
                # default to axis tick label size if available
                try:
                    ticks = ax.xaxis.get_ticklabels()
                    if ticks:
                        footer.set_fontsize(ticks[0].get_fontsize())
                except Exception:
                    pass
    except Exception:
        pass


def ui_font_size(raw: Any) -> str | None:
    """Return a CSS-ready font-size string for UI use, or None.

    - If *raw* is None, return None (do not fallback).
    - If *raw* is an int/float, returns "{int}px".
    - If *raw* is a numeric string like "14" or "14.0", returns "14px".
    - If *raw* already looks like a CSS size (endswith "px", "rem", "em",
      or contains "clamp("), returns it unchanged.
    - If parsing fails, return None.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return f"{int(raw)}px"
    if isinstance(raw, str):
        s = raw.strip()
        # numeric string -> px
        if re.fullmatch(r"\d+(?:\.\d+)?", s):
            return s + "px"
        # already px or rem/em or clamp() or percent, return as-is
        if s.endswith("px") or s.endswith("rem") or s.endswith("em") or "clamp(" in s or s.endswith("%"):
            return s
        return None
    return None


def font_size_px(raw: Any, rem_base: float = 16.0) -> float | None:
    """Return a numeric font size in points for Matplotlib, or None.

    - If *raw* cannot be parsed or is None, return None (no fallback).
    - Converts px/rem/em to pixels then to points (pt).
    """
    s = ui_font_size(raw)
    if s is None:
        return None
    s = s.strip()
    px_value: float | None = None
    # px
    if s.endswith("px"):
        try:
            px_value = float(s[:-2])
        except Exception:
            px_value = None
    # rem/em -> multiply by rem_base
    if px_value is None:
        m = re.fullmatch(r"([0-9.]+)(rem|em)", s)
        if m:
            try:
                px_value = float(m.group(1)) * float(rem_base)
            except Exception:
                px_value = None
    # plain number
    if px_value is None and re.fullmatch(r"\d+(?:\.\d+)?", s):
        try:
            px_value = float(s)
        except Exception:
            px_value = None

    if px_value is None:
        return None

    # Convert pixels to points: 1pt = 1/72in, 1px = 1/96in -> pt = px * 72/96
    return px_value * 72.0 / 96.0


def apply_theme_to_plots(labels: dict[str, Any], plot_keys: list[str], palette: dict[str, str]) -> None:
    for key in plot_keys:
        plot = labels.get(key)
        if plot is None:
            continue
        ax = plot.fig.axes[0]
        apply_plot_theme(ax, palette)
        plot.fig.canvas.draw_idle()
        plot.fig.canvas.draw()
        convert = getattr(plot, "_convert_to_html", None)
        if callable(convert):
            convert()
        update = getattr(plot, "update", None)
        if callable(update):
            update()


def set_logo_sources(logo_images: list[Any], src: str) -> None:
    for logo in logo_images:
        logo.props(f"src={src}")
        update = getattr(logo, "update", None)
        if callable(update):
            update()


def apply_theme(
    ui: Any,
    theme: str,
    gui_vars: dict[str, str],
    labels: dict[str, Any],
    plot_keys: list[str],
    logo_images: list[Any],
    logo_light_src: str,
    logo_dark_src: str,
) -> None:
    palette = get_theme_palette(gui_vars, theme)
    ui.colors(
        primary=palette["accent_color"],
        accent=palette["accent_color"],
        accent_color=palette["accent_color"],
        secondary=palette["secondary_bg"],
        dark=palette["primary_bg"],
    )
    ui.run_javascript(
        f"document.body.classList.remove('theme-dark','theme-light');document.body.classList.add('theme-{theme}');"
    )
    logo_src = logo_dark_src if theme == "dark" else logo_light_src
    set_logo_sources(logo_images, logo_src)
    apply_theme_to_plots(labels, plot_keys, palette)
