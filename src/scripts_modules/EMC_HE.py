# from __future__ import annotations

from queue import Empty
import time

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs
from widget_modules import ui_runtime_controller
import logging

info_log = logging.getLogger("info_log")

ebtcs.EBTCS_VERIFY_ENABLED = False


def run_emc_he() -> None:
    interface = eb_interface.get_egse_interface()

    #!Set TEC closed loop control setpoint to -35C
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    try:
        latest_hk = const.hk_queue.get(timeout=2.0)
    except Empty as exc:
        raise AssertionError("EMC_HE: missing HK queue data after TEC setpoint") from exc
    tec_setpoint = getattr(latest_hk, "TEC_SETPOINT", None)
    # 0xC018 is 49176 in decimal, check for exact match or tolerance if needed
    if tec_setpoint != 0xC018:
        raise AssertionError(f"EMC_HE: TEC_SETPOINT not set as expected (got {tec_setpoint:#06x}, expected 0xC018)")
    info_log.info(f"TEC setpoint confirmed: {tec_setpoint:#06x}")
    ui_runtime_controller.notify_script_pause(1, 10)

    #!Set Heater Configs to flight
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
    if not (110 <= ch4_current_ma <= 120):  #!Check Power consumptions
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
        "Power State 2 : OB HEATING - PSU_EB_I: %.2f mA,THRM_STATUS.HMS: %s, THRM_STATUS.HDS: %s",
        ch4_current_ma,
        getattr(latest_hk.THRM_STATUS, "HMS", 0),
        getattr(latest_hk.THRM_STATUS, "HDS", 0),
    )
    ui_runtime_controller.notify_script_pause(6, 10)

    i = 0
    while True:
        i += 1
        # Set acquisition configuration for ACQ High Emissions
        ebtcs.set_acq_configs(
            interface,
            0x00,  # ACQ_MODE: Sweep
            0x00,  # SCI_AVG: 0
            0x0000,  # RESERVED: 0
            0x0000,  # ACQ_SAMPLE_TIME:
            0x0000,  # ACQ_DURATION:
            0x00,  # ACQ_START_POINT : 5
            0x00AE,  # ACQ_END_POINT
            0x0,  # DETECTORS: Both
            0x1,  # PARK_MODE: Park at end
            0x1,  # CURRENT_SOL: 1
            0x1,  # MEAS_ID: 1
            i,  # RUN_NO: i
            0x01,  # CRITICALITY
            0x02,  # MEAS_TABLE: 2
        )
        # Set HK Rate back to 10 seconds (redundant but matches script)
        ebtcs.set_hk_rate(interface, 0, 10)
        # Send mode transition to Acquisition state
        ebtcs.acquisition(interface, 0x0)
        try:
            latest_hk = const.hk_queue.get(timeout=2.0)
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            raise AssertionError("Initial FFT verification failed: missing HK or PSU queue data") from exc

        # --- Start science acquisition timer in UI state (handled by UI async task) ---
        script_state = getattr(ui_runtime_controller, "script_state", None)
        if isinstance(script_state, dict):
            script_state["acq_timer_running"] = True
            script_state["acq_timer_start"] = time.time()

        while getattr(latest_hk, "CURRENT_OPERATING_STATE", None) == "ACQUISITION":
            info_log.info(
                f"Waiting to finish ACQUISITION - Current Operating State: {getattr(latest_hk, 'CURRENT_OPERATING_STATE', None)}, PSU_EB_I: {ch4_current_ma:.2f} mA"
            )
            time.sleep(1)
            try:
                latest_hk = const.hk_queue.get(timeout=2.0)
                latest_psu = const.psu_queue.get(timeout=2.0)
            except Empty as exc:
                raise AssertionError(
                    "Initial FFT verification failed: missing HK or PSU queue data during acquisition wait"
                ) from exc
            ch4_current_ma = float(latest_psu.get("PSU_EB_I") or 0.0) * 1000.0
        try:
            latest_sci = const.sci_queue.get(timeout=2.0)
        except Empty as exc:
            raise AssertionError("Initial FFT verification failed: missing SCI Packet") from exc

        # --- Stop science acquisition timer in UI state ---
        if isinstance(script_state, dict):
            script_state["acq_timer_running"] = False

        # Wait for SCI packet and mode to move to STANDBY (user should verify before proceeding)
        ui_runtime_controller.notify_script_pause(10, 10)
