"""
Desktop application wrapper using pywebview.
Runs the NiceGUI app as a standalone desktop application.
"""

import sys
import time
import threading
from pathlib import Path

try:
    import webview
except ImportError:
    print("Error: pywebview not installed. Install it with: pip install pywebview")
    sys.exit(1)

# Add src to path
_SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SRC_DIR))


def run_app_in_desktop(
    default_mode: str = "OB",
    psu_port=None,
    psu_lock=None,
    ob_port=None,
    port_lock=None,
    stop_event=None,
    psu_mode_state=None,
    reload: bool = False,
) -> None:
    """
    Run the NiceGUI app in a pywebview desktop window.
    
    Args:
        default_mode: Starting mode (EB or OB)
        psu_port: PSU serial port object
        psu_lock: Lock for PSU access
        ob_port: OB serial port object
        port_lock: Lock for port access
        stop_event: Event to signal shutdown
        psu_mode_state: PSU mode state dict
        reload: Enable hot reload (for development)
    """
    # Import NiceGUI components
    from nicegui import app, ui
    from widget_modules import parent_window_widget

    # Build the UI
    parent_window_widget.build_ui(
        default_mode=default_mode,
        psu_port=psu_port,
        psu_lock=psu_lock,
        ob_port=ob_port,
        port_lock=port_lock,
        stop_event=stop_event,
        psu_mode_state=psu_mode_state,
    )

    # Create pywebview window in a background thread
    # The window will connect to the NiceGUI server once it starts
    def create_pywebview_window():
        time.sleep(2)  # Wait for NiceGUI server to start
        webview.create_window(
            title="OB EGSE Control",
            url="http://localhost:8085",
            width=1920,
            height=1080,
            min_size=(1280, 720),
        )

    webview_thread = threading.Thread(target=create_pywebview_window, daemon=True)
    webview_thread.start()

    # Run NiceGUI server in main thread (required for signal handling)
    # show=False prevents opening a browser window
    ui.run(port=8085, reload=reload, show=False)


if __name__ == "__main__":
    import argparse
    from core_modules import config, constants as const
    from utility_modules import egse_logger

    parser = argparse.ArgumentParser(description="OB EGSE Desktop Application")
    parser.add_argument("-prefix", type=ascii, default=const.DEFAULT_PREFIX)
    parser.add_argument("-com", type=int, default=config.DEFAULT_COM_PORT)
    parser.add_argument("-psuport", type=int, default=config.PSU_COM_PORT)
    parser.add_argument("-basedir", type=Path, default=const.DEFAULT_PATH)
    parser.add_argument("-np", "--nopsu", action="store_true")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload for development")
    parser.add_argument("-m", "--mode", type=str, default="OB", choices=["EB", "OB"])

    args = parser.parse_args()

    # Setup logging
    if const.LOG_PATH == const.DEFAULT_PATH:
        const.LOG_PATH.mkdir(parents=True, exist_ok=True)
    event_log, info_log, psu_log = egse_logger.get_loggers(
        const.LOG_PATH, const.LOG_PREFIX, const.DEBUG_LEVEL
    )

    # Initialize comms (similar to main.py)
    import atexit
    from utility_modules import comms, psu

    startup_mode = args.mode
    startup_eb_mode = startup_mode == "EB"
    psu_lock = threading.Lock()
    psu_mode_state = {"value": startup_eb_mode}

    psu_port = None
    if not args.nopsu:
        psu_com = "COM" + str(args.psuport)
        info_log.info(f"Initialising PSU Comms on Port {psu_com}")
        try:
            psu_port = psu.init_psu_comms(psu_com)
            psu_port = psu.open_psu_comms(psu_port, args.nopsu)
            psu.setChannels(psu_port, startup_eb_mode)
        except SystemExit:
            info_log.warning(f"PSU initialization failed on {psu_com}; running without PSU")
            psu_port = None

    stop_event = threading.Event()
    rs485_com = "COM" + str(args.com)
    ob_port = None

    info_log.info(f"Initialising RS-485 Comms on Port {rs485_com}")
    try:
        ob_port = comms.initialise_comms(rs485_com)
        ob_port = comms.open_comms(ob_port)
    except Exception as exc:
        info_log.warning(f"RS-485 unavailable on {rs485_com}; running without OB comms ({exc})")
        ob_port = None

    port_lock = threading.Lock()

    def clean_exit_callback():
        stop_event.set()
        if psu_port:
            psu.close_psu_comms(psu_port)
        if ob_port:
            comms.close_comms(ob_port)

    atexit.register(clean_exit_callback)

    # Start PSU monitor thread
    psu_thread = threading.Thread(
        target=psu.psu_monitor_thread,
        args=(psu_port, startup_eb_mode, stop_event, config.PSU_LOGGING_FREQ, threading.Event(), psu_mode_state, psu_lock),
        daemon=True,
    )
    psu_thread.start()

    info_log.info("Starting OB EGSE in desktop mode")

    # Run the desktop app
    run_app_in_desktop(
        default_mode=startup_mode,
        psu_port=psu_port,
        psu_lock=psu_lock,
        ob_port=ob_port,
        port_lock=port_lock,
        stop_event=stop_event,
        psu_mode_state=psu_mode_state,
        reload=args.reload,
    )
