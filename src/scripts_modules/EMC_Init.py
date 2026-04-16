# from __future__ import annotations

from queue import Empty
import time

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs
from widget_modules import ui_runtime_controller
import logging

info_log = logging.getLogger("info_log")


def run_emc_init() -> None:
    interface = eb_interface.get_egse_interface()
    # RET command (SAFE mode)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    ebtcs.hk_request(interface, 0)
    try:
        latest_post = const.eb_post_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("EMC_Init: missing POST or PSU queue data after RET") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (85 <= ch4_current_ma <= 95.0):
        raise AssertionError(f"EMC_Init: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 80-90)")
    result = ui_runtime_controller.perform_hk_check(hk=None, post=latest_post, hk_type="post")
    info_log.info(f"SAFE mode: EB PSU I : {ch4_current_ma:.2f} mA,  Post Packet Check : {result}")
    ui_runtime_controller.notify_script_pause(2, 13)
    ui_runtime_controller.request_force_pause()

    # Transition to Standby and use automatic ASW
    ebtcs.standby(interface, 0, 0)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("EMC_Init: missing HK or PSU queue data after STANDBY") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (100.0 <= ch4_current_ma <= 110.0):
        raise AssertionError(f"EMC_Init: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 100-110)")
    result = ui_runtime_controller.perform_hk_check(hk=latest_hk, post=None, hk_type="hk")
    info_log.info(f"STANDBY mode: PSU_EB_I: {ch4_current_ma:.2f} mA, HK Check Result: {result}")
    ui_runtime_controller.notify_script_pause(4, 13)
    ui_runtime_controller.request_force_pause()

    # Set HK rate to 1s
    ebtcs.set_hk_rate(interface, 0, 1)
    # Configure Heaters for ON during test (Upper - 2245 +55 ) (Lower - 2211 +45 )
    ebtcs.set_heater_configs(interface, 0x00, 0x08C5, 0x08A3, 0x08C5, 0x08A3)
    # Activate both heaters
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    # Generic TC for heater status (see script)
    ebtcs.generic_tc(interface, 0x0, 0x6, 0x64, 0xC4, 0x01, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)

    ebtcs.hk_request(interface, 0)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("EMC_Init: missing HK or PSU queue data after STANDBY") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (155.0 <= ch4_current_ma <= 165.0):
        raise AssertionError(f"EMC_Init: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 100-110)")
    if not (getattr(latest_hk, "HEATER_STATUS", None) == 3):
        raise AssertionError(
            f"EMC_Init: HEATER_STATUS HK field not 3 (got {getattr(latest_hk, 'HEATER_STATUS', None)})"
        )
    instr_flags = getattr(latest_hk, "INSTR_STATUS_FLAGS", None)
    det_warm = getattr(instr_flags, "DETECTOR_WARM", None)
    mech_warm = getattr(instr_flags, "MECHANISM_WARM", None)
    if not (det_warm and mech_warm):
        raise AssertionError(
            f"EMC_Init: OB_WARM (DETECTOR_WARM and MECHANISM_WARM) not set (got DETECTOR_WARM={det_warm}, MECHANISM_WARM={mech_warm})"
        )
    info_log.info(f"STANDBY mode: PSU_EB_I: {ch4_current_ma:.2f} mA, HK Check Result: {result}")
    # TODO: Check OBWARM flag in HK (user should verify before proceeding)

    ui_runtime_controller.notify_script_pause(9, 13)
    ui_runtime_controller.request_force_pause()

    # Enable Mechanism and Detector boards
    ebtcs.en_mech_board(interface, 0x1)
    ebtcs.en_det_board(interface, 0x1)
    # Set Motor Parameters to defaults
    ebtcs.set_motor_configs(interface, 0, 0x40, 0x00, 0x08, 0x00, 0x00, 0x3C, 0x00, 0x0000, 0x00)
    # Perform Homing Cal to Base then Drive to Outer
    ebtcs.ob_homing(interface, 0x01)

    ob_homed = getattr(const.hk_queue.get(timeout=2.0), "OB_HOMED", None)
    while not ob_homed:
        ob_homed = getattr(const.hk_queue.get(timeout=2.0), "OB_HOMED", None)
        info_log.info(f"Waiting for OB_HOMED flag to be set in HK... (got {ob_homed})")
        time.sleep(1.0)

    # TODO: Check OBHOMED flag in HK (user should verify before proceeding)
    ui_runtime_controller.notify_script_pause(13, 13)
    # End of EMC_Init
    ui_runtime_controller.notify_script_done()
