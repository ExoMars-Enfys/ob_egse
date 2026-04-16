from __future__ import annotations

from queue import Empty

import time

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs
from widget_modules import ui_runtime_controller
import logging

info_log = logging.getLogger("info_log")


def run_fft() -> None:
    interface = eb_interface.get_egse_interface()
    # FFT.txt sequence

    # ?RET and first check
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    ebtcs.hk_request(interface, 0)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("Initial FFT verification failed: missing HK or PSU queue data") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (80.0 <= ch4_current_ma <= 90.0):
        raise AssertionError(
            f"Initial FFT verification failed: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 80-90)"
        )
    if int(getattr(latest_hk, "CURRENT_OPERATING_STATE", -1) or -1) != 0x02:
        raise AssertionError(
            f"Initial FFT verification failed: CURRENT_OPERATING_STATE not SAFE (got {getattr(latest_hk, 'CURRENT_OPERATING_STATE', None)})"
        )
    if int(getattr(latest_hk, "TCS_REJECTED", 0) or 0) != 0:
        raise AssertionError(
            f"Initial FFT verification failed: TCS_REJECTED not zero (got {getattr(latest_hk, 'TCS_REJECTED', None)})"
        )

    info_log.info(
        "Power State 1 : Safe - PSU_EB_I: %.2f mA, CURRENT_OPERATING_STATE: %s, TCS_REJECTED: %s",
        ch4_current_ma,
        getattr(latest_hk, "CURRENT_OPERATING_STATE", None),
        getattr(latest_hk, "TCS_REJECTED", None),
    )
    ui_runtime_controller.notify_script_pause(2, 108)
    ui_runtime_controller.request_force_pause()

    # ?Standby and check
    ebtcs.standby(interface, 0, 0)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("Initial FFT verification failed: missing HK or PSU queue data") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (100 <= ch4_current_ma <= 110):
        raise AssertionError(
            f"Initial FFT verification failed: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 100-110)"
        )
    if int(getattr(latest_hk, "CURRENT_OPERATING_STATE", -1) or -1) != 0x04:
        raise AssertionError(
            f"Initial FFT verification failed: CURRENT_OPERATING_STATE not STANDBY (got {getattr(latest_hk, 'CURRENT_OPERATING_STATE', None)})"
        )
    if int(getattr(latest_hk, "TCS_REJECTED", 0) or 0) != 0:
        raise AssertionError(
            f"Initial FFT verification failed: TCS_REJECTED not zero (got {getattr(latest_hk, 'TCS_REJECTED', None)})"
        )
    ui_runtime_controller.notify_script_pause(3, 108)
    ui_runtime_controller.request_force_pause()

    # ?Send Set Heater Configs command and check HK response to verify mechanism heater is ON and detector heater is OFF
    ebtcs.hk_request(interface, 0)
    ebtcs.set_hk_rate(interface, 0, 1)
    ebtcs.set_heater_configs(interface, 0x00, 0x08A3, 0x0881, 0x08A3, 0x0881)
    ebtcs.hk_request(interface, 0)
    ebtcs.en_mech_heater(interface, 0x1)
    # Check if mechanism heater is ON
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("Initial FFT verification failed: missing HK or PSU queue data") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (150 <= ch4_current_ma <= 160):  #!Check Power consumptions
        raise AssertionError(
            f"Initial FFT verification failed: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 100-110)"
        )
    if not (hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0)):
        raise AssertionError("Initial FFT verification failed: Mechanism heater is not ON (THRM_STATUS.HMS=0)")
    if not (hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0)):
        raise AssertionError(
            f"Initial FFT verification failed: Detector heater is  ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})"
        )
    ui_runtime_controller.notify_script_pause(8, 108)
    ui_runtime_controller.request_force_pause()

    # ?Turn off the Mech heater and turn on the Det heater, then check HK response to verify the change
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x1)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("Initial FFT verification failed: missing HK or PSU queue data") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (150 <= ch4_current_ma <= 160):  #!Check Power consumptions
        raise AssertionError(
            f"Initial FFT verification failed: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 100-110)"
        )
    if not (hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0)):
        raise AssertionError("Initial FFT verification failed: Mechanism heater is not ON (THRM_STATUS.HMS=0)")
    if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0):
        raise AssertionError(
            f"Initial FFT verification failed: Detector heater is  ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})"
        )
    ui_runtime_controller.notify_script_pause(10, 108)
    ui_runtime_controller.request_force_pause()

    # ?Turn on both heaters - Power State 2 - OB HEATING
    ebtcs.en_mech_heater(interface, 0x1)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("Initial FFT verification failed: missing HK or PSU queue data") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (150 <= ch4_current_ma <= 160):  #!Check Power consumptions
        raise AssertionError(
            f"Initial FFT verification failed: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 100-110)"
        )
    if not (hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0)):
        raise AssertionError("Initial FFT verification failed: Mechanism heater is not ON (THRM_STATUS.HMS=0)")
    if not hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0):
        raise AssertionError(
            f"Initial FFT verification failed: Detector heater is not ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})"
        )
    info_log.info(
        "Power State 2 : OB HEATING - PSU_EB_I: %.2f mA, CURRENT_OPERATING_STATE: %s,THRM_STATUS.HMS: %s, THRM_STATUS.HDS: %s",
        ch4_current_ma,
        getattr(latest_hk, "CURRENT_OPERATING_STATE", None),
        getattr(latest_hk.THRM_STATUS, "HMS", 0),
        getattr(latest_hk.THRM_STATUS, "HDS", 0),
    )

    # ?Set Heater Configs to flight
    info_log.info(
        "Setting Heater Configs to flight values and verifying HK response - For temperatures below -35, heaters on."
    )
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("Initial FFT verification failed: missing HK or PSU queue data") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (100 <= ch4_current_ma <= 120):  #!Check Power consumptions
        raise AssertionError(
            f"Initial FFT verification failed: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 100-110)"
        )
    if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0):
        raise AssertionError("Initial FFT verification failed: Mechanism heater is ON (THRM_STATUS.HMS=1)")
    if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0):
        raise AssertionError(
            f"Initial FFT verification failed: Detector heater is ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})"
        )
    info_log.info(
        "Power State 2 : OB HEATING - PSU_EB_I: %.2f mA, CURRENT_OPERATING_STATE: %s,THRM_STATUS.HMS: %s, THRM_STATUS.HDS: %s",
        ch4_current_ma,
        getattr(latest_hk, "CURRENT_OPERATING_STATE", None),
        getattr(latest_hk.THRM_STATUS, "HMS", 0),
        getattr(latest_hk.THRM_STATUS, "HDS", 0),
    )

    ebtcs.en_mech_board(interface, 0x1)
    ebtcs.set_motor_configs(interface, 0, 0x40, 0x00, 0x08, 0x00, 0x00, 0x3C, 0x00, 0x0000, 0x00)
    ebtcs.ob_homing(interface, 0x01)
    ebtcs.set_tec_current(interface, 0x00, 0xFFF)

    ebtcs.set_tec_current(interface, 0x00, 0x000)
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.en_det_board(interface, 0x1)
    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)

    ebtcs.set_hk_rate(interface, 0, 1)
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x08A3, 0x0881, 0x08A3, 0x0881)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    ebtcs.generic_tc(interface, 0x0, 0x6, 0x64, 0xC4, 0x01, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)

    ebtcs.en_mech_board(interface, 0x1)
    ebtcs.en_det_board(interface, 0x1)

    ebtcs.set_tec_current(interface, 0x00, 0xFFF)

    ebtcs.set_motor_configs(interface, 0, 0x40, 0x00, 0x08, 0x00, 0x00, 0x3C, 0x00, 0x0000, 0x00)
    ebtcs.ob_homing(interface, 0x01)

    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)

    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    ebtcs.set_tec_current(interface, 0x00, 0x000)
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.set_acq_configs(
        interface, 0x01, 0x00, 0x0000, 0x03E8, 0x05DC, 0x0005, 0x0, 0x02, 0x1, 0x1, 0x1, 0x1, 0x00, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)

    ebtcs.set_hk_rate(interface, 0, 1)

    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)

    ebtcs.safe(interface, 0)

    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
