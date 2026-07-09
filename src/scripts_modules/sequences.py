import logging
import sys
import time
from typing import Any
from utility_modules import tc
from utility_modules.send_cmd import cmd_repeat as repeat

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")


def _hk(port) -> Any:
    return tc.hk_request(port)


def _sci(port, sci_adc_samp, sci_adc_skip) -> Any:
    return tc.sci_request(port, sci_adc_samp, sci_adc_skip)


# ----
def power_up(port):
    try:
        repeat(port, tc.clear_errors)
        repeat(port, tc.power_control, 0x01)
        time.sleep(3)
        repeat(port, tc.set_mtr_param, 64, 0, 60, 8)
        resp = _hk(port)
        if (
            resp.PWR_STAT != 1
            or resp.MTR_CURRENT != 64
            or resp.MTR_GUARD_SELECT != 0
            or resp.MTR_CHOP != 60
            or resp.MTR_SPEED != 8
        ):
            raise ValueError(
                "OB Parameters not initialized correctly within HK:"
                + f"\n Power State : {resp.PWR_STAT}                ~ Expected : 1"
                + f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 64"
                + f"\n Guard Select : {resp.MTR_GUARD_SELECT}      ~ Expected : 0"
                + f"\n Chopper : {resp.MTR_CHOP}                  ~ Expected : 60"
                + f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 8"
            )
        else:
            event_log.info("Power Up and set params : Passed")
            return resp
    except ValueError as e:
        event_log.error(f"Power Up and set params failed : {e}")
        sys.exit(1)


def mech_heater_test(port):
    repeat(port, tc.hk_request)
    repeat(port, tc.heater_control, False, False, False, True, False)
    resp = _hk(port)
    init_mech_trp = resp.MECH_TRP
    init_motor_trp = resp.MOTOR_TRP
    if resp.THRM_STATUS_BYTE == 66:
        while resp.THRM_STATUS_BYTE == 66:
            time.sleep(1)
            resp = _hk(port)
            if (resp.MECH_TRP - init_mech_trp) >= 10 or (resp.MOTOR_TRP - init_motor_trp) >= 10:
                event_log.info("Mech and Motor Heater reached temp")
                repeat(port, tc.heater_control, False, False, False, False, False)
                pass
                exit()
    else:
        event_log.error(f"Mech Heater Status not On : {resp.THRM_STATUS_BYTE} ")
        exit()
    return


def parse_hk(port):
    resp = _hk(port)
    event_log.info(
        f" MOD_ID :{resp.MOD_ID}"
        + f"\n Unused1 : {resp.UNUSED1}"
        + f"\n CMD_ID :{resp.CMD_ID}"
        + f"\n CMD_CNT : {resp.CMD_CNT}"
        + f"\n ERROR_BYTE : {resp.ERROR_BYTE}"
        + f"\n UNUSED2 :{resp.UNUSED2}"
        + f"\n ERROR_MTR :{resp.ERROR_MTR}"
        + f"\n MTR_ERR_MSK : {resp.MTR_ERR_MSK_BYTE}"
        + f"\n MTR_FLAGS_BYTE : {resp.MTR_FLAGS_BYTE}"
        + f"\n MTR_ABS_STEPS : {resp.MTR_ABS_STEPS}"
        + f"\n MTR_REL_STEPS : {resp.MTR_REL_STEPS}"
        + f"\n UNUSED3 : {resp.UNUSED3}"
        + f"\n MTR_CURRENT : {resp.MTR_CURRENT}"
        + f"\n UNUSED4 : {resp.UNUSED4}"
        + f"\n MTR_GUARD_SELECT : {resp.MTR_GUARD_SELECT}"
        + f"\n MTR_CHOP : {resp.MTR_CHOP} "
        + f"\n UNUSED5 : {resp.UNUSED5}"
        + f"\n MTR_SPEED : {resp.MTR_SPEED}"
        + f"\n UNUSED6 : {resp.UNUSED6}"
        + f"\n PWR_STAT : {resp.PWR_STAT}"
        + f"\n THRM_STATUS_BYTE : {resp.THRM_STATUS_BYTE}"
        + f"\n THRM_MECH_OFF_SP : {resp.THRM_MECH_OFF_SP}"
        + f"\n THRM_MECH_ON_SP : {resp.THRM_MECH_ON_SP}"
        + f"\n THRM_DET_OFF_SP : {resp.THRM_DET_OFF_SP}"
        + f"\n THRM_DET_ON_SP : {resp.THRM_DET_ON_SP}"
        + f"\n SWIR_OFFSET : {resp.SWIR_OFFSET}"
        + f"\n MWIR_OFFSET : {resp.MWIR_OFFSET}"
        + f"\n HK_V_3V3 : {resp.HK_V_3V3}"
        + f"\n HK_V_1V5 : {resp.HK_V_1V5}"
        + f"\n DIGITAL_TRP : {resp.DIGITAL_TRP}"
        + f"\n DETEC_TRP : {resp.DETEC_TRP}"
        + f"\n MECH_TRP : {resp.MECH_TRP}"
        + f"\n MOTOR_TRP : {resp.MOTOR_TRP}"
        + f"\n HK_MECH_CUR : {resp.HK_MECH_CUR}"
        + f"\n UNUSED_ADC : {resp.UNUSED_ADC}"
        + f"\n HK_SAMPLES : {resp.HK_SAMPLES}"
        + f"\n UNUSED7 : {resp.UNUSED7}"
        + f"\n CRC8 : {resp.CRC8}"
    )
    event_log.info(
        "ERROR BYTE :"
        + f"\nIPI : {resp.ERRORS.IPI}"
        + f"\nIOS : {resp.ERRORS.IOS}"
        + f"\nICR : {resp.ERRORS.ICR}"
        + f"\nMOR : {resp.ERRORS.MOR}"
        + f"\nTMO : {resp.ERRORS.TMO}"
        + f"\nIPA : {resp.ERRORS.IPA}"
    )
    event_log.info(
        "MTR Flags :"
        + f"\n CAL : {resp.MTR_FLAGS.CAL}"
        + f"\n DIR : {resp.MTR_FLAGS.DIR}"
        + f"\n OUTER : {resp.MTR_FLAGS.OUTER}"
        + f"\n BASE : {resp.MTR_FLAGS.BASE}"
        + f"\n MOVING : {resp.MTR_FLAGS.MOVING}"
        + f"\n HOMING : {resp.MTR_FLAGS.HOMING}"
    )
    event_log.info(
        "MTR ERR Flags :"
        + f"\n CD : {resp.MTR_ERRORS.CD}"
        + f"\n AB : {resp.MTR_ERRORS.AB}"
        + f"\n ABS : {resp.MTR_ERRORS.ABS}"
        + f"\n DSE : {resp.MTR_ERRORS.DSE}"
    )
    # event_log.info(f" THRM STATUS :" + f"\n DET_Status : {resp.THRM_STATUS_BYTE.HDS & 0x03}")


def check_sci(port, sci_adc_samp, sci_adc_skip):
    resp = _sci(port, sci_adc_samp, sci_adc_skip)
    event_log.info(
        f"\tERROR_BYTE: {resp.ERROR_BYTE}"
        + f"  MTR_ABS_STEPS: {resp.MTR_ABS_STEPS}"
        + f"  THRM_STATUS_BYTE: {resp.THRM_STATUS_BYTE}"
        + f"  SWIR_OFFSET: {resp.SWIR_OFFSET}"
        + f"  MWIR_OFFSET: {resp.MWIR_OFFSET}"
        + f"  SCI_ADC_SAMPLES: {resp.SCI_ADC_SAMPLES}"
        + f"  SCI_ADC_SKIP: {resp.SCI_ADC_SKIP}"
        + f"  SW:H: {resp.SWIR_HIGH:04x}"
        + f"  SW:M: {resp.SWIR_MED:04x}"
        + f"  SW:L: {resp.SWIR_LOW:04x}"
        + f"  MW:H: {resp.MWIR_HIGH:04x}"
        + f"  MW:M: {resp.MWIR_MED:04x}"
        + f"  MW:L: {resp.MWIR_LOW:04x}"
        + f"  HT_SINK_TEMP: {resp.HT_SINK_TEMP:04x}"
        + f"  SWIR_TEMP: {resp.SWIR_TEMP:04x}"
    )
    return resp


def check_sci_vs_hk(port):
    repeat(port, tc.power_control, 0x03)
    resphk = _hk(port)
    respsci = _sci(port, 0x01, 0x01)
    repeat(port, tc.mtr_mov_pos, 0x140)
    resphk = _hk(port)
    if resphk.MTR_FLAGS.MOVING == 1:
        while resphk.MTR_FLAGS.MOVING == 1:
            time.sleep(1)
            resphk = _hk(port)
            event_log.info("Motor still moving ***********")
        event_log.info("Motor movement finished")
    resphk = _hk(port)
    if resphk.MTR_ABS_STEPS != respsci.MTR_ABS_STEPS:
        event_log.error(
            "Motor Steps in HK and in SCI packets do not match : "
            + f"\n HK : {resphk.MTR_ABS_STEPS}"
            + f"\n SCI : {respsci.MTR_ABS_STEPS}"
        )
    if abs(resphk.MTR_ABS_STEPS - respsci.MTR_ABS_STEPS) != 0:
        event_log.error(
            "Motor Steps Do not match expected : "
            + f"\n ABS : {abs(resphk.MTR_ABS_STEPS - respsci.MTR_ABS_STEPS)} , Expected : 0"
        )
        sys.exit(1)
    return


def hk_approx_cal(port):
    """Request a HK packet and provide an approximate calibration of all analogue parameters."""
    resp = _hk(port)
    event_log.info(
        f"3V3: {resp.HK_V_3V3 >> 4}"
        + f"    1V5: {resp.HK_V_1V5 >> 4}"
        + f"    DigT: {resp.DIGITAL_TRP >> 4}"
        + f"      DetT: {resp.DETEC_TRP >> 4}"
        + f"      MecT: {resp.MECH_TRP >> 4}"
        + f"      MotT: {resp.MOTOR_TRP >> 4}"
        + f"      Mec_Cur: {resp.HK_MECH_CUR >> 4}"
    )
    event_log.info(
        f"3V3: {resp.HK_V_3V3 * 2 / 1000 / 2**4:.2f}V"
        + f"   1V5: {resp.HK_V_1V5 / 1000 / 2**4:.2f}V"
        + f"   DigT: {resp.DIGITAL_TRP / 2**4 / (4.096 - (resp.DIGITAL_TRP / 1000 / 2**4)) / 1000:.4f}K"
        + f"   DetT: {resp.DETEC_TRP / 2**4 / (4.096 - (resp.DETEC_TRP / 1000 / 2**4)) / 1000:.4f}K"
        + f"   MecT: {resp.MECH_TRP / 2**4 / (4.096 - (resp.MECH_TRP / 1000 / 2**4)) / 1000:.4f}K"
        + f"   MotT: {resp.MOTOR_TRP / 2**4 / (4.096 - (resp.MOTOR_TRP / 1000 / 2**4)) / 1000:.4f}K"
        + f"   Mec_Cur: {resp.HK_MECH_CUR / 2**4 * 0.12 / (0.2 * 10):.2f}mA"
        + "\n"
    )
    return resp


def increasing_torque_test(port):
    """Perform a motor torque test by incrementally increasing the motor current until the motor moves."""
    power_up(port)
    initial_current = 0x38
    max_current = 0x70
    step = 0x08
    current = initial_current
    i = 1
    while current <= max_current:
        event_log.info(f"Testing motor movement at current: {hex(current)}, Test iteration: {i}")
        event_log.info("Press 'Enter' to send the command to move the motor...")
        # TODO keyboard.wait('return')
        repeat(port, tc.set_mtr_param, 64, 0, 60, 8)
        repeat(port, tc.mtr_mov_pos, 0x0A0)
        time.sleep(5)  # Wait for the command to take effect
        repeat(port, tc.mtr_halt)
        event_log.info("Motor halt command sent. - Reset the jig and press return to continue to next step.")
        # TODO keyboard.wait('return')

        current += step
        i += 1
    return


def torque_test(port):
    """Perform a motor torque test by incrementally increasing the motor current until the motor moves."""
    power_up(port)
    current = 0x40
    i = 1
    while True:
        event_log.info(f"Testing motor movement at current: {hex(current)}, Test iteration: {i}")
        event_log.info("Press 'Enter' to send the command to move the motor...")
        # TODO replace with input keyboard.wait('return')
        repeat(port, tc.set_mtr_param, 64, 0, 60, 8)
        repeat(port, tc.mtr_mov_pos, 0x0A0)
        time.sleep(5)  # Wait for the command to take effect
        repeat(port, tc.mtr_halt)
        event_log.info("Motor halt command sent. - Reset the jig and press return to continue to next step.")
        i += 1
    return
