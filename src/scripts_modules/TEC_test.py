from __future__ import annotations

import logging
from queue import Empty
from typing import TYPE_CHECKING

from core_modules import config
from core_modules import constants as const
from utility_modules import eb_interface, ebtcs
from utility_modules import eb_packet_utility as ebpu
from widget_modules import ui_runtime_controller

if TYPE_CHECKING:
    from tek_scope_api import TekScope

try:
    from tek_scope_api import ScopeConnectionError, connect_scope, setup_scope

    _SCOPE_API_AVAILABLE = True
except ImportError:  # tek_scope_api is an optional local package
    _SCOPE_API_AVAILABLE = False
    ScopeConnectionError = Exception  # type: ignore[assignment, misc]

info_log = logging.getLogger("info_log")


def _connect_scope(scope_setup_file: str | None) -> TekScope | None:
    """Connect to the scope and recall its requested scope-side setup file."""
    if not _SCOPE_API_AVAILABLE:
        info_log.warning("TEC current report: tek_scope_api not installed, skipping scope capture")
        return None
    if not scope_setup_file:
        info_log.warning("TEC current report: no scope setup file selected, skipping scope capture")
        return None
    try:
        scope = connect_scope(config.SCOPE_VISA_RESOURCE)
        setup_scope(scope, scope_setup_file)
        info_log.info("Connected to scope for TEC current capture using %s: %s", scope_setup_file, scope.idn())
        return scope
    except ScopeConnectionError as exc:
        info_log.warning("TEC current report: scope unavailable, skipping scope capture (%s)", exc)
        return None


def run_tec_test(verification: bool = False, scope_setup_file: str | None = None) -> None:
    interface = eb_interface.get_egse_interface()
    # FFT.txt sequence

    # ?RET and first check - State 1
    interface = eb_interface.get_egse_interface()
    # RET command (SAFE mode)

    ebtcs.hk_request(interface, 0)
    if verification:
        msg, passed = ui_runtime_controller.verify_safe_ret()
        if not passed:
            raise AssertionError(f"SAFE RET verification failed:\n{msg}")

    ui_runtime_controller.abortible_sleep(2)
    # Transition to Standby and use automatic ASW
    ebtcs.standby(interface, 5, 1)
    ebtcs.standby(interface, 5, 1)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    ebtcs.hk_request(interface, 0)
    ebtcs.set_hk_rate(interface, 0, 1)
    ui_runtime_controller.abortible_sleep(2)
    if verification:
        msg, passed = ui_runtime_controller.verify_standby_ret()
        if not passed:
            raise AssertionError(f"STANDBY RET verification failed:\n{msg}")
        else:
            info_log.info("STANDBY RET verification passed:\n%s", msg)

    ui_runtime_controller.request_force_pause("Press to continue with the test")

    scope = _connect_scope(scope_setup_file)
    scope_captures_dir = const.LOG_PATH / "scope_captures"

    ui_runtime_controller.abortible_sleep(1)
    for current in range(0, 4095, 204):
        if scope is not None:
            try:
                scope.arm_step()
            except ScopeConnectionError as exc:
                info_log.warning("TEC current report: scope arm failed at setpoint %d (%s)", current, exc)

        ebtcs.set_tec_current(interface, 0, current)
        ui_runtime_controller.abortible_sleep(5)

        # Wait for a fresh HK packet that arrives after the setpoint change, not a cached one
        latest_hk = ebpu.wait_for_fresh_hk(timeout=5.0)
        if latest_hk is None:
            info_log.warning("TEC current report: no fresh HK received at setpoint %d", current)
            latest_hk = ebpu.get_latest_hk()
        tec_current_adu = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", None) if latest_hk is not None else None
        tec_current_a = float(tec_current_adu) * 0.0000162 if tec_current_adu is not None else None
        operating_state = getattr(latest_hk, "CURRENT_OPERATING_STATE", None) if latest_hk is not None else None

        psu_sample = None
        if const.psu_queue is not None:
            try:
                psu_sample = ui_runtime_controller.get_smoothed_psu_sample(const.psu_queue, timeout=2.0)
            except Empty:
                info_log.warning("TEC current report: no PSU sample received at setpoint %d", current)

        measured_current_ma = None
        if isinstance(psu_sample, dict) and psu_sample.get("PSU_EB_I") is not None:
            measured_current_ma = float(psu_sample["PSU_EB_I"]) * 1000.0

        scope_measurements: dict[str, float] = {}
        if scope is not None:
            try:
                step = scope.read_step(
                    measurement_slots=(1, 2, 4, 5),
                    screenshot_local_path=scope_captures_dir / f"tec_step_{current:04d}.png",
                )
                scope_measurements = step.measurements
            except ScopeConnectionError as exc:
                info_log.warning("TEC current report: scope capture failed at setpoint %d (%s)", current, exc)

        info_log.info(
            "TEC HK current report: setpoint=%d ADU, drive_current_adu=%s, tec_current=%s A, operating_state=%s, "
            "PSU_EB_I=%s mA, scope_max=%s A, scope_rms=%s A, scope_mean=%s A, scope_top=%s A",
            current,
            tec_current_adu if tec_current_adu is not None else "N/A",
            f"{tec_current_a:.6f}" if tec_current_a is not None else "N/A",
            operating_state if operating_state is not None else "N/A",
            f"{measured_current_ma:.2f}" if measured_current_ma is not None else "N/A",
            f"{scope_measurements.get('MAXIMUM'):.6f}" if scope_measurements.get("MAXIMUM") is not None else "N/A",
            f"{scope_measurements.get('RMS'):.6f}" if scope_measurements.get("RMS") is not None else "N/A",
            f"{scope_measurements.get('MEAN'):.6f}" if scope_measurements.get("MEAN") is not None else "N/A",
            f"{scope_measurements.get('TOP'):.6f}" if scope_measurements.get("TOP") is not None else "N/A",
        )
        ebtcs.set_tec_current(interface, 0, 0)
        ui_runtime_controller.abortible_sleep(2)

    if scope is not None:
        scope.close()

    ui_runtime_controller.request_force_pause("Press to continue with the test")

    ebtcs.safe(interface, 0)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
