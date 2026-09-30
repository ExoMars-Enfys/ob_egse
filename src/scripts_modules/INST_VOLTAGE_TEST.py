# from __future__ import annotations

import logging
import time
from typing import Any
from utility_modules import eb_interface, ebtcs
from utility_modules.background_checks import (
    switch_psu,
)
from widget_modules import ui_runtime_controller

info_log = logging.getLogger("info_log")


def run_inst_voltage_test(
    psu_port: Any = None,
    psu_lock: Any = None,
) -> None:
    interface = eb_interface.get_egse_interface()
    ui_runtime_controller.request_force_pause("Pause for SAFE Voltage checks")

    ebtcs.standby(
        interface, 5, 1
    )  #! Change according to what image you want to start. For EQM at 3.6.2 image 5 (25.09.26)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    ebtcs.hk_request(interface, 0)

    ui_runtime_controller.request_force_pause("Pause for STANDBY Voltage Checks")
    ebtcs.safe(interface, 0)
    ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
    time.sleep(3)
    switch_psu(psu_port, enabled=False, psu_lock=psu_lock)
    # End of FFT
    ui_runtime_controller.notify_script_done()
    
