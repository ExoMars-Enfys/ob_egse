from __future__ import annotations

import logging
from utility_modules import eb_interface, ebtcs
from utility_modules import eb_packet_utility as ebpu
from widget_modules import ui_runtime_controller

info_log = logging.getLogger("info_log")


def run_general_Error_test(verification: bool = False) -> None:
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
    ebtcs.en_mech_board(interface, 1)
    if verification:
        errors = []
        latest_hk = ebpu.get_latest_hk()
        if latest_hk is not None:
            if (
                hasattr(latest_hk, "OB_MECHANISM_BOARD_ENABLED")
                and getattr(latest_hk, "OB_MECHANISM_BOARD_ENABLED", None) != 1
            ):
                errors.append(
                    f"Mech Board is not on (PWR STAT={getattr(latest_hk, 'OB_MECHANISM_BOARD_ENABLED', None)})"
                )
        if errors:
            msg = "\n".join(errors)
            ui_runtime_controller.notify_negative(msg)
            raise AssertionError(msg)

    ebtcs.ob_homing(interface, 0x03)
    ui_runtime_controller.perform_homing_check_sync()
    ebtcs.ob_homing(interface, 0x00)
    ui_runtime_controller.perform_homing_check_sync()
    ebtcs.set_acq_configs(
        interface, 0x00, 0x00, 0x0000, 0x0000, 0x0000, 0x0000, 0x00AE, 0x00, 0x1, 0x1, 0x1, 0x1, 0x01, 0x02
    )
    ebtcs.set_hk_rate(interface, 0, 2)
    ebtcs.acquisition(interface, 0x0)
    ui_runtime_controller.abortible_sleep(2)
    if verification:
        ui_runtime_controller.perform_acq_check_sync()
    ui_runtime_controller.request_force_pause("Press to continue with the test")

    ebtcs.ob_homing(interface, 0x02)
    ui_runtime_controller.perform_homing_check_sync()
    ui_runtime_controller.request_force_pause("Click to continue once ready.")

    ebtcs.generic_tc(interface, 0x1, 0x0A, 0x01, 0xE0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    ui_runtime_controller.request_force_pause("Click to continue once ready.")
    ebtcs.safe(interface, 0)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    # End of FFT
    ui_runtime_controller.notify_script_done()
