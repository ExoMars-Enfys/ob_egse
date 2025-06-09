import logging
import time
import send_cmd
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
    f"\n ERROR_MTR :{resp.ERROR_MTR}" + 
    f"\n PWR_STAT : {resp.PWR_STAT}" +
    f"\n UNUSED2 :{resp.UNUSED2}" + 
    f"\n MTR_ABS_STEPS : {resp.MTR_ABS_STEPS}" +
    f"\n MTR_REL_STEPS : {resp.MTR_REL_STEPS}" + 
    f"\n MTR_FLAGS_BYTE :{resp.MTR_FLAGS_BYTE}" + 
    f"\n MTR_GUARD : {resp.MTR_GUARD}" +
    f"\n UNUSED3 : {resp.UNUSED3}" + 
    f"\n MTR_RECVAL : {resp.MTR_RECVAL}" +
    f"\n MECH_LIM_REL : {resp.MECH_LIM_REL}" + 
    f"\n MTR_CURRENT :{resp.MTR_CURRENT}" + 
    f"\n UNUSED4 : {resp.PWR_STAT}" +
    f"\n MTR_SPEED :{resp.MTR_SPEED}" + 
    f"\n MTR_ERR_MSK : {resp.MTR_ERR_MSK}" +
    f"\n UNUSED5 : {resp.UNUSED5}" + 
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
    f"\n UNUSED6 :{resp.UNUSED6}" + 
    f"\n CRC8 : {resp.CRC8}")

def power_up_tests(port) :
    resp = tc.hk_request(port)
    if resp.PWR_STAT != 0 : 
        event_log.error(f"OB Initialised in wrong Power State : {resp.PWR_STAT}")
        exit
    else :         
        send_cmd.cmd_power_control(port,0x01)
        resp=tc.hk_request(port)
        if resp.PWR_STAT != 1 : 
            event_log.error(f"OB Initialised in wrong Power State : {resp.PWR_STAT}")
            exit
        else :
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
    if ((abs(abs_steps - resp.MTR_ABS_STEPS) != 320 or resp.MTR_REL_STEPS != 320)) : 
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 320" +
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 320")
        exit
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
    if ((abs(abs_steps - resp.MTR_ABS_STEPS) != 320 or resp.MTR_REL_STEPS != 320)) : 
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 320" +
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 320")
        exit
    return

def cal_test(port):
    event_log.info("CAL to base")
    resp = tc.hk_request(port)
    send_cmd.cmd_mtr_homing(port,True, False)    
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
    tm_log.info("Motor movement finished")

    time.sleep(3)

    tc.mtr_mov_neg(port, 0x0300)
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
        error_log.error(
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
            error_log.error(
                f"[EVENT] Initial Startup Healthcheck FAILED - Checks carried : Moving: {resp.MTR_FLAGS.MOVING} BaseStop: {resp.MTR_FLAGS.BASE} OuterStop: {resp.MTR_FLAGS.OUTER}  AbsSteps: {resp.MTR_ABS_STEPS} RelSteps: {resp.MTR_REL_STEPS} "
                f"Current: {resp.MTR_CURRENT} PWM Rate: {resp.MTR_PWM_RATE} Speed: {resp.MTR_SPEED} PWM Duty: {resp.MTR_PWM_DUTY} "
                f"Recirc: {resp.MTR_RECIRC} MTR Guard: {resp.MTR_GUARD} RecVal: {resp.MTR_RECVAL} SPiSel: {resp.MTR_SPISPSEL} "
                f"Back Off: {resp.MTR_SW_OFFSET}"
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
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")
    abs_log.info(f"Start of Measurement Cycle")

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
        error_log.error(
            f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
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
            error_log.error(
                f"[EVENT] Homing Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            return
        else:
            event_log.info(
                f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            info_log.info(
                f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
    else:
        event_log.info(
            f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        info_log.info(
            f"[EVENT] Homing Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")

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
        error_log.error(
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
            error_log.error(
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
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")

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
                error_log.error(
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
                    error_log.error(
                        f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
                    return
                else:
                    event_log.info(
                        f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
                    info_log.info(
                        f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
            else:
                event_log.info(
                    f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                )
                info_log.info(
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
            error_log.error(
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
                error_log.error(
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
        abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")

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
                error_log.error(
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
                    error_log.error(
                        f"[EVENT] Start Stop Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
                    return
                else:
                    event_log.info(
                        f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
                    info_log.info(
                        f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                    )
            else:
                event_log.info(
                    f"[EVENT] Start Stop Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{abs_steps_diff} RelSteps:{resp.MTR_REL_STEPS}"
                )
                info_log.info(
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
            error_log.error(
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
                error_log.error(
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
        error_log.error(
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
            error_log.error(
                f"[EVENT] Base Traverse Healthcheck FAILED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            return
        else:
            event_log.info(
                f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
            info_log.info(
                f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
            )
    else:
        event_log.info(
            f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
        info_log.info(
            f"[EVENT] Base Traverse Healthcheck PASSED - Checks carried : Moving:{resp.MTR_FLAGS.MOVING} BaseStop:{resp.MTR_FLAGS.BASE} OuterStop:{resp.MTR_FLAGS.OUTER}  AbsSteps:{resp.MTR_ABS_STEPS} RelSteps:{resp.MTR_REL_STEPS}"
        )
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")
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
        error_log.error(
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
            error_log.error(
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
    abs_log.info(f"ABS Steps at this PiT: {resp.MTR_ABS_STEPS}")

def check_sci_vs_hk(port):
    resphk = tc.hk_request(port)
    respsci = tc.sci_request(port)
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
    if (abs(abs_steps - respsci.MTR_ABS_STEPS) != 320) : 
        event_log.error(f"Motor Steps Do not match expected : " + 
                        f"\n ABS : {respsci.MTR_ABS_STEPS} , Expected : 320")
        exit
    return
