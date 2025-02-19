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
# COM_PORT = 'COM' + str(args.com)
# prefix = str(args.prefix).strip("'")
# basedir = args.basedir
COM_PORT = 'COM3'
prefix = input("Please Enter Test name\n")
basedir = "C:/wdir/ob_egse/loggers/"
loggerdir = basedir + '{:%Y-%m-%d}'.format(datetime.now()) + '_' + prefix

if os.path.exists(loggerdir) !=  True: 
    os.makedirs(loggerdir)

# ----Handlers---------------------------------------------------------------------------------------
cl_formatter = logging.Formatter("{levelname} - {message}", style="{") # Setting the logging format for console loggers
fh_formatter = logging.Formatter('%(asctime)s - %(message)s') # Setting the logging format for file loggers
# -- Console Stream Handler --
hdlr_1 = logging.StreamHandler()
hdlr_1.setFormatter(cl_formatter)
# -- File Stream Handlers --
# -- Info Handler - Streams every single command being sent to the OB with its Response --
info_fh = logging.FileHandler(loggerdir +'/INFO_DUMP.log')
info_fh.setFormatter(fh_formatter)
# -- Error Handler - Streams every Error --
error_fh = logging.FileHandler(loggerdir +'/ERROR.log')
error_fh.setFormatter(fh_formatter)
# -- AbsSteps Handler - Streams only every movement and ABS Steps --
abs_fh = logging.FileHandler(loggerdir +'/ABS_STEPS.log')
abs_fh.setFormatter(fh_formatter)
# -- HK Handler - Streams only HK --
hk_fh = logging.FileHandler(loggerdir +'/HK.log')
hk_fh.setFormatter(fh_formatter)
# -- CMD Handler - Streams only Commands --
cmd_fh = logging.FileHandler(loggerdir +'/CMD.log')
cmd_fh.setFormatter(fh_formatter)
# -- ACK Handler - Streams only every ACK --
ack_fh = logging.FileHandler(loggerdir +'/ACK.log')
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
def power_up_sequence():
    tc.clear_errors(port)
    tc.power_control(port, 0x01)
    tc.set_mtr_param(port, 0x4000, 0x0001, 0x09, 0xFF)
    tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x01E0)
    # TODO add parameter check with other checks
    resp = tc.hk_request(port)
    # Request HK, verify that motor flags are off, motor is not moving, ABS count is 0, Rel count is 0, motor parameters are as defaults/expected
    if (resp.MTR_FLAGS.MOVING == 1 #or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 0 #
        or resp.MTR_CURRENT != 16384 or resp.MTR_PWM_RATE != 1 or resp.MTR_SPEED !=9 or resp.MTR_PWM_DUTY != 255
        or resp.MTR_RECIRC != 3 or resp.MTR_GUARD != 32 or resp.MTR_RECVAL != 15 or resp.MTR_SPISPSEL != 2
        or resp.MTR_SW_OFFSET != 480) :
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
def move_forward_sequence():
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
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")  
def move_backward_sequence():
    tc.mtr_homing(port, False, False, True) #Set Homing towards Base
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)           
    else : 
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    resp = tc.hk_request(port)
    #Home to base - Movement Stopped, Base asserted, Outer de-asserted, abs - steps = 8800, rel-steps = 0, 
    if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 ):#or resp.MTR_ABS_STEPS != 8800 ):
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
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")   
    
@atexit.register
def clean_exit():
    print("Clean exit funtion executed")
    sys.exit(1001)
    #! TODO Add code here, possibly try and power insturment off
    #! TODO power off power supply
    #! TODO ensure all logs are written


start_time = datetime.now()
sequence = input("\nSelect which sequence you would like to carry out\n" 
                            + "\n Available Options Are:"
                            + "\n 1. Power Up"
                            + "\n 2. Forward Steps "
                            + "\n 3. Backward Steps\n")
match sequence:
    case "1":
        power_up_sequence()
    case "2":
        move_forward_sequence()         
    case "3":                   
        move_backward_sequence()
end_time = datetime.now()


print(f"Loop execution time: {(end_time - start_time)/3}")
