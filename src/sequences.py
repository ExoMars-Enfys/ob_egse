import logging
import time

import tc

tm_log = logging.getLogger("tm_log")
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")
abs_log = logging.getLogger("abs_log")
error_log = logging.getLogger("error_log")

# ----
def script_repeat_hk(port):
    for i in range(100):
        tc.hk_request(port)
        time.sleep(2)

def script_homing(port, HEATERS=False):
    tc.hk_request(port)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    tc.set_mtr_param(port, 0x4000, 0x0001, 0x09, 0xFF)
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
    return

def verify_sequence(port, HEATERS=False):
    tc.clear_errors(port)
    if HEATERS:
        tc.power_control(port, 0x03)
    else:
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
                return
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
            return
        else :
            event_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    else:
        event_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        info_log.info(f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")
    
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
    if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (520>=resp.MTR_ABS_STEPS>=1400) or resp.MTR_REL_STEPS != 480):
        event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (520>=resp.MTR_ABS_STEPS>=1400) or resp.MTR_REL_STEPS != 480):
            event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            return
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
        for i in range(110):
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
                    return
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
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8040>=resp.MTR_ABS_STEPS>=9560) ):
            event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            resp = tc.hk_request(port)
            if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8040>=resp.MTR_ABS_STEPS>=9560) ):
                event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                return
            else :
                event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        else:
            event_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")
       
        #To Outer
        for i in range(110):
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
                    return
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
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (520>=resp.MTR_ABS_STEPS>=1400) or resp.MTR_REL_STEPS != 480):
            event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            resp = tc.hk_request(port)
            if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 1 or resp.MTR_FLAGS.OUTER == 0 or (520>=resp.MTR_ABS_STEPS>=1400) or resp.MTR_REL_STEPS != 480):
                event_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                error_log.error(f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
                return
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
    #         return
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
    #             return        
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
    #                 return
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
        #         return
        #     else :
        #         info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        # else:
        #     info_log.info(f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")

        # while resp.MTR_FLAGS.OUTER == 0:
        #     if resp.MTR_ABS_STEPS < 100 :
        #         event_log.error(f"[EVENT] : OB Timed out when carrying out the start stop traverse")
        #         error_log.error(f"[EVENT] : OB Timed out when carrying out the start stop traverse")
        #         return                
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
        #             return
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
    if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8040>=resp.MTR_ABS_STEPS>=9560)):
        event_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        error_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        resp = tc.hk_request(port)
        if (resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1 or (8040>=resp.MTR_ABS_STEPS>=9560)):
            event_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            error_log.error(f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            return
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
            return
        else :
            event_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
            info_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    else:
        event_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
        info_log.info(f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}")
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")