# ----Module Imports---------------------------------------------------------------------------------
import logging

import serial
import serial.rs485
from datetime import datetime

from crc8Function import crc8Calculate
import tc

# ----Loggers----------------------------------------------------------------------------------------
formatter = logging.Formatter("{levelname} - {message}", style="{")

tm_log = logging.getLogger("tm_log")
hdlr_1 = logging.StreamHandler()
hdlr_1.setFormatter(formatter)
tm_log.setLevel(logging.DEBUG)
tm_log.addHandler(hdlr_1)

tc_log = logging.getLogger("tc_log")
tc_log.setLevel(logging.DEBUG)
tc_log.addHandler(hdlr_1)

# ----FPGA Boot and Connect--------------------------------------------------------------------------
port = serial.rs485.RS485(
    port="COM9",  # Serial Port Initialisation
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.1,
)
# port.rs485_mode = serial.rs485.RS485Settings(
#     rts_level_for_tx= False,
#     rts_level_for_rx= True,
#     loopback= False,
#     delay_before_tx = 0,
#     delay_before_rx= 0
# )
# port.flushOutput() #Port Flushing to clear port
# port.flushInput()

# ----

pwr = "04030000000000"
sci = "1F000000000000"
pwr = "04030000000000"

mtr_par = "0A 61A8 0006 0F FF"  # Set Motor Default Param
mtr_grd = "0B7F0064380005"  # Set Motor Drive Guards
mtr_p100 = "10010000000000"  # Move x0100 steps forward
mtr_mask = "0DFF0000000000"
mtr_home = "13070000000000"

hk_sam = "1B010000000000"

start_time = datetime.now()
# for i in range(3):
tc.hk_request(port)
tc.set_mtr_param(port, 0, 0, 0, 0)
tc.set_mtr_param(port, 0x61A8, 0x0006, 0x0F, 0xFF)

end_time = datetime.now()

print(f"Loop execution time: {(end_time - start_time)/3}")
