import logging
from datetime import datetime
import time
import constants as const
import tm
from crc8_function import crc8Calculate

info_log = logging.getLogger("info_log")
"""
The verify used in the TC is only to verify the ACK response. Any HK checking or response checking
beyond that should be done at a higher level, such as in the main script or send_cmd.py.
"""

# TODO! Need to decide how to return errors and hadnle them at a higher level.
# TODO Add type hints to the functions and full docstrings for clarity.


def send_tc(port, cmd_bytes: bytes):
    # TODO: Would be nice to have a way to also include the short name of the command in the log.
    const.CMD_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
    const.CMD_LOG_FH.write(f" - {bytes.hex(cmd_bytes, ' ', 2)}\n")
    port.write(cmd_bytes)
    return


def verify_ack_hdr(parsed):
    if parsed.MOD_ID != const.EXP_MODEL_ID:
        info_log.error(f"ACK MOD_ID does not match expected. Got: {parsed.MOD_ID}, Expected: {const.EXP_MODEL_ID}")

    if parsed.UNUSED1 != 0:
        info_log.error(f"ACK UNUSED1 does not match expected. Got: {parsed.UNUSED1}, Expected: 0")

    # No need to verify CMD_ID as it is already used by the TM response case selection

    if parsed.ERROR_BYTE != 0:
        info_log.error(f"ACK ERROR_BYTE asserted. Got: {parsed.ERROR_BYTE}")
    return


def verify_blank_ack_params(parsed: tm.ACK, start_index: int = 1):
    """This function verifies that all unused parameters in the ACK resposne are set to 0. Saves
    having to check them all individually in each command. If the value is not 0, then a
    info_log.error is raised.

    Args:
        parsed (tm.ACK): The parsed ACK response object that already has the parameters decoded.
        start_index (int, optional): The number of the first blank parameter, this is used to
        generate the set of parameters that will be looped through. Defaults to 1.
    """

    # Create the list of parameters to check
    param_keys = [f"PARAM{i}" for i in range(start_index, 7)]

    # Loop through the param_keys of parsed.items() and check if they are all 0
    for key in param_keys:
        if hasattr(parsed, key):
            value = getattr(parsed, key)
            if value != 0:
                info_log.error(f"ACK {key} does not match expected. Got: {value}, Expected: 0")
        else:
            info_log.error(f"ACK {key} not found in parsed response.")
    return


def hk_request(port, verify=True):
    ## --- Check input parameters before sending CMD ---
    # No parameters for CMD

    ## --- Send CMD ---
    cmd = "00" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send HK:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get Response and check type ---
    response_bytes = tm.get_response(port, 66)
    response = tm.Response(response_bytes)

    if response.cmd_type != "HK_Request":
        info_log.error(f"Incorrect response to HK CMD. Got {response.cmd_type}")
        info_log.error(f"Response: {bytes.hex(response.raw_bytes, ' ', 2)}")

    parsed = tm.parse_tm(response)

    ## --- Verification ---
    # No verification performed here, but throughout scripts instead

    return parsed


def clear_errors(port, verify_ack=True):
    ## --- Check input parameters before sending CMD ---
    # No parameters for CMD

    ## --- Send CMD ---
    cmd = "02" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Clearing Errors:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get Response and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Clear_Errors":
        info_log.error(f"Incorrect ACK to Clear_Errors CMD. Got {ack.cmd_type}")
        return

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    # Clear errors, has no parameters but LAST_ERROR should be 0
    verify_ack_hdr(parsed)

    if parsed.ERROR_BYTE != 0:
        info_log.error(f"ACK LAST_ERROR still has errors flagged. Got: {parsed.ERRORS}.")

    verify_blank_ack_params(parsed, start_index=1)

    return


def set_errors(
    port,
    tmo: bool = False,
    ipa: bool = False,
    cd: bool = False,
    ab: bool = False,
    abs: bool = False,
    rel: bool = False,
    dse: bool = False,
    ig_b: bool = False,
    ig_o: bool = False,
    m_cd: bool = False,
    m_ab: bool = False,
    m_abs: bool = False,
    m_rel: bool = False,
    m_dse: bool = False,
    verify_ack: bool = True,
):
    param1 = (0 * 6 << 7) + (tmo << 1) + (ipa)
    param2 = (0 * 3 << 7) + (cd << 4) + (ab << 3) + (abs << 2) + (rel << 1) + (dse)
    param3 = (ig_b << 7) + (ig_o << 6) + (0 << 5) + (m_cd << 4) + (m_ab << 3) + (m_abs << 2) + (m_rel << 1) + (m_dse)
    cmd = "03" + f"{param1:02X}" + f"{param2:02X}" + f"{param3:02X}" + "00" * 3
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Setting Errors - {bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    #!No ACK
    try:
        response = tm.get_response(port, 9)
        if len(response) != 0:
            raise ValueError(f"Expected response length 0, got {len(response)}")
        else:
            info_log.info("Response length is 0 as expected.")

    except ValueError as e:
        info_log.error("Incorrect response to Set_Errors CMD")
        return


def power_control(port, pwr_stat, verify_ack=True):
    ## --- Check input parameters before sending CMD ---
    if (pwr_stat < 0) or (pwr_stat > 0x03):
        info_log.error(f"Power_Control command power_status out of limits. Rejected by EGSE {pwr_stat}")
        return

    ## --- Send CMD ---
    cmd = "04" + f"{pwr_stat:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Power Control:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Power_Control":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First parameter is the power status, so we can check it directly
    if parsed.PARAM1 != pwr_stat:
        info_log.error(f"Response does not match value. Got {parsed.PARAM1}, expected {pwr_stat}")

    verify_blank_ack_params(parsed, start_index=2)

    return


def heater_control(
    port,
    htr_sci_tog: bool = False,
    htr_detec_man: bool = False,
    htr_detec_auto: bool = False,
    htr_mech_man: bool = False,
    htr_mech_auto: bool = False,
    verify_ack: bool = True,
):
    ## --- Check input parameters before sending CMD ---
    # None needed as all boolean inputs

    ## --- Send CMD ---
    param = (htr_sci_tog << 4) + (htr_detec_man << 3) + (htr_detec_auto << 2) + (htr_mech_man << 1) + (htr_mech_auto)
    cmd = "05" + f"{param:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Heater Control:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Heater_Control":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First parameter is the heater status, so we can check it directly
    if parsed.PARAM1 != param:
        info_log.error(f"Response does not match value. Got {parsed.Param1}, expected {param}")

    verify_blank_ack_params(parsed, start_index=2)

    return


def set_mech_sp(port, thrm_mech_off_sp, thrm_mech_on_sp, verify_ack: bool = True):
    ## --- Check input parameters before sending CMD ---
    if (thrm_mech_off_sp < 0) or (thrm_mech_off_sp > 0xFFF):
        info_log.error(f"Set_Mech_SP command thrm_mech_off_sp out of limits. Rejected by EGSE {thrm_mech_off_sp}")
        return

    if (thrm_mech_on_sp < 0) or (thrm_mech_on_sp > 0xFFF):
        info_log.error(f"Set_Mech_SP command thrm_mech_on_sp out of limits. Rejected by EGSE {thrm_mech_on_sp}")
        return

    if thrm_mech_on_sp > thrm_mech_off_sp:
        info_log.error(
            f"Set_Mech_SP command thrm_mech_on_sp, on_sp:{thrm_mech_on_sp} is greater than off_sp:{thrm_mech_off_sp}. Rejected by EGSE"
        )
        return

    ## --- Send CMD ---
    cmd = "06" + f"{thrm_mech_off_sp:04X}" + f"{thrm_mech_on_sp:04X}" + "00" * 2
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Set MECH SP:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_Mech_SP":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First 2 parameters are the OFF SP
    value = (parsed.PARAM1 << 8) + (parsed.PARAM2)
    if value != thrm_mech_off_sp:
        info_log.error(f"ACK mech_off_sp does not match command. Set: x{thrm_mech_off_sp}, Got {value:04X}")

    # Next 2 parameters are the ON SP
    value = (parsed.PARAM3 << 8) + (parsed.PARAM4)
    if value != thrm_mech_on_sp:
        info_log.error(f"ACK mech_on_sp does not match command. Set: x{thrm_mech_on_sp}, Got {value:04X}")

    verify_blank_ack_params(parsed, start_index=5)

    return


def set_detec_sp(port, thrm_detec_off_sp, thrm_detec_on_sp, verify_ack: bool = True):
    ## --- Check input parameters before sending CMD ---
    if (thrm_detec_off_sp < 0) or (thrm_detec_off_sp > 0xFFF):
        info_log.error(f"Set_Detec_SP command thrm_detec_off_sp out of limits. Rejected by EGSE {thrm_detec_off_sp}")
        return

    if (thrm_detec_on_sp < 0) or (thrm_detec_on_sp > 0xFFF):
        info_log.error(f"Set_Detec_SP command thrm_detec_on_sp out of limits. Rejected by EGSE {thrm_detec_on_sp}")
        return

    if thrm_detec_on_sp > thrm_detec_off_sp:
        info_log.error(
            f"Set_Detec_SP command thrm_detec_on_sp, on_sp:{thrm_detec_on_sp} is greater than off_sp:{thrm_detec_off_sp}. Rejected by EGSE"
        )
        return

    ## --- Send CMD ---
    cmd = "07" + f"{thrm_detec_off_sp:04X}" + f"{thrm_detec_on_sp:04X}" + "00" * 2
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Set DETEC SP:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_Detec_SP":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First 2 parameters are the OFF SP
    value = (parsed.PARAM1 << 8) + (parsed.PARAM2)
    if value != thrm_detec_off_sp:
        info_log.error(f"ACK detec_off_sp does not match command. Set: x{thrm_detec_off_sp}, Got {value:04X}")

    # Next 2 parameters are the ON SP
    value = (parsed.PARAM3 << 8) + (parsed.PARAM4)
    if value != thrm_detec_on_sp:
        info_log.error(f"ACK detec_on_sp does not match command. Set: x{thrm_detec_on_sp}, Got {value:04X}")

    verify_blank_ack_params(parsed, start_index=5)

    return


def set_mtr_param(port, peak_current, guard, recval, speed, mech_lim_rel, verify_ack: bool = True):
    ## --- Check input parameters before sending CMD ---
    # TODO check strings are correct format using constants instead
    if (peak_current < 0) or (peak_current > 0xFF):
        # TODO limit the max current to ensure safe operations
        info_log.error(f"Set_MTR_Param command current out of limits. Rejected by EGSE {peak_current}")
        return

    if (guard < 0) or (guard > 0xFF):
        # TODO limit the guard to ensure safe operations
        info_log.error(f"Set_MTR_Param command guard out of limits. Rejected by EGSE {guard}")
        return

    if (recval < 0) or (recval > 0xFF):
        # TODO limit the guard to ensure safe operations
        info_log.error(f"Set_MTR_Param command recval out of limits. Rejected by EGSE {recval}")
        return

    if (speed < 0) or (speed > 0x0F):
        # TODO limit the guard to ensure safe operations
        info_log.error(f"Set_MTR_Param command speed out of limits. Rejected by EGSE {speed}")
        return

    if (mech_lim_rel < 0) or (mech_lim_rel > 0xFFFF):
        info_log.error(f"Set_MTR_Param command pwm_duty out of limits. Rejected by EGSE {mech_lim_rel}")
        return

    ## --- Send CMD ---
    cmd = "08" + f"{peak_current:02X}{guard:02X}{recval:02X}{speed:02X}{mech_lim_rel:04X}"
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Set_MTR_Param:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## -- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_MTR_Param":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    if parsed.PARAM1 != peak_current:
        info_log.error(f"ACK peak current not as commanded. Set: x{peak_current:02X}, Got: x{parsed.PARAM1:02X}")

    if parsed.PARAM2 != guard:
        info_log.error(f"ACK peak guard not as commanded. Set: x{guard:02X}, Got: x{parsed.PARAM2:02X}")

    if parsed.PARAM3 != recval:
        info_log.error(f"ACK peak recval not as commanded. Set: x{recval:02X}, Got: x{parsed.PARAM3:02X}")

    if parsed.PARAM4 != speed:
        info_log.error(f"ACK peak speed not as commanded. Set: x{speed:01X}, Got: x{parsed.PARAM4:01X}")

    value = (parsed.PARAM5 << 8) + (parsed.PARAM6)
    if value != mech_lim_rel:
        info_log.error(f"ACK peak mech_lim_rel not as commanded. Set: x{mech_lim_rel:04X}, Got: x{value:04X}")

    return


def mtr_mov_pos(port, pos_steps, verify_ack=True):
    ## --- Check input parameters before sending CMD ---
    if (pos_steps < 0) or (pos_steps > 0x3500):
        info_log.error(f"Move Pos Steps command pos_steps out of limits. Rejected by EGSE {pos_steps}")
        return

    ## --- Send CMD ---
    cmd = "09" + f"{pos_steps:04X}" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Move Pos Steps:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "MTR_Mov_Pos":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
        return "ERROR"

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First 2 parameters are the postive steps
    value = (parsed.PARAM1 << 8) + (parsed.PARAM2)
    if value != pos_steps:
        info_log.error(f"ACK pos_steps does not match command. Set: x{pos_steps:04X}, Got {value:04X}")

    verify_blank_ack_params(parsed, start_index=3)

    return


def mtr_mov_neg(port, neg_steps, verify_ack=True):
    ## --- Check input parameters before sending CMD ---
    if (neg_steps < 0) or (neg_steps > 0x3200):
        info_log.error(f"Move Neg Steps command pos_steps out of limits. Rejected by EGSE {neg_steps}")
        return

    ## --- Send CMD ---
    cmd = "0A" + f"{neg_steps:04X}" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Move Neg Steps:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "MTR_Mov_Neg":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
        return "ERROR"

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First 2 parameters are the negative steps
    value = (parsed.PARAM1 << 8) + (parsed.PARAM2)
    if value != neg_steps:
        info_log.error(f"ACK neg_steps does not match command. Set: x{neg_steps:04X}, Got {value:04X}")

    verify_blank_ack_params(parsed, start_index=3)

    return


def mtr_homing(port, CAL: bool, OUTER: bool, verify=True):
    ## --- Check input parameters before sending CMD ---
    # No parameters for CMD

    ## --- Send CMD ---
    param = (CAL << 1) + (OUTER)
    cmd = "0C" + f"{param:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send MTR_Homing:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get Response and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "MTR_Homing":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
        return "ERROR"

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First parameter is the homing status, so we can check it directly
    if parsed.PARAM1 != param:
        info_log.error(f"ACK homing status does not match command. Set: x{param:02X}, Got: x{parsed.PARAM1:02X}")

    verify_blank_ack_params(parsed, start_index=2)

    return parsed


def mtr_halt(port, verify=True):
    ## --- Check input parameters before sending CMD ---
    # No parameters for CMD

    ## --- Send CMD ---
    cmd = "0B" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send MTR_Halt:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get Response and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Halt":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    verify_blank_ack_params(parsed, start_index=1)

    return


def set_hk_samples(port, samp, verify_ack: bool = True):
    ## --- Check input parameters before sending CMD ---
    if (samp < 0) or (samp > 0x06):
        info_log.error(f"Set HK samples command samp parameter out of limits. Rejected by EGSE {samp}")
        return

    ## --- Send CMD ---
    cmd = "0D" + f"{samp:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Set HK Samples:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_HK_Samples":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First parameter is the power status, so we can check it directly
    if parsed.PARAM1 != samp:
        info_log.error(f"Response does not match value. Got {parsed.PARAM1}, expected {samp}")

    verify_blank_ack_params(parsed, start_index=2)


def sci_offset(port, swir_offset, mwir_offset, verify: bool = True):
    ## --- Check input parameters before sending CMD ---
    if (swir_offset < 0) or (swir_offset > 0xFFF):
        info_log.error(f"Set Sci Offset command swir_offset out of limits. Rejected by EGSE {swir_offset}")
        return

    if (mwir_offset < 0) or (mwir_offset > 0xFFF):
        info_log.error(f"Set Sci Offset command mwir_offset out of limits. Rejected by EGSE {mwir_offset}")
        return

    ## --- Send CMD ---
    cmd = "0E" + f"0{swir_offset:03X}" + f"0{mwir_offset:03X}" + "00" * 2
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Set Sci Offset:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "SCI_Offset":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First parameter is the swir_offset
    value = (parsed.PARAM1 << 8) + (parsed.PARAM2)
    if value != swir_offset:
        info_log.error(f"ACK swir_offset does not match command. Set: x{swir_offset}, Got {value:04X}")

    value = (parsed.PARAM3 << 8) + (parsed.PARAM4)
    if value != mwir_offset:
        info_log.error(f"ACK mwir_offset does not match command. Set: x{mwir_offset}, Got {value:04X}")

    verify_blank_ack_params(parsed, start_index=5)

    return


def set_hk_samples(port, samp, verify_ack: bool = True):
    ## --- Check input parameters before sending CMD ---
    if (samp < 0) or (samp > 0x06):
        info_log.error(f"Set HK samples command samp parameter out of limits. Rejected by EGSE {samp}")
        return

    ## --- Send CMD ---
    cmd = "0D" + f"{samp:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    info_log.info(f"Send Set HK Samples:{bytes.hex(cmd_tc, ' ', 2)}")
    send_tc(port, cmd_tc)

    ## --- Get ACK and check type ---
    ack_bytes = tm.get_response(port, 9)
    ack = tm.Response(ack_bytes)

    if ack.cmd_type != "Set_HK_Samples":
        info_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify_ack:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    verify_ack_hdr(parsed)

    # First parameter is the power status, so we can check it directly
    if parsed.PARAM1 != samp:
        info_log.error(f"Response does not match value. Got {parsed.PARAM1}, expected {samp}")

    verify_blank_ack_params(parsed, start_index=2)


# TODO: Update sci_request command so that it uses parameters SCI_ADC_SAMP and SCI_ADC_SKIP
def sci_request(port, sci_adc_samp, sci_adc_skip, verify_resp=True):
    ## --- Check input parameters before sending CMD ---
    if (sci_adc_samp < 0) or (sci_adc_samp > 0x0A):
        info_log.error(f"SCI_Request command sci_adc_samp out of limits. Rejected by EGSE {sci_adc_samp}")
        return

    if (sci_adc_skip < 0) or (sci_adc_skip > 0xFF):
        info_log.error(f"SCI_Request command sci_adc_skip out of limits. Rejected by EGSE {sci_adc_skip}")
        return

    ## --- Send CMD ---
    cmd = "0F" + f"0{sci_adc_samp:01X}" + f"{sci_adc_skip:02X}" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    info_log.info("Requesting Science Reading")
    send_tc(port, cmd_tc)

    ## --- Get Response and check type ---
    # Wait for Sci to be generated
    delay = (sci_adc_samp + sci_adc_skip) * 8 * 16 * 1e-6 + const.SCI_RESP_MARGIN
    time.sleep(delay)
    sci_bytes = tm.get_response(port, 29)
    sci = tm.Response(sci_bytes)

    if sci.cmd_type != "SCI_Request":
        info_log.error(f"Incorrect response to SCI CMD. Got {sci.cmd_type}")
        info_log.error(f"Response: {bytes.hex(sci.raw_bytes, ' ', 2)}")
        return

    if not verify_resp:
        return
    parsed = tm.parse_tm(sci)

    ## --- Verification ---
    # TODO
    return parsed
