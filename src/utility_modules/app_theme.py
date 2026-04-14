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

    def _get(name: str, fallback: str = "") -> str:
        return gui_vars.get(name, fallback)

    return {
        # Theme-aware colours
        "accent_color": _get("accent_color", "#2b6d34"),
        "secondary_bg": _get("secondary-bg", "#2d2d2d" if theme == "dark" else "#e6e9ef"),
        "primary_bg": _get("primary-bg", "#595959" if theme == "dark" else "#f4f5f7"),
        "plot_bg": _get("plot-bg", "#595959" if theme == "dark" else "#f4f5f7"),
        "plot_text": _get("plot-axis", "#ffffff" if theme == "dark" else "#1f2a3a"),
        "plot_grid": _get("plot-grid", "#6e6e6e" if theme == "dark" else "#c9ced6"),
        "plot_spine": _get("plot-spine", "#ffffff" if theme == "dark" else "#1f2a3a"),
        "plot_legend": _get("plot-legend", "#ffffff" if theme == "dark" else "#1f2a3a"),
        # Semantic / constant colours sourced from CSS variables
        "limit_warn": _get("limit-warn", "#e67e22"),
        "limit_alarm": _get("limit-alarm", "#e74c3c"),
        "status_ok": _get("status-ok", "#2ecc71"),
        "status_alarm": _get("status-alarm", "#e74c3c"),
        # Chart series identity colours
        "series_dig_trp": _get("series-dig-trp", "#e74c3c"),
        "series_det_trp": _get("series-det-trp", "#e67e22"),
        "series_mech_trp": _get("series-mech-trp", "#2ecc71"),
        "series_mtr_trp": _get("series-mtr-trp", "#3498db"),
        "series_ob_3v3": _get("series-ob-3v3", "#e74c3c"),
        "series_eb_3v3": _get("series-eb-3v3", "#e67e22"),
        "chart_rov_htr": _get("chart-rov-htr", "#2f80ed"),
        "chart_eb_current": _get("chart-eb-current", "#f2994a"),
    }


def apply_plot_theme(ax: Any, palette: dict[str, str]) -> None:
    """Apply the given color palette to a matplotlib Axes object."""
    # Style both axes and figure backgrounds so canvas margins match theme.
    fig = ax.figure
    fig.set_facecolor(palette["plot_bg"])
    fig.patch.set_facecolor(palette["plot_bg"])
    ax.set_facecolor(palette["plot_bg"])
    ax.tick_params(colors=palette["plot_text"])
    ax.xaxis.label.set_color(palette["plot_text"])
    ax.yaxis.label.set_color(palette["plot_text"])
    ax.title.set_color(palette["plot_text"])
    ax.grid(True, color=palette["plot_grid"], alpha=0.6, linewidth=0.6)

    for spine in ax.spines.values():
        spine.set_color(palette["plot_spine"])

    legend = ax.get_legend()
    if legend is not None:
        frame = legend.get_frame()
        frame.set_facecolor(palette["plot_bg"])
        frame.set_edgecolor(palette["plot_spine"])
        for text in legend.get_texts():
            text.set_color(palette["plot_legend"])


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
