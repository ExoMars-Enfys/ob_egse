from platform import system
import sys
import scripts.sequences as sq

import tc
import logging
import time
import constants as const
from send_cmd import cmd_repeat as repeat

event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")


def LTM_Measurement(port):
    sq.power_up(port)
    # traverse 1
    outer_cal(port)
    time.sleep(2)

    # traverse 2
    base_home(port)
    time.sleep(2)
    mwir_dark_region_start(port)
    time.sleep(2)
    base_home(port)
    tc.mtr_mov_neg(port, 10)
    time.sleep(2)

    # traverse 3
    acquisition(port, 0)
    time.sleep(2)
    tc.mtr_mov_pos(port, 7)
    time.sleep(2)

    # traverse 4
    acquisition(port, 1)
    time.sleep(2)
    tc.mtr_mov_neg(port, 7)
    time.sleep(2)

    # traverse 5
    acquisition(port, 0)
    time.sleep(2)
    tc.mtr_mov_pos(port, 7)
    time.sleep(2)

    # traverse 6
    acquisition(port, 1)
    time.sleep(2)
    tc.mtr_mov_pos(port, 7)
    time.sleep(2)

    # Parking
    park(port)


def outer_cal(port):
    event_log.info("Starting Outer Calibration Sequence")
    repeat(port, tc.mtr_homing, True, True)
    hk = repeat(port, tc.hk_request, port)
    timeout = 1
    # If ABS Steps at 1000 we are already there, otherwise wait for movement
    while (
        not hk.MTR_FLAGS.OUTER
        and not hk.MTR_FLAGS.CAL
        and hk.MTR_ABS_STEPS != 1000
        and timeout <= const.LTM_HOMING_TIMEOUT
    ):
        time.sleep(1)
        timeout += 1
        hk = repeat(port, tc.hk_request, port)
        event_log.info(
            f"Calibrating to the OUTER, waiting for switch to be pressed. - Motor relative steps: {hk.MTR_REL_STEPS}"
        )
    event_log.info("Motor movement finished")
    if timeout >= const.LTM_HOMING_TIMEOUT:
        event_log.error("Outer Homing Timeout Reached")
        event_log.error(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
        event_log.error(f"Motor Flags : OUTER : {hk.MTR_FLAGS.OUTER} , CAL : {hk.MTR_FLAGS.CAL}")
        sys.exit(1)

    # Check motor status now its stopped.

    hk = repeat(port, tc.hk_request, port)
    if hk.MTR_FLAGS.CAL != 1:
        event_log.error(f" Calibration Flag not Asserted : {hk.MTR_FLAGS.CAL}")
    if hk.MTR_FLAGS.DIR != 0:
        event_log.error(f" Calibration Dir not to BASE : {hk.MTR_FLAGS.DIR}")
    if hk.MTR_FLAGS.OUTER != 1:
        event_log.error(f"OUTER Switch Flag raised : {hk.MTR_FLAGS.OUTER}")
    if hk.MTR_FLAGS.BASE != 0:
        event_log.error(f"BASE Switch Flag is not asserted : {hk.MTR_FLAGS.BASE}")
    if hk.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {hk.MTR_FLAGS.MOVING}")
    if hk.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {hk.MTR_FLAGS.HOMING}")


def outer_home(port):
    event_log.info("Starting Outer Homing Sequence")
    repeat(port, tc.mtr_homing, False, True)
    hk = repeat(port, tc.hk_request, port)
    timeout = 1
    while (
        not hk.MTR_FLAGS.OUTER and hk.MTR_ABS_STEPS not in const.LTM_OUTER_TOL and timeout <= const.LTM_HOMING_TIMEOUT
    ):
        time.sleep(1)
        timeout += 1
        hk = repeat(port, tc.hk_request, port)
        event_log.info(
            f"Moving to the Outer, waiting for switch to be pressed. - Motor absolute steps: {hk.MTR_ABS_STEPS}"
        )
    event_log.info("Motor movement finished")

    if timeout >= const.LTM_HOMING_TIMEOUT:
        event_log.error("Outer Homing Timeout Reached")
        event_log.error(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
        event_log.error(f"Motor Flags : OUTER : {hk.MTR_FLAGS.OUTER} , CAL : {hk.MTR_FLAGS.CAL}")
        sys.exit(1)

    # Check motor status now its stopped.
    hk = repeat(port, tc.hk_request, port)
    if hk.MTR_FLAGS.CAL != 0:
        event_log.error(f" Calibration FlagAsserted : {hk.MTR_FLAGS.CAL}")
    if hk.MTR_FLAGS.DIR != 0:
        event_log.error(f" Calibration Dir not to BASE : {hk.MTR_FLAGS.DIR}")
    if hk.MTR_FLAGS.OUTER != 1:
        event_log.error(f"OUTER Switch Flag not raised : {hk.MTR_FLAGS.OUTER}")
    if hk.MTR_FLAGS.BASE != 0:
        event_log.error(f"BASE Switch Flag asserted : {hk.MTR_FLAGS.BASE}")
    if hk.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {hk.MTR_FLAGS.MOVING}")
    if hk.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {hk.MTR_FLAGS.HOMING}")


def base_home(port):
    event_log.info("Starting Base Homing Sequence")
    repeat(port, tc.mtr_homing, False, False)
    hk = repeat(port, tc.hk_request, port)
    timeout = 1
    while not hk.MTR_FLAGS.BASE and hk.MTR_ABS_STEPS not in const.LTM_BASE_TOL and timeout <= const.LTM_HOMING_TIMEOUT:
        time.sleep(1)
        timeout += 1
        hk = repeat(port, tc.hk_request, port)
        event_log.info(
            f"Moving to the Base, waiting for switch to be pressed. - Motor absolute steps: {hk.MTR_ABS_STEPS}"
        )
    event_log.info("Motor movement finished")

    if timeout >= const.LTM_HOMING_TIMEOUT:
        event_log.error("Base Homing Timeout Reached")
        event_log.error(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
        event_log.error(f"Motor Flags : BASE : {hk.MTR_FLAGS.BASE} , CAL : {hk.MTR_FLAGS.CAL}")
        sys.exit(1)

    # Check motor status now its stopped.
    hk = repeat(port, tc.hk_request, port)
    if hk.MTR_FLAGS.CAL != 0:
        event_log.error(f" Calibration FlagAsserted : {hk.MTR_FLAGS.CAL}")
    if hk.MTR_FLAGS.DIR != 0:
        event_log.error(f" Calibration Dir not to BASE : {hk.MTR_FLAGS.DIR}")
    if hk.MTR_FLAGS.OUTER != 0:
        event_log.error(f"OUTER Switch Flag raised : {hk.MTR_FLAGS.OUTER}")
    if hk.MTR_FLAGS.BASE != 1:
        event_log.error(f"BASE Switch Flag is not asserted : {hk.MTR_FLAGS.BASE}")
    if hk.MTR_FLAGS.MOVING != 0:
        event_log.error(f"Motor moving flag still asserted: {hk.MTR_FLAGS.MOVING}")
    if hk.MTR_FLAGS.HOMING != 0:
        event_log.error(f"Motor Homing flag is asserted: {hk.MTR_FLAGS.HOMING}")


def mwir_dark_region_start(port):
    event_log.info("Starting MWIR Dark Region Start Sequence")
    hk = repeat(port, tc.hk_request, port)
    movement_steps = abs(hk.MTR_ABS_STEPS - const.LTM_MWIR_DARK_POS)
    repeat(port, tc.mtr_mov_neg, movement_steps)
    hk = repeat(port, tc.hk_request, port)
    timeout = 1
    while hk.MTR_FLAGS.MOVING and hk.MTR_ABS_STEPS != 8000 and timeout <= const.LTM_HOMING_TIMEOUT:
        time.sleep(1)
        timeout += 1
        hk = repeat(port, tc.hk_request, port)
        event_log.info(f"Moving to the MWIR Dark Position - Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info("MWIR Dark Position reached")

    if timeout >= const.LTM_HOMING_TIMEOUT:
        event_log.error("MWIR Dark Position Timeout Reached")
        event_log.error(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
        event_log.error(f"Motor Flags : MOVING : {hk.MTR_FLAGS.MOVING}")
        sys.exit(1)


def stepping(port, dir, target_pos, steps):
    if dir == 0:
        repeat(port, tc.mtr_mov_neg, steps)
    else:
        repeat(port, tc.mtr_mov_pos, steps)
    hk = repeat(port, tc.hk_request, port)
    while hk.MTR_FLAGS.MOVING:  # TODO - potentially add check for rel steps
        hk = repeat(port, tc.hk_request, port)
    if hk.MTR_ABS_STEPS != target_pos:
        event_log.error(f"Target Position {target_pos} not reached - Motor absolute steps: {hk.MTR_ABS_STEPS}")
        sys.exit(1)

    # event_log.info("Motor movement finished")


def acquisition(port, dir):
    hk = repeat(port, tc.hk_request, port)
    initial_pos = hk.MTR_ABS_STEPS
    if dir == 0:
        dir_sign = -1
    else:
        dir_sign = 1
    for i in range(21):
        target_pos = initial_pos + (i + 1) * 32 * dir_sign
        stepping(port, dir, target_pos, 32)
        event_log.info(f"Dark Region Loop {i + 1} of 21 - Motor absolute steps: {target_pos}")
    initial_pos = target_pos
    for i in range(149):
        target_pos = initial_pos + (i + 1) * 48 * dir_sign
        stepping(port, dir, target_pos, 48)
        event_log.info(f"Open Aperture Loop {i + 1} of 149 - Motor absolute steps: {target_pos}")

    initial_pos = target_pos
    for i in range(21):
        target_pos = initial_pos + (i + 1) * 32 * dir_sign
        stepping(port, dir, target_pos, 32)
        event_log.info(f"Dark Region Loop {i + 1} of 21 - Motor absolute steps: {target_pos}")


def park(port):
    event_log.info("Starting Parked Sequence")
    base_home(port)
    time.sleep(2)
    hk = repeat(port, tc.hk_request, port)
    target_steps = hk.MTR_ABS_STEPS - const.LTM_PARKED
    repeat(port, tc.mtr_mov_neg, target_steps)
    timeout = 1
    while hk.MTR_ABS_STEPS != const.LTM_PARKED and timeout <= const.LTM_PARKING_TIMEOUT:
        time.sleep(1)
        timeout += 1
        hk = repeat(port, tc.hk_request, port)
        event_log.info(f"Parking - Motor absolute steps: {hk.MTR_ABS_STEPS}")
    event_log.info("Motor movement finished")

    if timeout >= const.LTM_PARKING_TIMEOUT:
        event_log.error("Base Homing Timeout Reached")
        event_log.error(f"Motor absolute steps: {hk.MTR_ABS_STEPS}")
        event_log.error(f"Motor Flags : BASE : {hk.MTR_FLAGS.BASE} , CAL : {hk.MTR_FLAGS.CAL}")
        sys.exit(1)
