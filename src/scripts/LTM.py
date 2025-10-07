import scripts.sequences as sq

import tc
import logging
import time
from send_cmd import cmd_repeat as repeat
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")


def LTM_Measurement(port):
    sq.power_up(port)
    base_cal(port)
    outer_home(port)
    for i in range(2):
        pos_acquisition(port)
        neg_acquisition(port)
    # base_home(port)
    # park(port)

def base_cal(port):
    event_log.info("Starting Base Calibration Sequence")
    hk = repeat(port,tc.hk_request,port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port,tc.power_control, hk.PWR_STAT | 0x01)
    repeat(port, tc.mtr_homing,True, False)    
    hk = repeat(port,tc.hk_request,port)

    # If ABS Steps at 8960 we are already there, otherwise wait for movement
    if hk.MTR_ABS_STEPS != 9960:
        event_log.info("Moving to the BASE, waiting for switch to be pressed.")
        timeout = 0
        while hk.MTR_FLAGS.MOVING:
            try:
                if  timeout<=30:
                    time.sleep(1)
                    timeout += 1
                    hk = repeat(port,tc.hk_request,port)
                    event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
                else:
                    raise TimeoutError("Timeout waiting for motor to home to base")
            except TimeoutError as e:
                    event_log.error(f"Error occurred: {e}")
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, already at Base")

    #Check motor status now its stopped.
    resp = repeat(port,tc.hk_request,port)
    if resp.MTR_FLAGS.CAL != 1 : 
        event_log.error(f" Calibration Flag not Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0 : 
        event_log.error(f" Calibration Dir not to BASE : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 0 : 
        event_log.error(f"OUTER Switch Flag raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 1 : 
        event_log.error(f"BASE Switch Flag is not asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")
   
    if (resp.MTR_ABS_STEPS != 9960):
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
    if (resp.MTR_REL_STEPS == 0):
        event_log.error(f"Motor Steps Do not match expected REL : {resp.MTR_REL_STEPS} , Expected : 0")
        
    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")

def outer_home(port):
    event_log.info("Starting Outer Homing Sequence")
    hk = repeat(port,tc.hk_request,port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port,tc.power_control, hk.PWR_STAT | 0x01)
    repeat(port, tc.mtr_homing,False, True)    
    hk = repeat(port,tc.hk_request,port)

    # If ABS Steps at 0 we are already there, otherwise wait for movement
    if (50 > hk.MTR_ABS_STEPS or 150 < hk.MTR_ABS_STEPS):
        event_log.info("Moving to the OUTER, waiting for switch to be pressed.")
        timeout = 0
        while hk.MTR_FLAGS.MOVING:
            try:
                if  timeout<=30:
                    time.sleep(1)
                    timeout += 1
                    hk = repeat(port,tc.hk_request,port)
                    event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
                else:
                    raise TimeoutError("Timeout waiting for motor to home to outer")
            except TimeoutError as e:
                    event_log.error(f"Error occurred: {e}")
    else:
        event_log.info("Motor Did not Move, already at Outer")

    #Check motor status now its stopped.
    resp = repeat(port,tc.hk_request,port)
    if resp.MTR_FLAGS.CAL != 0 : 
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 1 : 
        event_log.error(f" Calibration Dir not to OUTER : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 1 : 
        event_log.error(f"OUTER Switch Flag not raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 0 : 
        event_log.error(f"BASE Switch Flag is asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")
   
    if (50 > hk.MTR_ABS_STEPS or 150 < hk.MTR_ABS_STEPS):
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 50-150")
        
    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")

def base_home(port):
    event_log.info("Starting Base Homing Sequence")
    hk = repeat(port,tc.hk_request,port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port,tc.power_control, hk.PWR_STAT | 0x01)
    repeat(port, tc.mtr_homing,False, False)    
    hk = repeat(port,tc.hk_request,port)

    # If ABS Steps at 0 we are already there, otherwise wait for movement
    if (8910 > hk.MTR_ABS_STEPS > 9010):
        event_log.info("Moving to the Base, waiting for switch to be pressed.")
        timeout = 0
        while hk.MTR_FLAGS.MOVING:
            try:
                if  timeout<=30:
                    time.sleep(1)
                    timeout += 1
                    hk = repeat(port,tc.hk_request,port)
                    event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
                else:
                    raise TimeoutError("Timeout waiting for motor to home to base")
            except TimeoutError as e:
                    event_log.error(f"Error occurred: {e}")
    else:
        event_log.info("Motor Did not Move, already at Base")

    #Check motor status now its stopped.
    resp = repeat(port,tc.hk_request,port)
    if resp.MTR_FLAGS.CAL != 0 : 
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0 : 
        event_log.error(f" Calibration Dir not to Base : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 0 : 
        event_log.error(f"OUTER Switch Flag not raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 1 : 
        event_log.error(f"BASE Switch Flag is asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")

    if (8910 > resp.MTR_ABS_STEPS > 9010):
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 8910-9010")

    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")

def dark_region_step(port,dir):
    # event_log.info("Starting Dark Region Step Sequence")
    if dir == 0 :
        repeat(port, tc.mtr_mov_pos, 30)
    else:
        repeat(port, tc.mtr_mov_neg, 30)
    hk = repeat(port,tc.hk_request,port)
    timeout = 0
    while hk.MTR_FLAGS.MOVING:
        try:
            if  timeout<=45:
                time.sleep(1)
                timeout += 1
                hk = repeat(port,tc.hk_request,port)
                event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
            else:
                raise TimeoutError("Timeout waiting for motor to home to base")
        except TimeoutError as e:
                event_log.error(f"Error occurred: {e}")
    # event_log.info("Motor movement finished")

def open_aperture_step(port,dir):
    # event_log.info("Starting Open Aperture Step Sequence")
    if dir == 0 :
        repeat(port, tc.mtr_mov_pos, 50)
    else:
        repeat(port, tc.mtr_mov_neg, 50)
    hk = repeat(port,tc.hk_request,port)
    timeout = 0
    while hk.MTR_FLAGS.MOVING:
        try:
            if  timeout<=45:
                time.sleep(1)
                timeout += 1
                hk = repeat(port,tc.hk_request,port)
                event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
            else:
                raise TimeoutError("Timeout waiting for motor to home to base")
        except TimeoutError as e:
                event_log.error(f"Error occurred: {e}")
    # event_log.info("Motor movement finished")

def pos_acquisition(port,dir = 0):
    hk = repeat(port, tc.hk_request)
    while hk.MTR_ABS_STEPS <= 672 : 
        dark_region_step(port,dir)
        hk = repeat(port, tc.hk_request)
        event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info(f"At end of first Dark Region, ABS Steps: {hk.MTR_ABS_STEPS}")
    while hk.MTR_ABS_STEPS <= 7968 : 
        open_aperture_step(port,dir)
        hk = repeat(port, tc.hk_request)
        event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info(f"At end of Open Aperture, ABS Steps: {hk.MTR_ABS_STEPS}")
    while hk.MTR_ABS_STEPS <=8640  or  hk.MTR_FLAGS.BASE ==0: 
        dark_region_step(port,dir)
        hk = repeat(port, tc.hk_request)
        event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info(f"At end of second Dark Region, ABS Steps: {hk.MTR_ABS_STEPS}")

def neg_acquisition(port,dir=1):
    hk = repeat(port, tc.hk_request)
    while hk.MTR_ABS_STEPS >= 7968 : 
        dark_region_step(port,dir)
        hk = repeat(port, tc.hk_request)
        event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info(f"At end of first Dark Region, ABS Steps: {hk.MTR_ABS_STEPS}")
    while hk.MTR_ABS_STEPS >= 672 : 
        open_aperture_step(port,dir)
        hk = repeat(port, tc.hk_request)
        event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info(f"At end of Open Aperture, ABS Steps: {hk.MTR_ABS_STEPS}")
    while hk.MTR_ABS_STEPS >=100  or  hk.MTR_FLAGS.OUTER ==0: 
        dark_region_step(port,dir)
        hk = repeat(port, tc.hk_request)
        event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info(f"At end of second Dark Region, ABS Steps: {hk.MTR_ABS_STEPS}")

def park(port):
    event_log.info("Starting Parked Sequence")    
    repeat(port, tc.mtr_mov_abs, 8100)
    hk = repeat(port,tc.hk_request,port)
    if hk.MTR_ABS_STEPS != 8100:
        event_log.info("Moving to Parked, waiting for movement to finish")
        timeout = 0
        while hk.MTR_FLAGS.MOVING:
            try:
                if  timeout<=30:
                    time.sleep(1)
                    timeout += 1
                    hk = repeat(port,tc.hk_request,port)
                    event_log.info(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
                else:
                    raise TimeoutError("Timeout waiting for motor to home to base")
            except TimeoutError as e:
                    event_log.error(f"Error occurred: {e}")
    else:
        event_log.info("Motor Did not Move, already at Parked")

    #Check motor status now its stopped.
    resp = repeat(port,tc.hk_request,port)
    if resp.MTR_FLAGS.CAL != 0 : 
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 1 : 
        event_log.error(f" Calibration Dir not to OUTER : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 0 : 
        event_log.error(f"OUTER Switch Flag not raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 0 : 
        event_log.error(f"BASE Switch Flag is asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")
   
    if resp.MTR_ABS_STEPS != 8100:
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 8100")
        
    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")
