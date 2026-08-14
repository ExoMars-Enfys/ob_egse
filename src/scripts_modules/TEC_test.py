from __future__ import annotations

import logging
from queue import Empty

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs
from utility_modules import eb_packet_utility as ebpu
from widget_modules import ui_runtime_controller

info_log = logging.getLogger("info_log")


def run_tec_test(verification: bool = False) -> None:
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
    ebtcs.standby(interface, 0, 0)
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

    ui_runtime_controller.abortible_sleep(1)
    for current in range(0, 4095, 205):
        ebtcs.set_tec_current(interface, 0, current)
        ui_runtime_controller.abortible_sleep(5)

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

        info_log.info(
            "TEC HK current report: setpoint=%d ADU, drive_current_adu=%s, tec_current=%s A, operating_state=%s",
            "PSU_EB_I=%s mA",
            current,
            tec_current_adu if tec_current_adu is not None else "N/A",
            f"{tec_current_a:.6f}" if tec_current_a is not None else "N/A",
            operating_state if operating_state is not None else "N/A",
            current,
            f"{measured_current_ma:.2f}" if measured_current_ma is not None else "N/A",
        )

    ui_runtime_controller.request_force_pause("Press to continue with the test")

    ebtcs.safe(interface, 0)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
