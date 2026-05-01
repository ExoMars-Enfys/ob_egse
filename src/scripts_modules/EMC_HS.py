# from __future__ import annotations

from queue import Empty
import time

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs, eb_packet_utility as ebpu
from widget_modules import ui_runtime_controller
import logging

info_log = logging.getLogger("info_log")

ebtcs.EBTCS_VERIFY_ENABLED = False


def run_emc_hs(verification : bool = True) -> None:
    interface = eb_interface.get_egse_interface()

    # Set delay between TCs (t 500 in script, but handled by ebtcs flow control)

    # Set TEC closed loop control setpoint to -35C
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.hk_request(interface, 0)
    time.sleep(1)
    try:
        latest_hk = ebpu.get_latest_hk()
    except Empty as exc:
        raise AssertionError("EMC_HE: missing HK queue data after TEC setpoint") from exc
    tec_setpoint = getattr(latest_hk, "TEC_SETPOINT", None)
    # 0xC018 is 49176 in decimal, check for exact match or tolerance if needed
    if tec_setpoint != 0xC018:
        raise AssertionError(f"EMC_HE: TEC_SETPOINT not set as expected (got {tec_setpoint:#06x}, expected 0xC018)")
    info_log.info(f"TEC setpoint confirmed: {tec_setpoint:#06x}")

    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    if verification:
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty:
            errors.append("Missing HK or PSU queue data (mech ON, det ON)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = None
        if latest_psu is not None:
            ui_runtime_controller.consumption_check(["Standby", "Mech", "Det"], latest_psu, errors)
        if latest_hk is not None:
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0) == 1:
                errors.append(
                    f"Mechanism heater is ON (THRM_STATUS.HMS={getattr(latest_hk.THRM_STATUS, 'HMS', 0)})"
                )
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0) == 1:
                errors.append(f"Detector heater is ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})")
        if errors:
            count = len(errors)
            numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
            info_log.info(f"PSU_EB_I: {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA")
            msg = (
                f"Heater config verification failed (mech ON, det ON): {count} error{'s' if count != 1 else ''} :\n"
                + "\n".join(numbered)
            )
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)
        else:
            msg = "Power State 2 : OB HEATING - PSU_EB_I: %.2f mA, CURRENT_OPERATING_STATE: %s,THRM_STATUS.HMS: %s, THRM_STATUS.HDS: %s"
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # Set HK Rate to 10 seconds
    ebtcs.set_hk_rate(interface, 0, 2)

   
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
    # ui_runtime_controller.perform_acq_check_sync(2100)
