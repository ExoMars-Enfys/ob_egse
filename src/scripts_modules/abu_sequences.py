"""Sequences for use by ABU."""

import logging
import pathlib
import time

import serial

import scripts_modules.measurement_table as mt
from core_modules import constants as const
from egse_dump_decoder import EGSEDumpDecoder
from scripts_modules import sequences as sq
from utility_modules import tc, tm
from utility_modules.send_cmd import cmd_repeat as repeat

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")

# ----Constants Setup-------------------------------------------------------------------------------

# Sampling parameters
SCI_ADC_SAMP = 4
SCI_ADC_SKIP = 100

# Binary chop parameters
SWIR_BINARY_CHOP_LOCATION = 9600
SWIR_BINARY_CHOP_TARGET = 5000
MWIR_BINARY_CHOP_LOCATION = 8000
MWIR_BINARY_CHOP_TARGET = 15000

# Motor parameters
MTR_CURRENT = 64
MTR_GUARD_SELECT = 0
MTR_CHOP = 60
MTR_SPEED = 8

# ----Helper Functions------------------------------------------------------------------------------

def hk_request(port: serial.rs485.RS485) -> tm.HK:
    """A thin wrapper around tc.hk_request."""
    return tc.hk_request(port)


def sci_request(port: serial.rs485.RS485) -> tm.SCI:
    """A thin wrapper around tc.sci_request.

    This specifies default values for sci_adc_samp and sci_adc_skip
    """
    return tc.sci_request(port, SCI_ADC_SAMP, SCI_ADC_SKIP)


def check_sci(port: serial.rs485.RS485) -> tm.SCI:
    """A thin wrapper around sequences.check_sci.

    Again, this specifies default values for sci_adc_samp and sci_adc_skip
    """
    return sq.check_sci(port, SCI_ADC_SAMP, SCI_ADC_SKIP)


def read_hk(port: serial.rs485.RS485) -> None:
    """A thin wrapper around sequences.parse_hk.

    I'm not sure why we've ended up with this duplication in abu_sequences,
    so I'm going to replace the body with a call out to sequences.parse_hk.
    """
    sq.parse_hk(port)


# ----Low(ish) level operations---------------------------------------------------------------------


def power_on_mech(port: serial.rs485.RS485) -> None:
    """Check mechanism is powered. If not enable and set motor parameters."""
    hk_tm = hk_request(port)
    if not (hk_tm.PWR_STAT & 0x01):
        # Perform bitwise OR in case Detector is on and we want to leave it powered
        repeat(port, tc.power_control, hk_tm.PWR_STAT | 0x01)

    # Set motor parameters after turning on.
    set_motor_parameters(port)


def wait_movement_complete(port: serial.rs485.RS485, num_steps_expected: int = 8960) -> None:
    """Wait until a movement operation has completed.

    Uses the optional num_steps_expected field to optimise polling for fast response.
    """

    hk_tm = hk_request(port)
    while hk_tm.MTR_FLAGS.MOVING:
        event_log.info(
            "Motor MOVING: Absolute Steps : " + f"{hk_tm.MTR_ABS_STEPS:04d}, Relative Steps: {hk_tm.MTR_REL_STEPS:04d}"
        )
        time.sleep(0.1 if num_steps_expected < 640 else 1)
        hk_tm = hk_request(port)

    if hk_tm.ERROR_MTR != 0:
        event_log.error(
            f"***MOTOR ERROR*** got the following: "
            f"\n CD : {hk_tm.MTR_ERRORS.CD}"
            f"\n AB : {hk_tm.MTR_ERRORS.AB}"
            f"\n ABS : {hk_tm.MTR_ERRORS.ABS}"
            f"\n DSE : {hk_tm.MTR_ERRORS.DSE}"
        )


def mv_pos_steps(port: serial.rs485.RS485, steps: int) -> None:
    """Move the mechanism a certain number of steps positive (towards the base).

    Automatically checks that we are not already at the base.
    """

    event_log.info("Running ABU move positive steps")

    # First check that there we are are not already at the base.
    hk_tm = hk_request(port)
    if hk_tm.MTR_FLAGS.BASE:
        event_log.error("Request to move positive steps but already at the base, skipping movement")
        return

    # Then move the desired number of steps
    repeat(port, tc.mtr_mov_pos, steps)

    # Wait until no longer moving
    wait_movement_complete(port, steps)


def mv_neg_steps(port: serial.rs485.RS485, steps: int) -> None:
    """Move the mechanism a certain number of steps negative (towards the outer).

    Automatically checks that we are not already at the outer.
    """
    event_log.info("Running ABU move negative steps")

    # First check that we are not already at the outer.
    hk_tm = hk_request(port)
    if hk_tm.MTR_FLAGS.OUTER:
        event_log.error("Request to move negative steps but already at the outer, skipping movement")
        return

    # Then move the desired number of steps
    repeat(port, tc.mtr_mov_neg, steps)

    # Wait until no longer moving
    wait_movement_complete(port, steps)


def mv_abs_pos(port: serial.rs485.RS485, position: int) -> None:
    """Move to an absolute position.

    Get the current motor position, then send a relative command to
    take it to the specified position.

    :param port: The serial port for comms with the instrument.
    :param position: The absolute motor position to move to.
    """
    event_log.info(f"Running ABU mv_abs_pos({position})")

    # Get the current position.
    hk = hk_request(port)

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


def choose_dac_offsets(port: serial.rs485.RS485) -> None:
    """Select SWIR and MWIR DAC offsets using the default locations and targets."""
    # SWIR binary chop
    mv_abs_pos(port, SWIR_BINARY_CHOP_LOCATION)
    swir_offset = find_dac_offset(port, "SWIR", SWIR_BINARY_CHOP_TARGET, 1)
    event_log.info(f"SWIR offset = {swir_offset}")

    # MWIR binary chop.
    mv_abs_pos(port, MWIR_BINARY_CHOP_LOCATION)
    mwir_offset = find_dac_offset(port, "MWIR", MWIR_BINARY_CHOP_TARGET, swir_offset)
    event_log.info(f"MWIR offset = {mwir_offset}")


def do_table_scan(port: serial.rs485.RS485,
        table: mt.MeasurementTable,
        table_start_position: int|None = None,
        table_end_position: int|None = None
    ) -> None:
    """Take science measurements across a MeasurementTable object."""

    # Run through a measurement table - we tell the iterator the
    # current motor steps so it can align things where we expect them to be.
    hk_tm = hk_request(port)

    for relative_steps, absolute_position in table.scan(
                start_motor_steps=hk_tm.MTR_ABS_STEPS,
                start=table_start_position,
                end=table_end_position
    ):
        # Move the desired number of steps, if any.
        if relative_steps != 0:
            event_log.info(f"Moving {relative_steps} step(s) to reach absolute position {absolute_position}")
            if relative_steps < 0:
                repeat(port, tc.mtr_mov_neg, -steps)
            else:
                repeat(port, tc.mtr_mov_pos, steps)

            # Wait until no longer moving
            wait_movement_complete(port, steps)
        else:
            event_log.info(f"No movement needed for the next science reading")

        # Request a Science Measurement and log the result.
        sci = sci_request(port)
        event_log.info(
            f"ABS_STEPS: {sci.MTR_ABS_STEPS:04d}"
            f"   SWIR_OFFSET: {sci.SWIR_OFFSET:04d}"
            f"   MWIR_OFFSET: {sci.MWIR_OFFSET:04d}"
            f"\t\t SW_L: {sci.SWIR_LOW:04d}"
            f"   SW_M: {sci.SWIR_MED:04d}"
            f"   SW_H: {sci.SWIR_HIGH:04d}"
            f"\t MW_L: {sci.MWIR_LOW:04d}"
            f"   MW_M: {sci.MWIR_MED:04d}"
            f"   MW_HH: {sci.MWIR_HIGH:04d}"
            f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}"
            f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}"
        )

        # Also request a HK so we've got other TRP values. This is
        # purely there for debugging drift and is probably not needed on the
        # EB.
        hk_tm = hk_request(port)


def set_motor_parameters(port: serial.rs485.RS485) -> None:
    """Set default motor parameters and confirm values."""

    repeat(port, tc.set_mtr_param, MTR_CURRENT, MTR_GUARD_SELECT, MTR_CHOP, MTR_SPEED)
    hk_tm = hk_request(port)
    if (
        hk_tm.MTR_CURRENT != MTR_CURRENT or
        hk_tm.MTR_GUARD_SELECT != MTR_GUARD_SELECT or
        hk_tm.MTR_CHOP != MTR_CHOP or
        hk_tm.MTR_SPEED != MTR_SPEED
    ):
        event_log.error(
            f"OB Parameters not initialized correctly:"
            f"\n Current : {hk_tm.MTR_CURRENT}                ~ Expected : {MTR_CURRENT}"
            f"\n Guard Select : {hk_tm.MTR_GUARD_SELECT}      ~ Expected : {MTR_GUARD_SELECT}"
            f"\n Chopper : {hk_tm.MTR_CHOP}                  ~ Expected : {MTR_CHOP}"
            f"\n Speed : {hk_tm.MTR_SPEED}                   ~ Expected : {MTR_SPEED}"
        )


def set_offset_and_check_sci(port: serial.rs485.RS485, swir_offset: int, mwir_offset: int) -> None:
    """Apply DAC offsets and check that they're now reported by HK and SCI.

    Function that will power the detector board if it isn't already.
    Apply the offsets, set within the variables.
    Automatically request a science packet and ensure that the packet contents matches those set.
    """
    event_log.info("Running abu set_offset_and_check_sci")

    # Check detector powered, if not enable.
    hk_tm = hk_request(port)
    if not (hk_tm.PWR_STAT & 0x02):
        # Perform bitwise OR in case Mechanism is on and we want to leave it powered
        repeat(port, tc.power_control, hk_tm.PWR_STAT | 0x02)

    # Set SWIR and MWIR offset
    repeat(port, tc.sci_offset, swir_offset, mwir_offset)

    hk_tm = hk_request(port)
    if hk_tm.SWIR_OFFSET != swir_offset:
        event_log.error(f"SWIR offset not updated in HK. Got {hk_tm.SWIR_OFFSET}")
    if hk_tm.MWIR_OFFSET != mwir_offset:
        event_log.error(f"MWIR offset not updated in HK. Got {hk_tm.MWIR_OFFSET}")

    # Take SCI reading and check.
    sci = check_sci(port)
    if sci.SWIR_OFFSET != swir_offset:
        event_log.error(f"SWIR offset not updated in SCI. Got {sci.SWIR_OFFSET}")
    if sci.MWIR_OFFSET != mwir_offset:
        event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}")


# ----High(er) level operations---------------------------------------------------------------------


def home_to_base(port: serial.rs485.RS485, calibrate: bool = False) -> None:
    """Home to base with optional calibration.

    This function powers the Mechanism board (if it isn't already).
    Then commands the motor to HOME to BASE, possibly with calibration.
    As it moves it will report the relative and absolute steps.
    After movement is complete, it checks the general state is as expected.
    """

    event_log.info(f"Running abu home_to_base with calibrate={calibrate}")

    # Ensure mech is turned on.
    power_on_mech(port)

    # Home to base, optionally with calibration.
    repeat(port, tc.mtr_homing, calibrate, False)

    # Check to see if at the Base
    hk_tm = hk_request(port)
    if not hk_tm.MTR_FLAGS.BASE:
        event_log.info("Moving to the base, waiting for switch to be pressed.")
        wait_movement_complete(port)
        event_log.info("Motor movement finished")
    else:
        event_log.error("Motor Did not Move, Base Flag Asserted")

    # Check motor status now its stopped.
    hk_tm = hk_request(port)
    if calibrate:
        if hk_tm.MTR_FLAGS.CAL == 0:
            event_log.error(f" Calibration Flag unexpectedly not Asserted : {hk_tm.MTR_FLAGS.CAL}")
    else:
        if hk_tm.MTR_FLAGS.CAL != 0:
            event_log.error(f" Calibration Flag unexpectedly Asserted : {hk_tm.MTR_FLAGS.CAL}")
    if hk_tm.MTR_FLAGS.DIR != 0:
        event_log.error(f" Calibration Dir not to Base : {hk_tm.MTR_FLAGS.DIR}")
    if hk_tm.MTR_FLAGS.OUTER != 0:
        event_log.error(f"OUTER Switch Flag raised : {hk_tm.MTR_FLAGS.OUTER}")
    if hk_tm.MTR_FLAGS.BASE != 1:
        event_log.error(f"Base Switch Flag not raised : {hk_tm.MTR_FLAGS.BASE}")
    if hk_tm.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {hk_tm.MTR_FLAGS.MOVING}")
    if hk_tm.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {hk_tm.MTR_FLAGS.HOMING}")

    if calibrate and hk_tm.MTR_ABS_STEPS != 9960:
        event_log.error(f"Motor ABS Steps Do not match expected ABS : {hk_tm.MTR_ABS_STEPS} , Expected : 9960")

    event_log.info(f"Motor relative steps: {hk_tm.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {hk_tm.MTR_ABS_STEPS}")


def cal_motor_to_base(port: serial.rs485.RS485) -> None:
    """This is now a thin wrapper around home_to_base."""
    home_to_base(port, calibrate=True)


def home_to_outer(port: serial.rs485.RS485, calibrate: bool = False) -> None:
    """Home to outer, with optional calibration.

    This function powers the Mechanism board (if it isn't already).
    Then commands the motor to HOME to OUTER, possibly with calibration.
    As it moves it will report the relative and absolute steps.
    After movement is complete, it checks the general state is as expected.
    """

    event_log.info(f"Running abu home_to_outer with calibrate={calibrate}")

    # Ensure mechanism is turned on.
    power_on_mech(port)

    # Home to outer, optionally with calibration.
    repeat(port, tc.mtr_homing, calibrate, True)

    # Check to see if at the Outer
    hk_tm = hk_request(port)
    if not hk_tm.MTR_FLAGS.OUTER:
        event_log.info("Moving to outer, waiting for switch to be pressed.")
        wait_movement_complete(port)
        event_log.info("Motor movement finished")
    else:
        event_log.info("Motor Did not Move, Outer Flag Asserted")

    # Check motor status now its stopped.
    hk_tm = hk_request(port)
    if calibrate:
        if hk_tm.MTR_FLAGS.CAL == 0:
            event_log.error(f" Calibration Flag unexpectedly not asserted : {hk_tm.MTR_FLAGS.CAL}")
    else:
        if hk_tm.MTR_FLAGS.CAL != 0:
            event_log.error(f" Calibration Flag unexpectedly asserted : {hk_tm.MTR_FLAGS.CAL}")
    if hk_tm.MTR_FLAGS.DIR != 1:
        event_log.error(f" Calibration Dir not to Outer : {hk_tm.MTR_FLAGS.DIR}")
    if hk_tm.MTR_FLAGS.OUTER != 1:
        event_log.error(f"OUTER Switch Flag not asserted : {hk_tm.MTR_FLAGS.OUTER}")
    if hk_tm.MTR_FLAGS.BASE != 0:
        event_log.error(f"Base Switch Flag is asserted : {hk_tm.MTR_FLAGS.BASE}")
    if hk_tm.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {hk_tm.MTR_FLAGS.MOVING}")
    if hk_tm.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {hk_tm.MTR_FLAGS.HOMING}")

    if calibrate and hk_tm.MTR_ABS_STEPS != 1000:
        event_log.error(f"Motor ABS Steps does not match expected : {hk_tm.MTR_ABS_STEPS}, Expected 1000")

    event_log.info(f"Motor relative steps moved: {hk_tm.MTR_REL_STEPS}")
    event_log.info(f"Motor absolute steps: {hk_tm.MTR_ABS_STEPS}")


def cal_motor_to_outer(port: serial.rs485.RS485) -> None:
    """This is now a thin wrapper around home_to_outer."""
    home_to_outer(port, calibrate=True)


def move_and_measure(port: serial.rs485.RS485, steps: int) -> None:
    """Move the specified number of steps forward or backward and then takes a measurement.

    0 steps can be entered and the sequence will just measure the same point once again.

    This sequence should be executed once the motor has been HOMING and the offsets applied.

    The motor moves from the Outer to Base using (positive steps)
    """
    event_log.info("Running abu move_and_measure")

    if steps > 0:
        mv_pos_steps(port, steps)
    elif steps < 0:
        mv_neg_steps(port, abs(steps))
    else:
        event_log.info("No need to move any steps, proceeding to measurement")

    # Request a Science Mesaurement and log to the screen.
    sci = sci_request(port)
    hk_tm = hk_request(port)
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


def measurement_scan(port: serial.rs485.RS485, step_spacing: int = 30) -> None:
    """Performs a very basic Enfys science measurement.

    Homes and Calibrates to Base
    Goes to the Outer
    Drives across the whole range of the mechanism using the step_spacing specified in the function
    Halts once Base Stop is reached
    """
    event_log.info("Running ABU Measurement Scan")

    # Not entirely sure why this is here.
    _ = hk_request(port)

    # Cal to Base
    cal_motor_to_base(port)

    # Home to Outer
    home_to_outer(port)

    # Measurement sequence
    # TODO! Emulate Dark Offset and Edge finding (with SWIR and broad lamp)
    event_log.info("Starting Science Measurements")
    move_and_measure(port, 0)
    for _ in range(0, 8900, step_spacing):
        move_and_measure(port, step_spacing)

    event_log.info("Science Measurements Completed!!")


def measurement_scan_loop(port: serial.rs485.RS485) -> None:
    """Run 20 measurement scans."""

    for _ in range(0, 20, 1):
        measurement_scan(port, 30)


def measurement_scan_neg(port: serial.rs485.RS485, step_spacing: int = 30) -> None:
    """Performs a very basic Enfys science measurement, in reverse direction."""
    event_log.info("Running ABU Measurement Scan")

    # Not entirely sure why this is here.
    _ = hk_request(port)

    # Cal to Base
    cal_motor_to_base(port)

    # Measurement sequence
    # TODO! Emulate Dark Offset and Edge finding (with SWIR and broad lamp)
    event_log.info("Starting Science Measurements")
    move_and_measure(port, 0)
    for _ in range(0, 8900, step_spacing):
        move_and_measure(port, -step_spacing)

    event_log.info("Science Measurements Completed!!")


def sweep_offset_mwir(port: serial.rs485.RS485, start_value: int = 0, end_value: int = 4095, step: int = 16) -> None:
    """Sweep through MWIR DAC offset over the specified range of values.

    A science reading is the acquired at each DAC offset.
    """
    event_log.info("Running ABU MWIR Sweep")
    for offset in range(start_value, end_value + 1, step):
        set_offset_and_check_sci(port, 100, offset)


def sweep_offset_swir(port: serial.rs485.RS485, start_value: int = 0, end_value: int = 4095, step: int = 16) -> None:
    """Sweep through SWIR DAC offset over the specified range of values.

    A science reading is the acquired at each DAC offset.
    """
    event_log.info("Running ABU SWIR Sweep")
    for offset in range(start_value, end_value + 1, step):
        set_offset_and_check_sci(port, offset, 100)


def first_power_on_cal_base(port: serial.rs485.RS485) -> None:
    """Power on sequence with calibration to base.

    Very simple sequence that powers on both sub-systems.
    Then Calibrates the mech to BASE
    """
    event_log.info("Running ABU First power on, cal to Base, home to outer")

    # Power up motor and Detector
    repeat(port, tc.power_control, 0x3)

    # We've found that, without a 3s delay after tc.power_control, we
    # get a NAK back from the motor movements below.
    time.sleep(3)

    cal_motor_to_base(port)


def first_power_on_cal_outer(port: serial.rs485.RS485) -> None:
    """Power on sequence with calibration to outer.

    Very simple sequence that powers on both sub-systems.
    Then Calibrates the mech to OUTER.
    """
    event_log.info("Running ABU First power on, cal to Outer")

    # Power up motor and Detector
    repeat(port, tc.power_control, 0x3)

    # We've found that, without a 3s delay after tc.power_control, we
    # get a NAK back from the motor movements below.
    time.sleep(3)

    cal_motor_to_outer(port)


def find_dac_offset(
    port: serial.rs485.RS485,
    sensor_name: str,
    target_output: int,
    fixed_offset: int,
    max_miss: int = 1600,
) -> None:
    """Perform binary chop on a DAC offset.

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
    :return: The DAC offset that gives an output closest to the target value.
    """
    event_log.info(f"Running abu targeted_binary_chop for {sensor_name} with target value {target_output}")

    if sensor_name not in ("MWIR", "SWIR"):
        event_log.error(f"For DAC offsets, sensor name must be either MWIR or SWIR, not {sensor_name}")

    # Check detector powered, if not enable.
    hk = hk_request(port)
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
            sci = check_sci(port)
            if sci.MWIR_OFFSET != test_value:
                event_log.error(f"MWIR offset not updated in SCI. Got {sci.MWIR_OFFSET}, Expected: {test_value}")

            # Copy the reading so the rest of the loop doesn't depend on sensor.
            reading = sci.MWIR_HIGH
        else:
            # Ditto for SWIR.
            repeat(port, tc.sci_offset, test_value, fixed_offset)
            sci = check_sci(port)
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
    """Generate CSV logs for convenience.

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

        with pathlib.Path.open(csvname, "w") as csv_file:
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
        with pathlib.Path.open(csvname, "w") as csv_file:
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


def move_off_endstops(port: serial.rs485.RS485) -> None:
    """Make sure that the motor is at neither end stop.

    :param port: The serial port for comms with the instrument.
    """
    event_log.info("Running ABU move_off_endstops")
    hk = hk_request(port)

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
        hk = hk_request(port)

    if not hk.MTR_FLAGS.OUTER and not hk.MTR_FLAGS.BASE:
        event_log.info("Motor is away from end stops")

def measurement_table_scan(port: serial.rs485.RS485,
        table_number: int,
        table_start_position: int|None = None,
        table_end_position: int|None = None,
        dark_table_0: int = 0,
        dark_table_1: int = 1
    ) -> None:
    """Perform the basic Enfys science measurement table operation.

    After an earlier Calibration to Outer and home to base!!!
    Does ABC at SWIR and MWIR DAC locations.
    Uses predefined table from measurement_table.py to generate a list of locations for taking readings.
    """
    event_log.info(f"Running ABU Measurement Table Scan using table {table_number} ({mt.predefined[table_number].name})")

    table = mt.MeasurementTable(
        mt.predefined[table_number].relative_table,
        before_table=mt.predefined[dark_table_0],
        after_table=mt.predefined[dark_table_1],
        name=mt.predefined[table_number].name,
    )

    choose_dac_offsets(port)

    # FIXME - should we home to outer and check motor steps at this point?

    event_log.info("Starting Science Measurements")

    do_table_scan(port, table, table_start_position=table_start_position, table_end_position=table_end_position)

    # FIXME - should we home to base and check motor steps at this point?

    event_log.info("Science Measurements Completed")


def measurement_mode2(port: serial.rs485.RS485,
        measurement_location: int,
        interval_seconds: float,
        total_duration_seconds: float,
        dark_table_0: int = 0,
        dark_table_1: int = 1
    ) -> None:
    """Perform the basic Enfys science measurement at a single position.

    After an earlier Calibration to Outer and home to base!!!
    Does ABC at SWIR and MWIR DAC locations.
    Scans first dark table.
    Moves to specified position.
    Repeatedly requests science packets, pausing interval_seconds between
    requests, until total_duration_seconds have passed.
    """
    event_log.info(
        f"Running ABU Mode2 Scan at {measurement_location}: "
        f"samples at {interval_seconds}s intervals for {total_duration_seconds}s"
    )

    choose_dac_offsets(port)

    event_log.info("Starting Science Measurements")

    # FIXME - should we home to outer and check motor steps at this point?

    # Scan dark table 0.
    do_table_scan(port, mt.predefined[dark_table_0])

    # Move to measurement location
    mv_abs_pos(port, measurement_location)

    end_time = time.time() + total_duration_seconds
    while time.time() < end_time:
        # Request a Science Measurement and log the result.
        sci = sci_request(port)
        event_log.info(
            f"\t\t SW_L: {sci.SWIR_LOW:04d}"
            f"   SW_M: {sci.SWIR_MED:04d}"
            f"   SW_H: {sci.SWIR_HIGH:04d}"
            f"\t MW_L: {sci.MWIR_LOW:04d}"
            f"   MW_M: {sci.MWIR_MED:04d}"
            f"   MW_HH: {sci.MWIR_HIGH:04d}"
            f"\t\t HT_SINK_TEMP: {sci.HT_SINK_TEMP:04d}"
            f"   SWIR_TEMP: {sci.SWIR_TEMP:04d}"
        )
        time.sleep(interval_seconds)

    # Scan dark table 1.
    do_table_scan(port, mt.predefined[dark_table_1])

    # FIXME - should we home to base and check motor steps at this point?

    event_log.info("Science Measurements Completed")
