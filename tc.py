import logging

from crc8Function import crc8Calculate
import tm

tc_log = logging.getLogger("tc_log")


def hk_request(port, verify=True):
    cmd = "00" + "00" * 6
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send HK:{bytes.hex(cmd_tc, ' ', 2)}")

    port.write(cmd_tc)

    if not verify:
        return

    # Check we get HK back
    response = tm.getResponse(port)
    parsed = tm.parse_tm(response)

    if response.cmd_type != "HK_Request":
        tc_log.error(f"Incorrect response to HK CMD. Got {response.cmd_type}")
        tc_log.error(f"Response: {bytes.hex(response.raw_bytes, ' ', 2)}")

    return parsed


def set_mtr_guard(port, RECIRC, GUARD, RECVAL, SPI_SEL, verify=True):
    # Todo review checks properly

    cmd = "0B" + f"{RECIRC:02X}{GUARD:04X}{RECVAL:02X}{SPI_SEL:04X}"
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set_MTR_Guard:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    if not verify:
        return

    # Check we get back ACK
    response = tm.getResponse(port)


def set_mtr_mon(port, ABS, REL, BACKOFF, verify=True):
    # Todo review checks properly

    cmd = "0C" + f"{ABS:04X}{REL:04X}{BACKOFF:04X}"
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set_MTR_MON:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)


def mtr_homing(port, FORWARD: bool, CAL: bool, HOME: bool, verify=True):
    # Todo review checks properly
    param = (FORWARD << 2) + (CAL << 1) + HOME
    cmd = "13" + f"{param:02X}" + "00" * 5
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send MTR_Homing:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)


def set_mtr_param(port, peak_current, pwm_rate, speed, pwm_duty, verify=True):
    # Todo check strings are correct format using constants instead
    if (peak_current < 0) or (peak_current > 0xFFFF):
        tc_log.error(
            f"Set_MTR_Param command current out of limits. Rejected {peak_current}"
        )
        return

    if (pwm_rate < 0) or (pwm_rate > 0xFFFF):
        tc_log.error(
            f"Set_MTR_Param command pwm rate out of limits. Rejected {pwm_rate}"
        )

    cmd = "0A" + f"{peak_current:04X}{pwm_rate:04X}{speed:02X}{pwm_duty:02X}"
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Set_MTR_Param:{bytes.hex(cmd_tc, ' ', 2)}")

    port.write(cmd_tc)

    #! TODO Check ACK here
    ack = tm.getResponse(port)
    parsed = tm.parse_tm(ack)
    if ack.cmd_type == "HK_Request":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    if not verify:
        return

    hk = hk_request(port, verify=True)

    # Ensure that all parameters are set as expected
    if hk.MTR_CURRENT != peak_current:
        tc_log.error(
            f"Response HK peak current not as commanded. Set: x{peak_current:04X}, "
            f"Got: x{hk.MTR_CURRENT:04X}"
        )

    if hk.MTR_PWM_RATE != pwm_rate:
        tc_log.error(
            f"Response HK pwm_rate not as commanded. Set: x{pwm_rate:04X}, "
            f"Got: x{hk.MTR_PWM_RATE:04X}"
        )

    if hk.MTR_SPEED != speed:
        tc_log.error(
            f"Response HK speed not as commanded. Set: x{speed:04X}, "
            f"Got: x{hk.MTR_SPEED:04X}"
        )

    if hk.MTR_PWM_DUTY != pwm_duty:
        tc_log.error(
            f"Response HK pwm_duty not as commanded. Set: x{pwm_duty:04X}, "
            f"Got: x{hk.MTR_PWM_DUTY:04X}"
        )


def power_control(port, pwr_stat, verify=True):
    if (pwr_stat < 0) or (pwr_stat > 0xFF):
        tc_log.error(
            f"Power_Control command power_status out of limits. Rejected {pwr_stat}"
        )
        return

    cmd = "04" + f"{pwr_stat:02X}" + "AA" + "00" * 4
    cmd_tc = crc8Calculate(cmd)
    tc_log.info(f"Send Power Control:{bytes.hex(cmd_tc, ' ', 2)}")
    port.write(cmd_tc)

    ack = tm.getResponse(port)
    parsed = tm.parse_tm(ack)
    if ack.cmd_type == "HK_Request":
        tc_log.error(f"Incorrect ACK to CMD. Got {ack.cmd_type}")

    return


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
