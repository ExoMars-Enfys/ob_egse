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
import comms
import constants as const
import config
import egse_logger
import gui
import ebgui
import psu
import scripts.sequences as sq
import scripts.error_checks as ec
import scripts.abu_sequences as abu
from send_cmd import *
import tc


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
    parser.add_argument("-eb", "--ebmode", action="store_true")
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


def main() -> None:
    parser = init_arparse()
    args = parser.parse_args()

    # Setup loggers
    const.LOG_PREFIX = str(args.prefix).strip("'")
    const.LOG_PATH = args.basedir
    (event_log, info_log, psu_log) = setup_logs()   
    
    psu_port = None
    if not args.nopsu:
        psu_com = "COM" + str(args.psuport)
        info_log.info("Initialising PSU Comms")
        psu_port = psu.init_psu_comms(psu_com)
        psu_port = psu.open_psu_comms(psu_port, args.nopsu)
        psu.setChannels(psu_port, args.ebmode)

    stop_event = threading.Event()
    hk_pause_event = threading.Event()
    hk_pause_event.set()  # Start with HK polling paused until we know the PSU is on and stable
    port_lock = threading.Lock()
    psu.set_psu_lock(port_lock)

    if not args.ebmode:
        rs485_com = "COM" + str(args.com)

        info_log.info("Initialising RS-485 Comms")
        ob_port = comms.initialise_comms(rs485_com)
        ob_port = comms.open_comms(ob_port)
        atexit.register(stop_event.set)
        atexit.register(clean_exit, ob_port, psu_port, event_log)
    else : 
        atexit.register(stop_event.set)
        atexit.register(clean_exit, ob_port = None, psu_port = psu_port, event_log = event_log)

    time.sleep(1)  # Adding a 1 second delay before starting monitoring thread for compensation of OVP
    # TODO Update monitoring thread to start very early
    psu_thread = threading.Thread(
        target=psu.psu_monitor_thread,
        args=(psu_port, args.ebmode, stop_event, config.PSU_LOGGING_FREQ, hk_pause_event),
        daemon=True,
    )
    psu_thread.start()

    hk_thread = None

    if args.script:
        info_log.info("Running Script")
        psu.switchPSU(psu_port, ebmode = args.ebmode, state = 1)  # Switch on PSU
        time.sleep(1)  # Adding a 1 second delay for PSU to power on and stabilize before resuming HK polling
        hk_pause_event.clear()  # Resume HK polling

        # First HK
        abu.read_hk(ob_port)

        # ------------------------------------------------------------------------------------------
        # User add commands or sequences from here:
        # ------------------------------------------------------------------------------------------
        time.sleep(10)
        # ------------------------------------------------------------------------------------------
        # Clean up and exit
        # ------------------------------------------------------------------------------------------
        # Get final HK
        abu.read_hk(ob_port)
        stop_event.set()

    else:
        info_log.info("Running GUI")

    if args.ebmode:
        ebgui.build_ui(psu_port,  port_lock, stop_event)
        ui.run(port=8085, reload=False)
    else:
        hk_thread = threading.Thread(target=poll_hk, args=(ob_port, stop_event, port_lock, hk_pause_event), daemon=True)
        hk_thread.start()
        gui.build_ui(ob_port, psu_port, port_lock, stop_event)
        ui.run(port=8085, reload=False)
        # TODO What about stop_envent?

    event_log.info("Shutting down")
    event_log.info("Waiting for PSU monitor thread to finish")
    psu_thread.join(timeout=1.0)  # Wait for the PSU monitor thread to finish

    if hk_thread is not None:
        if hk_thread.is_alive():
            event_log.info("Waiting for HK polling thread to finish")
            hk_thread.join(timeout=1.0)  # Wait for the HK polling thread to finish


if __name__ == "__main__":
    main()

# TODO Fix display of HK
