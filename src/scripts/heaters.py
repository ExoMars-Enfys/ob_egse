import logging
import time
import constants as const
import send_cmd
import tc
import keyboard
# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
event_log = logging.getLogger("event_log")

def mech_auto_heater_test(port):    
    tc.set_mech_sp(port, 0x79A, 0x738) #Set mechanism heater setpoint to 823 Ohms
    event_log.info(f"Mech Heater On threshold : Resistance: 823 Ohms, Temp: -45 degrees C" + 
                   f"Setpoint : {(tc.hk_request(port)).THRM_MECH_ON_SP}")
    event_log.info(f"Mech Heater Off threshold : Resistance: 882 Ohms, Temp: -30 degrees C" + 
                   f"Setpoint : {(tc.hk_request(port)).THRM_MECH_OFF_SP}")
    try : 
        event_log.info(f"Turning Mech Auto Heaters ON")
        tc.heater_control(port, False, False, False, False, True) #Turn automatic mechanism heater on
        event_log.info(f"Turn Resistance below 823Ohm / 1848DN to trigger Auto On Mechanism Heater and press Return to confirm")
        keyboard.wait('return') #Wait for user to press Return
        event_log.info(f"Current Mech TRP: {tc.hk_request(port).MECH_TRP}")
        if (tc.hk_request(port)).THRM_STATUS == 65:
            event_log.info(f"Mech Auto Heaters are ON  : {tc.hk_request(port).THRM_STATUS}")
        else:
            raise ValueError(event_log.error(f"Mech Auto Heaters failed to turn ON : {tc.hk_request(port).THRM_STATUS}"))
    except ValueError as e:
        event_log.error(f"Error occurred while turning on Mech Auto Heaters: {e}")

    try : 
        event_log.info(f"Turning Mech Auto Heaters OFF")
        event_log.info(f"Turn Resistance above 882Ohm / 1946DN to trigger Auto Off Mechanism Heater and press Return to confirm")
        keyboard.wait('return') #Wait for user to press Return
        event_log.info(f"Current Mech TRP: {tc.hk_request(port).MECH_TRP}")
        if (tc.hk_request(port)).THRM_STATUS == 1:
            event_log.info(f"Mech Auto Heaters are Off  : {tc.hk_request(port).THRM_STATUS}")
        else:
            raise ValueError(event_log.error(f"Mech Auto Heaters failed to turn Off : {tc.hk_request(port).THRM_STATUS}"))
    except ValueError as e:
        event_log.error(f"Error occurred while turning Off Mech Auto Heaters: {e}")