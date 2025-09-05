import logging
import time
import constants as const
import send_cmd
import tc
import scripts.sequences as sq
import serial
import pathlib
from egse_dump_decoder import EGSEDumpDecoder

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")


# ----
def read_hk(port, display_contents=True):
    """
    This function requests a HK and generates a decoded log of all the HK parameters.
    """
    event_log.info("Running ABU read HK")
    resp = tc.hk_request(port)
    if display_contents:
        event_log.info(
            f" MOD_ID :{resp.MOD_ID}" +
            f"\n Unused1 : {resp.UNUSED1}" +
            f"\n CMD_ID :{resp.CMD_ID}" +
            f"\n CMD_CNT : {resp.CMD_CNT}" +
            f"\n ERROR_BYTE : {resp.ERROR_BYTE}" +
            f"\n UNUSED2 :{resp.UNUSED2}" +
            f"\n ERROR_MTR :{resp.ERROR_MTR}" +
            f"\n MTR_ERR_MSK : {resp.MTR_ERR_MSK}" +
            f"\n MTR_FLAGS_BYTE :{resp.MTR_FLAGS_BYTE}" +
            f"\n MTR_ABS_STEPS : {resp.MTR_ABS_STEPS}" +
            f"\n MTR_REL_STEPS : {resp.MTR_REL_STEPS}" +
            f"\n MTR_CURRENT :{resp.MTR_CURRENT}" +
            f"\n MTR_GUARD : {resp.MTR_GUARD}" +
            f"\n MTR_RECVAL : {resp.MTR_RECVAL}" +
            f"\n UNUSED3 : {resp.UNUSED3}" +
            f"\n MTR_SPEED :{resp.MTR_SPEED}" +
            f"\n MECH_LIM_REL : {resp.MECH_LIM_REL}" +
            f"\n UNUSED4 : {resp.PWR_STAT}" +
            f"\n PWR_STAT : {resp.PWR_STAT}" +
            f"\n THRM_STATUS :{resp.THRM_STATUS}" +
            f"\n THRM_MECH_OFF_SP : {resp.THRM_MECH_OFF_SP}" +
            f"\n THRM_MECH_ON_SP : {resp.THRM_MECH_ON_SP}" +
            f"\n THRM_DET_OFF_SP :{resp.THRM_DET_OFF_SP}" +
            f"\n THRM_DET_ON_SP : {resp.THRM_DET_ON_SP}" +
            f"\n SWIR_OFFSET : {resp.SWIR_OFFSET}" +
            f"\n MWIR_OFFSET : {resp.MWIR_OFFSET}" +
            f"\n HK_V_3V3 : {resp.HK_V_3V3}" +
            f"\n HK_V_1V5 :{resp.HK_V_1V5}" +
            f"\n DIGITAL_TRP : {resp.DIGITAL_TRP}" +
            f"\n DETEC_TRP :{resp.DETEC_TRP}" +
            f"\n MECH_TRP : {resp.MECH_TRP}" +
            f"\n MOTOR_TRP : {resp.MOTOR_TRP}" +
            f"\n HK_MECH_CUR :{resp.HK_MECH_CUR}" +
            f"\n UNUSED_ADC : {resp.UNUSED_ADC}" +
            f"\n HK_SAMPLES : {resp.HK_SAMPLES}" +
            f"\n UNUSED5 :{resp.UNUSED5}" +
            f"\n CRC8 : {resp.CRC8}")
        event_log.info("ERROR BYTE : " +
                       ("IPI " if resp.ERRORS.IPI else "") +
                       ("IOS " if resp.ERRORS.IOS else "") +
                       ("ICR " if resp.ERRORS.ICR else "") +
                       ("MOR " if resp.ERRORS.MOR else "") +
                       ("TMO " if resp.ERRORS.TMO else "") +
                       ("IPA " if resp.ERRORS.IPA else "") +
                       ("None" if resp.ERROR_BYTE == 0 else "")
        )
        event_log.info("MTR Flags : " +
                                ("Unused " if resp.MTR_FLAGS.UNUSED1 else "") +
                                ("CAL " if resp.MTR_FLAGS.CAL else "") +
                                ("HOLD " if resp.MTR_FLAGS.HOLD else "") +
                                ("DIR " if resp.MTR_FLAGS.DIR else "") +
                                ("OUTER " if resp.MTR_FLAGS.OUTER else "") +
                                ("BASE " if resp.MTR_FLAGS.BASE else "") +
                                ("MOVING " if resp.MTR_FLAGS.MOVING else "") +
                                ("HOMED " if resp.MTR_FLAGS.HOMED else "") +
                                ("None" if resp.MTR_FLAGS_BYTE == 0 else "")
        )
        event_log.info("MTR Errors : " +
                                ("Unused " if resp.MTR_ERRORS.UNUSED else "") +
                                ("CD " if resp.MTR_ERRORS.CD else "") +
                                ("AB " if resp.MTR_ERRORS.AB else "") +
                                ("ABS " if resp.MTR_ERRORS.ABS else "") +
                                ("REL " if resp.MTR_ERRORS.REL else "") +
                                ("DSE " if resp.MTR_ERRORS.DSE else "") +
                                ("None" if resp.ERROR_MTR == 0 else "")
        )


def cal_motor_to_base(port):
    """
    This function powers the Mechanism board (if it isn't already).
    Sets the default motor parameters
    Then commands the motor to HOME to BASE with CAL applied.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu cal_motor_to_base")
    #TODO: Update all to "send_cmd"
    # Check mechanism powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x01)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    # Set motor parameters
    send_cmd.cmd_mtr_param(port,0x17,0x20,0x0F,0x7,0x3200)
    resp = tc.hk_request(port)
    if (
    resp.MTR_CURRENT != 0x17
    or resp.MTR_GUARD != 0x20
    or resp.MTR_RECVAL != 0x0F
    or resp.MTR_SPEED != 0x7
    or resp.MECH_LIM_REL != 0x3200):
        event_log.error("OB Parameters not initialized correctly:"+
                        f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 64" +
                        f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32" +
                        f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15" +
                        f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9" +
                        f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800")

    # Cal to BASE
    send_cmd.cmd_mtr_homing(port, True, False)
    hk_tm = tc.hk_request(port)

    # Check to see if at the Base
    if not hk_tm.MTR_FLAGS.BASE:
        event_log.info("Moving to the BASE, waiting for switch to be pressed.")
        while hk_tm.MTR_FLAGS.MOVING:
            time.sleep(1)
            hk_tm = tc.hk_request(port)
            event_log.info(f"Motor MOVING: Absolute Steps : {hk_tm.MTR_ABS_STEPS:04d}, Relative Steps: {hk_tm.MTR_REL_STEPS:04d}")
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, Base Flag Asserted")

    #Check motor status now its stopped.
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.CAL != 1 :
        event_log.error(f" Calibration Flag not Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0 :
        event_log.error(f" Calibration Dir not to BASE : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER != 0 :
        event_log.error(f"OUTER Switch Flag raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE != 1 :
        event_log.error(f"BASE Switch Flag is not asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMED != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMED}")

    if (resp.MTR_ABS_STEPS != 8960):
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
    if (resp.MTR_REL_STEPS == 0):
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
    #TODO: Update all to "send_cmd"
    # Check mechanism powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x01)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    # Home to Outer with no Cal
    send_cmd.cmd_mtr_homing(port, False, True)
    hk_tm = tc.hk_request(port)

    # Check to see if at the Outer
    if not hk_tm.MTR_FLAGS.OUTER:
        event_log.info("Moving to outer, waiting for switch to be pressed.")
        while hk_tm.MTR_FLAGS.MOVING:
            time.sleep(1)
            hk_tm = tc.hk_request(port)
            event_log.info(f"Motor MOVING: Absolute Steps : {hk_tm.MTR_ABS_STEPS:04d}, Relative Steps: {hk_tm.MTR_REL_STEPS:04d}")
        event_log.info("Motor movement finished")
    else :
        event_log.info("Motor Did not Move, Outer Flag Asserted")

    #Check motor status now its stopped.
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.CAL != 0 :
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 1 :
        event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER !=1 :
        event_log.error(f"OUTER Switch Flag not asserted : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE !=0 :
        event_log.error(f"Base Switch Flag is asserted : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMED != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMED}")

    if (resp.MTR_REL_STEPS == 0):
        event_log.error("Motor Steps Do not match expected : " +
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")

    event_log.info(f"Motor relative steps moved: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def home_to_base(port):
    """
    Then commands the motor to HOME to BASE.
    As it moves it will report the relative and absolute steps.
    """
    event_log.info("Running abu home_to_base")
    #TODO: Update all to "send_cmd"

    # Check mechanism powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x01)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    # Home to base
    send_cmd.cmd_mtr_homing(port,False, False)
    hk_tm = tc.hk_request(port)

    # Check to see if at the Base
    if not hk_tm.MTR_FLAGS.BASE:
        event_log.info("Moving to the base, waiting for switch to be pressed.")
        while hk_tm.MTR_FLAGS.MOVING:
            time.sleep(1)
            hk_tm = tc.hk_request(port)
            event_log.error(f"MTR Flags : \nUnused : {hk_tm.MTR_FLAGS.UNUSED1}" +
                            f"\n CAL : {hk_tm.MTR_FLAGS.CAL}"+
                            f"\n HOLD : {hk_tm.MTR_FLAGS.HOLD}" +
                            f"\n DIR : {hk_tm.MTR_FLAGS.DIR}" +
                            f"\n OUTER : {hk_tm.MTR_FLAGS.OUTER}" +
                            f"\n BASE : {hk_tm.MTR_FLAGS.BASE}" +
                            f"\n MOVING : {hk_tm.MTR_FLAGS.MOVING}" +
                            f"\n HOMED : {hk_tm.MTR_FLAGS.HOMED}"
                            )
        event_log.info("Motor movement finished")
    else :
        event_log.error("Motor Did not Move, Base Flag Asserted")

    #Check motor status now its stopped.
    resp = tc.hk_request(port)
    if resp.MTR_FLAGS.CAL != 0 :
        event_log.error(f" Calibration Flag Asserted : {resp.MTR_FLAGS.CAL}")
    if resp.MTR_FLAGS.DIR != 0 :
        event_log.error(f" Calibration Dir not to Base : {resp.MTR_FLAGS.DIR}")
    if resp.MTR_FLAGS.OUTER !=0 :
        event_log.error(f"OUTER Switch Flag raised : {resp.MTR_FLAGS.OUTER}")
    if resp.MTR_FLAGS.BASE !=1 :
        event_log.error(f"Base Switch Flag not raised : {resp.MTR_FLAGS.BASE}")
    if resp.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {resp.MTR_FLAGS.MOVING}")
    if resp.MTR_FLAGS.HOMED != 0:
        event_log.error(f"Motor Homing flag is asserted: {resp.MTR_FLAGS.HOMED}")

    if (resp.MTR_REL_STEPS == 0):
        event_log.error("Motor Steps Do not match expected : " +
                        f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")

    event_log.info(f"Motor relative steps: {resp.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {resp.MTR_ABS_STEPS}")


def mv_pos_steps(port, pos_steps):
    """
    Script that moves the mechanism a certain number of steps positive (towards the base).
    Automatically checks that we are not already at the base.
    """
    event_log.info("Running ABU move positive steps")

    # First check that there we are are not already at the base.
    hk = tc.hk_request(port)

    if hk.MTR_FLAGS.BASE:
        event_log.error("Request to move positive steps but already at the base, skipping movement")
        return

    # Then move the desired number of steps
    send_cmd.cmd_mtr_mov_pos(port, pos_steps)

    # Request a HK and wait until no longer moving
    hk = tc.hk_request(port)
    while hk.MTR_FLAGS.MOVING:
        hk = tc.hk_request(port)

    if hk.ERROR_MTR != 0:
        event_log.error("***MOTOR ERROR*** got the following: " +
                        f"\n CD : {hk.MTR_ERRORS.CD}"+
                        f"\n AB : {hk.MTR_ERRORS.AB}" +
                        f"\n ABS : {hk.MTR_ERRORS.ABS}" +
                        f"\n REL : {hk.MTR_ERRORS.REL}" +
                        f"\n DSE : {hk.MTR_ERRORS.DSE}"
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
    hk = tc.hk_request(port)

    if hk.MTR_FLAGS.OUTER:
        event_log.error("Request to move negative steps but already at the outer, skipping movement")
        return

    # Then move the desired number of steps
    send_cmd.cmd_mtr_mov_neg(port, pos_steps)

    # Request a HK and wait until no longer moving
    hk = tc.hk_request(port)
    while hk.MTR_FLAGS.MOVING:
        hk = tc.hk_request(port)

    if hk.ERROR_MTR != 0:
        event_log.error("***MOTOR ERROR*** got the following: " +
                        f"\n CD : {hk.MTR_ERRORS.CD}"+
                        f"\n AB : {hk.MTR_ERRORS.AB}" +
                        f"\n ABS : {hk.MTR_ERRORS.ABS}" +
                        f"\n REL : {hk.MTR_ERRORS.REL}" +
                        f"\n DSE : {hk.MTR_ERRORS.DSE}"
                        )


def set_offset_and_check_sci(port, swir_offset, mwir_offset, sci_adc_samp=4, sci_adc_skip=20):
    """
    Function that will power the detector board if it isn't already.
    Apply the offsets, set within the variables.
    Automatically request a science packet and ensure that the packet contents matches those set.
    """
    event_log.info("Running abu set_offset_and_check_sci")

    # Check detector powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x02)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    #Dark measurement to determine offset to be applied
    #Set SWIR and MWIR offset
    tc.sci_offset(port, swir_offset, mwir_offset)
    hk = tc.hk_request(port)
    if hk.SWIR_OFFSET != swir_offset:
        event_log.error(f"SWIR offset not updated in HK. Got {hk.SWIR_OFFSET}")
    if hk.MWIR_OFFSET != mwir_offset:
        event_log.error(f"MWIR offset not updated in HK. Got {hk.MWIR_OFFSET}")

    #Take SCI reading and check.
    sci = sq.check_sci(port, sci_adc_samp, sci_adc_skip)
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
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x02)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    mwir_value = 0x0 # Seed value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        mwir_delta = 0x1 << (i - 1)
        event_log.info(f"Setting the MWIR Value to: {mwir_value + mwir_delta}")
        tc.sci_offset(port, swir_fixed, mwir_value + mwir_delta)
        sci = sq.check_sci(port, sci_adc_samp, sci_adc_skip)
        if sci.MWIR_OFFSET != (mwir_value + mwir_delta):
            event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {mwir_value + mwir_delta}")

        event_log.info(f"Got the following MWIR High Reading: {sci.MWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.MWIR_HIGH >= const.MWIR_DAC_MIN_TH:
            mwir_value = mwir_value + mwir_delta

        # Check if we are within the range (we are done) otherwise loop
        if const.MWIR_DAC_MIN_TH <= sci.MWIR_HIGH <= const.MWIR_DAC_MAX_TH:
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
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x02)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    swir_value = 0x0 # Seed Value

    for i in range(12, 0, -1):
        event_log.info(f"Testing bit {i} out of 12")
        swir_delta  = 0x1 << (i -1)
        event_log.info(f"Setting the SWIR value to: {swir_value + swir_delta}")
        tc.sci_offset(port, swir_value + swir_delta, mwir_fixed)
        sci = sq.check_sci(port, sci_adc_samp, sci_adc_skip)
        if sci.SWIR_OFFSET != (swir_value + swir_delta):
            event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}, Expected: {swir_value + swir_delta}")

        event_log.info(f"Got the following SWIR High Reading: {sci.SWIR_HIGH}")

        # If the HIGH reading is greater than threshold (keep value)
        if sci.SWIR_HIGH > const.SWIR_DAC_MIN_TH:
            swir_value = swir_value + swir_delta

        # Check if we are within the range (we are done) otherwise loop
        if const.SWIR_DAC_MIN_TH <= sci.SWIR_HIGH <= const.SWIR_DAC_MAX_TH:
            event_log.info("SWIR offset in threshold finished!")
            event_log.info(f"Final SWIR value: {swir_value}")
            return swir_value

    event_log.error(f"No solution found. Last MWIR Offset set to: {sci.SWIR_OFFSET}")
    return sci.SWIR_OFFSET


def move_and_measure(port, pos_steps, sci_adc_samp=4, sci_adc_skip=20):
    """
    Moves the specified number of steps forward and then takes a measurement. 0 steps can be entered
    and the sequence will just measure the same point once again.

    This sequence should be executed once the motor has been homed and the offsets applied.

    The motor moves from the Outer to Base using (positive steps)
    """
    event_log.info("Running abu move_and_measure")

    if pos_steps > 0:
        mv_pos_steps(port, pos_steps)
    else:
        event_log.info("No need to move any steps, proceeding to measurement")

    # Request a Science Mesaurement and log to the screen.
    sci = tc.sci_request(port, sci_adc_samp, sci_adc_skip)
    hk_tm = tc.hk_request(port)
    event_log.info(f"ABS_STEPS: {sci.MTR_ABS_STEPS:04d}" +
                  f"   HK_ABS_STEPS: {hk_tm.MTR_ABS_STEPS:04d}" +
                  f"   SWIR_OFFSET: {sci.SWIR_OFFSET:04d}" +
                  f"   MWIR_OFFSET: {sci.MWIR_OFFSET:04d}" +
                  f"\t\t SW_L: {sci.SWIR_LOW:04d}" +
                  f"   SW_M: {sci.SWIR_MED:04d}" +
                  f"   SW_H: {sci.SWIR_HIGH:04d}" +
                  f"\t MW_L: {sci.MWIR_LOW:04d}" +
                  f"   MW_M: {sci.MWIR_MED:04d}" +
                  f"   MW_H: {sci.MWIR_HIGH:04d}" +
                  f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}" +
                  f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}")
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
    for offset in range(1440, 1785, step):
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
    tc.power_control(port, 0x3)

    cal_motor_to_base(port)
    home_to_outer(port)


def find_dac_offset(port: serial.rs485.RS485, sensor_name: str, target_output: int, fixed_offset: int, max_miss: int = 100, sci_adc_samp: int = 4, sci_adc_skip: int = 20):
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

    # If our target high gain output is above medium_gain_switch_threshold
    # then we'll scale by medium_to_high_gain_scale and use the medium gain
    # value instead. This gives a measure of protection against saturation.
    medium_gain_switch_threshold = 3700
    medium_to_high_gain_scale = 30

    if sensor_name not in ("MWIR", "SWIR"):
        event_log.error(f"For DAC offsets, sensor name must be either MWIR or SWIR, not {sensor_name}")

    # Check detector powered, if not enable.
    hk = tc.hk_request(port)
    if not (hk.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        tc.power_control(port, hk.PWR_STAT | 0x02)

        # TODO can probably remove this check and replace above with send_cmd and verify
        resp = tc.hk_request(port)

    dac_value = 0x0
    bit_value = 1<<11

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
            tc.sci_offset(port, fixed_offset, test_value)

            # Check it was successfully set
            sci = sq.check_sci(port, sci_adc_samp, sci_adc_skip)
            if sci.MWIR_OFFSET != test_value:
                event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {test_value}")

            # Copy the reading so the rest of the loop doesn't depend on sensor.
            if target_output <= medium_gain_switch_threshold:
                reading = sci.MWIR_HIGH
            else:
                reading = medium_to_high_gain_scale*sci.MWIR_MED
        else:
            # Ditto for SWIR.
            tc.sci_offset(port, test_value, fixed_offset)
            sci = sq.check_sci(port, sci_adc_samp, sci_adc_skip)
            if sci.SWIR_OFFSET != test_value:
                event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}, Expected: {test_value}")
            reading = sci.SWIR_HIGH

            if target_output <= medium_gain_switch_threshold:
                reading = sci.SWIR_HIGH
            else:
                reading = medium_to_high_gain_scale*sci.SWIR_MED

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


def piecewise_linear(table: list, target: int) -> int:
    """
    Piecewise linear interpolation. This will be used for estimating a
    dark offset target in the "bathtub" range. The EB doesn't use floating
    point, so while we have an exponential formula relating bathtub output
    offsets to temperature, we can't use the formula. Instead, we have a
    table of points and we'll use interpolation to get a close value.

    :param table:  A list of tuples (x, y), in increasing x order.
    :param target: The x value for which you'd like to obtain a y value.
    :return: The interpolated y value.
    """

    # Work through the table until we hit an entry whose
    # x value is less than the target.
    pos = 0
    while pos < len(table):
        if table[pos][0] >= target:
            if pos == 0:
                # Our target is lower than the first table x position.
                # Return the first position's y value.
                return table[0][1]
            else:
                # Piecewise linear interpolation between the bracketing
                # table values. We're expecting to work in integer maths
                # on the real hardware, so do the same here.
                return (table[pos-1][1] + ((target-table[pos-1][0])*(table[pos][1]-table[pos-1][1]))
                                    // (table[pos][0]-table[pos-1][0]))
        pos += 1

    # We hit the end of the table, which means the target is above
    # the range covered by the table. Return the last position's y
    # value.
    return table[pos-1][1]


def dac_auto_offset(port: serial.rs485.RS485, sci_adc_samp: int = 4, sci_adc_skip: int = 20) -> tuple[int, int]:
    """
    This function tries to determine sensible SWIR and MWIR DAC
    offsets using a model of the difference between outputs at
    a position behind the mask and a "minimum" position in the
    field of view when dark.

    :param port: The serial port for comms with the instrument.
    :param sci_adc_samp: ADC oversampling factor.
    :param sci_adc_skip: How many samples to skip.
    :return: The MWIR and SWIR offsets chosen.
    """
    event_log.info("Running abu dac_auto_offset")

    # The interpolation tables below (from the jupyter notebook) give the
    # target high gain values at 510 motor steps to try to get a dark DAC
    # level of 200 at 7500 motor steps. It uses HT_SINK_TEMP for the
    # estimation.
    measurement_position = 510

    # From 2025-08-20 data set
    #mwir_interpolation_table = [
    #        (298, 84), (306, 107), (314, 140), (323, 193),
    #        (331, 263), (339, 362), (347, 503), (355, 703),
    #        (363, 988), (371, 1393), (379, 1971), (388, 2917),
    #        (396, 4139), (404, 5877), (412, 8352), (420, 11874)
    #]

    # From 2025-08-20 and 2025-09-03/04 data sets
    mwir_interpolation_table = [
       (297, 92), (305, 112), (313, 140), (321, 180), (330, 248), (338, 336),
       (346, 462), (354, 645), (363, 948), (371, 1345), (379, 1916), (387, 2739),
       (395, 3925), (404, 5893), (412, 8468), (420, 12177)
    ]
    swir_interpolation_table = [
            (298, 190), (420, 190)
    ]

    # Move to the measurement position.
    mv_abs_pos(port, measurement_position)

    # Aha, we can't have confidence in HT_SINK_TEMP unless we've
    # already set the DAC offsets to safe values - if the current
    # values are causing ADC underflow, this will affect the reading
    # of HT_SINK_TEMP. So set both DAC offsets low first, which
    # will likely cause overflow, but this is safe.
    #
    # I'm told that using zero for the offset isn't a good idea,
    # but 1 is safe.
    tc.sci_offset(port, 1, 1)

    # Get a science packet so we can read HT_SINK_TEMP
    sci = tc.sci_request(port, sci_adc_samp, sci_adc_skip)

    # Double check the offsets were set properly.
    if sci.MWIR_OFFSET != 1 or sci.SWIR_OFFSET != 1:
        event_log.error("Setting initial offsets failed - requested 1, 1 got {sci.MWIR_OFFSET}, {sci.SWIR_OFFSET}")

    # Using the interpolation tables, get target high gain outputs
    # at this position that we hope will give a good minimum
    # in "real" dark.
    mwir_target_output = piecewise_linear(mwir_interpolation_table, sci.HT_SINK_TEMP)
    swir_target_output = piecewise_linear(swir_interpolation_table, sci.HT_SINK_TEMP)

    event_log.info(f"Estimated target outputs are {mwir_target_output} (MWIR) and {swir_target_output} (SWIR)")

    # Get our estimated offsets.
    swir_dac_offset = find_dac_offset(port, "SWIR", swir_target_output, 1, sci_adc_samp=sci_adc_samp, sci_adc_skip=sci_adc_skip)
    mwir_dac_offset = find_dac_offset(port, "MWIR", mwir_target_output, swir_dac_offset, sci_adc_samp=sci_adc_samp, sci_adc_skip=sci_adc_skip)

    # Take a final reading just so we can output the results below.
    sci = tc.sci_request(port, sci_adc_samp, sci_adc_skip)

    event_log.info(f"DAC offsets were set to {mwir_dac_offset} (MWIR) and {swir_dac_offset} (SWIR)")
    event_log.info(f"Targets were {mwir_target_output} (MWIR) and {swir_target_output} (SWIR)")
    event_log.info(f"Readings were {sci.MWIR_HIGH} (MWIR) and {sci.SWIR_HIGH} (SWIR)")

    return mwir_dac_offset, swir_dac_offset


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
                print(date, end=",", file=csv_file)
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
    hk = tc.hk_request(port)

    # Work out delta needed to reach measurement_position
    delta = position - hk.MTR_ABS_STEPS

    event_log.info(f"Current position is {hk.MTR_ABS_STEPS}, need to move {delta} steps")

    if delta > 0:
        mv_pos_steps(port, delta)
    elif delta < 0:
        mv_neg_steps(port, -delta)
    else:
        event_log.info("No movement needed")


def move_off_endstops(port: serial.rs485.RS485) -> None:
    """
    Make sure that the motor is at neither end stop.

    :param port: The serial port for comms with the instrument.
    """

    event_log.info("Running ABU move_off_endstops")
    hk = tc.hk_request(port)

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
        hk = tc.hk_request(port)

    if not hk.MTR_FLAGS.OUTER and not hk.MTR_FLAGS.BASE:
        event_log.info("Motor is away from end stops")


def fix_double_stop_error(port: serial.rs485.RS485, at_outer: bool) -> None:
    """
    This is code Barry suggested to try to clear the case where both
    endstops are flagging true. It didn't work when trying to fix things
    the other day, but this function has been added to document the
    procedure as something to try out.

    :param port: The serial port for comms with the instrument.
    :param at_outer: Set this to True if you think the instrument is actually at the outer stop, False if you think it's at the base stop.
    """

    # Power on Mech board
    tc.power_control(port, 0x01)

    # Use motor mask to disable DSE, Base and Outer checks
    tc.set_errors(port, 0,0,0,0,0,0,0,True,True,0,0,0,0,True)

    # Set Motor Params
    tc.set_mtr_param(port, 0x17,0x20,0x0f,0x7,0x3200)

    # Move the appropriate direction.
    if at_outer:
        tc.mtr_mov_pos(port, 100)
    else:
        tc.mtr_mov_neg(port, 100)

    # Wait for move to happen.
    time.sleep(1)

    # Read status
    read_hk(port)
