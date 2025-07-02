import logging
import time
import constants as const
import send_cmd
import tc

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")


# ----
def script_repeat_hk(port):
    for i in range(100):
        tc.hk_request(port)
        time.sleep(2)

def mech_heater_test(port):
    resp = send_cmd.cmd_hk(port)
    send_cmd.cmd_heater_control(port,False, False, False, True,False)
    resp = tc.hk_request(port)
    init_mech_trp = resp.MECH_TRP
    init_motor_trp = resp.MOTOR_TRP
    if resp.THRM_STATUS == 66 :
        while resp.THRM_STATUS ==66:
            time.sleep(1)
            resp = tc.hk_request(port)
            if ((resp.MECH_TRP - init_mech_trp) >= 10 or (resp.MOTOR_TRP - init_motor_trp) >= 10):
                event_log.info("Mech and Motor Heater reached temp")
                send_cmd.cmd_heater_control(port,False, False, False, False,False)
                pass
                exit
    else :           
        event_log.error(f"Mech Heater Status not On : {resp.THRM_STATUS} ")
        exit
    return

def check_hk(port) :
    resp = tc.hk_request(port)
    event_log.info(
    f" MOD_ID :{resp.MOD_ID}" + 
    f"\n Unused1 : {resp.UNUSED1}" + 
    f"\n CMD_ID :{resp.CMD_ID}" + 
    f"\n CMD_CNT : {resp.CMD_CNT}" +
    f"\n ERROR_BYTE : {resp.ERROR_BYTE}" + 
    f"\n UNUSED2 :{resp.UNUSED2}" + 
    f"\n ERROR_MTR :{resp.ERROR_MTR}" + 
    f"\n MTR_ERR_MSK : {resp.MTR_ERR_MSK}" + 
    f"\n MTR_FLAGS_BYTE :{resp.MTR_FLAGS_BYTE}" +
    f"\n MTR_ABS_STEPS : {resp.MTR_ABS_STEPS}" +
    f"\n MTR_REL_STEPS : {resp.MTR_REL_STEPS}" + 
    f"\n MTR_CURRENT :{resp.MTR_CURRENT}" + 
    f"\n MTR_GUARD : {resp.MTR_GUARD}" + 
    f"\n MTR_RECVAL : {resp.MTR_RECVAL}" +
    f"\n UNUSED3 : {resp.UNUSED3}" +
    f"\n MTR_SPEED :{resp.MTR_SPEED}" +
    f"\n MECH_LIM_REL : {resp.MECH_LIM_REL}" + 
    f"\n UNUSED4 : {resp.PWR_STAT}" +  
    f"\n PWR_STAT : {resp.PWR_STAT}" +
    f"\n THRM_STATUS :{resp.THRM_STATUS}" + 
    f"\n THRM_MECH_OFF_SP : {resp.THRM_MECH_OFF_SP}" +
    f"\n THRM_MECH_ON_SP : {resp.THRM_MECH_ON_SP}" + 
    f"\n THRM_DET_OFF_SP :{resp.THRM_DET_OFF_SP}" + 
    f"\n THRM_DET_ON_SP : {resp.THRM_DET_ON_SP}" +
    f"\n SWIR_OFFSET : {resp.SWIR_OFFSET}" + 
    f"\n MWIR_OFFSET : {resp.MWIR_OFFSET}" +
    f"\n HK_V_3V3 : {resp.HK_V_3V3}" + 
    f"\n HK_V_1V5 :{resp.HK_V_1V5}" + 
    f"\n DIGITAL_TRP : {resp.DIGITAL_TRP}" +
    f"\n DETEC_TRP :{resp.DETEC_TRP}" + 
    f"\n MECH_TRP : {resp.MECH_TRP}" +
    f"\n MOTOR_TRP : {resp.MOTOR_TRP}" + 
    f"\n HK_MECH_CUR :{resp.HK_MECH_CUR}" + 
    f"\n UNUSED_ADC : {resp.UNUSED_ADC}" +
    f"\n HK_SAMPLES : {resp.HK_SAMPLES}" + 
    f"\n UNUSED5 :{resp.UNUSED5}" + 
    f"\n CRC8 : {resp.CRC8}")

def check_sci(port, sci_adc_samp, sci_adc_skip):
    resp = tc.sci_request(port, sci_adc_samp, sci_adc_skip)
    event_log.info(
        f"\tERROR_BYTE: {resp.ERROR_BYTE}" +
        f"  MTR_ABS_STEPS: {resp.MTR_ABS_STEPS}" +
        f"  THRM_STATUS: {resp.THRM_STATUS}" +
        f"  SWIR_OFFSET: {resp.SWIR_OFFSET}" +
        f"  MWIR_OFFSET: {resp.MWIR_OFFSET}" +
        f"  SCI_ADC_SAMPLES: {resp.SCI_ADC_SAMPLES}" +
        f"  SCI_ADC_SKIP: {resp.SCI_ADC_SKIP}" +
        f"  SWIR_HIGH: {resp.SWIR_HIGH}" +
        f"  SWIR_MED: {resp.SWIR_MED}" +
        f"  SWIR_LOW: {resp.SWIR_LOW}" +
        f"  MWIR_HIGH: {resp.MWIR_HIGH}" +
        f"  MWIR_MED: {resp.MWIR_MED}" +
        f"  MWIR_LOW: {resp.MWIR_LOW}" +
        f"  HT_SINK_TEMP: {resp.HT_SINK_TEMP}" +
        f"  SWIR_TEMP: {resp.SWIR_TEMP}"
    )
    return resp

def power_up_tests(port) :
    # resp = tc.hk_request(port)
    # if resp.PWR_STAT != 0 : 
    #     event_log.error(f"OB Initialised in wrong Power State : {resp.PWR_STAT}")
    #     exit
    # else :         
    #     send_cmd.cmd_power_control(port,0x01)
    #     resp=tc.hk_request(port)
    #     if resp.PWR_STAT != 1 : 
    #         event_log.error(f"OB Initialised in wrong Power State : {resp.PWR_STAT}")
    #         exit
    #     else :
    tc.power_control(port,0x03)
    send_cmd.cmd_mtr_param(port,0x40,0x20,0x0F,0x9,0x3200)
    resp = tc.hk_request(port)
    if (
    resp.MTR_CURRENT != 40
    or resp.MTR_GUARD != 32
    or resp.MTR_RECVAL != 15
    or resp.MTR_SPEED != 9
    or resp.MECH_LIM_REL != 12800):
        event_log.error(f"OB Parameters not initialized correctly:"+
                        f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 40" +
                        f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32" +
                        f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15" +
                        f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9" +
                        f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800")
        # exit
        send_cmd.cmd_mtr_param(port,0x28,0x20,0x0F,0x9,0x3200)
        resp = tc.hk_request(port)
        if (
        resp.MTR_CURRENT != 40
        or resp.MTR_GUARD != 32
        or resp.MTR_RECVAL != 15
        or resp.MTR_SPEED != 9
        or resp.MECH_LIM_REL != 12800):
            event_log.error(f"OB Parameters not initialized correctly:"+
                            f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 40" +
                            f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32" +
                            f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15" +
                            f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9" +
                            f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800")

def positive_test(port):
    resp = tc.hk_request(port)
    abs_steps = resp.MTR_ABS_STEPS
    send_cmd.cmd_mtr_mov_pos(port, 0x140)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(0.1)
            resp = tc.hk_request(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    else : 
        event_log.error("Motor Did not Move :")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )
    if ((abs(abs_steps - resp.MTR_ABS_STEPS) != 320 or resp.MTR_REL_STEPS != 320)) : 
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 320" +
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 320")
        exit
    else : event_log.info(f"Step count was fine : "+
        f"\n Abs : {abs(abs_steps - resp.MTR_ABS_STEPS)}"+
        f"\n Rel : {resp.MTR_REL_STEPS}")
    return

def negative_test(port):
    resp = tc.hk_request(port)
    abs_steps = resp.MTR_ABS_STEPS
    send_cmd.cmd_mtr_mov_neg(port, 0x140)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    else : 
        event_log.error("Motor Did not Move :")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )
    resp = tc.hk_request(port)
    if ((abs(abs_steps - resp.MTR_ABS_STEPS) != 320 or resp.MTR_REL_STEPS != (65536-320))) : 
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n ABS : {abs(abs_steps - resp.MTR_ABS_STEPS)} , Expected : 320" +
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 320")
        exit
    else : event_log.info(f"Step count was fine : "+
        f"\n Abs : {abs(abs_steps - resp.MTR_ABS_STEPS)}"+
        f"\n Rel : {resp.MTR_REL_STEPS}")
    return

def cal_test(port):
    tc.power_control(port,0x01)
    event_log.info("CAL to base")
    resp = tc.hk_request(port)
    send_cmd.cmd_mtr_homing(port,True, False)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
    else : 
        event_log.error("Motor Did not Move :")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )
    if resp.MTR_FLAGS.BASE !=1 : 
        event_log.error(f"BASE Switch Flag not raised : {resp.MTR_FLAGS.BASE}")
    else:
        if resp.MTR_FLAGS.CAL != 1 : 
            event_log.error(f" Calibration Flag not Asserted : {resp.MTR_FLAGS.CAL}")
        if resp.MTR_FLAGS.DIR != 0 : 
            event_log.error(f" Calibration Dir not to Base : {resp.MTR_FLAGS.DIR}")
        if (resp.MTR_ABS_STEPS != 8960):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
        if (resp.MTR_REL_STEPS != 0):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
            
    
    time.sleep(5)
    event_log.info("CAL to OUTER")
    resp = tc.hk_request(port)
    send_cmd.cmd_mtr_homing(port,True, True)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    else : 
        event_log.error("Motor Did not Move :")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )
    if resp.MTR_FLAGS.OUTER !=1 : 
        event_log.error(f"OUTER Switch Flag not raised : {resp.MTR_FLAGS.OUTER}")
    else:
        if resp.MTR_FLAGS.CAL != 1 : 
            event_log.error(f" Calibration Flag not Asserted : {resp.MTR_FLAGS.CAL}")
        if resp.MTR_FLAGS.DIR != 1 : 
            event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
        if (resp.MTR_ABS_STEPS != 100):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 100")
        if (resp.MTR_REL_STEPS != 0):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
            
    return

def homing_test(port):
    event_log.info("HOME to BASE")
    resp = tc.hk_request(port)
    send_cmd.cmd_mtr_homing(port,False, False)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    else : 
        event_log.error("Motor Did not Move :")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )
    
    if resp.MTR_FLAGS.BASE !=1 : 
        event_log.error(f"BASE Switch Flag not raised : {resp.MTR_FLAGS.BASE}")
    else:
        if resp.MTR_FLAGS.CAL != 0 : 
            event_log.error(f" Calibration Flag Falsely Asserted : {resp.MTR_FLAGS.CAL}")
        if resp.MTR_FLAGS.DIR != 1 : 
            event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
        if (resp.MTR_ABS_STEPS != 8960):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
        if (resp.MTR_REL_STEPS != 0):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
    
    time.sleep(5)
    event_log.info("HOME to OUTER")
    resp = tc.hk_request(port)
    send_cmd.cmd_mtr_homing(port,False, True)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    else : 
        event_log.error("Motor Did not Move :")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )
    
    if resp.MTR_FLAGS.OUTER !=1 : 
        event_log.error(f"OUTER Switch Flag not raised : {resp.MTR_FLAGS.OUTER}")
    else:
        if resp.MTR_FLAGS.CAL != 0 : 
            event_log.error(f" Calibration Flag Falsely Asserted : {resp.MTR_FLAGS.CAL}")
        if resp.MTR_FLAGS.DIR != 1 : 
            event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
        if (resp.MTR_ABS_STEPS != 100):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 100")
        if (resp.MTR_REL_STEPS != 0):
            event_log.error(f"Motor Steps Do not match expected : " + 
                            f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
    return

def motor_fw_test(port, HEATERS=False):
    tc.hk_request(port)
    if HEATERS:
        tc.power_control(port, 0xC3)
    else:
        tc.power_control(port, 0x01)
    tc.set_mtr_param(port, 0x4000, 0x0000, 0x09, 0x00)
    tc.set_mtr_guard(port, 0x03, 0x0020, 0x00, 0x0002)
    tc.set_mtr_mon(port, 0x3200, 0x3200, 0x00A0)
    # tc.mtr_homing(port, True, False, True)
    tc.mtr_mov_pos(port, 0x1000)
    resp = tc.hk_request(port)

    while resp.MTR_FLAGS.MOVING == 1:
        time.sleep(1)
        resp = tc.hk_request(port)
        event_log.info("Motor still moving ***********")
    info_log.info("Motor movement finished")

    time.sleep(3)

    tc.mtr_mov_neg(port, 0x0300)
    resp = tc.hk_request(port)

    while resp.MTR_FLAGS.MOVING == 1:
        time.sleep(1)
        resp = tc.hk_request(port)
        event_log.info("Motor still moving ***********")
    info_log.info("Motor movement finished")
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
    if (
        resp.MTR_FLAGS.MOVING == 1  # or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 0 #
        or resp.MTR_CURRENT != 16384
        or resp.MTR_PWM_RATE != 1
        or resp.MTR_SPEED != 9
        or resp.MTR_PWM_DUTY != 255
        or resp.MTR_RECIRC != 3
        or resp.MTR_GUARD != 32
        or resp.MTR_RECVAL != 15
        or resp.MTR_SPISPSEL != 2
        or resp.MTR_SW_OFFSET != 480
    ):
        event_log.error(
            f"[EVENT] Initial Startup Healthcheck FAILED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} "
            f"Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} "
            f"Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} "
            f" Back Off: {resp.MTR_SW_OFFSET}"
        )
        resp = tc.hk_request(port)
        if (
            resp.MTR_FLAGS.MOVING == 1  # or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 0
            or resp.MTR_ABS_STEPS != 0
            or resp.MTR_CURRENT != 16384
            or resp.MTR_PWM_RATE != 1
            or resp.MTR_SPEED != 9
            or resp.MTR_PWM_DUTY != 255
            or resp.MTR_RECIRC != 3
            or resp.MTR_GUARD != 32
            or resp.MTR_RECVAL != 15
            or resp.MTR_SPISPSEL != 2
            or resp.MTR_SW_OFFSET != 160
        ):
            event_log.error(
                f"[EVENT] Initial Startup Healthcheck FAILED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} "
                f"Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} "
                f"Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} "
                f" Back Off: {resp.MTR_SW_OFFSET}"
            )
            return
        else:
            event_log.info(
                f"[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} "
                f"Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} "
                f"Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} "
                f" Back Off: {resp.MTR_SW_OFFSET}"
            )
            info_log.info(
                f"[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} "
                f"Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} "
                f"Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} "
                f" Back Off: {resp.MTR_SW_OFFSET}"
            )
    else:
        event_log.info(
            f"[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} "
            f"Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} "
            f"Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} "
            f"ABS Step Limit: {resp.MTR_ABS_STEPS} REL Step Limit: {resp.MTR_REL_STEPS} Back Off: {resp.MTR_SW_OFFSET}"
        )
        info_log.info(
            f"[EVENT] Initial Startup Healthcheck PASSED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} "
            f"Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} "
            f"Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} "
            f" Back Off: {resp.MTR_SW_OFFSET}"
        )

    # Home to base
    tc.mtr_homing(port, True, False, True)  # Set Homing towards Base
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
    else:
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    resp = tc.hk_request(port)
    # Home to base - Movement Stopped, Base asserted, Outer de-asserted, abs - steps = 8800, rel-steps = 0,
    if (
        resp.MTR_FLAGS.MOVING == 1 or resp.MTR_FLAGS.BASE == 0 or resp.MTR_FLAGS.OUTER == 1
    ):  # or resp.MTR_ABS_STEPS != 8800 ):
        event_log.error(
            f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        resp = tc.hk_request(port)
        if (
            resp.MTR_FLAGS.MOVING == 1
            or resp.MTR_FLAGS.BASE == 0
            or resp.MTR_FLAGS.OUTER == 1
            or resp.MTR_ABS_STEPS != 8800
        ):
            event_log.error(
                f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            return
        else:
            event_log.info(
                f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
    else:
        event_log.info(
            f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )

    # To Outer
    # Command as a large amound of steps as to not reset abs step count
    tc.mtr_mov_neg(port, 0x2190)
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
    else:
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")

    # Once finished request HK, verify that Outer Flag is active, motor moving is off, ABS count is within+-5 of usual back off, verify relative steps is 160
    resp = tc.hk_request(port)
    if (
        resp.MTR_FLAGS.MOVING == 1
        or resp.MTR_FLAGS.BASE == 1
        or resp.MTR_FLAGS.OUTER == 0
        or (520 >= resp.MTR_ABS_STEPS >= 1400)
        or resp.MTR_REL_STEPS != 480
    ):
        event_log.error(
            f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        resp = tc.hk_request(port)
        if (
            resp.MTR_FLAGS.MOVING == 1
            or resp.MTR_FLAGS.BASE == 1
            or resp.MTR_FLAGS.OUTER == 0
            or (520 >= resp.MTR_ABS_STEPS >= 1400)
            or resp.MTR_REL_STEPS != 480
        ):
            event_log.error(
                f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            return
        else:
            event_log.info(
                f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            info_log.info(
                f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
    else:
        event_log.info(
            f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        info_log.info(
            f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )

    # Start Stop Sweeps
    for i in range(2):
        # To Base
        for i in range(110):
            abs_steps = resp.MTR_ABS_STEPS
            tc.mtr_mov_pos(port, 0x0040)
            resp = tc.hk_request(port)
            abs_steps_diff = resp.MTR_ABS_STEPS - abs_steps
            if (
                resp.MTR_FLAGS.MOVING == 1
                or resp.MTR_FLAGS.BASE == 1
                or resp.MTR_FLAGS.OUTER == 1
                or abs(abs_steps_diff) != 64
                or abs(resp.MTR_REL_STEPS) != 64
            ):
                event_log.error(
                    f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                )
                resp = tc.hk_request(port)
                abs_steps_diff = abs_steps - resp.MTR_ABS_STEPS
                if (
                    resp.MTR_FLAGS.MOVING == 1
                    or resp.MTR_FLAGS.BASE == 1
                    or resp.MTR_FLAGS.OUTER == 1
                    or abs(abs_steps_diff) != 64
                    or abs(resp.MTR_REL_STEPS) != 64
                ):
                    event_log.error(
                        f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
                    return
                else:
                    event_log.info(
                        f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
            else:
                event_log.info(
                    f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                )
        tc.mtr_mov_pos(port, 0x0500)
        resp = tc.hk_request(port)
        if resp.MTR_FLAGS.MOVING == 1:
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                resp = tc.hk_request(port)
        else:
            event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
        resp = tc.hk_request(port)
        if (
            resp.MTR_FLAGS.MOVING == 1
            or resp.MTR_FLAGS.BASE == 0
            or resp.MTR_FLAGS.OUTER == 1
            or (8040 >= resp.MTR_ABS_STEPS >= 9560)
        ):
            event_log.error(
                f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            resp = tc.hk_request(port)
            if (
                resp.MTR_FLAGS.MOVING == 1
                or resp.MTR_FLAGS.BASE == 0
                or resp.MTR_FLAGS.OUTER == 1
                or (8040 >= resp.MTR_ABS_STEPS >= 9560)
            ):
                event_log.error(
                    f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
                )
                return
            else:
                event_log.info(
                    f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
                )
        else:
            event_log.info(
                f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )

        # To Outer
        for i in range(110):
            abs_steps = resp.MTR_ABS_STEPS
            tc.mtr_mov_neg(port, 0x0040)
            resp = tc.hk_request(port)
            abs_steps_diff = resp.MTR_ABS_STEPS - abs_steps
            if (
                resp.MTR_FLAGS.MOVING == 1
                or resp.MTR_FLAGS.BASE == 1
                or resp.MTR_FLAGS.OUTER == 1
                or abs(abs_steps_diff) != 64
            ):
                event_log.error(
                    f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                )
                resp = tc.hk_request(port)
                abs_steps_diff = abs_steps - resp.MTR_ABS_STEPS
                if (
                    resp.MTR_FLAGS.MOVING == 1
                    or resp.MTR_FLAGS.BASE == 1
                    or resp.MTR_FLAGS.OUTER == 1
                    or abs(abs_steps_diff) != 64
                ):
                    event_log.error(
                        f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
                    return
                else:
                    event_log.info(
                        f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
            else:
                event_log.info(
                    f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                )

        tc.mtr_mov_neg(port, 0x0500)
        resp = tc.hk_request(port)
        if resp.MTR_FLAGS.MOVING == 1:
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                resp = tc.hk_request(port)
        else:
            event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
        resp = tc.hk_request(port)
        if resp.MTR_FLAGS.MOVING == 1:
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                resp = tc.hk_request(port)
        else:
            event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
        resp = tc.hk_request(port)
        if (
            resp.MTR_FLAGS.MOVING == 1
            or resp.MTR_FLAGS.BASE == 1
            or resp.MTR_FLAGS.OUTER == 0
            or (520 >= resp.MTR_ABS_STEPS >= 1400)
            or resp.MTR_REL_STEPS != 480
        ):
            event_log.error(
                f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            resp = tc.hk_request(port)
            if (
                resp.MTR_FLAGS.MOVING == 1
                or resp.MTR_FLAGS.BASE == 1
                or resp.MTR_FLAGS.OUTER == 0
                or (520 >= resp.MTR_ABS_STEPS >= 1400)
                or resp.MTR_REL_STEPS != 480
            ):
                event_log.error(
                    f"[EVENT] Outer Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
                )
                return
            else:
                event_log.info(
                    f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
                )
        else:
            event_log.info(
                f"[EVENT] Outer Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )

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
    else:
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    if (
        resp.MTR_FLAGS.MOVING == 1
        or resp.MTR_FLAGS.BASE == 0
        or resp.MTR_FLAGS.OUTER == 1
        or (8040 >= resp.MTR_ABS_STEPS >= 9560)
    ):
        event_log.error(
            f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        resp = tc.hk_request(port)
        if (
            resp.MTR_FLAGS.MOVING == 1
            or resp.MTR_FLAGS.BASE == 0
            or resp.MTR_FLAGS.OUTER == 1
            or (8040 >= resp.MTR_ABS_STEPS >= 9560)
        ):
            event_log.error(
                f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            return
        else:
            event_log.info(
                f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
    else:
        event_log.info(
            f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
    # To Parked
    tc.mtr_mov_abs(port, 0x1FA4)
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1:
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
    else:
        event_log.error(f"[EVENT] Motor not Moving as expected. MTR Moving Flag : {resp.MTR_FLAGS.MOVING}")
    if (
        resp.MTR_FLAGS.MOVING == 1
        or resp.MTR_FLAGS.BASE == 1
        or resp.MTR_FLAGS.OUTER == 1
        or (7995 >= resp.MTR_ABS_STEPS >= 8005)
    ):
        event_log.error(
            f"[EVENT] Parked Position Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        resp = tc.hk_request(port)
        if (
            resp.MTR_FLAGS.MOVING == 1
            or resp.MTR_FLAGS.BASE == 1
            or resp.MTR_FLAGS.OUTER == 1
            or (7995 >= resp.MTR_ABS_STEPS >= 8005)
        ):
            event_log.error(
                f"[EVENT] Parked Position Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            return
        else:
            event_log.info(
                f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            info_log.info(
                f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
    else:
        event_log.info(
            f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        info_log.info(
            f"[EVENT] Parked Position Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )

def check_sci_vs_hk(port):
    send_cmd.cmd_power_control(port,0x03)
    resphk = tc.hk_request(port)
    respsci = tc.sci_request(port,0x01,0x01)
    abs_steps = respsci.MTR_ABS_STEPS
    send_cmd.cmd_mtr_mov_pos(port, 0x140)    
    resphk = tc.hk_request(port)
    if resphk.MTR_FLAGS.MOVING == 1 : 
        while resphk.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resphk = tc.hk_request(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    resphk = tc.hk_request(port)
    if (resphk.MTR_ABS_STEPS != respsci.MTR_ABS_STEPS) : 
        event_log.error(f"Motor Steps in HK and in SCI packets do not match : " + 
                        f"\n HK : {resphk.MTR_ABS_STEPS}" +
                        f"\n SCI : {respsci.MTR_ABS_STEPS}")
    if (abs(resphk.MTR_ABS_STEPS - respsci.MTR_ABS_STEPS) != 0) : 
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n ABS : {abs(resphk.MTR_ABS_STEPS - respsci.MTR_ABS_STEPS)} , Expected : 0")
        exit
    return

def check_halt(port):

    tc.power_control(port,0x01)
    resp = tc.hk_request(port)
    abs_steps = resp.MTR_ABS_STEPS
    send_cmd.cmd_mtr_mov_pos(port, 0x140)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(0.1)
            resp = tc.hk_request(port)
            event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    send_cmd.cmd_mtr_mov_pos(port, 0x2000)
    time.sleep(5)
    send_cmd.cmd_mtr_halt(port)
    resp = tc.hk_request(port)
    event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                    f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                    f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                    f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                    f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                    f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                    f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                    f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                    )
    return

def abu_hk(port, display_contents=True):
    event_log.info("Running ABU_HK")
    resp = tc.hk_request(port)
    if display_contents:
        event_log.info(
        f" MOD_ID :{resp.MOD_ID}" + 
    f"\n Unused1 : {resp.UNUSED1}" + 
    f"\n CMD_ID :{resp.CMD_ID}" + 
    f"\n CMD_CNT : {resp.CMD_CNT}" +
    f"\n ERROR_BYTE : {resp.ERROR_BYTE}" + 
    f"\n UNUSED2 :{resp.UNUSED2}" + 
    f"\n ERROR_MTR :{resp.ERROR_MTR}" + 
    f"\n MTR_ERR_MSK : {resp.MTR_ERR_MSK}" + 
    f"\n MTR_FLAGS_BYTE :{resp.MTR_FLAGS_BYTE}" +
    f"\n MTR_ABS_STEPS : {resp.MTR_ABS_STEPS}" +
    f"\n MTR_REL_STEPS : {resp.MTR_REL_STEPS}" + 
    f"\n MTR_CURRENT :{resp.MTR_CURRENT}" + 
    f"\n MTR_GUARD : {resp.MTR_GUARD}" + 
    f"\n MTR_RECVAL : {resp.MTR_RECVAL}" +
    f"\n UNUSED3 : {resp.UNUSED3}" +
    f"\n MTR_SPEED :{resp.MTR_SPEED}" +
    f"\n MECH_LIM_REL : {resp.MECH_LIM_REL}" + 
    f"\n UNUSED4 : {resp.PWR_STAT}" +  
    f"\n PWR_STAT : {resp.PWR_STAT}" +
    f"\n THRM_STATUS :{resp.THRM_STATUS}" + 
    f"\n THRM_MECH_OFF_SP : {resp.THRM_MECH_OFF_SP}" +
    f"\n THRM_MECH_ON_SP : {resp.THRM_MECH_ON_SP}" + 
    f"\n THRM_DET_OFF_SP :{resp.THRM_DET_OFF_SP}" + 
    f"\n THRM_DET_ON_SP : {resp.THRM_DET_ON_SP}" +
    f"\n SWIR_OFFSET : {resp.SWIR_OFFSET}" + 
    f"\n MWIR_OFFSET : {resp.MWIR_OFFSET}" +
    f"\n HK_V_3V3 : {resp.HK_V_3V3}" + 
    f"\n HK_V_1V5 :{resp.HK_V_1V5}" + 
    f"\n DIGITAL_TRP : {resp.DIGITAL_TRP}" +
    f"\n DETEC_TRP :{resp.DETEC_TRP}" + 
    f"\n MECH_TRP : {resp.MECH_TRP}" +
    f"\n MOTOR_TRP : {resp.MOTOR_TRP}" + 
    f"\n HK_MECH_CUR :{resp.HK_MECH_CUR}" + 
    f"\n UNUSED_ADC : {resp.UNUSED_ADC}" +
    f"\n HK_SAMPLES : {resp.HK_SAMPLES}" + 
    f"\n UNUSED5 :{resp.UNUSED5}" + 
    f"\n CRC8 : {resp.CRC8}")
    
def abu_cal_motor(port):
    event_log.info("Running abu_cal_motor")
    #TODO: Update all to "send_cmd"
    # Check mechanism powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x01)
        
        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)
    
    # Set motor parameters
    send_cmd.cmd_mtr_param(port,0x40,0x20,0x0F,0x9,0x3200)
    resp = tc.hk_request(port)
    if (
    resp.MTR_CURRENT != 0x40
    or resp.MTR_GUARD != 0x20
    or resp.MTR_RECVAL != 0x0F
    or resp.MTR_SPEED != 0x9
    or resp.MECH_LIM_REL != 0x3200):
        event_log.error(f"OB Parameters not initialized correctly:"+
                        f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 64" +
                        f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32" +
                        f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15" +
                        f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9" +
                        f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800")
        
    # Cal to BASE
    send_cmd.cmd_mtr_homing(port, True, False)    
    hk = tc.hk_request(port)

    # If ABS Steps at 8960 we are already there, otherwise wait for movement
    if hk.MTR_ABS_STEPS != 8960:
        event_log.info("Moving to the BASE, waiting for switch to be pressed.")
        while hk.MTR_FLAGS.MOVING:
            time.sleep(1)
            hk = tc.hk_request(port)
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, already at Base")

    #Check motor status now its stopped.
    resp = tc.hk_request(port)
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
    if resp.MTR_FLAGS.HOMED != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMED}")
   
    if (resp.MTR_ABS_STEPS != 8960):
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
    if (resp.MTR_REL_STEPS == 0):
        event_log.error(f"Motor Steps Do not match expected REL : {resp.MTR_REL_STEPS} , Expected : 0")
        
    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")

def abu_outer_home(port):
    event_log.info("Running abu_outer_home")
    #TODO: Update all to "send_cmd" 
    # Check mechanism powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x01)
        
        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    # Home to Outer with no Cal
    send_cmd.cmd_mtr_homing(port, False, True)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        event_log.info("Moving to outer, waiting for switch to be pressed.")
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                                        f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                                        f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                                        f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                                        f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                                        f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                                        f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                                        f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                                        )
            event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        event_log.info("Motor movement finished")
    else : 
        event_log.error("Motor Did not Move :")

    #Check motor status now its stopped.
    resp = tc.hk_request(port)  
    if resp.MTR_FLAGS.CAL != 0 : 
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 1 : 
        event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER !=1 : 
        event_log.error(f"OUTER Switch Flag not asserted : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE !=0 : 
        event_log.error(f"Base Switch Flag is asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMED != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMED}")

    if (resp.MTR_REL_STEPS == 0):
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
        
    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")

def abu_rtn_to_base(port):
    event_log.info("Running abu_rtn_to_base")
    #TODO: Update all to "send_cmd" 

    # Check mechanism powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x01)
        
        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    # Home to base
    send_cmd.cmd_mtr_homing(port,False, False)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        event_log.info("Moving to the base, waiting for switch to be pressed.")
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.info("Motor movement finished")
    else : 
        event_log.error("Motor Did not Move :")

    #Check motor status now its stopped.
    resp = tc.hk_request(port)  
    if resp.MTR_FLAGS.CAL != 0 : 
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0 : 
        event_log.error(f" Calibration Dir not to Base : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER !=0 : 
        event_log.error(f"OUTER Switch Flag raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE !=1 : 
        event_log.error(f"Base Switch Flag not raised : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMED != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMED}")

    if (resp.MTR_REL_STEPS == 0):
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
        
    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")
   
def abu_pos_steps(port, pos_steps):
    """
    Script that moves the mechanism a certain number of steps positive (towards the base).
    Automatically checks that we are not already at the base.
    """

    # First check that there we are are not already at the base.
    hk = tc.hk_request(port)
    # TODO! Can uncomment once bug is resolved
    # if hk.MTR_FLAGS.BASE:
    #     event_log.error("Request to move positive steps but already at the base, skipping movement")
    #     return
    
    # Then move the desired number of steps
    send_cmd.cmd_mtr_mov_pos(port, pos_steps)

    # Request a HK and wait until no longer moving
    hk = tc.hk_request(port)
    while hk.MTR_FLAGS.MOVING:
        hk = tc.hk_request(port)

    if hk.ERROR_MTR != 0:
        event_log.error(f"***MOTOR ERROR*** got the following: " +
                        f"\n CD : {hk.MTR_ERRORS.CD}"+
                        f"\n AB : {hk.MTR_ERRORS.AB}" + 
                        f"\n ABS : {hk.MTR_ERRORS.ABS}" + 
                        f"\n REL : {hk.MTR_ERRORS.REL}" + 
                        f"\n DSE : {hk.MTR_ERRORS.DSE}"
                        )
    
    # Then print a summary of the motor movement
    # event_log.info(f"HK After Motor Movement Complete:" +
    #                f"\t Error Byte: {hk.ERROR_BYTE}" +
    #                f"\t Error MTR: {hk.ERROR_MTR}" +
    #                f"\t MTR_ABS_STEPS: {hk.MTR_ABS_STEPS}" +
    #                f"\t MTR_REL_STEPS: {hk.MTR_REL_STEPS}" +
    #                f"\t MTR_FLAGS: {hk.MTR_FLAGS_BYTE}"
    #                )
    
    return

def abu_neg_steps(port, pos_steps):
    """
    Script that moves the mechanism a certain number of steps negative (towards the outer).
    Automatically checks that we are not already at the outer.
    """

    # First check that we are not already at the outer.
    hk = tc.hk_request(port)
    # TODO! Can uncomment once bug is resolved
    # if hk.MTR_FLAGS.OUTER:
    #     event_log.error("Request to move negative steps but already at the outer, skipping movement")
    #     return

    # Then move the desired number of steps
    send_cmd.cmd_mtr_mov_neg(port, pos_steps)

    # Request a HK and wait until no longer moving
    hk = tc.hk_request(port)
    while hk.MTR_FLAGS.MOVING:
        hk = tc.hk_request(port)

    if hk.ERROR_MTR != 0:
        event_log.error(f"***MOTOR ERROR*** got the following: " +
                        f"\n CD : {hk.MTR_ERRORS.CD}"+
                        f"\n AB : {hk.MTR_ERRORS.AB}" + 
                        f"\n ABS : {hk.MTR_ERRORS.ABS}" + 
                        f"\n REL : {hk.MTR_ERRORS.REL}" + 
                        f"\n DSE : {hk.MTR_ERRORS.DSE}"
                        )

def abu_set_offset(port, swir_offset, mwir_offset, sci_adc_samp=4, sci_adc_skip=20):
    event_log.info("Running abu_set_offset")

    # Check detector powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x02)
        
        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)
    
    #Dark measurement to determine offset to be applied 
    #Set SWIR and MWIR offset
    tc.sci_offset(port, swir_offset, mwir_offset)
    hk = tc.hk_request(port)
    if hk.SWIR_OFFSET != swir_offset:
        event_log.error(f"SWIR offset not updated in HK. Got {hk.SWIR_OFFSET}")
    if hk.MWIR_OFFSET != mwir_offset:
        event_log.error(f"MWIR offset not updated in HK. Got {hk.MWIR_OFFSET}")

    #Take SCI reading and check. 
    sci = check_sci(port, sci_adc_samp, sci_adc_skip)
    if sci.SWIR_OFFSET != swir_offset:
        event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}")
    if sci.MWIR_OFFSET != mwir_offset:
        event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}")

def abu_dac_mwir_offset(port, swir_initial=2048, sci_adc_samp=4, sci_adc_skip=2):
    """
    This automatically determines and reports the DAC offsets
    """
    event_log.info("Running abu_dac_mwir_offset")

    # Check detector powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x02)
        
        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    mwir_value = 0x0 # Seed value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        mwir_delta = 0x1 << (i - 1)
        event_log.info(f"Setting the MWIR Value to: {mwir_value + mwir_delta}")
        tc.sci_offset(port, swir_initial, mwir_value + mwir_delta)
        sci = check_sci(port, sci_adc_samp, sci_adc_skip)
        if sci.MWIR_OFFSET != (mwir_value + mwir_delta):
            event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {mwir_value + mwir_delta}")
        
        event_log.info(f"Got the following MWIR High Reading: {sci.MWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.MWIR_HIGH >= const.MWIR_DAC_MIN_TH:
            mwir_value = mwir_value + mwir_delta

        # Check if we are within the range (we are done) otherwise loop
        if const.MWIR_DAC_MIN_TH <= sci.MWIR_HIGH <= const.MWIR_DAC_MAX_TH:
            event_log.info(f"MWIR offset in threshold finished!")
            event_log.info(f"Final MWIR value: {mwir_value}")
            return mwir_value
    
    event_log.error(f"No solution found. Last MWIR Offset set to: {sci.MWIR_OFFSET}")
    return sci.MWIR_OFFSET

def abu_dac_swir_offset(port, mwir_value=2048, sci_adc_samp=4, sci_adc_skip=2):
    """
    This automatically determines and reports the DAC offsets
    """
    event_log.info("Running abu_dac_swir_offset")

    # Check detector powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x02)
        
        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)
    
    swir_value = 0x0 # Seed Value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        swir_delta  = 0x1 << (i -1)
        event_log.info(f"Setting the SWIR value to: {swir_value + swir_delta}")
        tc.sci_offset(port, swir_value + swir_delta, mwir_value)
        sci = check_sci(port, sci_adc_samp, sci_adc_skip)
        if sci.SWIR_OFFSET != (swir_value + swir_delta):
            event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}, Expected: {swir_value + swir_delta}")

        event_log.info(f"Got the following SWIR High Reading: {sci.SWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.SWIR_HIGH > const.SWIR_DAC_MIN_TH:
            swir_value = swir_value + swir_delta

        # Check if we are within the range (we are done) otherwise loop
        if const.SWIR_DAC_MIN_TH <= sci.SWIR_HIGH <= const.SWIR_DAC_MAX_TH:
            event_log.info(f"SWIR offset in threshold finished!")
            event_log.info(f"Final SWIR value: {swir_value}")
            return swir_value
            
    event_log.error(f"No solution found. Last MWIR Offset set to: {sci.SWIR_OFFSET}")
    return sci.SWIR_OFFSET

def abu_measure(port, pos_steps, sci_adc_samp=4, sci_adc_skip=20):
    """
    Moves the specified number of steps forward and then takes a measurement. 0 steps can be entered
    and the sequence will just measure the same point once again.

    This sequence should be executed once the motor has been homed and the offsets applied.

    The motor moves from the Outer to Base using (positive steps)
    """
    if pos_steps > 0:
        abu_pos_steps(port, pos_steps)
    else:
        event_log.info(f"No need to move any steps, proceeding to measurement")

    # Request a Science Mesaurement and log to the screen.
    sci = tc.sci_request(port, sci_adc_samp, sci_adc_skip)
    event_log.info(f"MTR_ABS_STEPS: {sci.MTR_ABS_STEPS}" +
                  f"\t SWIR_LOW: {sci.SWIR_LOW}" +
                  f"\t SWIR_MED: {sci.SWIR_MED}" +
                  f"\t SWIR_HIGH: {sci.SWIR_HIGH}" +
                  f"\t MWIR_LOW: {sci.MWIR_LOW}" +
                  f"\t MWIR_MED: {sci.MWIR_MED}" +
                  f"\t MWIR_HIGH: {sci.MWIR_HIGH}")
    
    return
    
def abu_measurement_scan(port, step_spacing=50, sci_adc_samp=4, sci_adc_skip=20):
    """
    Performs the basic Enfys science measurement
    Homes and Calibrates to Base
    Goes to the Outer
    Performs Dark Measurement Offsets
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    Once Base Stop is reached
    Repeats the Dark Mesaurement Offsets at Base
    """
    event_log.info("Running ABU Measurement Scan")
    abu_hk(port, False)
        
    # Cal to Base
    abu_cal_motor(port)

    # Home to Outer
    abu_outer_home(port)

    # MWIR Offset determination
    mwir_offset = abu_dac_mwir_offset(port, 2048, sci_adc_samp, sci_adc_skip)
        
    # SWIR Offset determination
    swir_offset = abu_dac_swir_offset(port, mwir_offset, sci_adc_samp, sci_adc_skip)

    # Measurement sequence
    # TODO! Emulate Dark Offset and Edge finding (with SWIR and broad lamp)
    event_log.info("Starting Science Measurements")
    abu_measure(port, 0, sci_adc_samp, sci_adc_skip)
    for i in range(0, 8600, step_spacing):
        abu_measure(port, step_spacing, sci_adc_samp, sci_adc_skip)
    
    # MWIR Offset determination at the end
    mwir_offset = abu_dac_mwir_offset(port, swir_offset, sci_adc_samp, sci_adc_skip)

    # SWIR Offset determination at the end
    swir_offset = abu_dac_swir_offset(port, mwir_offset, sci_adc_samp, sci_adc_skip)

    event_log.info("Science Measurements Completed!!")

def vsense_test(port) : 
    tc.power_control(port,0x03)
    send_cmd.cmd_mtr_param(port,0x40,0x20,0x0F,0x9,0x3200)
    resp = tc.hk_request(port)
    event_log.info("HOME to BASE")
    resp = tc.hk_request(port)
    send_cmd.cmd_mtr_homing(port,False, False)    
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.MOVING == 1 : 
        while resp.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resp = tc.hk_request(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )
    else : 
        event_log.error("Motor Did not Move :")
        event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
        event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        if resp.ERROR_MTR != 0:
            event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            ) 