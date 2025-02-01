# ----Module Imports--------------------------------------------------------------------------------
# Std library
import logging
import time
import sys
import atexit
import argparse
from pathlib import Path
from datetime import datetime

# Added packages
import serial.rs485

# Local modules
import constants as const
import egse_logger
import sequences as sq
import tc

## ----Constants -----------------------------------------------------------------------------------



## ----Script Start --------------------------------------------------------------------------------

parser = argparse.ArgumentParser(
                prog='ob_egse',
                description = 'Exercise OB EGSE')
parser.add_argument('-prefix', type=ascii, default=const.DEFAULT_PREFIX)
parser.add_argument('-com', type=int, default=const.DEFAULT_COM_PORT,)
parser.add_argument('-basedir', type=Path, default=const.DEFAULT_PATH)
args=parser.parse_args()

com_port = 'COM' + str(args.com)

prefix = str(args.prefix).strip("'")
basedir = args.basedir

if basedir == const.DEFAULT_PATH:
    basedir.mkdir(parents=True)

tm_log, tc_log, event_log, info_log, error_log, abs_log, cmd_log, ack_log = egse_logger.get_loggers(basedir, prefix, const.DEBUG_LEVEL)

# ----FPGA Boot and Connect-------------------------------------------------------------------------
try:
    port = serial.rs485.RS485(
        port=com_port,
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_ODD,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.2,
    )
except serial.SerialException:
    tc_log.error(f"No device found on COM Port {com_port}, try another")
    raise SystemExit

port.rs485_mode = serial.rs485.RS485Settings(
    rts_level_for_tx=False,
    rts_level_for_rx=True,
    loopback=False,
    delay_before_tx=0.1,
    delay_before_rx=0.1,
)
port.flushOutput()  # Port Flushing to clear port
port.flushInput()

@atexit.register
def clean_exit():
    sys.exit(1001)
    #! TODO Add code here, possibly try and power insturment off
    #! TODO power off power supply
    #! TODO ensure all logs are written

start_time = datetime.now()

# hk = tc.hk_request(port)                                                      #cmd 00
# tc.clear_errors(port)                                                         #cmd 01
# TODO: Add set errors      (02)
# tc.power_control(port, 0x03)                                                  #cmd 04
# tc.heater_control(port, False, True, False, False, True, verify=True)         #cmd 05
# tc.set_mech_sp(port, 0x0ABC, 0x0123)                                          #cmd 06
# tc.set_detec_sp(port, 0x0DEF, 0x0456)                                         #cmd 07
# tc.set_mtr_param(port, 0x4000, 0x0001, 0x09, 0xFF)                            #cmd 0A
# tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)                            #cmd 0B
# tc.set_mtr_mon(port, 0x3200, 0x3200, 0x01E0)                                  #cmd 0C
# TODO: Add Set Mtr Errors  (0D)
# tc.mtr_mov_pos(port, 0x2190)                                                  #cmd 10
# tc.mtr_mov_neg(port, 0x02190)                                                  #cmd 11
# tc.mtr_mov_abs(port, 0x1FA4)                                                  #cmd 12
# tc.mtr_homing(port, False, False, True)                                        #cmd 13
# TODO: Add Motor Halt      (15)
# TODO: Add SWIR            (18)
# TODO: Add MWIR            (19)
# TODO: Add HK Samples      (1B)
# tc.sci_request(port)
# cmd_mtr_mov_pos(port, 0x1000, True)

for i in range(0, 50):
    hk = tc.hk_request(port)
    print(hk.approx_cal_1V5)


# hk = tc.hk_request(port)
# set_params(HEATERS=False)
# tc.mtr_mov_abs(port, 0x1FA4)
# sq.verify_sequence(port)
# continuous_runs()
# sq.script_repeat_hk(port)
# start_stops()
# script_stops()
end_time = datetime.now()


print(f"Loop execution time: {(end_time - start_time)/3}")
