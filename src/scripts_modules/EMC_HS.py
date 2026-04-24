# from __future__ import annotations

from queue import Empty
import time

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs
from widget_modules import ui_runtime_controller
import logging

info_log = logging.getLogger("info_log")

ebtcs.EBTCS_VERIFY_ENABLED = False


def run_emc_hs() -> None:
    interface = eb_interface.get_egse_interface()

    # Set delay between TCs (t 500 in script, but handled by ebtcs flow control)

    # Set TEC closed loop control setpoint to -35C
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("EMC_HS: missing HK queue data after TEC setpoint") from exc
    tec_setpoint = getattr(latest_hk, "TEC_SETPOINT", None)
    if tec_setpoint != 0xC018:
        raise AssertionError(f"EMC_HS: TEC_SETPOINT not set as expected (got {tec_setpoint:#06x}, expected 0xC018)")
    info_log.info(f"TEC setpoint confirmed: {tec_setpoint:#06x}")

    # Disable both heaters and configure for flight
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
        latest_psu = const.psu_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("EMC_HS: missing HK or PSU queue data after heater config") from exc
    ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
    if not (110 <= ch4_current_ma <= 120):
        raise AssertionError(f"EMC_HS: PSU_EB_I out of range (got {ch4_current_ma:.2f} mA, expected 110-120)")
    if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0):
        raise AssertionError("EMC_HS: Mechanism heater is ON (THRM_STATUS.HMS=1)")
    if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0):
        raise AssertionError(
            f"EMC_HS: Detector heater is ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})"
        )
    info_log.info(
        "Power State 2 : OB HEATING - PSU_EB_I: %.2f mA,THRM_STATUS.HMS: %s, THRM_STATUS.HDS: %s",
        ch4_current_ma,
        getattr(latest_hk.THRM_STATUS, "HMS", 0),
        getattr(latest_hk.THRM_STATUS, "HDS", 0),
    )

    # Activate both heaters once again
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)

    # Set HK Rate to 10 seconds
    ebtcs.set_hk_rate(interface, 0, 10)

    i = 0
    while True:
        i += 1
        # Set acquisition configuration for ACQ High Sensitivity
        ebtcs.set_acq_configs(
            interface,
            0x01,  # ACQ_MODE: Fixed
            0x00,  # SCI_AVG: 0
            0x0000,  # RESERVED: 0
            0x01F4,  # ACQ_SAMPLE_TIME: 500ms
            0x0708,  # ACQ_DURATION: 30m
            0x0005,  # ACQ_START_POINT
            0x0,  # ACQ_END_POINT
            0x00,  # DETECTORS : Both
            0x1,  # PARK_MODE: Park at end
            0x1,  # CURRENT_SOL: 1
            0x2,  # MEAS_ID : 2
            i,  # RUN_NO: i
            0x01,  # CRITICALITY
            0x02,  # MEAS_TABLE: 2
        )

        # Set HK Rate back to 10 seconds (redundant but matches script)
        ebtcs.set_hk_rate(interface, 0, 2)

        # Send mode transition to Acquisition state
        ebtcs.acquisition(interface, 0x0)
        ui_runtime_controller.perform_acq_check_sync(2100)
