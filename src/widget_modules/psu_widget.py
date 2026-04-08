from __future__ import annotations

from typing import Any


def update_psu_readings(
    labels: dict[str, Any],
    status: dict[str, int],
    last_psu_readings: dict[str, float | int | None],
    psu: dict[str, Any],
) -> None:
    status["psu"] = psu["STATUS"]
    last_psu_readings["status"] = psu["STATUS"]
    last_psu_readings["PSU_ROV_HTR_V"] = psu["PSU_ROV_HTR_V"]
    last_psu_readings["PSU_ROV_HTR_I"] = psu["PSU_ROV_HTR_I"]
    last_psu_readings["PSU_EB_V"] = psu["PSU_EB_V"]
    last_psu_readings["PSU_EB_I"] = psu["PSU_EB_I"]

    labels["PSU_ROV_HTR_V"].set_text(f"V: {psu['PSU_ROV_HTR_V']:.2f}")
    labels["PSU_ROV_HTR_I"].set_text(f"mA: {psu['PSU_ROV_HTR_I'] * 1000:.1f}")
    labels["PSU_EB_V"].set_text(f"V: {psu['PSU_EB_V']:.2f}")
    labels["PSU_EB_I"].set_text(f"mA: {psu['PSU_EB_I'] * 1000:.1f}")


def push_psu_currents(
    labels: dict[str, Any], psu_times: list[Any], rov_currents_ma: list[float], eb_currents_ma: list[float]
) -> None:
    if not psu_times:
        return

    labels["plot_psu_rov_htr"].push(
        psu_times,
        [rov_currents_ma],
    )
    labels["plot_psu_eb"].push(
        psu_times,
        [eb_currents_ma],
    )
