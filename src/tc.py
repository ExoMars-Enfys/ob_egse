import logging
from datetime import datetime
import time
import constants as const
import tm
from crc8_function import crc8Calculate

tc_log = logging.getLogger("tc_log")
info_log = logging.getLogger("info_log")
error_log = logging.getLogger("error_log")
cmd_log = logging.getLogger("cmd_log")
# TODO: Have a return pass/fail for each TC, so extra logic can be added to script


def log_tc_bytes(cmd_bytes: bytes):
    const.CMD_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
    const.CMD_LOG_FH.write(f" - {bytes.hex(cmd_bytes, ' ', 2)}\n")
def hk_request(port, verify=True):
    ## --- Check input parameters before sending CMD ---
    # No parameters for CMD

    ## --- Send CMD ---
    cmd = "00" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    # tc_log.info(f"Send HK:{bytes.hex(cmd_tc, ' ', 2)}")
    # info_log.info(f"\nSend HK:{bytes.hex(cmd_tc, ' ', 2)}")
    # cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get Response and check type ---
    response_bytes = tm.get_response(port, 66)
    response = tm.Response(response_bytes)

    if response.cmd_type != "HK_Request":
        tc_log.error(f"Incorrect response to HK CMD. Got {response.cmd_type}")
        tc_log.error(f"Response: {bytes.hex(response.raw_bytes, ' ', 2)}")

    if not verify:
        return  # TODO Might need to always return parsed.
    parsed = tm.parse_tm(response)

    ## --- Verification ---
    # None at this time

    return parsed

def clear_errors(port, verify=True):
    cmd = "01" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Clearing Errors")
    info_log.info(f"\nClearing Errors")
    port.write(cmd_tc)

    ack_bytes = tm.get_response(port, 3)
    ack = tm.Response(ack_bytes)
    parsed = tm.parse_tm(ack)
    if ack.cmd_type != "Clear_Errors":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
    return parsed

# def set_errors(port)

def power_control(port, pwr_stat, verify=True):
    ## --- Check input parameters before sending CMD ---
    # TODO Adjust back to 0x03 when heater is actually implemented
    if (pwr_stat < 0) or (pwr_stat > 0x03):
        tc_log.error(
            f"Power_Control command power_status out of limits. Rejected by EGSE {pwr_stat}"
        )
        return

    ## --- Send CMD ---
    cmd = "04" + f"{pwr_stat:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Power Control:{bytes.hex(cmd_tc, ' ', 2)}")
    info_log.info(f"\nSend Power Control:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Power_Control":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.PWR_STAT != pwr_stat:
        tc_log.error(
            f"Response does not match value. Got {parsed.Param0}, expected {pwr_stat}"
        )

    # TODO decide if to return?
    return

def heater_control(
    port,
    htr_sci_tog: bool,
    htr_detec_man: bool,
    htr_detec_auto: bool,
    htr_mech_man: bool,
    htr_mech_auto: bool,
    verify: bool = True,
):
    ## --- Check input parameters before sending CMD ---
    # None needed as all boolean inputs

    ## --- Send CMD ---
    param = (
        (htr_sci_tog << 4)
        + (htr_detec_man << 3)
        + (htr_detec_auto << 2)
        + (htr_mech_man << 1)
        + (htr_mech_auto)
    )
    cmd = "05" + f"{param:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Heater Control:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Heater_Control":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.HTR_STAT != param:
        tc_log.error(
            f"Response does not match value. Got {parsed.Param0}, expected {param}"
        )

def set_mech_sp(port, thrm_mech_off_sp, thrm_mech_on_sp, verify: bool = True):
    ## --- Check input parameters before sending CMD ---
    if (thrm_mech_off_sp < 0) or (thrm_mech_off_sp > 0xFFF):
        tc_log.error(
            f"Set_Mech_SP command thrm_mech_off_sp out of limits. Rejected by EGSE {thrm_mech_off_sp}"
        )
        return

    if (thrm_mech_on_sp < 0) or (thrm_mech_on_sp > 0xFFF):
        tc_log.error(
            f"Set_Mech_SP command thrm_mech_on_sp out of limits. Rejected by EGSE {thrm_mech_on_sp}"
        )
        return

    if thrm_mech_on_sp > thrm_mech_off_sp:
        tc_log.error(
            f"Set_Mech_SP command thrm_mech_on_sp, on_sp:{thrm_mech_on_sp} is greater than off_sp:{thrm_mech_off_sp}. Rejected by EGSE"
        )
        return

    ## --- Send CMD ---
    cmd = "06" + f"{thrm_mech_off_sp:04X}" + f"{thrm_mech_on_sp:04X}" + "00" * 2
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set MECH SP:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_Mech_SP":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return

    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.THRM_MECH_OFF_SP != thrm_mech_off_sp:
        tc_log.error(
            f"ACK mech_off_sp does not match command. Set: x{thrm_mech_off_sp}, "
            f"Got {parsed.THRM_MECH_OFF_SP}"
        )

    if parsed.THRM_MECH_ON_SP != thrm_mech_on_sp:
        tc_log.error(
            f"ACK mech_on_sp does not match command. Set: x{thrm_mech_on_sp}, "
            f"Got {parsed.THRM_MECH_ON_SP}"
        )

def set_detec_sp(port, thrm_detec_off_sp, thrm_detec_on_sp, verify: bool = True):
    ## --- Check input parameters before sending CMD ---
    if (thrm_detec_off_sp < 0) or (thrm_detec_off_sp > 0xFFF):
        tc_log.error(
            f"Set_Detec_SP command thrm_detec_off_sp out of limits. Rejected by EGSE {thrm_detec_off_sp}"
        )
        return

    if (thrm_detec_on_sp < 0) or (thrm_detec_on_sp > 0xFFF):
        tc_log.error(
            f"Set_Detec_SP command thrm_detec_on_sp out of limits. Rejected by EGSE {thrm_detec_on_sp}"
        )
        return

    if thrm_detec_on_sp > thrm_detec_off_sp:
        tc_log.error(
            f"Set_Detec_SP command thrm_detec_on_sp, on_sp:{thrm_detec_on_sp} is greater than off_sp:{thrm_detec_off_sp}. Rejected by EGSE"
        )
        return

    ## --- Send CMD ---
    cmd = "07" + f"{thrm_detec_off_sp:04X}" + f"{thrm_detec_on_sp:04X}" + "00" * 2
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set DETEC SP:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_Detec_SP":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return

    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.THRM_DETEC_OFF_SP != thrm_detec_off_sp:
        tc_log.error(
            f"ACK detec_off_sp does not match command. Set: x{thrm_detec_off_sp}, "
            f"Got {parsed.THRM_DETEC_OFF_SP}"
        )

    if parsed.THRM_DETEC_ON_SP != thrm_detec_on_sp:
        tc_log.error(
            f"ACK detec_on_sp does not match command. Set: x{thrm_detec_on_sp}, "
            f"Got {parsed.THRM_DETEC_ON_SP}"
        )

def set_mtr_param(port, peak_current,guard,recval,speed,mech_lim_rel, verify: bool = True):
    ## --- Check input parameters before sending CMD ---
    # TODO check strings are correct format using constants instead
    if (peak_current < 0) or (peak_current > 0xFF):
        # TODO limit the max current to ensure safe operations
        tc_log.error(f"Set_MTR_Param command current out of limits. Rejected by EGSE {peak_current}")
        error_log.error(f"Set_MTR_Param command current out of limits. Rejected by EGSE {peak_current}")
        return

    if (guard < 0) or (guard > 0xFF):
        # TODO limit the guard to ensure safe operations
        tc_log.error(f"Set_MTR_Param command guard out of limits. Rejected by EGSE {guard}")
        error_log.error(f"Set_MTR_Param command guard out of limits. Rejected by EGSE {guard}")
        return
    
    if (recval < 0) or (recval > 0xFF):
        # TODO limit the guard to ensure safe operations
        tc_log.error(f"Set_MTR_Param command recval out of limits. Rejected by EGSE {recval}")
        error_log.error(f"Set_MTR_Param command recval out of limits. Rejected by EGSE {recval}")
        return
    
    if (speed < 0) or (speed > 0x0F):
        # TODO limit the guard to ensure safe operations
        tc_log.error(f"Set_MTR_Param command speed out of limits. Rejected by EGSE {speed}"        )
        error_log.error(f"Set_MTR_Param command speed out of limits. Rejected by EGSE {speed}")
        return    

    if (mech_lim_rel < 0) or (mech_lim_rel > 0xFFFF):
        tc_log.error(f"Set_MTR_Param command pwm_duty out of limits. Rejected by EGSE {mech_lim_rel}"        )
        error_log.error(f"Set_MTR_Param command pwm_duty out of limits. Rejected by EGSE {mech_lim_rel}")
        return

    ## --- Send CMD ---
    cmd = "08" + f"{peak_current:02X}{guard:02X}{recval:02X}{speed:02X}{mech_lim_rel:04X}"
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set_MTR_Param:{bytes.hex(cmd_tc, ' ', 2)}")
    info_log.info(f"\nSend Set_MTR_Param:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## -- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_MTR_Param":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.MTR_CURRENT != peak_current:
        tc_log.error(
            f"ACK peak current not as commanded. Set: x{peak_current:02X}, "
            f"Got: x{parsed.MTR_CURRENT:02X}"
        )
    
    if parsed.MTR_GUARD != guard:
        tc_log.error(
            f"ACK peak guard not as commanded. Set: x{guard:02X}, "
            f"Got: x{parsed.MTR_GUARD:02X}"
        )

    if parsed.MTR_RECVAL != recval:
        tc_log.error(
            f"ACK peak recval not as commanded. Set: x{recval:02X}, "
            f"Got: x{parsed.MTR_RECVAL:02X}"
        )

    if parsed.MTR_SPEED != speed:
        tc_log.error(
            f"ACK peak speed not as commanded. Set: x{speed:01X}, "
            f"Got: x{parsed.MTR_SPEED:01X}"
        )

   
    if parsed.MECH_LIM_REL != mech_lim_rel:
        tc_log.error(
            f"ACK peak mech_lim_rel not as commanded. Set: x{mech_lim_rel:04X}, "
            f"Got: x{parsed.MECH_LIM_REL:04X}"
        )

def mtr_mov_pos(port, pos_steps, verify=True):
    ## --- Check input parameters before sending CMD ---
    if (pos_steps < 0) or (pos_steps > 0x3200):
        tc_log.error(
            f"Move Pos Steps command pos_steps out of limits. Rejected by EGSE {pos_steps}"
        )
        return
    # param = (0<<15) + (pos_steps <<14)
    ## --- Send CMD ---
    cmd = "09" + f"{pos_steps:04X}" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Move Pos Steps:{bytes.hex(cmd_tc, ' ', 2)}")
    info_log.info(f"\nSend Move Pos Steps:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)
    parsed = tm.parse_tm(ack)

    if ack.cmd_type != "MTR_Mov_Pos":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
        return "ERROR"

    if not verify:
        return

    return parsed

def mtr_mov_neg(port, neg_steps, verify=True):
    ## --- Check input parameters before sending CMD ---
    if (neg_steps < 0) or (neg_steps > 0x3200):
        tc_log.error(
            f"Move Neg Steps command pos_steps out of limits. Rejected by EGSE {neg_steps}"
        )
        return
   
    ## --- Send CMD ---
    cmd = "0A" + f"{neg_steps:04X}" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Move Neg Steps:{bytes.hex(cmd_tc, ' ', 2)}")
    info_log.info(f"\nSend Move Neg Steps:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)
    parsed = tm.parse_tm(ack)

    if ack.cmd_type != "MTR_Mov_Neg":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
        return "ERROR"

    if not verify:
        return

    return parsed

def mtr_homing(port, CAL: bool, FORWARD: bool, verify=True):
    # Todo review checks properly
    param = (CAL << 1) + (FORWARD)
    cmd = "0C" + f"{param:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send MTR_Homing:{bytes.hex(cmd_tc, ' ', 2)}")
    info_log.info(f"\nSend MTR_Homing:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)
    parsed = tm.parse_tm(ack)

    if ack.cmd_type != "MTR_Homing":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
        return "ERROR"

    if not verify:
        return

    return parsed

def mtr_halt(port, verify = True):
    cmd = "0B" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send MTR_Halt:{bytes.hex(cmd_tc, ' ', 2)}")
    info_log.info(f"Send MTR_Halt:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)
    time.sleep(5)

    ack_bytes = tm.get_response(port, 4)
    ack = tm.Response(ack_bytes)
    parsed = tm.parse_tm(ack)
    if not verify:
        return
    
    if ack.cmd_type != "Halt":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
    return parsed

def sci_offset(port, swir_offset, mwir_offset, verify: bool = True):
    ## --- Send CMD ---
    cmd = "0E" + f"0{swir_offset:03X}" + f"0{mwir_offset:03X}" + "00" * 2
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set Sci Offset:{bytes.hex(cmd_tc, ' ', 2)}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "SCI_Offset":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.SWIR_OFFSET != swir_offset:
        tc_log.error(
            f"ACK swir_offset does not match command. Set: x{swir_offset}, "
            f"Got {parsed.SWIR_OFFSET}"
        )
        
    if parsed.MWIR_OFFSET != mwir_offset:
        tc_log.error(
            f"ACK mwir_offset does not match command. Set: x{mwir_offset}, "
            f"Got {parsed.MWIR_OFFSET}"
        )

#TODO: Update sci_request command so that it uses parameters SCI_ADC_SAMP and SCI_ADC_SKIP
def sci_request(port, sci_adc_samp, sci_adc_skip, verify=True):
    ## --- Check input parameters before sending CMD ---
    if (sci_adc_samp < 0) or (sci_adc_samp > 0x0A):
        tc_log.error(
            f"SCI_Request command sci_adc_samp out of limits. Rejected by EGSE {sci_adc_samp}"
        )
        return
    
    if (sci_adc_skip < 0) or (sci_adc_skip > 0xFF):
        tc_log.error(
            f"SCI_Request command sci_adc_skip out of limits. Rejected by EGSE {sci_adc_skip}"
        )
        return
    
    ## --- Send CMD ---
    cmd = "0F" + f"0{sci_adc_samp:01X}" + f"{sci_adc_skip:02X}" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Requesting Science Reading")
    info_log.info(f"\nRequesting Sci with samp:{sci_adc_samp}, skip:{sci_adc_skip}")
    cmd_log.info(f"{bytes.hex(cmd_tc, ' ', 2)}\n")
    port.write(cmd_tc)
    
    ## --- Get Response and check type ---
    # Wait for Sci to be generated
    delay = (sci_adc_samp + sci_adc_skip) * 8 * 16 * 1e-6 + const.SCI_RESP_MARGIN
    time.sleep(delay)
    sci_bytes = tm.get_response(port, 29)
    sci = tm.Response(sci_bytes)
    if sci.cmd_type != "SCI_Request":
        tc_log.error(f"Incorrect response to SCI CMD. Got {sci.cmd_type}")
        tc_log.error(f"Response: {bytes.hex(sci.raw_bytes, ' ', 2)}")
    
    if not verify:
        return
    
    parsed = tm.parse_tm(sci)

    ## --- Verification ---
    # TODO
    return parsed
