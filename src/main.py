# ----Module Imports--------------------------------------------------------------------------------
# Std library
import logging
import sys
import time
import atexit
import argparse
from pathlib import Path
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

# import scripts.heaters as h
from send_cmd import cmd_repeat as repeat
from scripts.OB_FFT import fft as fft
import tc
# from scripts.LTM import LTM_Measurement as LTM
from scripts import LTM
from scripts import analysis as ana


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

def clean_exit(psuport):
    const.ACK_LOG_FH.close()
    const.CMD_LOG_FH.close()
    const.HK_LOG_FH.close()
    const.SCI_LOG_FH.close()
    psu.emergencyShutDown(psuport)
    ana.analysis(const.LOG_PATH,const.DEFAULT_PREFIX)



    #! TODO add emergency shutdown to that powers off the OB
    #! TODO power off power supply


def main() -> None:
    parser = init_arparse()
    args = parser.parse_args()

    # Setup loggers
    const.LOG_PREFIX = str(args.prefix).strip("'")
    const.LOG_PATH = args.basedir
    (event_log, info_log, psu_log) = setup_logs()

    rs485_com = "COM" + str(args.com)
    psu_com = "COM" + str(args.psuport)

    if args.script:
        info_log.info("Running Script")
        info_log.info("Initialising RS-485 Comms")
        ob_port = comms.initialise_comms(rs485_com)
        ob_port = comms.open_comms(ob_port)

        info_log.info("Initialising PSU Comms")
        psuport = psu.init_psu_comms(psu_com)
        psuport = psu.open_psu_comms(psuport, args.nopsu)
        psu.setChannels(psuport, const.CH1_OVP, const.CH1_I, const.CH2_OVP, const.CH2_I, const.CH3_OVP, const.CH3_I)
        psu.switchPSU(psuport, 1)  # Switch on PSU
        atexit.register(clean_exit, psuport)
        stop_event = threading.Event()

        time.sleep(1)  # Adding a 1 second delay before starting monitoring thread for compensation of OVP
        psu_thread = threading.Thread(
            target=psu.psu_monitor_thread, args=(psuport, stop_event, const.PSU_LOGGING_FREQ), daemon=True
        )
        psu_thread.start()

        # First HK
        # abu.read_hk(ob_port)
        # ------------------------------------------------------------------------------------------
        # User add commands or sequences from here:
        # ------------------------------------------------------------------------------------------
        # TODO! When psu current limit hit trip off so obvious
        LTM.LTM_Measurement(ob_port)
        # ------------------------------------------------------------------------------------------
        # Clean up and exit
        # # ------------------------------------------------------------------------------------------
        # Get final HK
        # abu.read_hk(ob_port)

        stop_event.set()
        psu_thread.join(timeout=1.0)  # Wait for the PSU monitor thread to finish

        comms.close_comms(ob_port)
    else:
        info_log.info("Running GUI")

        rs485port = comms.initialise_comms(rs485_com)
        rs485port = comms.open_comms(rs485port)
        stop_event = threading.Event()
        hk_thread = threading.Thread(target=poll_hk, args=(rs485port, stop_event), daemon=True)
        hk_thread.start()
        time.sleep(3)
        gui.init()


if __name__ == "__main__":
    main()

# TODO
# 1 Add a way to stop the script
# ?1 A keyboard interrupt of CTRL+C triggers the psu thread stop, closes all comms and shuts down psu

# 2 See if the python run button can have arguments in vscode
# ?2 launch.json file can have args passed and already implemented. Sadly json needs to be added as a configuration file in vscode workspace by adding the file in .vscode
# ?2 Current version has args for -s -np prepassed

# - Implement some sort of thread queue with the GUI running seperately
# - Move streamlit stuff to a different module
# - See if there is a better way to launch streamlit
