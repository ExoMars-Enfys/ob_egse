# Std library
import logging
import time
from pathlib import Path
from datetime import datetime
import threading

# Local modules
import comms
import constants as const
import psu
from send_cmd import cmd_repeat as repeat
import tc

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")



def fft(port,psu_com,nopsu) :
        event_log.info(f"\n- - - - -              OB FFT V1               - - - - - "+"\n- - - - - Follows §2.1 of the OB - EB ICD V3.0 - - - - - " 
                       + f"\n- - - - -          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}         - - - - - "
                       + f"\n- - - - -       Using COM port:  {str(port.port)}         - - - - - "
                       + f"\n- - - - -       Using PSU COM port: {str(psu_com)}       - - - - - "
                       )
        
# Block 2
        event_log.info(f"\n- - - - -              Block 1 - IDLE IMPEDANCES             - - - - - ")
        input(event_log.info(f"\n - - 1.1 Please record Idle impedances and confirm to turn on the psu channels"))
        psu.switchPSU(psu_com,1)

# Block 2
        event_log.info(f"\n- - - - -              Block 2 - IDLE IMPEDANCES and POWER CONSUMPTION             - - - - - ")
        
        input(event_log.info(f"\n - - 2.1 Please record Idle impedances and confirm to turn on the psu channels"))
        psu.switchPSU(psu_com,1)
# Block 2.2
        input(event_log.info(f"\n - - 2.1 Please record Idle Current and Voltage consumptions on all 3 PSU channels and confirm to continue"))
        event_log.info(f"\n - - 2.2 Will now move to step 2.2. Checking the Boot HK. - - ")
        hk_check(port)
# Block 2.3
        input(event_log.info(f" - - 2.2 Note down and confirm HK fields. Press Enter to Continue - - "))
        #TODO! ADD a step 2.3 to get hk and check that the HK ADC readings for the voltages are as expected

# Block 3
        event_log.info(f"\n- - - - -              Block 3 - Heater Consumption and Functionality            - - - - - ")
#  Block 3.1
        input(event_log.info(f"\n - - 3.1 Turn on Mechanism Manual heaters - Press Enter to Confirm - -"))

        repeat(port,tc.heater_control, False, False, False, True, False)
        resp = repeat(port,tc.hk_request)
        try : 
                if resp.THRM_STATUS != 64:
                        raise ValueError(event_log.error(f"Mechanism Heaters did not Turn on. Powering off to investigate"))
        except ValueError as e : 
                event_log.error(f"Error in Thermal test : {e}")
# Block 3.2
        input(event_log.info(f"\n - - 3.2 Confirm Power Consumption on -12V Heater line is ~83mA. Press Enter to Confirm - - "))
        event_log.info(f"\n- - 3.2 Now waiting one minute for the Mechanism board to heat up - - ")
        time.sleep(60)
        resp = repeat(port, tc.hk_request)
        input(event_log.info(f"\n - - Please note the Mechanism and Motor TRPs and press Enter to confirm - - "+
                             f"\n - - Mechanism TRP - : {resp.MECH_TRP} - - " +
                             f"\n - - Motor TRP -: {resp.MTR_TRP}"))
# Block 3.3
        input(event_log.info( f"\n - - 3.3 Turning off Manual Heaters. Measure Idle Power Consumption and Press Enter to confirm - - "))
        repeat(port,tc.heater_control, False, False, False, False, False) 
# Block 3.4
        event_log.info(f"\n - - 3.4 Now Commencing Mechanism board Heater Auto test - - ")
        repeat(port,tc.set_mech_sp,port, 0x79A, 0x738) #Set mechanism heater setpoint to 823 Ohms
        event_log.info(f"Mech Heater On threshold : Resistance: 823 Ohms, Temp: -45 degrees C" + 
                        f"Setpoint : {repeat(port,tc.hk_request).THRM_MECH_ON_SP}")
        event_log.info(f"Mech Heater Off threshold : Resistance: 882 Ohms, Temp: -30 degrees C" + 
                        f"Setpoint : {repeat(port,tc.hk_request).THRM_MECH_OFF_SP}")
        try : 
                event_log.info(f"Turning Mech Auto Heaters ON")
                repeat(port,tc.heater_control, False, False, False, False, True) #Turn automatic mechanism heater on
                input(event_log.info(f"Turn Resistance below 823Ohm / 1848DN to trigger Auto On Mechanism Heater and press Return to confirm"))
                input(event_log.info(f"Please note Current Mech TRP: {repeat(port,tc.hk_request).MECH_TRP} and Press Enter to Confirm"))
                if repeat(port,tc.hk_request).THRM_STATUS == 65:
                        event_log.info(f"Mech Auto Heaters are ON  : {repeat(port,tc.hk_request).THRM_STATUS}")
                else:
                        raise ValueError(event_log.error(f"Mech Auto Heaters failed to turn ON : {repeat(port,tc.hk_request).THRM_STATUS}"))
        except ValueError as e:
                event_log.error(f"Error occurred while turning on Mech Auto Heaters: {e}")

        try : 
                event_log.info(f"Turning Mech Auto Heaters OFF")
                input(event_log.info(f"Turn Resistance above 882Ohm / 1946DN to trigger Auto Off Mechanism Heater and press Return to confirm"))
                input(event_log.info(f"Please note Current Mech TRP: {repeat(port,tc.hk_request).MECH_TRP} and Press Enter to confirm"))
                if (repeat(port,tc.hk_request)).THRM_STATUS == 1:
                        event_log.info(f"Mech Auto Heaters are Off  : {repeat(port,tc.hk_request).THRM_STATUS}")
                else:
                        raise ValueError(event_log.error(f"Mech Auto Heaters failed to turn Off : {repeat(port,tc.hk_request).THRM_STATUS}"))
        except ValueError as e:
                event_log.error(f"Error occurred while turning Off Mech Auto Heaters: {e}")


def hk_check(port) :         
        try : 
                resp = repeat(port,tc.hk_request)
                if (resp.MOD_ID !=const.EXP_MODEL_ID
                or resp.UNUSED1 !=0
                or resp.CMD_ID !=0
                or resp.CMD_CNT!=1
                or resp.ERROR_BYTE!= 0
                or resp.UNUSED2 != 0 
                or resp.ERROR_MTR != 0
                or resp.MTR_ERR_MSK != 0 
                or resp.MTR_FLAGS_BYTE != 1
                or resp.MTR_ABS_STEPS != 0 
                or resp.MTR_REL_STEPS != 0 
                or resp.MTR_CURRENT != 64
                or resp.MTR_GUARD != 32
                or resp.MTR_RECVAL != 64
                or resp.UNUSED3 != 0 
                or resp.MTR_SPEED != 9
                or resp.MECH_LIM_REL != 1280
                or resp.PWR_STAT != 0
                or resp.THRM_STATUS != 0
                or resp.THRM_MECH_OFF_SP
                or resp.THRM_MECH_ON_SP
                or resp.THRM_DET_OFF_SP
                or resp.THRM_DET_ON_SP
                or resp.SWIR_OFFSET
                or resp.MWIR_OFFSET
                or resp.HK_V_3V3
                or resp.HK_V_1V5
                or resp.DIGITAL_TRP
                or resp.DETEC_TRP
                or resp.MECH_TRP
                or resp.MOTOR_TRP
                or resp.HK_MECH_CUR
                or resp.UNUSED_ADC
                or resp.HK_SAMPLES
                or resp.UNUSED5 ):
                        raise ValueError(event_log.error(f" - - Boot HK does not match expected. "+
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
                                        f"\n CRC8 : {resp.CRC8}"))
                        
        except ValueError as e:
                event_log.error(f"Value Error at HK : ")
        
        return

        
