from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# CSS variable parser
# ---------------------------------------------------------------------------


def _extract_block_vars(text: str, selector: str) -> dict[str, str]:
    """Return all CSS custom properties declared by *selector*.

    A stylesheet may contain several ``:root`` blocks for readability. All
    matching blocks are merged in source order, so later declarations override
    earlier declarations exactly as they do in CSS.
    """
    pattern = re.compile(
        re.escape(selector) + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )

    variables: dict[str, str] = {}
    for block in pattern.findall(text):
        variables.update(
            re.findall(
                r"--([a-zA-Z0-9_-]+)\s*:\s*([^;]+?)\s*;",
                block,
            )
        )
    return variables


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
    """Load and resolve CSS variables for the requested theme.

    Every ``:root`` block is merged first. The selected
    ``body.theme-dark`` or ``body.theme-light`` block is then applied over the
    root values.

    Returned keys retain their CSS spelling without the leading ``--``.
    For example, ``--plot-color-1`` becomes ``"plot-color-1"`` here.
    """
    theme_name = str(theme).strip().lower()
    if theme_name not in {"dark", "light"}:
        raise ValueError(f"Unsupported theme {theme!r}; expected 'dark' or 'light'.")

    text = css_path.read_text(encoding="utf-8")
    root_vars = _extract_block_vars(text, ":root")
    theme_vars = _extract_block_vars(text, f"body.theme-{theme_name}")
    merged = {**root_vars, **theme_vars}
    return _resolve_vars(merged)


def get_theme_palette(
    gui_vars: dict[str, str],
    theme: str,
) -> dict[str, str]:
    """Map resolved CSS variables to Python-friendly palette keys.

    All CSS variables are included automatically with hyphens converted to
    underscores. Therefore ``--plot-color-1`` is available to Python as
    ``palette["plot_color_1"]``.

    A small set of compatibility aliases is also provided for plotting code
    whose key names describe purpose rather than the exact CSS variable name.
    """
    _ = theme  # Retained for API compatibility with existing callers.

    # Generic mapping: CSS kebab-case becomes Python snake_case.
    palette = {css_name.replace("-", "_"): value for css_name, value in gui_vars.items()}

    # Purpose-based aliases used by the Matplotlib theming helpers.
    aliases = {
        "primary_bg": gui_vars.get("primary-bg"),
        "secondary_bg": gui_vars.get("secondary-bg"),
        "accent_color": gui_vars.get("accent_color"),
        "plot_bg": gui_vars.get("plot-bg"),
        "plot_text": gui_vars.get("plot-axis"),
        "plot_grid": gui_vars.get("plot-grid"),
        "plot_spine": gui_vars.get("plot-spine"),
        "plot_legend": gui_vars.get("plot-legend"),
        "plot_footer": gui_vars.get("plot-tick"),
        # The reorganised CSS uses simpler typography token names.
        "ui_label_size": gui_vars.get("small-text"),
        "medium-size": gui_vars.get("medium-text"),
        "heading_size": gui_vars.get("heading"),
    }
    palette.update({name: value for name, value in aliases.items() if value is not None})
    return palette


def get_plot_colors(
    palette: dict[str, str],
    *,
    count: int = 7,
) -> dict[int, str]:
    """Return numbered plot colours from the mapped CSS palette.

    CSS variables are expected to be named ``--plot-color-1`` through
    ``--plot-color-N``. Missing or blank values raise a clear error before
    Matplotlib receives an invalid ``None`` colour.
    """
    if count < 1:
        raise ValueError("Plot colour count must be at least 1.")

    colors: dict[int, str] = {}
    missing: list[int] = []

    for index in range(1, count + 1):
        key = f"plot_color_{index}"
        value = palette.get(key)
        if isinstance(value, str) and value.strip():
            colors[index] = value.strip()
        else:
            missing.append(index)

    if missing:
        missing_css_names = ", ".join(f"--plot-color-{index}" for index in missing)
        raise ValueError(f"Missing or empty CSS plot colour variable(s): {missing_css_names}")

    return colors


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
