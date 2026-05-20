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
    ebtcs.set_heater_configs(interface, 0x00, 0x08A3, 0x0881, 0x08A3, 0x0881)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    time.sleep(2)
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
    ebtcs.hk_request(interface, 0)
    time.sleep(2)
    if verification:
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
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
    ebtcs.hk_request(interface, 0)
    time.sleep(2)
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
    ebtcs.hk_request(interface, 0)
    time.sleep(2)
    htr = False
    time.sleep(1)
    if verification:
        hk = ebpu.get_latest_hk()
        trp = getattr(hk, "OB_DIGITAL_TRP")
        if ( trp < 1848):
            htr = True
        else:
            htr = False
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
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
    ui_runtime_controller.perform_homing_check_sync()

    # ?Turn on TEC - State 2 + Mech Board ON + TEC at 1A
    ebtcs.set_tec_current(interface, 0x00, 0xFFF)
    ebtcs.hk_request(interface, 0)
    # Verification: TEC current > 1A and PSU current as expected, wait for TEC ramp up
    if verification:
        errors = []
        tec_ramped = False
        timeout_count = 0
        while not tec_ramped and timeout_count < 30:
            time.sleep(1)
            timeout_count += 1
            try:
                latest_hk = ebpu.get_latest_hk()
                latest_psu = const.psu_queue.get(timeout=2.0)
            except Empty:
                continue
            if latest_hk is None:
                continue
            # Check TEC current > 1A
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
            if tec_current <= 1.0:
                continue  # Keep waiting
            else:
                tec_ramped = True
            # Check PSU current for this state
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "Mech", "TEC1A"], latest_psu, errors)
        
        if timeout_count >= 30:
            errors.append("Timeout waiting for TEC current to reach > 1A")
        if errors:
            msg = "\n".join(errors)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)

    # ?Turn off TEC - State 2 + Mech Board
    ebtcs.set_tec_current(interface, 0x00, 0x000)
    # Verification: TEC current = 0 and PSU current as expected
    ebtcs.hk_request(interface, 0)
    time.sleep(2)
    if verification:
        errors = []
        tec_ramped = False
        timeout_count = 0
        while not tec_ramped and timeout_count < 30:
            time.sleep(1)
            timeout_count += 1
            try:
                latest_hk = ebpu.get_latest_hk()
                latest_psu = const.psu_queue.get(timeout=2.0)
            except Empty:
                continue
            if latest_hk is None:
                continue
            # Check TEC current > 1A
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
            if tec_current >= 0.01:
                continue  # Keep waiting
            else:
                tec_ramped = True
            # Check PSU current for this state
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "Mech"], latest_psu, errors)

    # ?Set TEC setpoint to -35oC, enable detectors, and start acquisition
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.en_det_board(interface, 0x1)
    time.sleep(1)
    if verification:
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
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
    time.sleep(1)
    if verification:
        ui_runtime_controller.perform_acq_check_sync()

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
    ui_runtime_controller.perform_homing_check_sync()

    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)

    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    htr = False
    time.sleep(2)
    if verification:
        hk = ebpu.get_latest_hk()
        trp = getattr(hk, "OB_DIGITAL_TRP")
        if ( trp < 1848):
            htr = True
        else:
            htr = False
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            errors.append("Missing HK or PSU queue data (mech ON, det ON)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = None
        if latest_psu is not None:
            if htr:
                 ch4_current_ma = ui_runtime_controller.consumption_check(["State2","MechHTR", "DetHTR", "TEC1A"], latest_psu, errors)
            else:
                ch4_current_ma = ui_runtime_controller.consumption_check(["State2", "TEC1A"], latest_psu, errors)
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
        interface, 0x01, 0x00, 0x0000, 0x0064, 0x0078, 0x0005, 0x0, 0x02, 0x1, 0x1, 0x1, 0x1, 0x00, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)
    time.sleep(1)
    if verification:
        ui_runtime_controller.perform_acq_check_sync()

    ui_runtime_controller.request_force_pause(f"Remove Baffle Hat and continue with acquisition. Click to continue once ready.")
    ebtcs.set_hk_rate(interface, 0, 1)

    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)
    time.sleep(1)
    if verification:
        ui_runtime_controller.perform_acq_check_sync()

    ebtcs.safe(interface, 0)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    # End of FFT
    ui_runtime_controller.notify_script_done()
