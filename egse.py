# ----Module Imports--------------------------------------------------------------------------------
import logging
import time
import sys
import atexit
import serial
import serial.rs485
from datetime import datetime
import pathlib

from crc8Function import crc8Calculate
import tc

DEBUG_LEVEL = logging.INFO
COM_PORT = 'COM' + input("Please enter the com port number of the FPGA\n")
prefix = input('\n Test Prefix : \n')
# ----Handlers---------------------------------------------------------------------------------------
cl_formatter = logging.Formatter("{levelname} - {message}", style="{") # Setting the logging format for console loggers
fh_formatter = logging.Formatter('%(asctime)s - %(message)s') # Setting the logging format for file loggers
# -- Console Stream Handler --
hdlr_1 = logging.StreamHandler()
hdlr_1.setFormatter(cl_formatter)
# -- File Stream Handlers --
# -- Info Handler - Streams every single command being sent to the OB with its Response --
info_fh = logging.FileHandler('C:/wdir/ob_egse/loggers/INFO/' + prefix + ' - {:%Y-%m-%d}.log'.format(datetime.now()))
info_fh.setFormatter(fh_formatter)
# -- Error Handler - Streams every Error --
error_fh = logging.FileHandler('C:/wdir/ob_egse/loggers/ERRORS/' + prefix + ' - {:%Y-%m-%d}.log'.format(datetime.now()))
error_fh.setFormatter(fh_formatter)
# -- AbsSteps Handler - Streams only every movement and ABS Steps --
abs_fh = logging.FileHandler('C:/wdir/ob_egse/loggers/ABS_STEPS/' + prefix + ' - {:%Y-%m-%d}.log'.format(datetime.now()))
abs_fh.setFormatter(fh_formatter)
# ----Loggers---------------------------------------------------------------------------------------
# -- Initiate tm_log streamer --
tm_log = logging.getLogger("tm_log")
tm_log.setLevel(DEBUG_LEVEL)
tm_log.addHandler(hdlr_1)
# -- Initiate tc_log streamer --
tc_log = logging.getLogger("tc_log")
tc_log.setLevel(DEBUG_LEVEL)
tc_log.addHandler(hdlr_1)
# -- Initiate event_log streamer --
event_log = logging.getLogger("event_log")
event_log.setLevel(DEBUG_LEVEL)
event_log.addHandler(hdlr_1)
# -- Initiate info writer --
info_log = logging.getLogger("info_log")
info_log.setLevel(logging.INFO)
info_log.addHandler(info_fh)
# -- Initiate error writer --
error_log = logging.getLogger("error_log")
error_log.setLevel(logging.ERROR)
error_log.addHandler(error_fh)
# -- Initiate error writer --
abs_log = logging.getLogger("abs_log")
abs_log.setLevel(logging.INFO)
abs_log.addHandler(abs_fh)

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
def script_homing(HEATERS=False):
    tc.hk_request(port)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    tc.set_mtr_param(port, 0x5000, 0x0001, 0x09, 0xFF)
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

def verify_Sequence(HEATERS=False):
    tc.hk_request(port)
    time.sleep(1)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    time.sleep(1)
    tc.set_mtr_param(port, 0x4000, 0x0001, 0x04, 0xFF)
    time.sleep(1)
    tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)
    time.sleep(1)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
    time.sleep(1)
    tc.mtr_homing(port, False, False, True) #Set Homing towards Base
    # resp = tc.hk_request(port)
    # if resp.MTR_FLAGS.MOVING == 1:
    #     while resp.MTR_FLAGS.MOVING == 1:
    #         time.sleep(1)
    #         resp = tc.hk_request(port)
    #         abs_log.info(f"ABS Steps at this PiT: {hk.MTR_REL_STEPS}")
    # else : 
    #     event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")        
    cmd_mtr_mov_pos(port, 0x2190, repeat=True, exit_if_error=False) #Move to Outer Switch full traverse
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            abs_log.info(f"ABS Steps at this PiT: {hk.MTR_REL_STEPS}")
    else : 
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")          
    tc.mtr_mov_neg(port, 0x2190) #Move to Base Switch full traverse
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            
            abs_log.info(f"ABS Steps at this PiT: {hk.MTR_REL_STEPS}")
    else : 
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")  

@atexit.register
def clean_exit():
    print("Clean exit funtion executed")
    #! TODO Add code here, possibly try and power insturment off
    #! TODO power off power supply
    #! TODO ensure all logs are written


start_time = datetime.now()

# script_repeat_hk()
# tc.clear_errors(port)
# tc.power_control(port, 0x01)
# tc.mtr_mov_pos(port, 0x1000)
# cmd_mtr_mov_pos(port, 0x1000, True)


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
# tc.clear_errors(port)

# script_homing_default(False)
# tc.clear_errors(port)
# script_homing(False)
# tc.mtr_homing(port, True, False, True) #Set Homing towards Base
# tc.mtr_mov_pos(port, 0x1000)
verify_Sequence()
end_time = datetime.now()


print(f"Loop execution time: {(end_time - start_time)/3}")
