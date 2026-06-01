"""
Desktop application wrapper using pywebview.
Runs the NiceGUI app as a standalone desktop application.
"""

import signal
import time
import threading
import logging

info_log = logging.getLogger("info_log")

# Module-level reference to the pywebview window; set once the window is created.
# Other modules can call destroy_desktop_window() to close the app cleanly.
_window_ref: list = [None]


def destroy_desktop_window() -> None:
    """Destroy the pywebview window if running in desktop mode."""
    if _window_ref[0] is not None:
        # Run destroy() on a separate thread: calling it directly from NiceGUI's
        # async event loop can be blocked by the GUI thread on Windows.
        t = threading.Thread(target=_window_ref[0].destroy, daemon=True)
        t.start()


def run_app_in_desktop(reload: bool = False) -> None:
    """
    Run the NiceGUI app in a pywebview desktop window.
    
    Args:
        reload: Enable hot reload (for development) - Note: reload doesn't work with
                threaded pywebview due to signal handling requirements in main thread.
                Use browser-based launcher (src/main.py) for development with reload.
    """
    try:
        import webview
    except ImportError:
        info_log.error("pywebview not installed. Install it with: pip install pywebview")
        return

    from nicegui import ui

    if reload:
        info_log.warning(
            "Hot reload not supported in desktop mode (requires main thread signals). "
            "Use: python src/main.py -np --reload for development with hot reload."
        )
        reload = False

    # Run NiceGUI server in a background thread
    def run_nicegui_server():
        # show=False prevents opening a browser window
        ui.run(port=8085, reload=False, show=False)

    server_thread = threading.Thread(target=run_nicegui_server, daemon=True)
    server_thread.start()

    # Register SIGINT handler early so Ctrl+C during startup sleep is caught cleanly
    # Reuse the module-level _window_ref so destroy_desktop_window() also works.
    def _handle_sigint(_sig, _frame):
        info_log.info("Keyboard interrupt received, closing window...")
        if _window_ref[0] is not None:
            _window_ref[0].destroy()

    signal.signal(signal.SIGINT, _handle_sigint)

    # Wait for server to start, then create and show the pywebview window in main thread
    # Catch KeyboardInterrupt: on Windows, even with a custom SIGINT handler,
    # time.sleep() still raises KeyboardInterrupt as a Python exception.
    try:
        time.sleep(2)
    except KeyboardInterrupt:
        info_log.info("Interrupted during startup, exiting...")
        return

    try:
        info_log.info("Creating pywebview window...")
        window = webview.create_window(
            title="OB EGSE Control",
            url="http://localhost:8085",
            width=1920,
            height=1080,
            min_size=(1280, 720),
        )
        _window_ref[0] = window

        info_log.info("Window created, starting webview...")
        webview.start()
        info_log.info("Webview closed")
    except Exception as e:
        info_log.error(f"Failed to create/start pywebview window: {e}", exc_info=True)
