import logging
import time
import constants as const
import send_cmd
import tc

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")


# ----
def power_up(port):
    try : 
        send_cmd.cmd_power_control(port,0x01)
        send_cmd.cmd_mtr_param(port,0x17,0x20,0x0F,0x7,0x3200)
        resp = tc.hk_request(port)
        if resp.PWR_STAT != 1 or resp.MTR_CURRENT != 23 or resp.MTR_GUARD != 32 or resp.MTR_RECVAL != 15 or resp.MTR_SPEED != 7 or resp.MECH_LIM_REL != 12800:            
            raise ValueError(f"OB Parameters not initialized correctly:"+
                            f"\n Power State : {resp.PWR_STAT}                ~ Expected : 1" +
                            f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 64" +
                            f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32" +
                            f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15" +
                            f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9" +
                            f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800")
        else : 
            event_log.info("Power Up and set params : Passed")
            return resp
    except ValueError as e:
        event_log.error(f"Power Up and set params failed : {e}")
        exit()

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
                exit()
    else :           
        event_log.error(f"Mech Heater Status not On : {resp.THRM_STATUS} ")
        exit()
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
    event_log.info(f"ERROR BYTE :"+
                   f"\nIPI : {resp.ERRORS.IPI}" + 
                   f"\nIOS : {resp.ERRORS.IOS}" + 
                   f"\nICR : {resp.ERRORS.ICR}" + 
                   f"\nMOR : {resp.ERRORS.MOR}" + 
                   f"\nTMO : {resp.ERRORS.TMO}" + 
                   f"\nIPA : {resp.ERRORS.IPA}"
                   )
    event_log.info(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                            f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                            f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                            f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                            f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                            f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                            )
    event_log.info(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                            f"\n CD : {resp.MTR_ERRORS.CD}"+
                            f"\n AB : {resp.MTR_ERRORS.AB}" + 
                            f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                            f"\n REL : {resp.MTR_ERRORS.REL}" + 
                            f"\n DSE : {resp.MTR_ERRORS.DSE}"
                            )

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
        f"  SW:H: {resp.SWIR_HIGH}" +
        f"  SW:M: {resp.SWIR_MED}" +
        f"  SW:L: {resp.SWIR_LOW}" +
        f"  MW:H: {resp.MWIR_HIGH}" +
        f"  MW:M: {resp.MWIR_MED}" +
        f"  MW:L: {resp.MWIR_LOW}" +
        f"  HT_SINK_TEMP: {resp.HT_SINK_TEMP}" +
        f"  SWIR_TEMP: {resp.SWIR_TEMP}"
    )
    return resp

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
