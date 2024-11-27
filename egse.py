# ----Module Imports--------------------------------------------------------------------------------
import logging
import time
import sys
import atexit

import serial
import serial.rs485
from datetime import datetime

from crc8Function import crc8Calculate
import tc

DEBUG_LEVEL = logging.INFO
COM_PORT = "COM14"

# ----Loggers---------------------------------------------------------------------------------------
formatter = logging.Formatter("{levelname} - {message}", style="{")

tm_log = logging.getLogger("tm_log")
hdlr_1 = logging.StreamHandler()
hdlr_1.setFormatter(formatter)
tm_log.setLevel(DEBUG_LEVEL)
tm_log.addHandler(hdlr_1)

tc_log = logging.getLogger("tc_log")
tc_log.setLevel(DEBUG_LEVEL)
tc_log.addHandler(hdlr_1)

event_log = logging.getLogger("event_log")
event_log.setLevel(DEBUG_LEVEL)
event_log.addHandler(hdlr_1)

# def setup_logging():
#     """Adds a configured stream handler to the root logger for console output.

#     2 logging streams created:
#         - display errors to console
#         - display status to console

#     Returns:
#         logger -- standard logger to console used for errors
#         stat -- logger used for status of processing for many files
#     """

#     # Setup 2 loggers one for general and one for status
#     logger = logging.getLogger()
#     logger.setLevel(logging.INFO)

#     stat = logging.getLogger('status')
#     stat.setLevel(logging.INFO)

#     # create console handler logger
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.ERROR)
#     ch_formatter = logging.Formatter(
#         '%(module)s.%(funcName)s - %(levelname)s - %(message)s')
#     ch.setFormatter(ch_formatter)
#     logger.addHandler(ch)

#     # create status logger
#     sh = logging.StreamHandler()
#     sh_formatter = logging.Formatter(
#         'STATUS:   %(module)s.%(funcName)s - %(message)s')
#     sh.setFormatter(sh_formatter)
#     stat.addHandler(sh)

#     return logger, stat


# def setup_proc_logging(logger, proc_dir):
#     """Sets the output file of the main logger with INFO logging level.

#     Arguments:
#         logger -- the logging.logger used to record messages
#         proc_dir -- pathlib.dir where to create the processing.log
#     """

#     fh = logging.FileHandler(proc_dir / 'processing.log')
#     fh.setLevel(logging.INFO)
#     fh_formatter = logging.Formatter(
#         '%(asctime)s - %(levelname)s - %(module)s.%(funcName)s - %(message)s')
#     fh.setFormatter(fh_formatter)

#     logger.addHandler(fh)

# ----FPGA Boot and Connect-------------------------------------------------------------------------
try:
    port = serial.rs485.RS485(
        port=COM_PORT,
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_ODD,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.2,
    )
except:
    Exception(f"No device found on COM Port {COM_PORT}, try another")
    tc_log.error(f"No device found on COM Port {COM_PORT}, try another")
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


# ----
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
    tc.set_mtr_param(port, 0x4000, 0x0001, 0x04, 0xFF)
    tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
    # tc.mtr_homing(port, True, False, True)
    tc.mtr_mov_pos(port, 0x1000)
    resp = tc.hk_request(port)

    while resp.MTR_FLAGS.MOVING == 1:
        time.sleep(1)
        resp = tc.hk_request(port)
        event_log.info("Motor still moving ***********")
    tm_log.info("Motor movement finished")


def script_repeat_hk():
    for i in range(100):
        tc.hk_request(port)
        time.sleep(2)


def cmd_mtr_mov_pos(port, pos_steps, repeat=True, exit_if_error=False):
    resp = tc.mtr_mov_pos(port, pos_steps, verify=True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error(f"MTR_MOV_POS exit on error asserted")
        sys.exit(1001)

    if repeat:
        tc_log.warning(f"Clearing errors")
        tc.clear_errors(port)
        tc_log.warning(f"Repeating MTR_MOV_POS command")
        resp = cmd_mtr_mov_pos(port, pos_steps, repeat=False, exit_if_error=True)

    return resp


@atexit.register
def clean_exit():
    print("Clean exit funtion executed")
    #! TODO Add code here, possibly try and power insturment off
    #! TODO power off power supply
    #! TODO ensure all logs are written


start_time = datetime.now()

# script_repeat_hk()
tc.clear_errors(port)
tc.power_control(port, 0x00)
# tc.mtr_mov_pos(port, 0x1000)
cmd_mtr_mov_pos(port, 0x1000, True)

hk = tc.hk_request(port)
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
tc.clear_errors(port)

# script_homing_default(False)
# tc.clear_errors(port)
# script_homing(False)
# tc.mtr_mov_pos(port, 0x1000)
end_time = datetime.now()


print(f"Loop execution time: {(end_time - start_time)/3}")
