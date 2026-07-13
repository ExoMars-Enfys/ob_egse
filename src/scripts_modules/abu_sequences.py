import logging
import time
from typing import Any

from core_modules import config
from scripts_modules import sequences as sq
from utility_modules import tc
from utility_modules.send_cmd import cmd_repeat as repeat

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")


def _hk(port) -> Any:
    return tc.hk_request(port)


def _sci(port, sci_adc_samp, sci_adc_skip) -> Any:
    return tc.sci_request(port, sci_adc_samp, sci_adc_skip)


def _check_sci(port, sci_adc_samp, sci_adc_skip) -> Any:
    return sq.check_sci(port, sci_adc_samp, sci_adc_skip)


# ----
def read_hk(port, display_contents=True):
    """
    This function requests a HK and generates a decoded log of all the HK parameters.
    """
    event_log.info("Running ABU read HK")
    resp = _hk(port)
    if display_contents:
        event_log.info(
            f" MOD_ID :{resp.MOD_ID}"
            + f"\n Unused1 : {resp.UNUSED1}"
            + f"\n CMD_ID :{resp.CMD_ID}"
            + f"\n CMD_CNT : {resp.CMD_CNT}"
            + f"\n ERROR_BYTE : {resp.ERROR_BYTE}"
            + f"\n UNUSED2 :{resp.UNUSED2}"
            + f"\n ERROR_MTR :{resp.ERROR_MTR}"
            + f"\n MTR_ERR_MSK_BYTE : {resp.MTR_ERR_MSK_BYTE}"
            + f"\n MTR_FLAGS_BYTE :{resp.MTR_FLAGS_BYTE}"
            + f"\n MTR_ABS_STEPS : {resp.MTR_ABS_STEPS}"
            + f"\n MTR_REL_STEPS : {resp.MTR_REL_STEPS}"
            + f"\n MTR_CURRENT :{resp.MTR_CURRENT}"
            + f"\n MTR_GUARD_SELECT : {resp.MTR_GUARD_SELECT}"
            + f"\n MTR_CHOP : {resp.MTR_CHOP}"
            + f"\n UNUSED3 : {resp.UNUSED3}"
            + f"\n MTR_SPEED :{resp.MTR_SPEED}"
            + f"\n UNUSED4 : {resp.UNUSED4}"
            + f"\n PWR_STAT : {resp.PWR_STAT}"
            + f"\n THRM_STATUS_BYTE :{resp.THRM_STATUS_BYTE}"
            + f"\n THRM_MECH_OFF_SP : {resp.THRM_MECH_OFF_SP}"
            + f"\n THRM_MECH_ON_SP : {resp.THRM_MECH_ON_SP}"
            + f"\n THRM_DET_OFF_SP :{resp.THRM_DET_OFF_SP}"
            + f"\n THRM_DET_ON_SP : {resp.THRM_DET_ON_SP}"
            + f"\n SWIR_OFFSET : {resp.SWIR_OFFSET}"
            + f"\n MWIR_OFFSET : {resp.MWIR_OFFSET}"
            + f"\n HK_V_3V3 : {resp.HK_V_3V3}"
            + f"\n HK_V_1V5 :{resp.HK_V_1V5}"
            + f"\n DIGITAL_TRP : {resp.DIGITAL_TRP}"
            + f"\n DETEC_TRP :{resp.DETEC_TRP}"
            + f"\n MECH_TRP : {resp.MECH_TRP}"
            + f"\n MOTOR_TRP : {resp.MOTOR_TRP}"
            + f"\n HK_MECH_CUR :{resp.HK_MECH_CUR}"
            + f"\n UNUSED_ADC : {resp.UNUSED_ADC}"
            + f"\n HK_SAMPLES : {resp.HK_SAMPLES}"
            + f"\n UNUSED7 :{resp.UNUSED7}"
            + f"\n CRC8 : {resp.CRC8}"
        )
        event_log.info(
            "\n\n ERROR BYTE :"
            + f"\nIPI : {resp.ERRORS.IPI}"
            + f"\nIOS : {resp.ERRORS.IOS}"
            + f"\nICR : {resp.ERRORS.ICR}"
            + f"\nMOR : {resp.ERRORS.MOR}"
            + f"\nTMO : {resp.ERRORS.TMO}"
            + f"\nIPA : {resp.ERRORS.IPA}"
        )
        event_log.info(
            f"\n\n MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}"
            + f"\n CAL : {resp.MTR_FLAGS.CAL}"
            + f"\n DIR : {resp.MTR_FLAGS.DIR}"
            + f"\n OUTER : {resp.MTR_FLAGS.OUTER}"
            + f"\n BASE : {resp.MTR_FLAGS.BASE}"
            + f"\n MOVING : {resp.MTR_FLAGS.MOVING}"
            + f"\n HOMING : {resp.MTR_FLAGS.HOMING}"
        )
        event_log.info(
            f"Unused : {resp.MTR_ERRORS.UNUSED}"
            + f"\n CD : {resp.MTR_ERRORS.CD}"
            + f"\n AB : {resp.MTR_ERRORS.AB}"
            + f"\n ABS : {resp.MTR_ERRORS.ABS}"
            + f"\n DSE : {resp.MTR_ERRORS.DSE}"
        )


def cal_motor_to_base(port):
    """
    This function powers the Mechanism board (if it isn't already).
    Sets the default motor parameters
    Then commands the motor to HOME to BASE with CAL applied.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu cal_motor_to_base")
    # TODO: Update all to "send_cmd"
    # Check mechanism powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x01)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = _hk(port)

    # Set motor parameters
    repeat(port, tc.set_mtr_param, 64, 0, 60, 8)
    resp = _hk(port)
    if resp.MTR_CURRENT != 64 or resp.MTR_GUARD_SELECT != 0 or resp.MTR_CHOP != 60 or resp.MTR_SPEED != 8:
        event_log.error(
            "OB Parameters not initialized correctly:"
            + f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 64"
            + f"\n Guard Select : {resp.MTR_GUARD_SELECT}      ~ Expected : 0"
            + f"\n Chopper : {resp.MTR_CHOP}                  ~ Expected : 60"
            + f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 8"
        )

    # Cal to BASE
    repeat(port, tc.mtr_homing, True, False)
    hk_tm = _hk(port)

    # Check to see if at the Base
    if not hk_tm.MTR_FLAGS.BASE:
        event_log.info("Moving to the BASE, waiting for switch to be pressed.")
        while hk_tm.MTR_FLAGS.MOVING:
            time.sleep(1)
            hk_tm = _hk(port)
            event_log.info(
                f"Motor MOVING: Absolute Steps : {hk_tm.MTR_ABS_STEPS:04d}, Relative Steps: {hk_tm.MTR_REL_STEPS:04d}"
            )
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, Base Flag Asserted")

    # Check motor status now its stopped.
    resp = _hk(port)
    if resp.MTR_FLAGS.CAL != 1:
        event_log.error(f" Calibration Flag not Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0:
        event_log.error(f" Calibration Dir not to BASE : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 0:
        event_log.error(f"OUTER Switch Flag raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 1:
        event_log.error(f"BASE Switch Flag is not asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")

    if resp.MTR_ABS_STEPS != 8960:
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
    if resp.MTR_REL_STEPS == 0:
        event_log.error(f"Motor Steps Do not match expected REL : {resp.MTR_REL_STEPS} , Expected : 0")

    event_log.info(f"Motor relative steps moved: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def home_to_outer(port):
    """
    This function powers the Mechanism board (if it isn't already).
    Then commands the motor to HOME to OUTER.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu home_to_outer")
    # TODO: Update all to "send_cmd"
    # Check mechanism powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x01)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = _hk(port)

    # Home to Outer with no Cal
    repeat(port, tc.mtr_homing, False, True)
    hk_tm = _hk(port)

    # Check to see if at the Outer
    if not hk_tm.MTR_FLAGS.OUTER:
        event_log.info("Moving to outer, waiting for switch to be pressed.")
        while hk_tm.MTR_FLAGS.MOVING:
            time.sleep(1)
            hk_tm = _hk(port)
            event_log.info(
                f"Motor MOVING: Absolute Steps : {hk_tm.MTR_ABS_STEPS:04d}, Relative Steps: {hk_tm.MTR_REL_STEPS:04d}"
            )
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, Outer Flag Asserted")

    # Check motor status now its stopped.
    resp = _hk(port)
    if resp.MTR_FLAGS.CAL != 0:
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 1:
        event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 1:
        event_log.error(f"OUTER Switch Flag not asserted : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 0:
        event_log.error(f"Base Switch Flag is asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")

    if resp.MTR_REL_STEPS == 0:
        event_log.error("Motor Steps Do not match expected : " + f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")

    event_log.info(f"Motor relative steps moved: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def home_to_base(port):
    """
    Then commands the motor to HOME to BASE.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu home_to_base")
    # TODO: Update all to "send_cmd"

    # Check mechanism powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x01)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = _hk(port)

    # Home to base
    repeat(port, tc.mtr_homing, False, False)
    hk_tm = _hk(port)

    # Check to see if at the Base
    if not hk_tm.MTR_FLAGS.BASE:
        event_log.info("Moving to the base, waiting for switch to be pressed.")
        while hk_tm.MTR_FLAGS.MOVING:
            time.sleep(1)
            hk_tm = _hk(port)
            event_log.error(
                f"MTR Flags : \nUnused : {hk_tm.MTR_FLAGS.UNUSED1}"
                + f"\n CAL : {hk_tm.MTR_FLAGS.CAL}"
                + f"\n UNUSED2 : {hk_tm.MTR_FLAGS.UNUSED2}"
                + f"\n DIR : {hk_tm.MTR_FLAGS.DIR}"
                + f"\n OUTER : {hk_tm.MTR_FLAGS.OUTER}"
                + f"\n BASE : {hk_tm.MTR_FLAGS.BASE}"
                + f"\n MOVING : {hk_tm.MTR_FLAGS.MOVING}"
                + f"\n HOMING : {hk_tm.MTR_FLAGS.HOMING}"
            )
        event_log.info("Motor movement finished")
    else:
        event_log.error("Motor Did not Move, Base Flag Asserted")

    # Check motor status now its stopped.
    resp = _hk(port)
    if resp.MTR_FLAGS.CAL != 0:
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0:
        event_log.error(f" Calibration Dir not to Base : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 0:
        event_log.error(f"OUTER Switch Flag raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 1:
        event_log.error(f"Base Switch Flag not raised : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMING}")

    if resp.MTR_REL_STEPS == 0:
        event_log.error("Motor Steps Do not match expected : " + f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")

    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def mv_pos_steps(port, pos_steps):
    """
    Script that moves the mechanism a certain number of steps positive (towards the base).
    Automatically checks that we are not already at the base.
    """
    event_log.info("Running ABU move positive steps")

    # First check that there we are are not already at the base.
    hk = _hk(port)

    if hk.MTR_FLAGS.BASE:
        event_log.error("Request to move positive steps but already at the base, skipping movement")
        return

    # Then move the desired number of steps
    repeat(port, tc.mtr_mov_pos, pos_steps)

    # Request a HK and wait until no longer moving
    hk = _hk(port)
    while hk.MTR_FLAGS.MOVING:
        hk = _hk(port)

    if hk.ERROR_MTR != 0:
        event_log.error(
            "***MOTOR ERROR*** got the following: "
            + f"\n CD : {hk.MTR_ERRORS.CD}"
            + f"\n AB : {hk.MTR_ERRORS.AB}"
            + f"\n ABS : {hk.MTR_ERRORS.ABS}"
            + f"\n DSE : {hk.MTR_ERRORS.DSE}"
        )

    # Then print a summary of the motor movement
    # event_log.info(f"HK After Motor Movement Complete:" +
    #                f"\t Error Byte: {hk.ERROR_BYTE}" +
    #                f"\t Error MTR: {hk.ERROR_MTR}" +
    #                f"\t MTR_ABS_STEPS: {hk.MTR_ABS_STEPS}" +
    #                f"\t MTR_REL_STEPS: {hk.MTR_REL_STEPS}" +
    #                f"\t MTR_FLAGS: {hk.MTR_FLAGS_BYTE}"
    #                )

    return


def mv_neg_steps(port, pos_steps):
    """
    Script that moves the mechanism a certain number of steps negative (towards the outer).
    Automatically checks that we are not already at the outer.
    """
    event_log.info("Running ABU move negative steps")

    # First check that we are not already at the outer.
    hk = _hk(port)

    if hk.MTR_FLAGS.OUTER:
        event_log.error("Request to move negative steps but already at the outer, skipping movement")
        return

    # Then move the desired number of steps
    repeat(port, tc.mtr_mov_neg, pos_steps)

    # Request a HK and wait until no longer moving
    hk = _hk(port)
    while hk.MTR_FLAGS.MOVING:
        hk = _hk(port)

    if hk.ERROR_MTR != 0:
        event_log.error(
            "***MOTOR ERROR*** got the following: "
            + f"\n CD : {hk.MTR_ERRORS.CD}"
            + f"\n AB : {hk.MTR_ERRORS.AB}"
            + f"\n ABS : {hk.MTR_ERRORS.ABS}"
            + f"\n DSE : {hk.MTR_ERRORS.DSE}"
        )


def set_offset_and_check_sci(port, swir_offset, mwir_offset, sci_adc_samp=4, sci_adc_skip=20):
    """
    Function that will power the detector board if it isn't already.
    Apply the offsets, set within the variables.
    Automatically request a science packet and ensure that the packet contents matches those set.
    """
    event_log.info("Running abu set_offset_and_check_sci")

    # Check detector powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x02)

    # Dark measurement to determine offset to be applied
    # Set SWIR and MWIR offset
    repeat(port, tc.sci_offset, swir_offset, mwir_offset)
    hk = _hk(port)
    if hk.SWIR_OFFSET != swir_offset:
        event_log.error(f"SWIR offset not updated in HK. Got {hk.SWIR_OFFSET}")
    if hk.MWIR_OFFSET != mwir_offset:
        event_log.error(f"MWIR offset not updated in HK. Got {hk.MWIR_OFFSET}")

    # Take SCI reading and check.
    sci = _check_sci(port, sci_adc_samp, sci_adc_skip)
    if sci.SWIR_OFFSET != swir_offset:
        event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}")
    if sci.MWIR_OFFSET != mwir_offset:
        event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}")


def mwir_binary_chop(port, swir_fixed=2048, sci_adc_samp=4, sci_adc_skip=2):
    """
    This fixes the SWIR DAC offset as per the functional call.
    It then itterates throgh the MWIR DAC offsets doing a binary search.
    The function aims for the science readings for the MWIR to be between the values set within the
    constants file.
    """
    event_log.info("Running abu mwir_binary_chop")

    # Check detector powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x02)

    mwir_value = 0x0  # Seed value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        mwir_delta = 0x1 << (i - 1)
        event_log.info(f"Setting the MWIR Value to: {mwir_value + mwir_delta}")
        repeat(port, tc.sci_offset, swir_fixed, mwir_value + mwir_delta)
        sci = _check_sci(port, sci_adc_samp, sci_adc_skip)
        if sci.MWIR_OFFSET != (mwir_value + mwir_delta):
            event_log.error(
                f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {mwir_value + mwir_delta}"
            )

        event_log.info(f"Got the following MWIR High Reading: {sci.MWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.MWIR_HIGH >= config.MWIR_DAC_MIN_TH:
            mwir_value = mwir_value + mwir_delta

        # Check if we are within the range (we are done) otherwise loop
        if config.MWIR_DAC_MIN_TH <= sci.MWIR_HIGH <= config.MWIR_DAC_MAX_TH:
            event_log.info("MWIR offset in threshold finished!")
            event_log.info(f"Final MWIR value: {mwir_value}")
            return mwir_value

    event_log.error(f"No solution found. Last MWIR Offset set to: {sci.MWIR_OFFSET}")
    return sci.MWIR_OFFSET


def swir_binary_chop(port, mwir_fixed=2048, sci_adc_samp=4, sci_adc_skip=2):
    """
    This sets the MWIR DAC offset as per the functional call.
    It then itterates throgh the SWIR DAC offsets doing a binary search.
    The function aims for the science readings for the SWIR to be between the values set within the
    constants file.
    """
    event_log.info("Running abu swir_binary_chop")

    # Check detector powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x02)

    swir_value = 0x0  # Seed Value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        swir_delta = 0x1 << (i - 1)
        event_log.info(f"Setting the SWIR value to: {swir_value + swir_delta}")
        repeat(port, tc.sci_offset, swir_value + swir_delta, mwir_fixed)
        sci = _check_sci(port, sci_adc_samp, sci_adc_skip)
        if sci.SWIR_OFFSET != (swir_value + swir_delta):
            event_log.error(
                f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}, Expected: {swir_value + swir_delta}"
            )

        event_log.info(f"Got the following SWIR High Reading: {sci.SWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.SWIR_HIGH > config.SWIR_DAC_MIN_TH:
            swir_value = swir_value + swir_delta

        # Check if we are within the range (we are done) otherwise loop
        if config.SWIR_DAC_MIN_TH <= sci.SWIR_HIGH <= config.SWIR_DAC_MAX_TH:
            event_log.info("SWIR offset in threshold finished!")
            event_log.info(f"Final SWIR value: {swir_value}")
            return swir_value

    event_log.error(f"No solution found. Last MWIR Offset set to: {sci.SWIR_OFFSET}")
    return sci.SWIR_OFFSET


def move_and_measure(port, pos_steps, sci_adc_samp=4, sci_adc_skip=20):
    """
    Moves the specified number of steps forward and then takes a measurement. 0 steps can be entered
    and the sequence will just measure the same point once again.

    This sequence should be executed once the motor has been HOMING and the offsets applied.

    The motor moves from the Outer to Base using (positive steps)
    """
    event_log.info("Running abu move_and_measure")

    if pos_steps > 0:
        mv_pos_steps(port, pos_steps)
    elif pos_steps < 0:
        mv_neg_steps(port, abs(pos_steps))
    else:
        event_log.info("No need to move any steps, proceeding to measurement")
    # Request a Science Mesaurement and log to the screen.
    sci = _sci(port, sci_adc_samp, sci_adc_skip)
    hk_tm = _hk(port)
    event_log.info(
        f"ABS_STEPS: {sci.MTR_ABS_STEPS:04d}" + f"   HK_ABS_STEPS: {hk_tm.MTR_ABS_STEPS:04d}"
        f"   SWIR_OFFSET: {sci.SWIR_OFFSET:04d}"
        + f"   MWIR_OFFSET: {sci.MWIR_OFFSET:04d}"
        + f"\t\t SW_L: {sci.SWIR_LOW:04d}"
        + f"   SW_M: {sci.SWIR_MED:04d}"
        + f"   SW_H: {sci.SWIR_HIGH:04d}"
        + f"\t MW_L: {sci.MWIR_LOW:04d}"
        + f"   MW_M: {sci.MWIR_MED:04d}"
        + f"   MW_HH: {sci.MWIR_HIGH:04d}"
        + f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}"
        + f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}"
    )
    return


def abu_measurement_scan(port, step_spacing=50, sci_adc_samp=4, sci_adc_skip=20):
    """
    Performs the basic Enfys science measurement
    Homes and Calibrates to Base
    Goes to the Outer
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    Halts once Base Stop is reached
    """
    event_log.info("Running ABU Measurement Scan")
    read_hk(port, False)

    # Cal to Base
    cal_motor_to_base(port)

    # Home to Outer
    home_to_outer(port)

    # Measurement sequence
    # TODO! Emulate Dark Offset and Edge finding (with SWIR and broad lamp)
    event_log.info("Starting Science Measurements")
    move_and_measure(port, 0, sci_adc_samp, sci_adc_skip)
    for i in range(0, 8600, step_spacing):
        move_and_measure(port, step_spacing, sci_adc_samp, sci_adc_skip)

    event_log.info("Science Measurements Completed!!")


def sweep_offset_mwir(port, step=16, sci_adc_samp=0, sci_adc_skip=100):
    """
    This function sweeps through the mwir DAC from 0 to 4095 using the increment specified.
    A science reading is the acquired at each DAC offset.
    """
    event_log.info("Running ABU MWIR Sweep")
    for offset in range(0, 4096, step):
        set_offset_and_check_sci(port, 100, offset, sci_adc_samp, sci_adc_skip)


def sweep_offset_swir(port, step=16, sci_adc_samp=0, sci_adc_skip=100):
    """
    This function sweeps through the swir DAC from 0 to 4095 using the increment specified.
    A science reading is the acquired at each DAC offset.
    """
    event_log.info("Running ABU SWIR Sweep")
    for offset in range(0, 4096, step):
        set_offset_and_check_sci(port, offset, 100, sci_adc_samp, sci_adc_skip)


def first_power_on(port):
    """
    Very simple sequence that powers on both sub-systems.
    Then Calibrates the mech to BASE
    Then Moves the mech to OUTER
    """
    event_log.info("Running ABU First power on, cal to Base, home to outer")

    # Power up motor and Detector
    repeat(port, tc.power_control, 0x3)

    cal_motor_to_base(port)
    home_to_outer(port)
