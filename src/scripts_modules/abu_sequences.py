import logging
import time
from typing import Any
from core_modules import config
from core_modules import constants as const
from utility_modules import tc
from utility_modules.send_cmd import cmd_repeat as repeat
from scripts_modules import sequences as sq
import serial
import pathlib
from egse_dump_decoder import EGSEDumpDecoder
import scripts_modules.measurement_table as mt

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


def set_motor_parameters(port):
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


def wait_movement_complete(port, num_steps_expected=8960):
    hk = _hk(port)
    while hk.MTR_FLAGS.MOVING:
        event_log.info(
            "Motor MOVING: Absolute Steps : " + f"{hk.MTR_ABS_STEPS:04d}, Relative Steps: {hk.MTR_REL_STEPS:04d}"
        )
        time.sleep(0.1 if num_steps_expected < 640 else 1)
        hk = _hk(port)
    if hk.ERROR_MTR != 0:
        event_log.error(
            "***MOTOR ERROR*** got the following: "
            + f"\n CD : {hk.MTR_ERRORS.CD}"
            + f"\n AB : {hk.MTR_ERRORS.AB}"
            + f"\n ABS : {hk.MTR_ERRORS.ABS}"
            + f"\n DSE : {hk.MTR_ERRORS.DSE}"
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
    set_motor_parameters(port)

    # Cal to BASE
    repeat(port, tc.mtr_homing, True, False)

    # Check to see if at the Base
    resp = _hk(port)
    if not resp.MTR_FLAGS.BASE:
        event_log.info("Moving to the BASE, waiting for switch to be pressed.")
        wait_movement_complete(port)
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

        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 9960")
    if resp.MTR_REL_STEPS == 0:
        event_log.error(f"Motor Steps Do not match expected REL : {resp.MTR_REL_STEPS} , Expected : 0")

    event_log.info(f"Motor relative steps moved: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def cal_motor_to_outer(port):
    """
    This function powers the Mechanism board (if it isn't already).
    Then commands the motor to CAL to OUTER.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu cal_to_outer2")
    # TODO: Update all to "send_cmd"
    # Check mechanism powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x01)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = _hk(port)

    # Home to Outer with Cal
    repeat(port, tc.mtr_homing, True, True)
    resp = _hk(port)

    # Check to see if at the Outer
    if not resp.MTR_FLAGS.OUTER:
        event_log.info("Moving to outer, waiting for switch to be pressed.")
        wait_movement_complete(port)
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
    resp = _hk(port)

    # Check to see if at the Outer
    if not resp.MTR_FLAGS.OUTER:
        event_log.info("Moving to outer, waiting for switch to be pressed.")
        wait_movement_complete(port)
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
        wait_movement_complete(port)
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


def mv_pos_steps(port, steps):
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
    repeat(port, tc.mtr_mov_pos, steps)

    # Wait until no longer moving
    wait_movement_complete(port, steps)


def mv_neg_steps(port, steps):
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
    repeat(port, tc.mtr_mov_neg, steps)

    # Wait until no longer moving
    wait_movement_complete(port, steps)


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
    for i in range(0, 8900, step_spacing):
        move_and_measure(port, step_spacing, sci_adc_samp, sci_adc_skip)

    event_log.info("Science Measurements Completed!!")


def abu_measurement_scan_loop(port):
    """
    Performs the basic Enfys science measurement
    Homes and Calibrates to Base
    Goes to the Outer
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    and loops around for the number of times set
    """

    for i in range(0, 20, 1):
        abu_measurement_scan(port, 30, 4, 100)

    return


def abu_measurement_scan_neg(port, step_spacing=50, sci_adc_samp=4, sci_adc_skip=20):
    """
    Performs the basic Enfys science measurement
    Homes and Calibrates to Base
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    """
    event_log.info("Running ABU Measurement Scan")
    read_hk(port, False)

    # Cal to Base
    cal_motor_to_base(port)

    # Measurement sequence
    # TODO! Emulate Dark Offset and Edge finding (with SWIR and broad lamp)
    event_log.info("Starting Science Measurements")
    move_and_measure(port, 0, sci_adc_samp, sci_adc_skip)
    for i in range(0, 8900, step_spacing):
        move_and_measure(port, -step_spacing, sci_adc_samp, sci_adc_skip)

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

    # We've found that, without a 3s delay after tc.power_control, we
    # get a NAK back from the motor movements below.
    time.sleep(3)

    cal_motor_to_base(port)

    # Commented out - we don't need to move to outer,
    # and it adds 2 whole transitions across the range.
    # home_to_outer(port)


def first_power_on_cal_outer(port):
    """
    Very simple sequence that powers on both sub-systems.
    Then Calibrates the mech to OUTER
    Then Moves the mech to Base
    """
    event_log.info("Running ABU First power on, cal to Outer, home to Base")

    # Power up motor and Detector
    repeat(port, tc.power_control, 0x3)

    # We've found that, without a 3s delay after tc.power_control, we
    # get a NAK back from the motor movements below.
    time.sleep(3)

    cal_motor_to_outer(port)

    # Commented out - we don't need to move to base,
    # and it adds 2 whole transitions across the range.


def find_dac_offset(
    port: serial.rs485.RS485,
    sensor_name: str,
    target_output: int,
    fixed_offset: int,
    max_miss: int = 1600,
    sci_adc_samp: int = 4,
    sci_adc_skip: int = 100,
):
    """
    This function tries to find a DAC offset which results in a high gain output close
    to the value or target_output. The sensor that's *not* being configured has its gain
    value set to fixed_offset, while binary chop is used to find a suitable offset for
    the sensor that *is* being configured.

    The offset is returned, and the instrument is left configured with that offset.

    :param port: The serial port for comms with the instrument
    :param sensor_name: "MWIR" or "SWIR" - which sensor we're calibrating
    :param target_output: The output value we're aiming for
    :param fixed_offset: The fixed value that the other sensor will take during the chop.
    :param max_miss: If the final value is more than this distance from the target output, report a problem.
    :param sci_adc_samp: ADC oversampling factor.
    :param sci_adc_skip: How many samples to skip.
    :return: The DAC offset that gives an output closest to the target value.
    """
    event_log.info(f"Running abu targeted_binary_chop for {sensor_name} with target value {target_output}")

    if sensor_name not in ("MWIR", "SWIR"):
        event_log.error(f"For DAC offsets, sensor name must be either MWIR or SWIR, not {sensor_name}")

    # Check detector powered, if not enable.
    hk = _hk(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        repeat(port, tc.power_control, hk.PWR_STAT | 0x02)

    dac_value = 0x0
    bit_value = 1 << 11

    # Binary chop - work down through the bits, homing in on
    # the DAC offset value which gets closest to the target output.
    while bit_value != 0:
        # Make a test value with the current bit set.
        test_value = dac_value | bit_value

        # Log it.
        event_log.info(f"Setting the {sensor_name} DAC offset value to: {test_value}")

        # Do the part that depends on which sensor we're working on.
        if sensor_name == "MWIR":
            # Set the test offset value.
            repeat(port, tc.sci_offset, fixed_offset, test_value)

            # Check it was successfully set
            sci = _check_sci(port, sci_adc_samp, sci_adc_skip)
            if sci.MWIR_OFFSET != test_value:
                event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {test_value}")

            # Copy the reading so the rest of the loop doesn't depend on sensor.
            reading = sci.MWIR_HIGH
        else:
            # Ditto for SWIR.
            repeat(port, tc.sci_offset, test_value, fixed_offset)
            sci = _check_sci(port, sci_adc_samp, sci_adc_skip)
            if sci.SWIR_OFFSET != test_value:
                event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}, Expected: {test_value}")
            reading = sci.SWIR_HIGH

        event_log.info(f"Got the following {sensor_name} high reading: {reading}")

        # If the HIGH reading is >= target_output, keep the bit, otherwise discard.
        if reading >= target_output:
            dac_value = test_value

        # On to the next bit.
        bit_value >>= 1

    # Report whether we've managed to get in range.
    if abs(reading - target_output) <= max_miss:
        event_log.info(f"Suitable {sensor_name} offset found for target {target_output}.")
    else:
        event_log.error(f"No in-range {sensor_name} offset found for target {target_output}.")

    event_log.info(f"Final {sensor_name} DAC offset value: {dac_value}")
    event_log.info(f"Final {sensor_name} high reading: {reading}")
    return dac_value


def convert_logs() -> None:
    """
    Convert science and HK logs from hex to CSV, which will be placed in the
    same directory as the original hex log files. The log files are flushed
    before reading.

    If you add abu.convert_logs() as the last operation in the "script" area
    of main.py, this should mean you'll automatically get decoded logs as
    CSV files in the log directory.
    """
    event_log.info("Running abu convert_logs")

    if const.HK_LOG_FH is None:
        event_log.info("No HK log is present - skipping conversion")
    else:
        const.HK_LOG_FH.flush()
        printed_header = False

        # This is a bit fiddly - the TM classes log if *_FH is not None,
        # and we don't want that, otherwise they'll log infinite data as
        # we read them back in. So we take a copy and temporarily set
        # *_FH to None.
        temp_hk_log_fh = const.HK_LOG_FH
        const.HK_LOG_FH = None

        # Get a name for the CSV file.
        csvname = pathlib.Path(temp_hk_log_fh.name).with_suffix(".csv")
        event_log.info(f"Writing HK data to {csvname}")

        with open(csvname, "w") as csv_file:
            # Iterate over the log.
            decoder = EGSEDumpDecoder(temp_hk_log_fh.name)
            rows = 0
            for timestamp, entry in decoder:
                rows += 1
                # Print CSV header if not already printed.
                if not printed_header:
                    print("Date,Time,", file=csv_file, end="")
                    print(entry.csv_header(), file=csv_file)
                    printed_header = True
                date, timeofday = timestamp.split(" ")
                print(date, end=" ,", file=csv_file)
                print(timeofday, end=",", file=csv_file)
                print(entry.csv(), file=csv_file)

            event_log.info(f"Stored {rows} HK row(s) into {csv_file.name}")

            # Restore HK_LOG_FH from the copy.
            const.HK_LOG_FH = temp_hk_log_fh

    if const.SCI_LOG_FH is None:
        event_log.info("No Science log is present - skipping conversion")
    else:
        const.SCI_LOG_FH.flush()
        printed_header = False

        # As above, do a little dance with file handles.
        temp_sci_log_fh = const.SCI_LOG_FH
        const.SCI_LOG_FH = None

        csvname = pathlib.Path(temp_sci_log_fh.name).with_suffix(".csv")
        event_log.info(f"Writing science data to {csvname}")
        with open(csvname, "w") as csv_file:
            rows = 0
            decoder = EGSEDumpDecoder(temp_sci_log_fh.name)
            for timestamp, entry in decoder:
                rows += 1
                if not printed_header:
                    print("Date,Time,", file=csv_file, end="")
                    print(entry.csv_header(decoder.default_fields_per_type[type(entry)]), file=csv_file)
                    printed_header = True
                date, timeofday = timestamp.split(" ")
                print(date, end=",", file=csv_file)
                print(timeofday, end=",", file=csv_file)
                print(entry.csv(decoder.default_fields_per_type[type(entry)]), file=csv_file)
            event_log.info(f"Stored {rows} science row(s) into {csv_file.name}")
            const.SCI_LOG_FH = temp_sci_log_fh


def mv_abs_pos(port: serial.rs485.RS485, position: int) -> None:
    """
    Get the current motor position, then send a relative command to
    take it to the specified position.

    :param port: The serial port for comms with the instrument.
    :param position: The absolute motor position to move to.
    """
    event_log.info(f"Running ABU mv_abs_pos({position})")

    # Get the current position.
    hk = _hk(port)

    # Work out delta needed to reach measurement_position
    delta = position - hk.MTR_ABS_STEPS

    if delta > 0:
        event_log.info(f"Moving to {position}, which is {delta} positive steps from {hk.MTR_ABS_STEPS}")
        mv_pos_steps(port, delta)
    elif delta < 0:
        event_log.info(f"Moving to {position}, which is {-delta} negative steps from {hk.MTR_ABS_STEPS}")
        mv_neg_steps(port, -delta)
    else:
        event_log.info("No movement needed")


def move_off_endstops(port: serial.rs485.RS485) -> None:
    """
    Make sure that the motor is at neither end stop.

    :param port: The serial port for comms with the instrument.
    """

    event_log.info("Running ABU move_off_endstops")
    hk = _hk(port)

    while hk.MTR_FLAGS.OUTER or hk.MTR_FLAGS.BASE:
        if hk.MTR_FLAGS.OUTER and hk.MTR_FLAGS.BASE:
            event_log.error("Both OUTER and BASE flags are raised")
            break
        if hk.MTR_FLAGS.OUTER:
            event_log.info("Motor is at outer end stop. Moving +200.")
            mv_pos_steps(port, 200)

        elif hk.MTR_FLAGS.BASE:
            event_log.info("Motor is at base end stop. Moving -200.")
            mv_neg_steps(port, 200)
        hk = _hk(port)

    if not hk.MTR_FLAGS.OUTER and not hk.MTR_FLAGS.BASE:
        event_log.info("Motor is away from end stops")


def abu_measurement_table_scan(port, table_number, sci_adc_samp=4, sci_adc_skip=20, dark_table_0=0, dark_table_1=1):
    """
    Performs the basic Enfys science measurement table operation
    Homes and Calibrates to Base
    Goes to the Outer
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    Halts once Base Stop is reached
    """
    event_log.info(f"Running ABU Measurement Table Scan using table {table_number}")

    dark0 = mt.MeasurementTable(mt.predefined[dark_table_0])
    dark1 = mt.MeasurementTable(mt.predefined[dark_table_1])
    table = mt.MeasurementTable(mt.predefined[table_number], before_table=dark0, after_table=dark1)

    # Cal to Base
    cal_motor_to_base(port)

    # SWIR binary chop at base (9960)
    swir_offset = find_dac_offset(port, "SWIR", 5000, 1)
    event_log.info(f"SWIR offset = {swir_offset}")

    # Move to 8,000 for MWIR binary chop.
    mv_neg_steps(port, 1960)

    # Do MWIR binary chop.
    mwir_offset = find_dac_offset(port, "MWIR", 5000, swir_offset)
    event_log.info(f"MWIR offset = {mwir_offset}")

    # Home to Outer
    home_to_outer(port)

    # Get HK so we can find the current position.
    hk_tm = _hk(port)

    # FIXME: We should do something if MTR_ABS_STEPS is not
    # close enough to 1000 at this point.

    event_log.info(f"Starting Science Measurements, MTR_ABS_STEPS={hk_tm.MTR_ABS_STEPS}")

    # Run through the measurement table - we tell the iterator the
    # current motor steps so it can align things where we expect them to be.
    for rel_move, abs_pos in table.scan(start_motor_steps=hk_tm.MTR_ABS_STEPS):
        # Action the requested move (assuming a move was needed).
        if rel_move < 0:
            mv_neg_steps(port, -rel_move)
        elif rel_move > 0:
            mv_pos_steps(port, rel_move)

        # Request a Science Measurement and log the result.
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

    # Home to base so we can check motor steps is OK.
    home_to_base(port)

    # FIXME: We should do something if MTR_ABS_STEPS is not
    # close enough to 9960 at this point.

    event_log.info("Science Measurements Completed")


def abu_measurement_table_scan2(port, table_number, sci_adc_samp=4, sci_adc_skip=20, dark_table_0=0, dark_table_1=1):
    """
    Performs the basic Enfys science measurement table operation
    After an earlier Calibration to Outer and home to base!!!
    Goes to the Base Does ABC
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    Halts once Base Stop is reached
    """
    event_log.info(f"Running ABU Measurement Table Scan using table {table_number}")

    dark0 = mt.MeasurementTable(mt.predefined[dark_table_0])
    dark1 = mt.MeasurementTable(mt.predefined[dark_table_1])
    table = mt.MeasurementTable(mt.predefined[table_number], before_table=dark0, after_table=dark1)

    # Cal to Outer
    # cal_motor_to_outer(port)

    # Move to Base
    home_to_base(port)

    # SWIR binary chop at base (9600)
    swir_offset = find_dac_offset(port, "SWIR", 5000, 1)
    event_log.info(f"SWIR offset = {swir_offset}")

    # Move to 8,000 for MWIR binary chop.
    mv_neg_steps(port, 1600)

    # Do MWIR binary chop.
    mwir_offset = find_dac_offset(port, "MWIR", 15000, swir_offset)
    event_log.info(f"MWIR offset = {mwir_offset}")

    # Home to Outer
    home_to_outer(port)

    # Get HK so we can find the current position.
    hk_tm = _hk(port)

    # FIXME: We should do something if MTR_ABS_STEPS is not
    # close enough to 1000 at this point.

    event_log.info(f"Starting Science Measurements, MTR_ABS_STEPS={hk_tm.MTR_ABS_STEPS}")

    # Run through the measurement table - we tell the iterator the
    # current motor steps so it can align things where we expect them to be.
    for rel_move, abs_pos in table.scan(start_motor_steps=hk_tm.MTR_ABS_STEPS):
        # Action the requested move (assuming a move was needed).
        if rel_move < 0:
            mv_neg_steps(port, -rel_move)
        elif rel_move > 0:
            mv_pos_steps(port, rel_move)

        # Request a Science Measurement and log the result.
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

    # Home to base so we can check motor steps is OK.
    home_to_base(port)

    # FIXME: We should do something if MTR_ABS_STEPS is not
    # close enough to 9960 at this point.

    event_log.info("Science Measurements Completed")


def abu_measurement_mode2_scan(port, measurement_location, interval_seconds, count, sci_adc_samp=4, sci_adc_skip=20):
    """
    Performs the basic Enfys science measurement at a single position
    Homes and Calibrates to Base
    Does binary chops
    Takes a specified number of measurements at a single location, with specified interval between
    Gets measurements at binary chop locations
    Goes back to base
    """
    event_log.info(
        f"Running ABU Mode2 Scan at {measurement_location} for {count} samples at {interval_seconds}s intervals"
    )

    # Cal to Base
    cal_motor_to_base(port)

    # SWIR binary chop at base (9960)
    swir_offset = find_dac_offset(port, "SWIR", 5000, 1)
    event_log.info(f"SWIR offset = {swir_offset}")

    # Move to 8,000 for MWIR binary chop.
    mv_neg_steps(port, 1960)

    # Do MWIR binary chop.
    mwir_offset = find_dac_offset(port, "MWIR", 5000, swir_offset)
    event_log.info(f"MWIR offset = {mwir_offset}")

    mv_abs_pos(port, measurement_location)

    # Get HK so we know the current position.
    hk_tm = _hk(port)
    event_log.info(f"Starting Science Measurements, MTR_ABS_STEPS={hk_tm.MTR_ABS_STEPS}")

    for _ in range(count):
        # Request a Science Measurement and log the result.
        sci = _sci(port, sci_adc_samp, sci_adc_skip)
        event_log.info(
            f"\t\t SW_L: {sci.SWIR_LOW:04d}"
            + f"   SW_M: {sci.SWIR_MED:04d}"
            + f"   SW_H: {sci.SWIR_HIGH:04d}"
            + f"\t MW_L: {sci.MWIR_LOW:04d}"
            + f"   MW_M: {sci.MWIR_MED:04d}"
            + f"   MW_HH: {sci.MWIR_HIGH:04d}"
            + f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}"
            + f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}"
        )
        time.sleep(interval_seconds)

    mv_abs_pos(port, 8000)
    sci = _sci(port, sci_adc_samp, sci_adc_skip)
    event_log.info(
        "At MWIR BC location "
        + f"\t\t SW_L: {sci.SWIR_LOW:04d}"
        + f"   SW_M: {sci.SWIR_MED:04d}"
        + f"   SW_H: {sci.SWIR_HIGH:04d}"
        + f"\t MW_L: {sci.MWIR_LOW:04d}"
        + f"   MW_M: {sci.MWIR_MED:04d}"
        + f"   MW_HH: {sci.MWIR_HIGH:04d}"
        + f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}"
        + f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}"
    )

    # Home to base so we can check motor steps is OK.
    home_to_base(port)

    sci = _sci(port, sci_adc_samp, sci_adc_skip)
    event_log.info(
        "At SWIR BC location"
        + f"\t\t SW_L: {sci.SWIR_LOW:04d}"
        + f"   SW_M: {sci.SWIR_MED:04d}"
        + f"   SW_H: {sci.SWIR_HIGH:04d}"
        + f"\t MW_L: {sci.MWIR_LOW:04d}"
        + f"   MW_M: {sci.MWIR_MED:04d}"
        + f"   MW_HH: {sci.MWIR_HIGH:04d}"
        + f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}"
        + f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}"
    )

    # FIXME: We should do something if MTR_ABS_STEPS is not
    # close enough to 9960 at this point.

    event_log.info("Science Measurements Completed")
