# ----Module Imports--------------------------------------------------------------------------------
import logging
import time
import sys
import atexit
import serial
import serial.rs485
import argparse
from datetime import datetime
import pathlib
import os

from crc8Function import crc8Calculate
import tc

parser = argparse.ArgumentParser(
                prog='ob_egse',
                description = 'Exercise OB EGSE')
parser.add_argument('-prefix', type=ascii)
parser.add_argument('-com', type=int, default=3,)
parser.add_argument('-basedir', type=pathlib.Path, default='c:/wdir/ob_egse/loggers/')
args=parser.parse_args()

DEBUG_LEVEL = logging.INFO
COM_PORT = 'COM' + str(args.com)
prefix = str(args.prefix).strip("'")
basedir = args.basedir
# COM_PORT = 'COM21'
# prefix = 'Healthcheck_test'
# basedir = 'E:\LTM Tests'

# ----Handlers---------------------------------------------------------------------------------------
cl_formatter = logging.Formatter("{levelname} - {message}", style="{") # Setting the logging format for console loggers
fh_formatter = logging.Formatter('%(asctime)s - %(message)s') # Setting the logging format for file loggers
# -- Console Stream Handler --
hdlr_1 = logging.StreamHandler()
hdlr_1.setFormatter(cl_formatter)
# -- File Stream Handlers --
# -- Info Handler - Streams every single command being sent to the OB with its Response --
info_fh = logging.FileHandler(os.path.join(basedir,(prefix +'INFO_DUMP.log')))
info_fh.setFormatter(fh_formatter)
# -- Error Handler - Streams every Error --
error_fh = logging.FileHandler(os.path.join(basedir,(prefix + 'ERROR.log')))
error_fh.setFormatter(fh_formatter)
# -- AbsSteps Handler - Streams only every movement and ABS Steps --
abs_fh = logging.FileHandler(os.path.join(basedir,(prefix +   'ABS_STEPS.log')))
abs_fh.setFormatter(fh_formatter)
# -- HK Handler - Streams only HK --
hk_fh = logging.FileHandler(os.path.join(basedir,(prefix + 'HK.log')))
hk_fh.setFormatter(fh_formatter)
# -- CMD Handler - Streams only Commands --
cmd_fh = logging.FileHandler(os.path.join(basedir,(prefix +'CMD.log')))
cmd_fh.setFormatter(fh_formatter)
# -- ACK Handler - Streams only every ACK --
ack_fh = logging.FileHandler(os.path.join(basedir,(prefix + 'ACK.log')))
ack_fh.setFormatter(fh_formatter)
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
# -- Initiate hk writer --
hk_log = logging.getLogger("hk_log")
hk_log.setLevel(logging.INFO)
hk_log.addHandler(hk_fh)
# -- Initiate cmd writer --
cmd_log = logging.getLogger("cmd_log")
cmd_log.setLevel(logging.INFO)
cmd_log.addHandler(cmd_fh)
# -- Initiate ack writer --
ack_log = logging.getLogger("ack_log")
ack_log.setLevel(logging.INFO)
ack_log.addHandler(ack_fh)

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
def verify_Sequence(HEATERS=False):
    tc.clear_errors(port)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    tc.set_mtr_param(port, 0x4000, 0x0001, 0x09, 0xFF)
    tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
    # TODO add parameter check with other checks
    resp = tc.hk_request(port)
    # Request HK, verify that motor flags are off, motor is not moving, ABS count is 0, Rel count is 0, motor parameters are as defaults/expected
    if (resp.MTR_FLAGS.MOVING == 1 #or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 0 #
        or resp.MTR_CURRENT != 16384 or resp.MTR_PWM_RATE != 1 or resp.MTR_SPEED !=9 or resp.MTR_PWM_DUTY != 255
        or resp.MTR_RECIRC != 3 or resp.MTR_GUARD != 32 or resp.MTR_RECVAL != 15 or resp.MTR_SPISPSEL != 2
        or resp.MTR_SW_OFFSET != 160) :
            event_log.error(f'[EVENT] Initial Startup Healthcheck FAILED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f' Back Off: {resp.MTR_SW_OFFSET}')
            error_log.error(f'[EVENT] Initial Startup Healthcheck FAILED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f' Back Off: {resp.MTR_SW_OFFSET}')
            resp = tc.hk_request(port)
            if (resp.MTR_FLAGS.MOVING == 1 #or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 0 
                or resp.MTR_ABS_STEPS != 0
                or resp.MTR_CURRENT != 16384 or resp.MTR_PWM_RATE != 1 or resp.MTR_SPEED !=9 or resp.MTR_PWM_DUTY != 255
                or resp.MTR_RECIRC != 3 or resp.MTR_GUARD != 32 or resp.MTR_RECVAL != 15 or resp.MTR_SPISPSEL != 2
                or resp.MTR_SW_OFFSET != 160) :
                event_log.error(f'[EVENT] Initial Startup Healthcheck FAILED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f' Back Off: {resp.MTR_SW_OFFSET}')
                error_log.error(f'[EVENT] Initial Startup Healthcheck FAILED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f'Back Off: {resp.MTR_SW_OFFSET}')
                clean_exit()
            else :
                event_log.info(f'[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f' Back Off: {resp.MTR_SW_OFFSET}')
                info_log.info(f'[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f' Back Off: {resp.MTR_SW_OFFSET}')
    else:
        event_log.info(f'[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f'ABS Step Limit: {resp.MTR_ABS_STEPS} REL Step Limit: {resp.MTR_REL_STEPS} Back Off: {resp.MTR_SW_OFFSET}')
        info_log.info(f'[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} '
                                f'Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} '
                                f'Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} '
                                f' Back Off: {resp.MTR_SW_OFFSET}')
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")
    abs_log.info(f"Start of Measurement Cycle")     
   
   
    # Home to base
    tc.mtr_homing(port, True, False, True) #Set Homing towards Base
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)           
    else : 
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    resp = tc.hk_request(port)
    #Home to base - Movement Stopped, Base asserted, Outer de-asserted, abs - steps = 8800, rel-steps = 0, 
    if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 ):#or resp.MTR_ABS_STEPS != 8800 ):
        event_log.error(f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        error_log.error(f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or resp.MTR_ABS_STEPS != 8800 ):
            event_log.error(f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            clean_exit()
        else :
            event_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    else:
        event_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        info_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    
    
    #To Outer
    #Command as a large amound of steps as to not reset abs step count
    tc.mtr_mov_neg(port, 0x2190)
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)            
    else : 
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    
    # Once finished request HK, verify that Outer Flag is active, motor moving is off, ABS count is within+-5 of usual back off, verify relative steps is 160
    resp = tc.hk_request(port)
    if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (200>=resp.MTR_ABS_STEPS>=1080) or resp.MTR_REL_STEPS != 160):
        event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (200>=resp.MTR_ABS_STEPS>=1080) or resp.MTR_REL_STEPS != 160):
            event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            clean_exit()
        else :
            event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    else:
        event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")


    # Start Stop Sweeps
    for i in range(2) :
        #To Base
        for i in range(115):
            abs_steps = resp.MTR_ABS_STEPS
            tc.mtr_mov_pos(port,0x0040)
            resp = tc.hk_request(port)
            abs_steps_diff =resp.MTR_ABS_STEPS - abs_steps
            if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64 or abs(resp.MTR_REL_STEPS) != 64):
                event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                resp = tc.hk_request(port)       
                abs_steps_diff = abs_steps - resp.MTR_ABS_STEPS
                if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64 or abs(resp.MTR_REL_STEPS) != 64):
                    event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                    error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                    clean_exit()
                else :
                    event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                    info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
            else:
                event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
        tc.mtr_mov_pos(port,0x0500)
        resp = tc.hk_request(port)
        if resp.MTR_FLAGS.MOVING == 1:
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                resp = tc.hk_request(port)            
        else : 
            event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8360>=resp.MTR_ABS_STEPS>=9240) ):
            event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            resp = tc.hk_request(port)
            if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8360>=resp.MTR_ABS_STEPS>=9240) ):
                event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                clean_exit()
            else :
                event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        else:
            event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")
       
        #To Outer
        for i in range(115):
            abs_steps = resp.MTR_ABS_STEPS
            tc.mtr_mov_neg(port,0x0040)
            resp = tc.hk_request(port)
            abs_steps_diff =resp.MTR_ABS_STEPS - abs_steps
            if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64 ):
                event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                resp = tc.hk_request(port)       
                abs_steps_diff = abs_steps - resp.MTR_ABS_STEPS
                if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64):
                    event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                    error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                    clean_exit()
                else :
                    event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                    info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
            else:
                event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
                info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
        
        tc.mtr_mov_neg(port,0x0500)
        resp = tc.hk_request(port)
        if resp.MTR_FLAGS.MOVING == 1:
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                resp = tc.hk_request(port)            
        else : 
            event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
        resp = tc.hk_request(port)
        if resp.MTR_FLAGS.MOVING == 1:
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                resp = tc.hk_request(port)            
        else : 
            event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (200>=resp.MTR_ABS_STEPS>=1080) or resp.MTR_REL_STEPS != 160):
            event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            resp = tc.hk_request(port)
            if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (200>=resp.MTR_ABS_STEPS>=1080) or resp.MTR_REL_STEPS != 160):
                event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                clean_exit()
            else :
                event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        else:
            event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")


    # Request HK, verify Relative steps is as expected, motor moving is off, abs count is as expected, no limit switches are active Go back to step until 25mm has been moved.

    # abs_steps = resp.MTR_ABS_STEPS
    # tc.mtr_mov_pos(port,0x0040)
    # resp = tc.hk_request(port)
    # resp = tc.hk_req+uest(port)
    # abs_steps_diff =resp.MTR_ABS_STEPS - abs_steps
    # if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64 or abs(resp.MTR_REL_STEPS) != 64):
    #     event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #     error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #     resp = tc.hk_request(port)       
    #     abs_steps_diff = abs_steps - resp.MTR_ABS_STEPS
    #     if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64 or abs(resp.MTR_REL_STEPS) != 64):
    #         event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #         error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #         clean_exit()
    #     else :
    #         event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #         info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    # else:
    #     event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #     info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    # if resp.MTR_FLAGS.BASE == 0:
    #     while resp.MTR_FLAGS.BASE == 0:
    #         if resp.MTR_ABS_STEPS > 8960 :
    #             event_log.error(f"[EVENT] : OB Timed out when carrying out the start stop traverse")
    #             error_log.error(f"[EVENT] : OB Timed out when carrying out the start stop traverse")
    #             clean_exit()        
    #         abs_steps = resp.MTR_ABS_STEPS        
    #         tc.mtr_mov_pos(port,0x0040)
    #         resp = tc.hk_request(port)
    #         abs_steps_diff =resp.MTR_ABS_STEPS - abs_steps
    #         if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64 or abs(resp.MTR_REL_STEPS) != 64):
    #             event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #             error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #             resp = tc.hk_request(port)           
    #             abs_steps_diff = abs_steps - resp.MTR_ABS_STEPS
    #             if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs(abs_steps_diff) !=64 or abs(resp.MTR_REL_STEPS) != 64):
    #                 event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #                 error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #                 clean_exit()
    #             else :
    #                 event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #                 info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #         else:
    #             event_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    #             info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}")
    # abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")


        # To Outer
        # abs_steps = resp.MTR_ABS_STEPS
        # tc.mtr_mov_neg(port,0x0040)
        # resp = tc.hk_request(port)
        # abs_steps_diff = resp.MTR_ABS_STEPS - abs_steps
        # if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs_steps_diff !=64 or resp.MTR_REL_STEPS != 64):
        #     event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #     error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #     resp = tc.hk_request(port)
        #     abs_steps = resp.MTR_ABS_STEPS                       
        #     abs_steps_diff = resp.MTR_ABS_STEPS - abs_steps
        #     if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or abs_steps_diff !=64 or resp.MTR_REL_STEPS != 0):
        #         event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #         error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #         clean_exit()
        #     else :
        #         info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        # else:
        #     info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")

        # while resp.MTR_FLAGS.OUTER == 0:
        #     if resp.MTR_ABS_STEPS < 100 :
        #         event_log.error(f"[EVENT] : OB Timed out when carrying out the start stop traverse")
        #         error_log.error(f"[EVENT] : OB Timed out when carrying out the start stop traverse")
        #         clean_exit()                
        #     tc.mtr_mov_pos(port,0x0040)
        #     resp = tc.hk_request(port)  
        #     if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or abs_steps_diff !=64 or resp.MTR_REL_STEPS != 64):
        #         event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #         error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #         resp = tc.hk_request(port)
        #         abs_steps = resp.MTR_ABS_STEPS            
        #         abs_steps_diff = resp.MTR_ABS_STEPS - abs_steps
        #         if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or abs_steps_diff !=64 or resp.MTR_REL_STEPS != 0):
        #             event_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #             error_log.error(f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #             clean_exit()
        #         else :
        #             info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        #     else:
        #         info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")

    # To Base
    tc.mtr_mov_pos(port, 0x2190)
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)            
    else : 
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8360>=resp.MTR_ABS_STEPS>=9240)):
        event_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        error_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8360>=resp.MTR_ABS_STEPS>=9240)):
            event_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            clean_exit()
        else :
            event_log.info(f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    else:
        event_log.info(f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        info_log.info(f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")
    #To Parked
    tc.mtr_mov_abs(port, 0x1FA4)
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)            
    else : 
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or (7995>=resp.MTR_ABS_STEPS>=8005) ):
        event_log.error(f"[EVENT] Parked Position Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        error_log.error(f"[EVENT] Parked Position Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 1 or (7995>=resp.MTR_ABS_STEPS>=8005) ):
            event_log.error(f"[EVENT] Parked Position Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Parked Position Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            clean_exit()
        else :
            event_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    else:
        event_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        info_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")

@atexit.register
def clean_exit():
    print("Clean exit funtion executed")
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
# tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)                                  #cmd 0C
# TODO: Add Set Mtr Errors  (0D)
# tc.mtr_mov_pos(port, 0x0500)                                                  #cmd 10
# tc.mtr_mov_neg(port, 0x2190)                                                  #cmd 11
# tc.mtr_mov_abs(port, 0x1FA4)                                                  #cmd 12
# tc.mtr_homing(port, False, False, True)                                        #cmd 13
# TODO: Add Motor Halt      (15)
# TODO: Add SWIR            (18)
# TODO: Add MWIR            (19)
# TODO: Add HK Samples      (1B)
# tc.sci_request(port)
# cmd_mtr_mov_pos(port, 0x1000, True)


# hk = tc.hk_request(port)
# set_params(HEATERS=False)
# tc.mtr_mov_abs(port, 0x1FA4)  
verify_Sequence()
# continuous_runs()
# start_stops()
# script_stops()
end_time = datetime.now()


print(f"Loop execution time: {(end_time - start_time)/3}")
