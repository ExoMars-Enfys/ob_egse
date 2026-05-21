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
            raise AssertionError(f"SAFE RET verification failed:\n{msg}")

    time.sleep(3.5)
    # ?Transition to Standby and use automatic ASW - Standby
    ebtcs.standby(interface, 0, 0)
    ebtcs.hk_request(interface, 0)
    ebtcs.set_hk_rate(interface, 0, 1)
    time.sleep(3.5)
    if verification:
        msg, passed = ui_runtime_controller.verify_standby_ret()
        if not passed:
            raise AssertionError(f"STANDBY RET verification failed:\n{msg}")
        else:
            info_log.info("STANDBY RET verification passed:\n%s", msg)

    # ?Send Set Heater Configs + Enable Mech Heater - Standby + Mech HTR
    ebtcs.set_heater_configs(interface, 0x00, 0x08A3, 0x0881, 0x08A3, 0x0881)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            errors.append("Missing HK or PSU queue data (mech ON, det OFF)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby"], latest_psu, errors, latest_hk) if latest_psu is not None else None
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
            msg = f"Heater config: Mech ON, Det OFF — PSU_EB_I: {ch4_current_ma:.2f} mA"
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # ?Send Set Heater Configs + Enable Det Heater - Standby + Det HTR
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty as exc:
            errors.append("Missing HK or PSU queue data (mech OFF, det ON)")
            latest_hk = None
            latest_psu = None
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby"], latest_psu, errors, latest_hk) if latest_psu is not None else None
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
            msg = f"Heater config: Mech OFF, Det ON — PSU_EB_I: {ch4_current_ma:.2f} mA"
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # ?Turn on both heaters - State 2 - OB Heating
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        msg, passed = ui_runtime_controller.verify_power_state("State2")
        if not passed:
            raise AssertionError(msg)

    # ?Set Heater Configs to flight
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        errors = []
        try:
            latest_hk = ebpu.get_latest_hk()
            latest_psu = const.psu_queue.get(timeout=2.0)
        except Empty:
            errors.append("Missing HK or PSU queue data (flight HTR configs)")
            latest_hk = None
            latest_psu = None
        # Heaters are in automatic mode with flight configs — actual HMS/HDS depends on
        # temperature, so verify_heater_states will add only the physically active ones.
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby"], latest_psu, errors, latest_hk) if latest_psu is not None else None
        if errors:
            count = len(errors)
            numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
            msg = f"Flight HTR config verification failed: {count} error{'s' if count != 1 else ''}:\n" + "\n".join(numbered)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)
        else:
            msg = (
                f"Flight HTR config OK — PSU_EB_I: {ch4_current_ma:.2f} mA, "
                f"CURRENT_OPERATING_STATE: {getattr(latest_hk, 'CURRENT_OPERATING_STATE', None)}"
            )
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
        latest_hk = None
        latest_psu = None
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
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
            if tec_current <= 1.0:
                continue  # Keep waiting
            tec_ramped = True
        if not tec_ramped:
            errors.append("Timeout waiting for TEC current to reach > 1A")
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "Mech", "TEC1A"], latest_psu, errors, latest_hk) if latest_psu is not None else None
        if errors:
            count = len(errors)
            numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
            msg = f"TEC ramp-up verification failed: {count} error{'s' if count != 1 else ''}:\n" + "\n".join(numbered)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)
        else:
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
            msg = f"TEC ramp-up OK — TEC: {tec_current:.3f} A, PSU_EB_I: {ch4_current_ma:.2f} mA"
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # ?Turn off TEC - State 2 + Mech Board
    ebtcs.set_tec_current(interface, 0x00, 0x000)
    # Verification: TEC current = 0 and PSU current as expected
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        errors = []
        tec_off = False
        timeout_count = 0
        latest_hk = None
        latest_psu = None
        while not tec_off and timeout_count < 30:
            time.sleep(1)
            timeout_count += 1
            try:
                latest_hk = ebpu.get_latest_hk()
                latest_psu = const.psu_queue.get(timeout=2.0)
            except Empty:
                continue
            if latest_hk is None:
                continue
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
            if tec_current >= 0.01:
                continue  # Keep waiting
            tec_off = True
        if not tec_off:
            errors.append("Timeout waiting for TEC current to reach 0 A")
        ch4_current_ma = ui_runtime_controller.consumption_check(["Standby", "Mech"], latest_psu, errors, latest_hk) if latest_psu is not None else None
        if errors:
            count = len(errors)
            numbered = [f"{i + 1}. {err.strip()}" for i, err in enumerate(errors)]
            msg = f"TEC ramp-down verification failed: {count} error{'s' if count != 1 else ''}:\n" + "\n".join(numbered)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)
        else:
            tec_current = getattr(latest_hk, "EB_TEC_DRIVE_CURRENT", 0) * 0.0000162
            msg = f"TEC off OK — TEC: {tec_current:.4f} A, PSU_EB_I: {ch4_current_ma:.2f} mA"
            info_log.info(msg)
            ui_runtime_controller.notify_positive(msg)

    # ?Set TEC setpoint to -35oC, enable detectors, and start acquisition
    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.en_det_board(interface, 0x1)
    time.sleep(1)
    if verification:
        errors = []
        latest_hk = ebpu.get_latest_hk()
        if latest_hk is not None:
            if hasattr(latest_hk, "TEC_SETPOINT") and getattr(latest_hk, "TEC_SETPOINT", None) != 0xC018:
                errors.append(f"TEC setpoint is not -35C (HK TEC_SETPOINT={getattr(latest_hk, 'TEC_SETPOINT', None)})")
        if errors:
            msg = "\n".join(errors)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)

    # ?State 6 SCI ACQ
    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 2)
    ebtcs.acquisition(interface, 0x0)
    time.sleep(1)
    if verification:
        ui_runtime_controller.perform_acq_check_sync()

    # ?State3 - OB Heating + Powered On
    ebtcs.set_hk_rate(interface, 0, 1)
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x08D3, 0x08A3 ,0x08D3, 0x08A3)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    ebtcs.generic_tc(interface, 0x0, 0x6, 0x64, 0xC4, 0x01, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0)

    ebtcs.en_mech_board(interface, 0x1)
    ebtcs.en_det_board(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        msg, passed = ui_runtime_controller.verify_power_state("State3")
        if not passed:
            raise AssertionError(msg)

    #? State4 - OB Heating + Powered On + TEC at 1A
    ebtcs.set_tec_current(interface, 0x00, 0xFFF)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        msg, passed = ui_runtime_controller.verify_power_state("State4")
        if not passed:
            raise AssertionError(msg)

    # ?State 7 - All Active (OB Heating + Powered On + TEC at 1A + Moving)
    ebtcs.set_motor_configs(interface, 0, 0x40, 0x00, 0x08, 0x00, 0x00, 0x3C, 0x00, 0x0000, 0x00)
    ebtcs.ob_homing(interface, 0x01)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        msg, passed = ui_runtime_controller.verify_power_state("State7")
        if not passed:
            raise AssertionError(msg)

    ui_runtime_controller.perform_homing_check_sync()
    ui_runtime_controller.notify_script_pause(13, 13)
    
    time.sleep(3.5)
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)

    # ?State 5 - Powered On + TEC at 1A (Heaters off, mech board on, TEC at 1A)
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        msg, passed = ui_runtime_controller.verify_power_state("State5")
        if not passed:
            raise AssertionError(msg)


    ebtcs.set_tec_current(interface, 0x00, 0x000)

    ebtcs.set_tec_setpoint(interface, 0x0, 0xC018)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        errors = []
        latest_hk = ebpu.get_latest_hk()
        if latest_hk is not None:
            if hasattr(latest_hk, "TEC_SETPOINT") and getattr(latest_hk, "TEC_SETPOINT", None) != 0xC018:
                errors.append(f"TEC setpoint is not -35C (HK TEC_SETPOINT={getattr(latest_hk, 'TEC_SETPOINT', None)})")
        if errors:
            msg = "\n".join(errors)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)

    # ?State 6 SCI ACQ with heaters ON
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x08A3, 0x0881, 0x08A3, 0x0881)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)    
    ebtcs.set_acq_configs(
        interface, 0x01, 0x00, 0x0000, 0x0064, 0x0078, 0x0005, 0x0, 0x00, 0x1, 0x1, 0x1, 0x1, 0x00, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 10)
    ebtcs.acquisition(interface, 0x0)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        ui_runtime_controller.perform_acq_check_sync(acq_mode=2, acq_duration_s=0x0078, acq_sample_time_ms=0x0064)

    ui_runtime_controller.request_force_pause(f"Remove Baffle Hat and continue with acquisition. Click to continue once ready.")
    ebtcs.set_hk_rate(interface, 0, 1)

    #?State 6 SCI ACQ with heaters OFF and baffle hat off
    ebtcs.en_mech_heater(interface, 0x0)
    ebtcs.en_det_heater(interface, 0x0)
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)

    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 2)
    ebtcs.acquisition(interface, 0x0)
    ebtcs.hk_request(interface, 0)
    time.sleep(3.5)
    if verification:
        ui_runtime_controller.perform_acq_check_sync()

    ebtcs.safe(interface, 0)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    # End of FFT
    ui_runtime_controller.notify_script_done()
