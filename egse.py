# ----Module Imports---------------------------------------------------------------------------------
import logging
import time

import serial
import serial.rs485
from datetime import datetime

from crc8Function import crc8Calculate
import tc

DEBUG_LEVEL = logging.DEBUG

# ----Loggers----------------------------------------------------------------------------------------
formatter = logging.Formatter("{levelname} - {message}", style="{")

tm_log = logging.getLogger("tm_log")
hdlr_1 = logging.StreamHandler()
hdlr_1.setFormatter(formatter)
tm_log.setLevel(DEBUG_LEVEL)
tm_log.addHandler(hdlr_1)

tc_log = logging.getLogger("tc_log")
tc_log.setLevel(DEBUG_LEVEL)
tc_log.addHandler(hdlr_1)

# ----FPGA Boot and Connect--------------------------------------------------------------------------
port = serial.rs485.RS485(
    port="COM10",  # Serial Port Initialisation
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.2,
)
port.rs485_mode = serial.rs485.RS485Settings(
    rts_level_for_tx=False,
    rts_level_for_rx=True,
    loopback=False,
    delay_before_tx=0.1,
    delay_before_rx=0.1,
)
port.flushOutput()  # Port Flushing to clear port
port.flushInput()

# ----

sci = "1F000000000000"


def script_homing_default(HEATERS=False):
    tc.hk_request(port)
    time.sleep(1)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    time.sleep(1)
    tc.set_mtr_param(port, 0x61A8, 0x0006, 0x04, 0xFF)
    time.sleep(1)
    tc.set_mtr_guard(port, 0x03, 0x0064, 0x3E, 0x0005)
    time.sleep(1)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
    time.sleep(1)
    tc.hk_request(port)
    tc.mtr_homing(port, True, False, True)


def script_homing(HEATERS=False):
    tc.hk_request(port)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    # tc.set_mtr_param(port, 0x4000, 0x0001, 0x04, 0x5F)
    tc.set_mtr_param(port, 0x4000, 0x0001, 0x04, 0xFF)
    tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
    # tc.mtr_homing(port, True, False, True)
    tc.mtr_mov_pos(port, 0x1000)
    resp = tc.hk_request(port)
    while resp.MTR_FLAGS.MOVING == 1:
        time.sleep(1)
        resp = tc.hk_request(port)
        tm_log.info("Motor still moving ***********")


def script_repeat_hk():
    for i in range(20):
        tc.hk_request(port)
        time.sleep(1)


start_time = datetime.now()

# script_repeat_hk()
# tc.power_control(port, 0x00)

# hk = tc.hk_request(port)
# tc_log.info(f"Heater Before: {hk.THRM_STATUS}")
# tc.set_mech_sp(port, 0x0ABC, 0x0123)
# tc.set_detec_sp(port, 0x0DEF, 0x0456)
# # tc.heater_control(port, False, True, False, False, True, verify=True)
# hk = tc.hk_request(port)
# tc_log.info(f"Heater After: {hk.THRM_STATUS}")
# tc_log.info(f"Mech_OFF_SP: {hk.THRM_MECH_OFF_SP:04X}")
# tc_log.info(f"Mech_ON_SP: {hk.THRM_MECH_ON_SP:04X}")
# tc_log.info(f"Detec_OFF_SP: {hk.THRM_DET_OFF_SP:04X}")
# tc_log.info(f"Detec_ON_SP: {hk.THRM_DET_ON_SP:04X}")

# tc.set_mtr_param(port, 0x61A8, 0x0006, 0x04, 0xFF)
# tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)
# tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
# tc.clear_errors(port)
# tc.sci_request(port)
# tc.clear_errors(port)

# script_homing_default(False)
# script_homing(False)
# tc.mtr_mov_pos(port, 0x1000)
end_time = datetime.now()


print(f"Loop execution time: {(end_time - start_time)/3}")
