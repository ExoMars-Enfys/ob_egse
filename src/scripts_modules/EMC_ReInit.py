# from __future__ import annotations


import logging

from utility_modules import eb_interface, ebtcs
from widget_modules import ui_runtime_controller

info_log = logging.getLogger("info_log")


def run_emc_reinit() -> None:
    interface = eb_interface.get_egse_interface()

    # Set delay between TCs (t 500 in script, but handled by ebtcs flow control)

    # Requesting a ASW Housekeeping packet
    ebtcs.hk_request(interface, 0)
    ui_runtime_controller.notify_script_pause(1, 108)
    ui_runtime_controller.request_force_pause()

    # Configure Heaters for Flight (Upper - 1946 -24 ) (Lower - 1848 -45 )
    ebtcs.set_heater_configs(interface, 0x00, 0x079A, 0x0738, 0x079A, 0x0738)
    ebtcs.en_mech_heater(interface, 0x1)
    ebtcs.en_det_heater(interface, 0x1)

    # Wait for OB Heater status flags to be 'warm' else send generic command to force
    # ebtcs.generic_tc(interface, 0x0, 0x6, 0x64, 0xC4, 0x01, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0) # Uncomment if needed
    ui_runtime_controller.notify_script_pause(2, 108)
    ui_runtime_controller.request_force_pause()

    # Enable the Mechanism board
    ebtcs.en_mech_board(interface, 0x1)
    # Enable the OB Detector board
    ebtcs.en_det_board(interface, 0x1)
    # Set the Motor Parameters to defaults
    ebtcs.set_motor_configs(interface, 0, 0x40, 0x00, 0x08, 0x00, 0x00, 0x3C, 0x00, 0x0000, 0x00)
    # Perform Homing Cal to Base then Drive to Outer
    ebtcs.ob_homing(interface, 0x01)

    # Wait/check for OBHOMED flag (user should verify before proceeding)
    ui_runtime_controller.notify_script_pause(3, 108)
    ui_runtime_controller.request_force_pause()
