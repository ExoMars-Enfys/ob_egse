# ----Module Imports--------------------------------------------------------------------------------
# Std library
import argparse
import atexit
import logging
import threading
import time
from pathlib import Path

from nicegui import app, ui

# Local modules
# core
from core_modules import config as config
from core_modules import constants as const
from core_modules import tmstruct as tmstruct

# utilities
from scripts_modules import sequences
from utility_modules import comms as comms
from utility_modules import egse_logger as egse_logger
from utility_modules import psu as psu
from utility_modules import tc as tc
from utility_modules import tm as tm

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


def clean_exit(ob_port, psu_port, event_log, stop_event=None, psu_thread=None):
    """Gracefully winds down background telemetry tasks and returns PSU to Local mode."""
    event_log.info("Running clean exit sequence...")

    # 1. Stop background monitoring thread immediately to prevent trailing queries
    if stop_event is not None:
        stop_event.set()

    # 2. Wait for the background loop to step down before touching hardware lines
    if psu_thread is not None and psu_thread.is_alive():
        event_log.info("Waiting for PSU monitor thread to spin down...")
        psu_thread.join(timeout=1.0)

    # 3. Safely flush and close byte logging handles
    for handle in (const.ACK_LOG_FH, const.CMD_LOG_FH, const.HK_LOG_FH, const.SCI_LOG_FH):
        if handle is not None:
            handle.close()

    # 4. Release physical RS-485 link
    if ob_port is not None and ob_port.is_open:
        comms.close_comms(ob_port)

    # 5. Handshake down the PSU link using your verified working isolation sequence
    if psu_port is not None and psu_port.is_open:
        try:
            # Drop outputs
            psu_port.write("OPALL 0\n".encode("utf-8"))
            psu_port.flush()
            time.sleep(0.1)

            # Drop back to local panel control
            psu_port.write("LOCAL\n".encode("utf-8"))
            psu_port.flush()
            time.sleep(0.1)

            # Flush operating system serial caches
            psu_port.reset_input_buffer()
            psu_port.reset_output_buffer()
            psu_port.close()
            event_log.info("PSU safely unlocked and returned to local mode.")
        except Exception as e:
            event_log.error(f"Failed to cleanly release PSU interface: {e}")

    #! TODO add emergency shutdown to that powers off the OB


def main() -> None:
    parser = init_arparse()
    args = parser.parse_args()
    startup_mode = const.DEFAULT_STARTUP_MODE
    startup_eb_mode = startup_mode == "EB"
    psu_mode_state = {"ebmode": startup_eb_mode, "voltage_mode": "NOM"}

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

        # 1. First, declare your locks, events, and threads
    stop_event = threading.Event()
    hk_pause_event = threading.Event()
    hk_pause_event.set()
    psu_lock = threading.Lock()
    port_lock = threading.Lock()

    time.sleep(1)

    # 2. Instantiate the thread object so it exists as a valid local variable
    psu_thread = threading.Thread(
        target=psu.psu_monitor_thread,
        args=(psu_port, startup_eb_mode, stop_event, config.PSU_LOGGING_FREQ, hk_pause_event, psu_mode_state, psu_lock),
        daemon=True,
    )

    hk_thread = None

    # 3. Configure your RS-485 serial communication links
    rs485_com = "COM" + str(args.com)
    ob_port = None
    info_log.info("Initialising RS-485 Comms on Port " + rs485_com)
    try:
        ob_port = comms.initialise_comms(rs485_com)
        ob_port = comms.open_comms(ob_port)
    except Exception as exc:
        info_log.warning("RS-485 unavailable on %s; starting GUI without OB comms (%s)", rs485_com, exc)
        ob_port = None

    # 4. NOW register your unified clean_exit since ALL variables are fully defined
    atexit.register(clean_exit, ob_port, psu_port, event_log, stop_event, psu_thread)

    app.on_shutdown(stop_event.set)
    app.on_shutdown(lambda: clean_exit(ob_port, psu_port, event_log, stop_event, psu_thread))

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
        const.hk_queue = None
        # const.hk_explorer_queue = None  # Separate queue for HK parameter explorer
        const.eb_post_queue = None
        const.psu_queue = None
        const.sci_queue = None

        psu.switch_all_psu_channels(psu_port, 1)
        psu_thread.start()
        hk_pause_event.clear()  # Resume HK polling

        time.sleep(1)  #! Adjust  to your needs for delay before requesting HK

        # First HK
        # sequences.parse_hk(ob_port)
        # ------------------------------------------------------------------------------------------
        # User add commands or sequences from here:
        # ------------------------------------------------------------------------------------------
        # sequences.parse_hk(ob_port)
        # tc.power_control(ob_port, 1)
        # ------------------------------------------------------------------------------------------
        # Clean up and exit
        # ------------------------------------------------------------------------------------------
        # Get final HK
        # sequences.parse_hk(ob_port)

        #! No need for stop events as atexit does it automatically
        return

    else:
        info_log.info("Running GUI")
        if psu_port is not None and not psu_thread.is_alive():
            psu_thread.start()

        parent_window_widget.build_ui(
            default_mode=startup_mode,
            psu_port=psu_port,
            ob_port=ob_port,
            psu_lock=psu_lock,
            port_lock=port_lock,
            stop_event=stop_event,
            psu_mode_state=psu_mode_state,
        )
        ui.run(
            port=8085,
            reload=args.reload,
            show=not args.reload,
            uvicorn_reload_includes="*.py, *.css",
        )
        # TODO What about stop_event?

    event_log.info("Shutting down")
    if psu_thread.is_alive():
        event_log.info("Waiting for PSU monitor thread to finish")
        psu_thread.join(timeout=1.0)  # Wait for the PSU monitor thread to finish

    if hk_thread is not None:
        if hk_thread.is_alive():
            event_log.info("Waiting for HK polling thread to finish")
            hk_thread.join(timeout=1.0)  # Wait for the HK polling thread to finish

    # psu.emergencyShutDown(psu_port)


if __name__ in {"__main__", "__mp_main__"}:
    main()

# TODO Fix display of HK
