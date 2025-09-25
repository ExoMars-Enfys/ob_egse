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
import scripts.heaters as h
from send_cmd import cmd_repeat as repeat
from scripts.OB_FFT import fft as fft
import tc
from scripts.LTM import LTM_Measurement as LTM


## -- Setup session ----------------------------------------------------------------------------------------------------
def init_arparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] ",
        prog="ob_egse",
        description="Executes the OB EGSE either in script mode or with the streamlit GUI.",
    )
    parser.add_argument("-prefix", type=ascii, default=const.DEFAULT_PREFIX)
    parser.add_argument("-com", type=int, default=const.DEFAULT_COM_PORT)
    parser.add_argument("-psuport", type = int, default = const.PSU_COM_PORT)
    parser.add_argument("-basedir", type=Path, default=const.DEFAULT_PATH)
    parser.add_argument("-np","--nopsu", action="store_true")
    parser.add_argument("-s", "--script", action="store_true")
    return parser


def setup_logs() -> tuple[logging.Logger]:
    if const.LOG_PATH == const.DEFAULT_PATH:
        const.LOG_PATH.mkdir(parents=True, exist_ok=True)

    event_log, info_log, psu_log = egse_logger.get_loggers(
        const.LOG_PATH, const.LOG_PREFIX, const.DEBUG_LEVEL
    )

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


@atexit.register
def clean_exit():
# #     # Adding parsing to be able to shut down psu 
# #     # !TODO: Make sure this is the correct way?


    const.ACK_LOG_FH.close()
    const.CMD_LOG_FH.close()
    const.HK_LOG_FH.close()
    const.SCI_LOG_FH.close()
    # psu.emergencyShutDown("COM8")
    sys.exit(1001)
#     #! TODO Add code here, possibly try and power insturment off
#     #! TODO power off power supply
#     #! TODO ensure all logs are written

def main() -> None:
    try : 
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

            info_log.info("Initialising PSU Comms")
            psuport = psu.init_psu_comms(psu_com)       
            psuport = psu.open_psu_comms(psuport,args.nopsu)
            psu.psuLinkCheck(psuport)
            psu.setChannels(psuport, const.CH1_OVP, const.CH1_I, const.CH2_OVP, const.CH2_I, const.CH3_OVP, const.CH3_I)
            psu.switchPSU(psuport,True)
            time.sleep(3) #Adding a 1 second delay before starting monitoring thread for compensation of OVP
            stop_event = threading.Event()
            psu_thread = threading.Thread(target=psu.psu_monitor_thread, args=(psuport, stop_event,const.PSU_LOGGING_FREQ), daemon=True)
            psu_thread.start()

            # TODO: Ensure sequence runs are recorded in info log as well.
            # ------------------------------------------------------------------------------------------
            # User add commands or sequences from here:
            # ----------------------------------------------------------------------------------------
            # LTM(port)
            sq.power_up(port)
            tc.mtr_mov_pos(port,0x050)
            # ------------------------------------------------------------------------------------------

            comms.close_comms(port)
        else:
            info_log.info("Running GUI")
            gui.streamlit_gui(com_port,psu_com)
    except KeyboardInterrupt:
        info_log.error("Keyboard Interrupt detected, shutting down.")
        stop_event.set()
        psu_thread.join(timeout=1.0)  # Wait for the PSU monitor thread to finish
        comms.close_comms(port)
        psu.emergencyShutDown(psuport)
        clean_exit()



if __name__ == "__main__":
    main()

# TODO
# 1 Add a way to stop the script
#?1 A keyboard interrupt of CTRL+C triggers the psu thread stop, closes all comms and shuts down psu

#2 See if the python run button can have arguments in vscode
#?2 launch.json file can have args passed and already implemented. Sadly json needs to be added as a configuration file in vscode workspace by adding the file in .vscode
#?2 Current version has args for -s -np prepassed

# - Implement some sort of thread queue with the GUI running seperately
# - Move streamlit stuff to a different module
# - See if there is a better way to launch streamlit


