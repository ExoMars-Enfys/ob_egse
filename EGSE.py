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
    port="COM14",  # Serial Port Initialisation
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.2,
)
# port.rs485_mode = serial.rs485.RS485Settings(
#     rts_level_for_tx=False,
#     rts_level_for_rx=True,
#     loopback=False,
#     delay_before_tx=0,
#     delay_before_rx=0,
# )
port.flushOutput()  # Port Flushing to clear port
port.flushInput()

# ----

pwr = "04030000000000"
sci = "1F000000000000"
pwr = "04030000000000"

mtr_par = "0A61A800060FFF"  # Set Motor Default Param
mtr_grd = "0B7F0064380005"  # Set Motor Drive Guards
mtr_p100 = "10032000000000"  # Move x0100 steps forward
mtr_mask = "0DFF0000000000"
mtr_home = "13070000000000"

hk_sam = "1B010000000000"


def script_homing(HEATERS=False):
    tc.hk_request(port)
    time.sleep(1)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    time.sleep(1)
    tc.set_mtr_param(port, 0x61A8, 0x0006, 0x0F, 0xFF)
    time.sleep(1)
    tc.set_mtr_guard(port, 0x0F, 0x0064, 0x38, 0x0005)
    time.sleep(1)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
    time.sleep(1)
    tc.mtr_homing(port, True, False, True)


def script_repeat_hk():
    for i in range(20):
        tc.hk_request(port)
        time.sleep(0.25)


start_time = datetime.now()
# tc.power_control(port, 0xC3)
# time.sleep(1)
# tc.set_mtr_param(port, 0x7000, 0x0006, 0x0F, 0xFF)
# time.sleep(1)
# tc.hk_request(port)
# time.sleep(1)
# tc.mtr_mov_pos(port, 0x0500)
# time.sleep(0.4)
# for i in range(20):
# tc.hk_request(port)
# time.sleep(1.0)

# tc.clear_errors(port)
# tc.hk_request(port)
# tc.sci_request(port)
# tc.clear_errors(port)
tc.power_control(port, 0x03)
# tc.mtr_mov_pos(port, 0x0100)
# tc.power_control(port, 0x00)
# for i in range(3):
#     tc.hk_request(port)
#     tc.set_mtr_param(port, 0, 0, 0, 0)
#     tc.set_mtr_param(port, 0x61A8, 0x0006, 0x0F, 0xFF)

# script_homing(True)
# script_repeat_hk()
# tc.set_mtr_guard(port, 0x0F, 0x0064, 0x38, 0x0005)


end_time = datetime.now()

print(f"Loop execution time: {(end_time - start_time)/3}")
