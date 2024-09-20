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

    return parsed


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
