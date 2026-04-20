# from __future__ import annotations

from queue import Empty
import time

from core_modules import constants as const
from utility_modules import eb_interface, ebtcs
from widget_modules import ui_runtime_controller
import logging

info_log = logging.getLogger("info_log")


def run_emc_he() -> None:
    interface = eb_interface.get_egse_interface()

    #!Set TEC closed loop control setpoint to -35C
    ebtcs.set_tec_current(interface, 0, 0xFFFF)
    ebtcs.update_tc_t(0.1)
    for i in range(100):
        ebtcs.generic_tc(
            interface,
            0x1,
            0x09,
            0x00,
            0x1E,
            0x00,
            0x00,
            0x00,
            0x00,
            0x55,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        )  # Send move 30steps
        ebtcs.generic_tc(
            interface,
            0x1,
            0x0F,
            0x08,
            0x64,
            0x00,
            0x00,
            0x00,
            0x00,
            0x95,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        )  # Send move 30steps
    info_log.info("Completed 100 iterations of HE command")
