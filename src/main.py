# ----Module Imports--------------------------------------------------------------------------------
# Std library
import logging
import time
import sys
import atexit
import argparse
from pathlib import Path
from datetime import datetime
import threading

# Local modules
import comms
import constants as const
import egse_logger
import gui
import psu
import scripts.sequences as sq
import scripts.error_checks as ec
import scripts.abu_sequences as abu
import send_cmd
import tc


## -- Setup session ----------------------------------------------------------------------------------------------------
def init_arparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] ",
        prog="ob_egse",
        description="Executes the OB EGSE either in script mode or with the streamlit GUI.",
    )
    parser.add_argument("-prefix", type=ascii, default=const.DEFAULT_PREFIX)
    parser.add_argument("-com", type=int, default=const.DEFAULT_COM_PORT)
    parser.add_argument("-psuport", type=int, default=const.PSU_COM_PORT)
    parser.add_argument("-basedir", type=Path, default=const.DEFAULT_PATH)
    parser.add_argument("-np", "--nopsu", action="store_true")
    parser.add_argument("-s", "--script", action="store_true")
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


# ----FPGA Boot and Connect-------------------------------------------------------------------------


# @atexit.register
# def clean_exit(psuport):
#     # Adding parsing to be able to shut down psu
#     # !TODO: Make sure this is the correct way?


#     const.ACK_LOG_FH.close()
#     const.CMD_LOG_FH.close()
#     const.HK_LOG_FH.close()
#     const.SCI_LOG_FH.close()
#     psu.emergencyShutDown(psuport)
#     sys.exit(1001)
#     #! TODO Add code here, possibly try and power insturment off
#     #! TODO power off power supply
#     #! TODO ensure all logs are written


def main() -> None:
    parser = init_arparse()
    args = parser.parse_args()

    # Setup loggers
    const.LOG_PREFIX = str(args.prefix).strip("'")
    const.LOG_PATH = args.basedir
    (event_log, info_log, psu_log) = setup_logs()

    com_port = "COM" + str(args.com)
    psu_com = "COM" + str(args.psuport)

    if args.script:
        info_log.info("Running Script")
        info_log.info("Initialising RS-485 Comms")
        port = comms.initialise_comms(com_port)
        port = comms.open_comms(port)

        # info_log.info("Initialising PSU Comms")
        # psuport = psu.init_psu_comms(psu_com)
        # psuport = psu.open_psu_comms(psuport, args.nopsu)
        # psu.setChannels(psuport, const.CH1_OVP, const.CH1_I, const.CH2_OVP, const.CH2_I, const.CH3_OVP, const.CH3_I)
        # psu.switchPSU(psuport, 1)  # Switch on PSU
        # time.sleep(1)  # Adding a 1 second delay before starting monitoring thread for compensation of OVP
        # stop_event = threading.Event()
        # psu_thread = threading.Thread(
        #     target=psu.psu_monitor_thread, args=(psuport, stop_event, const.PSU_LOGGING_FREQ), daemon=True
        # )
        # psu_thread.start()

        # First HK
        abu.read_hk(port)

        # TODO: Ensure sequence runs are recorded in info log as well.
        # ------------------------------------------------------------------------------------------
        # User add commands or sequences from here:
        # ------------------------------------------------------------------------------------------
        # First power on
        # abu.first_power_on(port)

        # Move to position 510 and try to set DAC offsets
        #abu.dac_auto_offset(port)

        # Move to absolute position and take a reading
        #abu.mv_abs_pos(port, 7600)
        #abu.move_and_measure(port, 0)

        # sweep through SWIR DAC offset
        # abu.sweep_offset_swir(port, 5)

        # sweep through MWIR DAC offset
        # abu.sweep_offset_mwir(port, 1)

        # move to 7600 absolute (dark zone)
        # abu.mv_pos_steps(port, 7600-283)
        # abu.mv_neg_steps(port, 1358)

        # swir binary chop
        # abu.swir_binary_chop(port, 100, 0, 100)

        # mwir binary chop
        # abu.mwir_binary_chop(port, 2240, 0, 100)

        # Measurement scan with found values
        # abu.abu_measurement_scan(port, 30, 0, 100)

        # ------------------------------------------------------------------------------------------
        # Clean up and exit
        # # ------------------------------------------------------------------------------------------

        # Ensure we're off either endstop when finishing up.
        abu.move_off_endstops(port)

        # Get final HK
        abu.read_hk(port)

        # Auto-generate CSV files from HK and SCI logs
        abu.convert_logs()

        # stop_event.set()
        # psu_thread.join(timeout=1.0)  # Wait for the PSU monitor thread to finish
        # # TODO! Add ability to give back local control of PSU
        # psu.close_psu_comms(psuport)

        comms.close_comms(port)
    else:
        info_log.info("Running GUI")
        gui.streamlit_gui(com_port, psu_com)


if __name__ == "__main__":
    main()

# TODO
# - Add a way to stop the script
# - Implement some sort of thread queue with the GUI running seperately
# - Move streamlit stuff to a different module
# - See if there is a better way to launch streamlit
# - See if the python run button can have arguments in vscode
