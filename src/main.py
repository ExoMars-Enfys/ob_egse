# ----Module Imports--------------------------------------------------------------------------------
# Std library
import logging
import time
import atexit
import argparse
from nicegui import ui
from pathlib import Path
import threading


# Local modules
# core
from core_modules import config as config
from core_modules import constants as const
from core_modules import tmstruct as tmstruct

# utilities
from scripts_modules import abu_sequences as abu
from scripts_modules import sequences
from utility_modules import comms as comms
from utility_modules import egse_logger as egse_logger
from utility_modules import psu as psu
from utility_modules import tc as tc
from utility_modules import tm as tm
from utility_modules.send_cmd import cmd_repeat as repeat

# widgets
from widget_modules import parent_window_widget


## -- Setup session ----------------------------------------------------------------------------------------------------
def init_arparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] ",
        prog="ob_egse",
        description="Executes the OB EGSE either in script mode or with the streamlit GUI.",
    )
    parser.add_argument("-prefix", type=ascii, default=const.DEFAULT_PREFIX)
    parser.add_argument("-com", type=int, default=config.DEFAULT_COM_PORT)
    parser.add_argument("-psuport", type=int, default=config.PSU_COM_PORT)
    parser.add_argument("-basedir", type=Path, default=const.DEFAULT_PATH)
    parser.add_argument("-np", "--nopsu", action="store_true")
    parser.add_argument("-s", "--script", action="store_true")
    parser.add_argument("--reload", action="store_true", help="Enable NiceGUI hot reload for development")
    return parser


def setup_logs() -> tuple[logging.Logger, logging.Logger, logging.Logger]:
    if const.LOG_PATH == const.DEFAULT_PATH:
        const.LOG_PATH.mkdir(parents=True, exist_ok=True)

    event_log, info_log, psu_log = egse_logger.get_loggers(const.LOG_PATH, const.LOG_PREFIX, const.DEBUG_LEVEL)

    # Create ACK Byte Log
    ack_log_name = const.DEFAULT_PREFIX + "_ACK.LOG"
    const.ACK_LOG_FH = open(const.LOG_PATH / ack_log_name, "a+", encoding="utf-8")

    # Create CMD Byte Log
    cmd_log_name = const.DEFAULT_PREFIX + "_CMD.LOG"
    const.CMD_LOG_FH = open(const.LOG_PATH / cmd_log_name, "a+", encoding="utf-8")

    # Create HK Byte Log
    hk_log_name = const.DEFAULT_PREFIX + "_HK.LOG"
    const.HK_LOG_FH = open(const.LOG_PATH / hk_log_name, "a+", encoding="utf-8")

    # Create SCI Byte Log
    sci_log_name = const.DEFAULT_PREFIX + "_SCI.LOG"
    const.SCI_LOG_FH = open(const.LOG_PATH / sci_log_name, "a+", encoding="utf-8")

    return (event_log, info_log, psu_log)


def clean_exit(ob_port, psu_port, event_log):
    event_log.info("Running clean exit")
    const.ACK_LOG_FH.close()
    const.CMD_LOG_FH.close()
    const.HK_LOG_FH.close()
    const.SCI_LOG_FH.close()
    if ob_port is not None:
        comms.close_comms(ob_port)
    if psu_port is not None:
        psu.emergencyShutDown(psu_port)
    # psu.close_psu_comms(psuport)

    #! TODO add emergency shutdown to that powers off the OB

# Alun extras - these should go back into a new abu_sequences once
# we're happy.
def wait_movement_complete(port):
    hk = tc.hk_request(port)
    while hk.MTR_FLAGS.MOVING:
        hk = tc.hk_request(port)
        event_log.info(
            "Motor MOVING: Absolute Steps : " + f"{hk.MTR_ABS_STEPS:04d}, Relative Steps: {hk.MTR_REL_STEPS:04d}"
        )
        time.sleep(1)

    event_log.info("Motor movement finished")
    if hk.ERROR_MTR != 0:
        event_log.error(
            "***MOTOR ERROR*** got the following: "
            + f"\n CD : {hk.MTR_ERRORS.CD}"
            + f"\n AB : {hk.MTR_ERRORS.AB}"
            + f"\n ABS : {hk.MTR_ERRORS.ABS}"
            + f"\n DSE : {hk.MTR_ERRORS.DSE}"
        )

def move_to_position(port, abs_pos):
    hk_tm = tc.hk_request(port)
    delta = hk_tm.MTR_ABS_STEPS - abs_pos
    if delta < 0:
        event_log.info(f"Moving to {abs_pos}, which is {-delta} negative steps from {hk_tm.MTR_ABS_STEPS}")
        repeat(ob_port, tc.mtr_mov_neg, -delta)
    elif delta > 0:
        event_log.info(f"Moving to {abs_pos}, which is {delta} positive steps from {hk_tm.MTR_ABS_STEPS}")
        repeat(ob_port, tc.mtr_mov_pos, delta)
    else:
        event_log.info(f"No movement required - already at {abs_pos}")
        return
    wait_movement_complete(port)


def main() -> None:
    parser = init_arparse()
    args = parser.parse_args()
    startup_mode = "OB" if args.script else "EB"
    startup_eb_mode = startup_mode == "EB"
    psu_mode_state = {"ebmode": startup_eb_mode}

    # Setup loggers
    const.LOG_PREFIX = str(args.prefix).strip("'")
    const.LOG_PATH = args.basedir
    (event_log, info_log, psu_log) = setup_logs()

    psu_lock = threading.Lock()
    psu_port = None
    if not args.nopsu:
        psu_com = "COM" + str(args.psuport)
        info_log.info("Initialising PSU Comms on Port " + psu_com)
        try:
            psu_port = psu.init_psu_comms(psu_com)
            psu_port = psu.open_psu_comms(psu_port, args.nopsu)
            psu.setChannels(psu_port, startup_eb_mode)
        except SystemExit:
            info_log.warning(f"PSU initialization failed on {psu_com}; GUI will run without PSU comms")
            psu_port = None

    stop_event = threading.Event()
    hk_pause_event = threading.Event()
    hk_pause_event.set()  # Start with HK polling paused until we know the PSU is on and stable

    rs485_com = "COM" + str(args.com)
    ob_port = None

    info_log.info("Initialising RS-485 Comms on Port " + rs485_com)
    try:
        ob_port = comms.initialise_comms(rs485_com)
        ob_port = comms.open_comms(ob_port)
    except Exception as exc:
        info_log.warning("RS-485 unavailable on %s; starting GUI without OB comms (%s)", rs485_com, exc)
        ob_port = None
    atexit.register(stop_event.set)
    atexit.register(clean_exit, ob_port, psu_port, event_log)

    time.sleep(1)  # Adding a 1 second delay before starting monitoring thread for compensation of OVP
    # TODO Update monitoring thread to start very early
    psu_thread = threading.Thread(
        target=psu.psu_monitor_thread,
        args=(psu_port, startup_eb_mode, stop_event, config.PSU_LOGGING_FREQ, hk_pause_event, psu_mode_state, psu_lock),
        daemon=True,
    )

    hk_thread = None
    port_lock = threading.Lock()

    if args.script:
        info_log.info("Running Script")
        psu.switch_psu_channel(psu_port, channel=1, state=1)  # Switch on PSU
        psu.switch_psu_channel(psu_port, channel=2, state=1)
        time.sleep(2.5)
        psu.switch_psu_channel(psu_port, channel=3, state=1)
        time.sleep(1)  # Adding a 1 second delay for PSU to power on and stabilize before resuming HK polling
        psu_thread.start()
        hk_pause_event.clear()  # Resume HK polling

        # First HK
        # abu.read_hk(ob_port)

        # ------------------------------------------------------------------------------------------
        # User add commands or sequences from here:
        # ------------------------------------------------------------------------------------------
        sequences.parse_hk(ob_port)

        # Replicate the procedures that abu.* run so we can remove
        # abu_sequences from the equation.

        # This one does power_control and set_mtr_param
        sq.power_up(ob_port)

        # We've found that, without a 3s delay after tc.power_control, we
        # get a NAK back from the motor movements below.
        #time.sleep(3) # Commented for now, while we try out sq.power_up.

        # Cal to BASE
        repeat(ob_port, tc.mtr_homing, True, False)
        hk_tm = tc.hk_request(ob_port)
        if not hk_tm.MTR_FLAGS.BASE:
            event_log.info("Moving to the BASE, waiting for switch to be pressed.")
            wait_movement_complete(ob_port)
        else:
            event_log.info("Motor Did not Move, Base Flag Asserted")

        # Check motor status now its stopped.
        hk_tm = tc.hk_request(ob_port)
        if hk_tm.MTR_FLAGS.CAL != 1:
            event_log.error(f" Calibration Flag not Asserted : {hk_tm.MTR_FLAGS.CAL}")
        if hk_tm.MTR_FLAGS.DIR != 0:
            event_log.error(f" Calibration Dir not to BASE : {hk_tm.MTR_FLAGS.DIR}")
        if hk_tm.MTR_FLAGS.OUTER != 0:
            event_log.error(f"OUTER Switch Flag raised : {hk_tm.MTR_FLAGS.OUTER}")
        if hk_tm.MTR_FLAGS.BASE != 1:
            event_log.error(f"BASE Switch Flag is not asserted : {hk_tm.MTR_FLAGS.BASE}")
        if hk_tm.MTR_FLAGS.MOVING != 0:
            event_log.error(f"Motor moving flag still asserted: {hk_tm.MTR_FLAGS.MOVING}")
        if hk_tm.MTR_FLAGS.HOMING != 0:
            event_log.error(f"Motor Homing flag is asserted: {hk_tm.MTR_FLAGS.HOMING}")
        if hk_tm.MTR_ABS_STEPS != 9960:
            event_log.error(f"Motor ABS Steps Do not match expected ABS : {hk_tm.MTR_ABS_STEPS} , Expected : 9960")
        if hk_tm.MTR_REL_STEPS == 0:
            event_log.error(f"Motor Steps Do not match expected REL : {hk_tm.MTR_REL_STEPS} , Expected : 0")
        event_log.info(f"Motor relative steps moved: {hk_tm.MTR_REL_STEPS}")
        event_log.info(f"Motor absolute steps: {hk_tm.MTR_ABS_STEPS}")

        # Home to outer
        repeat(ob_port, tc.mtr_homing, False, True)
        hk_tm = tc.hk_request(ob_port)
        if not hk_tm.MTR_FLAGS.OUTER:
            event_log.info("Moving to outer, waiting for switch to be pressed.")
            wait_movement_complete(ob_port)
        else:
            event_log.info("Motor Did not Move, Outer Flag Asserted")

        # Check motor status now its stopped.
        hk_tm = tc.hk_request(ob_port)
        if hk_tm.MTR_FLAGS.CAL != 0:
            event_log.error(f" Calibration Flag Asserted : {hk_tm.MTR_FLAGS.CAL}")
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
        if hk_tm.MTR_REL_STEPS == 0:
            event_log.error("Motor Steps Do not match expected : " + f"\n REL : {hk_tm.MTR_REL_STEPS} , Expected : 0")
        event_log.info(f"Motor relative steps moved: {hk_tm.MTR_REL_STEPS}")
        event_log.info(f"Motor absolute steps: {hk_tm.MTR_ABS_STEPS}")

        # Now move back to 9960.
        move_to_position(ob_port, 9960)

        # SWIR DAC offset - we'll use the abu.* version for this, since it's biggish.
        swir_offset = abu.find_dac_offset(ob_port, "SWIR", 5000, 1)
        event_log.info(f"SWIR offset = {swir_offset}")

        # Now down to 8000.
        move_to_position(ob_port, 8000)

        # MWIR DAC offset
        mwir_offset = abu.find_dac_offset(ob_port, "MWIR", 5000, swir_offset)
        event_log.info(f"MWIR offset = {mwir_offset}")

        event_log.info("Starting Science Measurements")

        # Take samples from 1200 up to 9960 in steps of 30.
        for position in range(1200, 9960, 30):
            move_to_position(position)
            sci = tc.sci_request(ob_port, sci_adc_samp=4, sci_adc_skip=100)

        ## Clear Errors
        # tc.clear_errors(ob_port)

        ######## 2025-09-26 automation for darks
        #   Home to outer
        # abu.home_to_outer(ob_port)

        # 5 times over for dark data...
        # for i in range(5):
        # #   Move to 8000 and run SWIR/MWIR binary chops
        # abu.move_abs_pos(8000)
        # swir_offset = abu.find_dac_offset(ob_port, "SWIR", 4000, 1)
        # mwir_offset = abu.find_dac_offset(ob_port, "MWIR", 4000, swir_offset)

        # #   Start new log and do measurement scan in the forward direction.
        # open_new_logs()
        # abu.measurement_scan(ob_port, 30, 4, 100)

        # open_new_logs()
        # abu.measurement_scan_neg(ob_port, 30, 4, 100)
        ######## end of 2025-09-26 automation for darks

        # abu.mv_abs_pos(ob_port, 100)
        # abu.read_hk(ob_port)

        # Move to position 510 and try to set DAC offsets
        # abu.dac_auto_offset(ob_port)

        ## Move and Measure in a loop (set values in abu_sequences)
        # abu.move_and_measure_loop(ob_port, 0)

        # sweep through SWIR DAC offset
        # abu.sweep_offset_swir(ob_port, 5)
        # sweep through MWIR DAC offset
        # abu.sweep_offset_mwir(ob_port, 1)

        # move to 7600 absolute (dark zone)
        # abu.mv_pos_steps(ob_port, 7600-283)
        # abu.mv_neg_steps(ob_port, 1358)

        # abu.set_offset_and_check_sci(ob_port, 2112, 1544, 4, 100)

        ## Move to absolute position and take a reading
        # abu.mv_abs_pos(ob_port, 8000)
        # abu.move_and_measure(ob_port, 0)

        # swir binary chop
        # abu.swir_binary_chop(ob_port, 100, 4, 100)

        # mwir binary chop
        # abu.mwir_binary_chop(ob_port, 1600, 4, 100)

        # Measurement scan with found (or set) values
        # abu.abu_measurement_scan(ob_port, 30, 4, 100)

        # Measurement scan with found (or set) values looping
        # abu.abu_measurement_scan_loop(ob_port)

        ############################################
        ############################################
        # log_dir = Path(const.HK_LOG_FH.name).parent
        # choplog = open(log_dir / "swir-mwir.log", "w")

        ## CSV header
        # print("Seconds,SWIR_OFFSET,MWIR_OFFSET,HT_SINK_TRP,SWIR_TEMP,SW_H,MW_H", file=choplog)

        ## Where we'll measure.
        # abu.mv_abs_pos(ob_port, 8600)
        # while True:
        #    swir_offset = abu.find_dac_offset(ob_port, "SWIR", 200, 1)
        #    mwir_offset = abu.find_dac_offset(ob_port, "MWIR", 1500, swir_offset)
        #    hk_tm = tc.hk_request(ob_port)
        #    sci = tc.sci_request(ob_port, 4, 100)
        #    print(f"HT_SINK_TEMP={sci.HT_SINK_TEMP}")
        #    time.sleep(30)

        ## Run for an hour.
        # start_time = time.time()
        # end_time = start_time + 5400
        # while time.time() < end_time:
        ## Do full binary chop on swir and mwir, with
        ## swir target=200 and mwir target=1500.
        #    swir_offset = abu.find_dac_offset(ob_port, "SWIR", 200, 1)
        #    mwir_offset = abu.find_dac_offset(ob_port, "MWIR", 1500, swir_offset)

        ## Get a science packet so we can note the TRP values in our log.
        #    sci = tc.sci_request(ob_port, 4, 100)

        #    print(f"{time.time()-start_time:.0f},{swir_offset},{mwir_offset},{sci.HT_SINK_TEMP},{sci.SWIR_TEMP},{sci.SWIR_HIGH},{sci.MWIR_HIGH}", file=choplog)
        #    choplog.flush()
        #    event_log.info(f"SWIR_OFFSET: {sci.SWIR_OFFSET:5d}" +
        #          f" MWIR_OFFSET: {sci.MWIR_OFFSET:5d}" +
        #          f" SWIR_HIGH: {sci.SWIR_HIGH:5d}" +
        #          f" MWIR_HIGH: {sci.MWIR_HIGH:5d}" +
        #          f" HT_SINK_TEMP: {sci.HT_SINK_TEMP:5d}" +
        #          f" SWIR_TEMP: {sci.SWIR_TEMP:5d}")
        #    time.sleep(10)

        # choplog.close()
        ###############################

        # abu.mv_abs_pos(ob_port, 7500)
        # swir_offset = abu.swir_binary_chop(ob_port, 100, 4, 100)
        # abu.mwir_binary_chop(ob_port, swir_offset, 4, 100)

        # for i in range(7200):
        #    abu.move_and_measure(ob_port, 0)
        #    time.sleep(1)

        # Cal to base then Home to outer to count the steps
        # abu.home_to_base (ob_port)
        # abu.home_to_outer (ob_port)

        # ------------------------------------------------------------------------------------------
        # Clean up and exit
        # ------------------------------------------------------------------------------------------

        # Ensure we're off either endstop when finishing up.
        #abu.move_off_endstops(ob_port)

        # Get final HK
        #abu.read_hk(ob_port)

        # Auto-generate CSV files from HK and SCI logs
        # abu.convert_logs()
        # Commented out for now

        stop_event.set()

    else:
        info_log.info("Running GUI")
        if psu_port is not None and not psu_thread.is_alive():
            psu_thread.start()
        parent_window_widget.build_ui(
            default_mode=startup_mode,
            psu_port=psu_port,
            psu_lock=psu_lock,
            port_lock=port_lock,
            stop_event=stop_event,
            psu_mode_state=psu_mode_state,
        )
        ui.run(port=8085, reload=args.reload, show=not args.reload)
        # TODO What about stop_envent?

    event_log.info("Shutting down")
    if psu_thread.is_alive():
        event_log.info("Waiting for PSU monitor thread to finish")
        psu_thread.join(timeout=1.0)  # Wait for the PSU monitor thread to finish

    if hk_thread is not None:
        if hk_thread.is_alive():
            event_log.info("Waiting for HK polling thread to finish")
            hk_thread.join(timeout=1.0)  # Wait for the HK polling thread to finish


if __name__ in {"__main__", "__mp_main__"}:
    main()

# TODO Fix display of HK
