import logging
import time
import constants as const
import send_cmd
import tc

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")
class SetError(Exception): 
    pass
class ClearError(Exception):
    pass

def check_set_ob_errors(port):
    errors_found = []
    event_log.info(f"--Setting OB Errors... --")       
    tc.set_errors(port,True,True,False,False,False,False,False,False,False,False,False,False,False,False)
    try:
        resp = tc.hk_request(port)
         
        if resp.get_cmd_mod_id() == 0x01:
            resp = tc.hk_request(port)
        for err_name, err_value in vars(resp.ERRORS).items():
            if err_value == 0 and err_name in ["TMO", "IPA"]:
                errors_found.append(f"{err_name} error: value = {err_value}")
        if errors_found:
            raise SetError("; ".join(errors_found))
        else : 
            event_log.info("Test SetErrors : Passed")

    except SetError as e:
        event_log.error(f"SetError occurred: {e}")
    
    errors_found = []
    event_log.info(f"--Clearing OB Errors... --") 
    tc.clear_errors(port)
    try:
        resp = tc.hk_request(port)
        for err_name, err_value in vars(resp.ERRORS).items():
           if err_value == 1 and err_name in ["TMO", "IPA"]:
                errors_found.append(f"{err_name} error: value = {err_value}")
        if errors_found:
            raise ClearError("; ".join(errors_found))
        else : 
            event_log.info("Test ClearErrors : Passed")
# ...rest of your logic...
    except ClearError as e:
        event_log.error(f"ClearError occurred: {e}")

def check_set_mtr_errors(port):
    errors_found = []
    event_log.info(f"--Setting MTR Errors... --") 
    tc.power_control(port,0x03)
    tc.set_errors(port,False,False,False,False,True,True,True,False,False,False,False,False,False,False)
    tc.mtr_mov_pos(port,0x010)

    try:
        resp = tc.hk_request(port)
        if resp.get_cmd_mod_id() == 0x01:
            resp = tc.hk_request(port)
        for err_name, err_value in vars(resp.MTR_ERRORS).items():
            if err_value == 0 and err_name in ["CD","AB","ABS","REL","DSE"]:
                errors_found.append(f"{err_name} error: value = {err_value}")
        if errors_found:
            raise SetError("; ".join(errors_found))
        else : 
            event_log.info("Test SetMTRErrors : Passed")

    except SetError as e:
        event_log.error(f"SetMTRError occurred: {e}")
    
    errors_found = []
    event_log.info(f"--Clearing MTR Errors... --") 
    tc.clear_errors(port)
    try:
        resp = tc.hk_request(port)
        for err_name, err_value in vars(resp.MTR_ERRORS).items():
           if err_value == 1 and err_name in ["CD","AB","ABS","REL","DSE"]:
                errors_found.append(f"{err_name} error: value = {err_value}")
        if errors_found:
            raise ClearError("; ".join(errors_found))
        else : 
            event_log.info("Test ClearMTRErrors : Passed")
# ...rest of your logic...
    except ClearError as e:
        event_log.error(f"ClearMTRError occurred: {e}")

def check_mask_mtr_errors(port):
    errors_found = []
    event_log.info(f"--Setting MTR Masks... --") 
    tc.power_control(port,0x03)
    tc.set_errors(port,False,False,False,False,False,False,False,True,True,True,True,True,True,True)
    tc.mtr_mov_pos(port,0x010)

    try:
        resp = tc.hk_request(port)
        if resp.get_cmd_mod_id() == 0x01:
            resp = tc.hk_request(port)
        for err_name, err_value in vars(resp.MTR_ERROR_MASK).items():
            if err_value == 0 and err_name in ["IG_B","IG_O""M_CD","M_AB","M_ABS","M_REL","M_DSE"]:
                errors_found.append(f"{err_name} error: value = {err_value}")
        if errors_found:
            raise SetError("; ".join(errors_found))
        else : 
            event_log.info("Test SetMaskMTRErrors : Passed")

    except SetError as e:
        event_log.error(f"SetMaskMTRError occurred: {e}")

    errors_found = []
    event_log.info(f"--Setting MTR Errors for Masked Errors... --") 
    tc.set_errors(port,False,False,True,True,True,True,True,True,True,True,True,True,True,True)
    try:
        resp = tc.hk_request(port)
        for err_name, err_value in vars(resp.MTR_ERRORS).items():
           if err_value == 1 and err_name in ["CD","AB","ABS","REL","DSE"]:
                errors_found.append(f"{err_name} error: value = {err_value}")
        if errors_found:
            raise SetError("; ".join(errors_found))
        else : 
            event_log.info("Test Set MTRMaskErrors : Passed")
    except SetError as e:
        event_log.error(f"SetMTRMMaskError occurred: {e}")


        