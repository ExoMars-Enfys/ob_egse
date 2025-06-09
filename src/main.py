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

## ----Script Start --------------------------------------------------------------------------------

parser = argparse.ArgumentParser(prog="ob_egse", description="Exercise OB EGSE")
parser.add_argument("-prefix", type=ascii, default=const.DEFAULT_PREFIX)
parser.add_argument(
    "-com",
    type=int,
    default=const.DEFAULT_COM_PORT,
)
parser.add_argument("-basedir", type=Path, default=const.DEFAULT_PATH)
args = parser.parse_args()

com_port = "COM" + str(args.com)

const.LOG_PREFIX = str(args.prefix).strip("'")
const.LOG_PATH = args.basedir

if const.LOG_PATH == const.DEFAULT_PATH:
    const.LOG_PATH.mkdir(parents=True)

tm_log, tc_log, event_log, info_log, error_log, abs_log = egse_logger.get_loggers(
    const.LOG_PATH, const.LOG_PREFIX, const.DEBUG_LEVEL
)

# Create ACK Byte Log
ack_log_name = const.DEFAULT_PREFIX + "_ACK.LOG"
const.ACK_LOG_FH = open(const.LOG_PATH / ack_log_name, "a+", encoding="utf-8")

# Create CMD Byte Log
cmd_log_name = const.DEFAULT_PREFIX + "_CMD.LOG"
const.CMD_LOG_FH = open(const.LOG_PATH / ack_log_name, "a+", encoding="utf-8")

# Create HK Byte Log
hk_log_name = const.DEFAULT_PREFIX + "_HK.LOG"
const.HK_LOG_FH = open(const.LOG_PATH / hk_log_name, "a+", encoding="utf-8")

# ----FPGA Boot and Connect-------------------------------------------------------------------------
try:
    port = serial.rs485.RS485(
        port=com_port,
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_ODD,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0,
    )
except serial.SerialException:
    tc_log.error(f"No device found on COM Port {com_port}, try another")
    raise SystemExit

port.rs485_mode = serial.rs485.RS485Settings(
    rts_level_for_tx=False,
    rts_level_for_rx=True,
    loopback=False,
    delay_before_tx=const.CMD_SPEED_DICT[const.DEFAULT_CMD_SPEED],
    delay_before_rx=0,
)
port.flushOutput()  # Port Flushing to clear port
port.flushInput()


@atexit.register
def clean_exit():
    event_log.info("...Exiting...")
    const.ACK_LOG_FH.close()
    const.CMD_LOG_FH.close()
    const.HK_LOG_FH.close()
    sys.exit(1001)
    #! TODO Add code here, possibly try and power insturment off
    #! TODO power off power supply
    #! TODO ensure all logs are written


t1 = time.perf_counter(), time.process_time()
# sq.mech_heater_test(port)
# sq.check_hk(port)
# sq.power_up_tests(port)
tc.power_control(port,0x01)
# sq.positive_test(port)
# sq.negative_test(port)
# sq.cal_test(port)
# sq.homing_test(port)
# sq.check_sci_vs_hk(port)
t2 = time.perf_counter(), time.process_time()
print(f" Real time: {t2[0] - t1[0]:.4f} seconds")
print(f" CPU time: {t2[1] - t1[1]:.4f} seconds")
