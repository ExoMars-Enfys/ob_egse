from __future__ import annotations

from typing import Any


def get_theme_palette(gui_vars: dict[str, str], theme: str) -> dict[str, str]:
    def _get(name: str, fallback: str = "") -> str:
        return gui_vars.get(name, fallback)

    return {
        "accent_color": _get("accent-color", "#2196f3"),
        "secondary_bg": _get("secondary-bg", "#f3f4f6") if theme == "light" else _get("secondary-bg", "#111827"),
        "primary_bg": _get("primary-bg", "#ffffff") if theme == "light" else _get("primary-bg", "#0f172a"),
        "plot_bg": _get("plot-bg", "#ffffff") if theme == "light" else _get("plot-bg", "#1f2937"),
        "plot_text": _get("plot-text", "#111827") if theme == "light" else _get("plot-text", "#e5e7eb"),
        "plot_grid": _get("plot-grid", "#d1d5db") if theme == "light" else _get("plot-grid", "#374151"),
        "plot_spine": _get("plot-spine", "#9ca3af"),
        "plot_legend": _get("plot-legend", "#111827") if theme == "light" else _get("plot-legend", "#e5e7eb"),
    }


def apply_plot_theme(ax: Any, palette: dict[str, str]) -> None:
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


def update_unit_dependent_plots(labels: dict[str, Any], temperature_units: dict[str, str], const: Any) -> None:
    is_adu = temperature_units["value"] == "ADU"

    if "plot_3v3" in labels:
        ax_3v3 = labels["plot_3v3"].fig.axes[0]
        ax_3v3.set_title(f"3V3 Voltage ({'ADU' if is_adu else 'V'})")
        while len(ax_3v3.lines) > 1:
            ax_3v3.lines[-1].remove()
        wlim_3v3 = const.WLIM_3V3_ADU if is_adu else const.WLIM_3V3
        alim_3v3 = const.ALIM_3V3_ADU if is_adu else const.ALIM_3V3
        ax_3v3.axhline(wlim_3v3[0], color="orange", linewidth=1.0, linestyle="--")
        ax_3v3.axhline(wlim_3v3[1], color="orange", linewidth=1.0, linestyle="--")
        ax_3v3.axhline(alim_3v3[0], color="red", linewidth=1.0, linestyle="--")
        ax_3v3.axhline(alim_3v3[1], color="red", linewidth=1.0, linestyle="--")
        labels["plot_3v3"].update()

    if "plot_1v5" in labels:
        ax_1v5 = labels["plot_1v5"].fig.axes[0]
        ax_1v5.set_title(f"1V5 Voltage ({'ADU' if is_adu else 'V'})")
        while len(ax_1v5.lines) > 1:
            ax_1v5.lines[-1].remove()
        wlim_1v5 = const.WLIM_1V5_ADU if is_adu else const.WLIM_1V5
        alim_1v5 = const.ALIM_1V5_ADU if is_adu else const.ALIM_1V5
        ax_1v5.axhline(wlim_1v5[0], color="orange", linewidth=1.0, linestyle="--")
        ax_1v5.axhline(wlim_1v5[1], color="orange", linewidth=1.0, linestyle="--")
        ax_1v5.axhline(alim_1v5[0], color="red", linewidth=1.0, linestyle="--")
        ax_1v5.axhline(alim_1v5[1], color="red", linewidth=1.0, linestyle="--")
        labels["plot_1v5"].update()

    if "plot_temps" in labels:
        ax_temps = labels["plot_temps"].fig.axes[0]
        ax_temps.set_ylabel(f"Temperature ({'ADU' if is_adu else 'degC'})")
        while len(ax_temps.lines) > 4:
            ax_temps.lines[-1].remove()
        wlim_tpr = const.WLIM_TPR_ADU if is_adu else const.WLIM_TPR
        alim_tpr = const.ALIM_TPR_ADU if is_adu else const.ALIM_TPR
        ax_temps.axhline(wlim_tpr[0], color="orange", linewidth=1.0, linestyle="--")
        ax_temps.axhline(wlim_tpr[1], color="orange", linewidth=1.0, linestyle="--")
        ax_temps.axhline(alim_tpr[0], color="red", linewidth=1.0, linestyle="--")
        ax_temps.axhline(alim_tpr[1], color="red", linewidth=1.0, linestyle="--")
        labels["plot_temps"].update()


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


def toggle_theme(theme_state: dict[str, str], apply_theme_fn: Any) -> None:
    theme_state["value"] = "light" if theme_state["value"] == "dark" else "dark"
    apply_theme_fn(theme_state["value"])


def toggle_temperature_units(temperature_units: dict[str, str], labels: dict[str, Any], update_fn: Any) -> None:
    temperature_units["value"] = "ADU" if temperature_units["value"] == "Metric" else "Metric"
    if "unit_toggle_btn" in labels:
        labels["unit_toggle_btn"].set_text(f"Unit Toggle : {temperature_units['value']}")
    update_fn()
