"""
Desktop application wrapper using pywebview.
Runs the NiceGUI app as a standalone desktop application.
"""

import time
import threading
import logging

info_log = logging.getLogger("info_log")


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

    server_thread = threading.Thread(target=run_nicegui_server, daemon=False)
    server_thread.start()

    # Wait for server to start, then create and show the pywebview window in main thread
    time.sleep(2)
    
    try:
        info_log.info("Creating pywebview window...")
        window = webview.create_window(
            title="OB EGSE Control",
            url="http://localhost:8085",
            width=1920,
            height=1080,
            min_size=(1280, 720),
        )
        info_log.info("Window created, starting webview...")
        webview.start()
        info_log.info("Webview closed")
    except Exception as e:
        info_log.error(f"Failed to create/start pywebview window: {e}", exc_info=True)
