import logging

from crc8Function import crc8Calculate
import tm

tc_log = logging.getLogger("tc_log")

# TODO: Have a return pass/fail for each TC, so extra logic can be added to script


def hk_request(port, verify=True):
    ## --- Check input parameters before sending CMD ---
    # No parameters for CMD

    ## --- Send CMD ---
    cmd = "00" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send HK:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    ## --- Get Response and check type ---
    response = tm.getResponse(port)
    if response.cmd_type != "HK_Request":
        tc_log.error(f"Incorrect response to HK CMD. Got {response.cmd_type}")
        tc_log.error(f"Response: {bytes.hex(response.raw_bytes, ' ', 2)}")

    if not verify:
        return
    parsed = tm.parse_tm(response)

    ## --- Verification ---
    # None at this time

    return parsed


# def clear_errors(port)

# def set_errors(port)


def power_control(port, pwr_stat, verify=True):
    ## --- Check input parameters before sending CMD ---
    # TODO Adjust back to 0x03 when heater is actually implemented
    if (pwr_stat < 0) or (pwr_stat > 0xFF):
        tc_log.error(
            f"Power_Control command power_status out of limits. Rejected {pwr_stat}"
        )
        return

    ## --- Send CMD ---
    cmd = "04" + f"{pwr_stat:02X}" + "AA" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Power Control:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    ## --- Get ACK and check type ---
    ack = tm.getResponse(port)

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


# def heater_control(port)

# def set_mech_sp(port)

# def set_detec_sp(port)


def set_mtr_param(port, peak_current, pwm_rate, speed, pwm_duty, verify=True):
    ## --- Check input parameters before sending CMD ---
    # TODO check strings are correct format using constants instead
    if (peak_current < 0) or (peak_current > 0xFFFF):
        # TODO limit the max current to ensure safe operations
        tc_log.error(
            f"Set_MTR_Param command current out of limits. Rejected {peak_current}"
        )
        return

    if (pwm_rate < 0) or (pwm_rate > 0xFFFF):
        tc_log.error(
            f"Set_MTR_Param command pwm rate out of limits. Rejected {pwm_rate}"
        )

    ## --- Send CMD ---
    cmd = "0A" + f"{peak_current:04X}{pwm_rate:04X}{speed:02X}{pwm_duty:02X}"
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set_MTR_Param:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    ## -- Get ACK and check type ---
    ack = tm.getResponse(port)

    if ack.cmd_type != "Set_MTR_Param":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.MTR_CURRENT != peak_current:
        tc_log.error(
            f"ACK peak current not as commanded. Set: x{peak_current:04X}, "
            f"Got: x{parsed.MTR_CURRENT:04X}"
        )

    if parsed.MTR_PWM_RATE != pwm_rate:
        tc_log.error(
            f"ACK pwm_rate not as commanded. Set: x{pwm_rate:04X}, "
            f"Got: x{parsed.MTR_PWM_RATE:04X}"
        )

    if parsed.MTR_SPEED != speed:
        tc_log.error(
            f"ACK HK speed not as commanded. Set: x{speed:04X}, "
            f"Got: x{parsed.MTR_SPEED:04X}"
        )

    if parsed.MTR_PWM_DUTY != pwm_duty:
        tc_log.error(
            f"ACK HK pwm_duty not as commanded. Set: x{pwm_duty:04X}, "
            f"Got: x{parsed.MTR_PWM_DUTY:04X}"
        )


def set_mtr_guard(port, recirc, guard, recval, spisel, verify=True):
    ## --- Check input parameters before sending CMD ---
    # TODO check inputs
    # TODO check strings are correct format using constants instead

    ## --- Send CMD ---
    cmd = "0B" + f"{recirc:02X}{guard:04X}{recval:02X}{spisel:04X}"
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set_MTR_Guard:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    ## -- Get ACK and check type ---
    ack = tm.getResponse(port)

    if ack.cmd_type != "Set_MTR_Guard":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)

    ## --- Verification ---
    if parsed.MTR_RECIRC != recirc:
        tc_log.error(
            f"ACK recirc not as commanded. Set: x{recirc:04X}, "
            f"Got: x{parsed.RECIRC:04X}"
        )

    if parsed.MTR_GUARD != guard:
        tc_log.error(
            f"ACK guard not as commanded. Set: x{guard:04X}, "
            f"Got: x{parsed.GUARD:04X}"
        )

    if parsed.MTR_RECVAL != recval:
        tc_log.error(
            f"ACK recval not as commanded. Set: x{recval:04X}, "
            f"Got: x{parsed.MTR_RECVAL:04X}"
        )

    if parsed.MTR_SPISEL != spisel:
        tc_log.error(
            f"ACK spi_sel not as commanded. Set: x{spisel:04X}, "
            f"Got: x{parsed.MTR_SPISEL:04X}"
        )


def set_mtr_mon(port, ABS, REL, BACKOFF, verify=True):
    ## --- Check input parameters before sending CMD ---
    # TODO check strings are correct format using constants instead

    ## --- Send CMD ---
    cmd = "0C" + f"{ABS:04X}{REL:04X}{BACKOFF:04X}"
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set_MTR_MON:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    ## -- Get ACK and check type ---
    ack = tm.getResponse(port)

    if ack.cmd_type != "Set_MTR_Mon":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return
    parsed = tm.parse_tm(ack)


def mtr_homing(port, FORWARD: bool, CAL: bool, HOME: bool, verify=True):
    # Todo review checks properly
    param = (FORWARD << 2) + (CAL << 1) + HOME
    cmd = "13" + f"{param:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send MTR_Homing:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)


def mtr_mov_pos(port, pos_steps, verify=True):
    if (pos_steps < 0) or (pos_steps > 0xFFFF):
        tc_log.error(
            f"Move Pos Steps command pos_steps out of limits. Rejected {pos_steps}"
        )
        return

    cmd = "10" + f"{pos_steps:04X}" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Move Pos Steps:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    ack = tm.getResponse(port)
    parsed = tm.parse_tm(ack)
    if ack.cmd_type == "HK_Request":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
    return


def clear_errors(port, verify=True):
    cmd = "01" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Clearing Errors")
    port.write(cmd_tc)

    ack = tm.getResponse(port)
    parsed = tm.parse_tm(ack)
    if ack.cmd_type == "HK_Request":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
    return


def sci_request(port, verify=True):
    cmd = "1F" + "01" + "05" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Requesting Science Reading")
    port.write(cmd_tc)

    ack = tm.getResponse(port)
    parsed = tm.parse_tm(ack)
    if ack.cmd_type == "HK_Request":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")
    return
