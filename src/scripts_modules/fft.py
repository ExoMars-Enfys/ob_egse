from __future__ import annotations

from queue import Empty

import time

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs, eb_packet_utility as ebpu
from widget_modules import ui_runtime_controller
import logging

info_log = logging.getLogger("info_log")


def run_fft(verification: bool = True) -> None:
    interface = eb_interface.get_egse_interface()
    # FFT.txt sequence

    # ?RET and first check - State 1
    interface = eb_interface.get_egse_interface()
    # RET command (SAFE mode)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    ebtcs.hk_request(interface, 0)
    if verification:
        msg, passed = ui_runtime_controller.verify_safe_ret()
        if not passed:
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(f"SAFE RET verification failed:\n{msg}")
        else:
            ui_runtime_controller.notify_positive(msg)

    time.sleep(2)
    # ?Transition to Standby and use automatic ASW - Standby
    ebtcs.standby(interface, 0, 0)
    ebtcs.hk_request(interface, 0)
    ebtcs.set_hk_rate(interface, 0, 1)
    time.sleep(2)
    if verification:
        msg, passed = ui_runtime_controller.verify_standby_ret()
        if not passed:
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(f"STANDBY RET verification failed:\n{msg}")
        else:
            info_log.info("STANDBY RET verification passed:\n%s", msg)
        ui_runtime_controller.notify_positive(msg)

    # ?Send Set Heater Configs + Enable Mech Heater - Standby + Mech HTR
    ebtcs.set_hk_rate(interface, 0, 1)
    ebtcs.set_heater_configs(interface, 0x00, 0x08A3, 0x0881, 0x08A3, 0x0881)
    ebtcs.hk_request(interface, 0)
    ebtcs.en_mech_heater(interface, 0x1)
    if verification:
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            errors.append("Missing HK or PSU queue data (mech ON, det OFF)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = None
        if latest_psu is not None:
            ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "MechHTR"], latest_psu, errors)
        if latest_hk is not None:
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0) != 1:
                errors.append(
                    f"Mechanism heater is not ON (THRM_STATUS.HMS={getattr(latest_hk.THRM_STATUS, 'HMS', 0)})"
                )
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0) != 0:
                errors.append(
                    f"Detector heater is not OFF (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})"
                )
        if errors:
            count = len(errors)
            numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
            info_log.info(f"PSU_EB_I: {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA")
            msg = (
                f"Heater config verification failed (mech ON, det OFF): {count} error{'s' if count != 1 else ''} :\n"
                + "\n".join(numbered)
            )
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)
        else:
            msg = f"Heater config: Mech ON, Det OFF. EB PSU I : {ch4_current_ma:.2f} mA"
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # ?Send Set Heater Configs + Enable Det Heater - Standby + Det HTR
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x1)
    if verification:
        errors = []
        try:
            latest_hk = const.hk_queue.get(timeout=2.0)
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            errors.append("Missing HK or PSU queue data (mech OFF, det ON)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = None
        if latest_psu is not None:
            ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "DetHTR"], latest_psu, errors)
        if latest_hk is not None:
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0) != 0:
                errors.append(
                    f"Mechanism heater is not OFF (THRM_STATUS.HMS={getattr(latest_hk.THRM_STATUS, 'HMS', 0)})"
                )
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0) != 1:
                errors.append(f"Detector heater is not ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})")
        if errors:
            count = len(errors)
            numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
            info_log.info(f"PSU_EB_I: {ch4_current_ma if ch4_current_ma is not None else 'N/A'} mA")
            msg = (
                f"Heater config verification failed (mech OFF, det ON): {count} error{'s' if count != 1 else ''} :\n"
                + "\n".join(numbered)
            )
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)
        else:
            msg = f"Heater config: Mech OFF, Det ON. EB PSU I : {ch4_current_ma:.2f} mA"
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # ?Turn on both heaters - State 2 - OB Heating
    ebtcs.en_mech_heater(interface, 0x1)
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
            ch4_current_ma = ui_runtime_controller.consumption_check(["State2"], latest_psu, errors)
        if latest_hk is not None:
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0) != 1:
                errors.append(
                    f"Mechanism heater is not ON (THRM_STATUS.HMS={getattr(latest_hk.THRM_STATUS, 'HMS', 0)})"
                )
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0) != 1:
                errors.append(f"Detector heater is not ON (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})")
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
            msg = (
                f"Power State 2 : OB HEATING - PSU_EB_I: {ch4_current_ma if ch4_current_ma is not None else 0.0:.2f} mA, "
                f"CURRENT_OPERATING_STATE: {getattr(latest_hk, 'CURRENT_OPERATING_STATE', None)}, "
                f"THRM_STATUS.HMS: {getattr(getattr(latest_hk, 'THRM_STATUS', None), 'HMS', 0)}, "
                f"THRM_STATUS.HDS: {getattr(getattr(latest_hk, 'THRM_STATUS', None), 'HDS', 0)}"
            )
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # ?Set Heater Configs to flight - Standby | State 2 - OB Heating
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    htr = False
    if verification:
        hk = ebpu.get_latest_hk()
        trp = getattr(hk, "OB_DIGITAL_TRP")
        if ( trp < 1848):
            htr = True
        else:
            htr = False
        errors = []
        try:
            latest_hk = const.hk_queue.get(timeout=2.0)
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            errors.append("Missing HK or PSU queue data (mech ON, det ON)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = None
        if htr and latest_psu is not None:
            ch4_current_ma = ui_runtime_controller.consumption_check(["State2"], latest_psu, errors)
        elif latest_psu is not None:
            ui_runtime_controller.consumption_check(["Standby"], latest_psu, errors)
        if latest_hk is not None:
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0) != htr:
                errors.append(f"Mechanism heater is {'OFF' if htr else 'ON'} (THRM_STATUS.HMS={getattr(latest_hk.THRM_STATUS, 'HMS', 0)})")
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0) != htr:
                errors.append(f"Detector heater is {'OFF' if htr else 'ON'} (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})")
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

    # ?Turn on the mechanism board, set configs and home - State 2 + Mech Board ON + Moving
    ebtcs.en_mech_board(interface, 0x1)
    ebtcs.set_motor_configs(interface, 0, 0x40, 0x00, 0x08, 0x00, 0x00, 0x3C, 0x00, 0x0000, 0x00)
    ebtcs.ob_homing(interface, 0x01)
    # Wait until homing is completed
    homing_timeout_s = 60.0
    start_time = time.monotonic()
    latest_hk = const.hk_queue.get(timeout=2.0)
    homing_complete = getattr(latest_hk.INSTRUMENT_STATUS_FLAGS, "HOMING_COMPLETE", 0)
    if homing_complete == 0:
        while homing_complete == 0:
            time.sleep(1)  # Sleep briefly to avoid tight loop if HK updates are very frequent
            latest_hk = const.hk_queue.get(timeout=2.0)
            latest_psu = const.psu_queue.get(timeout=2.0)
            hk_time = getattr(latest_hk, "TIME", None)
            homing_complete = getattr(latest_hk.INSTRUMENT_STATUS_FLAGS, "HOMING_COMPLETE", 0)
            ch4_current_ma = ui_runtime_controller.consumption_check(["State2", "Mech","Moving"], latest_psu, [])
            info_log.info(
                f"Polling HK for HOMING_COMPLETE flag... Current value: {homing_complete}, HK TIME: {hk_time}"
            )

            if homing_complete == 1:
                break
            if time.monotonic() - start_time > homing_timeout_s:
                info_log.error("Timeout waiting for HOMING_COMPLETE flag in HK telemetry (waited 60s)")
                ui_runtime_controller.notify_negative("Timeout waiting for HOMING_COMPLETE flag in HK telemetry.")
                raise TimeoutError("Timeout waiting for HOMING_COMPLETE flag in HK telemetry.")
    ui_runtime_controller.notify_positive(f"HOMING_COMPLETE flag detected in HK telemetry. {homing_complete}")

    # ?Turn on TEC - State 2 + Mech Board ON + TEC at 1A
    ebtcs.set_tec_current(interface, 0x00, 0xFFF)
    # Verification: TEC current > 1A and PSU current as expected, wait for TEC at setpoint
    if verification:
        errors = []
        tec_at_setpoint = False
        while not tec_at_setpoint:
            try:
                latest_hk = const.hk_queue.get(timeout=2.0)
                latest_psu = const.psu_queue.get(timeout=2.0)
            except Empty:
                continue
            # Check TEC current > 1A
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162 if latest_hk is not None else 0
            if tec_current <= 1.0:
                errors.append(f"TEC current too low: {tec_current:.3f} A (expected > 1A)")
            # Check PSU current for this state
            ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "Mech", "TEC1A"], latest_psu, errors)
            # Wait for TEC at setpoint (example: assume HK has attribute TEC_AT_SETPOINT)
            tec_at_setpoint = getattr(latest_hk, "TEC_AT_SETPOINT", False)
        if errors:
            msg = "\n".join(errors)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)

    # ?Turn off TEC - State 2 + Mech Board
    ebtcs.set_tec_current(interface, 0x00, 0x000)
    # Verification: TEC current = 0 and PSU current as expected
    if verification:
        errors = []
        try:
            latest_hk = const.hk_queue.get(timeout=2.0)
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty:
            latest_hk = None
            latest_psu = None
        tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162 if latest_hk is not None else 0
        if abs(tec_current) > 0.01:
            errors.append(f"TEC current not zero: {tec_current:.4f} A (expected 0)")
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "Mech", "TEC1A"], latest_psu, errors)
        if errors:
            msg = "\n".join(errors)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)

    # ?Set TEC setpoint to -35oC, enable detectors, and start acquisition
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.en_det_board(interface, 0x1)
    if verification:
        errors = []
        try:
            latest_hk = const.hk_queue.get(timeout=2.0)
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty:
            errors.append("Missing HK or PSU queue data (mech ON, det ON, TEC setpoint -35C)")
            latest_hk = None
            latest_psu = None
        # Check Detector board is ON
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "Mech", "Det"], latest_psu, errors)
        if latest_hk is not None:
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0) != htr:
                errors.append(f"Mechanism heater is {'OFF' if htr else 'ON'} (THRM_STATUS.HMS={getattr(latest_hk.THRM_STATUS, 'HMS', 0)})")
        if errors:
            msg = "\n".join(errors)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)


    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)
    # Verification: Check transition into and out of acquisition, and science packet
    if verification:
        errors = []
        # Wait for entering acquisition state
        entered_acquisition = False
        while True:
            try:
                latest_hk = const.hk_queue.get(timeout=2.0)
            except Empty:
                continue
            state = getattr(latest_hk, "CURRENT_OPERATING_STATE", None)
            if state == "ACQUISITION":
                entered_acquisition = True
                break
        if not entered_acquisition:
            errors.append("Did not enter ACQUISITION state.")
        # Wait for exit from acquisition (i.e., state changes from ACQUISITION)
        exited_acquisition = False
        while True:
            try:
                latest_hk = const.hk_queue.get(timeout=2.0)
            except Empty:
                continue
            state = getattr(latest_hk, "CURRENT_OPERATING_STATE", None)
            if state != "ACQUISITION":
                exited_acquisition = True
                break
        if not exited_acquisition:
            errors.append("Did not exit ACQUISITION state.")
        # Check for science packet (assume science packets are in const.sci_queue)
        found_science = False
        try:
            sci_packet = const.sci_queue.get(timeout=2.0)
            found_science = sci_packet is not None
        except Empty:
            found_science = False
        if not found_science:
            errors.append("No science packet found after acquisition.")
        if errors:
            count = len(errors)
            numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
            msg = f"Acquisition verification failed: {count} error{'s' if count != 1 else ''} :\n" + "\n".join(numbered)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)

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
    htr = False
    if verification:
        hk = ebpu.get_latest_hk()
        trp = getattr(hk, "OB_DIGITAL_TRP")
        if ( trp < 1848):
            htr = True
        else:
            htr = False
        errors = []
        try:
            latest_hk = const.hk_queue.get(timeout=2.0)
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            errors.append("Missing HK or PSU queue data (mech ON, det ON)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = None
        if latest_psu is not None:
            ui_runtime_controller.consumption_check(["State2"], latest_psu, errors)
        if latest_hk is not None:
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HMS", 0) != htr:
                errors.append(f"Mechanism heater is {'OFF' if htr else 'ON'} (THRM_STATUS.HMS={getattr(latest_hk.THRM_STATUS, 'HMS', 0)})")
            if hasattr(latest_hk, "THRM_STATUS") and getattr(latest_hk.THRM_STATUS, "HDS", 0) != htr:
                errors.append(f"Detector heater is {'OFF' if htr else 'ON'} (THRM_STATUS.HDS={getattr(latest_hk.THRM_STATUS, 'HDS', 0)})")
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


    ebtcs.set_tec_current(interface, 0x00, 0x000)

    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.set_acq_configs(
        interface, 0x01, 0x00, 0x0000, 0x03E8, 0x05DC, 0x0005, 0x0, 0x02, 0x1, 0x1, 0x1, 0x1, 0x00, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)
    #!Add Sci check


    ui_runtime_controller.request_force_pause(f"Remove Baffle Hat and continue with acquisition. Click to continue once ready.")
    ebtcs.set_hk_rate(interface, 0, 1)

    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)

    #!Add Sci check

    ebtcs.safe(interface, 0)

    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
