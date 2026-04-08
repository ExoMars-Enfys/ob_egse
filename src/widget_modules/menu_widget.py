from __future__ import annotations

from datetime import datetime
from typing import Any
from nicegui import app, ui

def menu_handler():
    """Method that renders the menu page."""
    with ui.grid(columns = 3, gap = "md", padding = "md"):
        ui.button("Start EGSE Tools", on_click=lambda: start_tools_handler(app.state.log_search_state, app.state.eb_interface, app.logger))
        ui.button("Stop EGSE Tools", on_click=lambda: stop_tools_handler(app.state.log_search_state, app.state.eb_interface, app.logger))
        ui.button("Select RS422 Log", on_click=lambda: select_log_handler(app.state.log_search_state, app.state.eb_interface, app.logger))
        ui.button("Log Snapshot", on_click=lambda: log_snapshot_handler(app.logger, app.state.last_psu_readings, app.state.last_hk, app.state.last_post, app.state.snapshot_state))
        ui.button("Log PSU Snapshot", on_click=lambda: log_psu_snapshot_handler(app.logger, app.state.last_psu_readings))
    
    

def start_tools_handler(log_search_state: dict[str, bool], eb_interface: Any, logger: Any) -> None:
    """"""
    log_search_state["enabled"] = True
    eb_interface.start_egse_tools(logger)


def stop_tools_handler(log_search_state: dict[str, bool], eb_interface: Any, logger: Any) -> None:
    log_search_state["enabled"] = False
    eb_interface.stop_egse_tools(logger)


def select_log_handler(log_search_state: dict[str, bool], eb_interface: Any, logger: Any) -> None:
    selected = eb_interface.select_rs422_log(logger)
    log_search_state["enabled"] = selected


def log_psu_snapshot(logger: Any, last_psu_readings: dict[str, float | int | None]) -> None:
    status_value = last_psu_readings["status"]
    if status_value is None:
        logger.info("PSU status: no PSU readings available yet")
        return

    rov_v = last_psu_readings["PSU_ROV_HTR_V"]
    rov_i = last_psu_readings["PSU_ROV_HTR_I"]
    eb_v = last_psu_readings["PSU_EB_V"]
    eb_i = last_psu_readings["PSU_EB_I"]

    logger.info(
        "PSU status: STATUS=%s | ROV_HTR: V=%.2f, I=%.1f mA | EB: V=%.2f, I=%.1f mA",
        status_value,
        float(rov_v) if rov_v is not None else float("nan"),
        (float(rov_i) * 1000) if rov_i is not None else float("nan"),
        float(eb_v) if eb_v is not None else float("nan"),
        (float(eb_i) * 1000) if eb_i is not None else float("nan"),
    )


def log_hk_snapshot(logger: Any, last_hk: dict[str, Any]) -> None:
    hk = last_hk["value"]
    if hk is None:
        logger.info("HK checks: no HK data available yet")
        return

    hk_checks = [
        ("TCS_ACCEPTED", hk.TCS_ACCEPTED, hk.TCS_ACCEPTED == 2),
        ("TCS_REJECTED", hk.TCS_REJECTED, hk.TCS_REJECTED == 0),
        ("INSTRUMENT_STATUS_FLAGS", hk.INSTRUMENT_STATUS_FLAGS, hk.INSTRUMENT_STATUS_FLAGS == 6),
        ("ERROR_FLAGS", hk.ERROR_FLAGS, hk.ERROR_FLAGS == 0),
        ("WARNING_FLAGS", hk.WARNING_FLAGS, hk.WARNING_FLAGS == 0),
        ("FDIR_ALARM_FLAGS", hk.FDIR_ALARM_FLAGS, hk.FDIR_ALARM_FLAGS == 0),
        ("FDIR_WARNING_FLAGS", hk.FDIR_WARNING_FLAGS, hk.FDIR_WARNING_FLAGS == 0),
    ]

    logger.info("HK checks:")
    for name, value, passed in hk_checks:
        logger.info("  - %s=%s (%s)", name, value, "PASS" if passed else "FAIL")


def log_post_snapshot_if_updated(
    logger: Any, last_post: dict[str, Any], snapshot_state: dict[str, datetime | None]
) -> None:
    post = last_post["value"]
    if post is None:
        logger.info("POST HK: no POST HK available yet")
        return

    post_time = getattr(post, "TIME", None)
    if not isinstance(post_time, datetime):
        logger.info("POST HK: available but timestamp missing; skipping update check")
        return

    if snapshot_state["last_post_logged_time"] == post_time:
        logger.info("POST HK: not updated since last snapshot")
        return

    snapshot_state["last_post_logged_time"] = post_time
    logger.info(
        "POST HK update at %s | WARN=%s ERR=%s BAD_FLASH=%s BAD_SRAM=%s",
        post_time.strftime("%Y-%m-%d %H:%M:%S"),
        post.POST_WARNING_FLAGS,
        post.POST_ERROR_FLAGS,
        post.NUM_BAD_FLASH_BLOCKS,
        post.NUM_BAD_SRAM_BLOCKS,
    )


def log_snapshot_handler(
    logger: Any,
    last_psu_readings: dict[str, float | int | None],
    last_hk: dict[str, Any],
    last_post: dict[str, Any],
    snapshot_state: dict[str, datetime | None],
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info('Log Snapshot at "%s"', timestamp)
    log_psu_snapshot(logger, last_psu_readings)
    log_hk_snapshot(logger, last_hk)
    log_post_snapshot_if_updated(logger, last_post, snapshot_state)


def log_psu_snapshot_handler(logger: Any, last_psu_readings: dict[str, float | int | None]) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info('Log Snapshot at "%s"', timestamp)
    log_psu_snapshot(logger, last_psu_readings)
