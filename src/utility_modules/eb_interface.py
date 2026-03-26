# Std library
import logging
import subprocess
import time

# Added packages
from pathlib import Path
from tkinter import filedialog
import pywinauto
from pywinauto.keyboard import send_keys

# Local modules
# core
from core_modules import config as config

# utilities
from utility_modules import comms as comms
from utility_modules import tc as tc
from utility_modules import tm as tm

# widgets
from widget_modules import file_dialog_window_widget as window  #! To be populated

info_log = logging.getLogger("info_log")


class EGSEInterface:
    def __init__(self, egse_path: str | Path = r"C:\wdir\IFM\EB"):
        """Interface class to manage interactions with the EB EGSE tools, including starting/stopping the tools and sending commands via typecasting."""
        self.egse_path = Path(egse_path)
        self.process_handle = None

    def start_egse(self, script_arg: str | None = None) -> bool:
        """Start the EGSE tools by running the Start_tools.bat script. Optionally, a script argument can be passed to be executed after the tools start."""
        try:
            start_bat = self.egse_path / "Start_tools.bat"
            if not start_bat.exists():
                print(f"Start_tools.bat not found at {start_bat}")
                return False

            self.process_handle = subprocess.Popen(
                [start_bat, *(script_arg.split() if script_arg else [])], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            print(f"EGSE tools started{' with script: ' + script_arg if script_arg else ''}")
            time.sleep(5)  # Wait for tools to initialize
            return True
        except Exception as e:
            print(f"Error starting EGSE: {e}")
            return False

    def stop_egse(self) -> bool:
        """Stop the EGSE tools by running the Stop_tools.bat script."""
        try:
            stop_bat = self.egse_path / "Stop_tools.bat"
            if not stop_bat.exists():
                print(f"Stop_tools.bat not found at {stop_bat}")
                return False

            subprocess.Popen([stop_bat])
            print("EGSE tools stopped")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Error stopping EGSE: {e}")
            return False

    def typecast(self, script_path: str | Path, verbose: bool = False) -> bool:
        """Typecasting function that sends the commands from a script file to the CMDTool window."""
        try:
            script_file = Path(script_path)
            if not script_file.exists():
                print(f"[ERROR] Script file not found: {script_path}")
                return False

            # Connect to CmdTool window
            try:
                app = pywinauto.Application().connect(title="CmdTool")
                cmd_window = app.window(title="CmdTool")
            except Exception as e:
                print(f"[ERROR] Could not find CmdTool window: {e}")
                return False

            # Read and send each line
            with open(script_file, encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.rstrip("\n\r")
                    if not line or line.startswith("#"):
                        continue

                    try:
                        cmd_window.set_focus()
                        time.sleep(0.1)
                        send_keys(line, pause=0.05)
                        send_keys("{ENTER}")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"[ERROR] Failed to send line {line_num}: {e}")
                        return False

            print(f"[OK] Script completed: {script_file.name}")
            return True
        except Exception as e:
            print(f"[ERROR] Unexpected error in typecast: {e}")
            return False


# Global state for EGSE tools management
egse_started = False
egse_script_path = None
egse_log_file = None
egse_tools_path = r"C:\wdir\IFM\EB\EGSE"
egse_interface = None
rs422_log_path: str | None = None
_egse_log_state: dict[str, Path | float | None] = {"path": None, "mtime": None}
_rs422_log_state: dict[str, Path | float | None] = {"path": None, "mtime": None}


# EGSE log management functions
def rs422_log_changed(log_path: Path | None) -> bool:
    """Return True if the RS422 log path or mtime changed since last check."""
    if log_path is None:
        _rs422_log_state["path"] = None
        _rs422_log_state["mtime"] = None
        return False

    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return False

    if log_path == _rs422_log_state.get("path") and mtime == _rs422_log_state.get("mtime"):
        return False

    _rs422_log_state["path"] = log_path
    _rs422_log_state["mtime"] = mtime
    return True


def get_egse_log_snapshot(
    max_lines: int,
    force: bool = False,
) -> tuple[bool, str | None, list[str], str | None]:
    """Return latest EB EGSE log snapshot if changed.
    Returns (changed, header, lines, error).
    """
    log_path = locate_latest_egse_log()
    if log_path is None:
        if force:
            _egse_log_state["path"] = None
            _egse_log_state["mtime"] = None
            return True, None, [], "EB EGSE log not found in the tools folder."
        return False, None, [], None

    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        if force:
            return True, None, [], "[ERROR] Failed to stat EB EGSE log file."
        return False, None, [], None

    last_path = _egse_log_state.get("path")
    last_mtime = _egse_log_state.get("mtime")
    if not force and log_path == last_path and mtime == last_mtime:
        return False, f"EB EGSE log: {log_path}", [], None

    _egse_log_state["path"] = log_path
    _egse_log_state["mtime"] = mtime

    header = f"EB EGSE log: {log_path}"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return True, header, [], f"[ERROR] Failed to read EB EGSE log: {exc}"

    return True, header, lines[-max_lines:], None


def get_egse_interface() -> EGSEInterface:
    """Get the EGSE interface instance, initializing it if it doesn't exist."""
    global egse_interface
    if egse_interface is None:
        egse_interface = EGSEInterface(egse_tools_path)
    return egse_interface


def update_egse_interface_path(new_path: str | Path) -> None:
    """Update the EGSE interface path and reinitialize the interface if it already exists."""
    global egse_interface
    if egse_interface is None:
        egse_interface = EGSEInterface(new_path)
    else:
        egse_interface.egse_path = Path(new_path)


# Button callbacks for file pickers
def select_cmd_script(logger) -> None:
    """Open a file picker instance to select an EGSE script file and send it to CmdTool using Typecast."""
    global egse_started, egse_script_path

    # Checks that the RAL EGSE tools are started before allowing the user to select a script, since the script needs to be sent to CmdTool using Typecast and will fail if the tools are not running
    if not egse_started:
        logger.warning("[WARN] EGSE tools must be started before selecting a script")
        return

    root = None
    try:
        # Create root window to select script file with the selected EGSE tools path as initial directory
        root = window.create_dialog_root()
        egse_script_path = filedialog.askopenfilename(
            title="Select EGSE script file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=egse_tools_path,
            parent=root,
        )

        # If a file was selected, send it to CmdTool
        if egse_script_path:
            script_filename = Path(egse_script_path).name
            logger.info(f"Selected script: {script_filename}")
            interface = get_egse_interface()
            if not interface.typecast(egse_script_path, verbose=True):
                logger.error("[ERROR] Failed to execute script")
    except Exception as e:
        logger.error(f"[ERROR] Error selecting script: {e}")
    finally:
        if root is not None:
            root.destroy()


def select_egse_folder(logger) -> None:
    """Open folder picker to set the EGSE tools directory."""
    global egse_tools_path

    root = None
    try:
        root = window.create_dialog_root()
        egse_tools_path = filedialog.askdirectory(
            title="Select EGSE tools folder",
            initialdir=egse_tools_path,
            parent=root,
        )

        if egse_tools_path:
            update_egse_interface_path(egse_tools_path)
            logger.info(f"EGSE tools folder set to: {egse_tools_path}")
    except Exception as e:
        logger.error(f"[ERROR] Error selecting EGSE tools folder: {e}")
    finally:
        if root is not None:
            root.destroy()


def select_rs422_log(logger) -> bool:
    """Open file picker to select an RS422if log file."""
    global rs422_log_path

    root = None
    try:
        root = window.create_dialog_root()
        rs422_log_path = filedialog.askopenfilename(
            title="Select RS422if log file",
            filetypes=[("RS422if log", "RS422if_*.log"), ("RS422if log", "RS422if_*.LOG"), ("Text files", "*.txt")],
            initialdir=egse_tools_path,
            parent=root,
        )

        if rs422_log_path:
            logger.info(f"RS422if log set to: {rs422_log_path}")
            return True
    except Exception as e:
        logger.error(f"[ERROR] Error selecting RS422if log file: {e}")
    finally:
        if root is not None:
            root.destroy()
    return False


# Button callbacks for EGSE tools management (start/stop)
def locate_latest_egse_log() -> Path | None:
    """Locate the newest EB EGSE log file."""
    base = Path(egse_tools_path)
    if not base.exists():
        return None

    log_files = list(base.glob("*.log")) + list(base.glob("*.LOG"))
    return max(log_files, key=lambda p: p.stat().st_mtime) if log_files else None


def start_egse_tools(logger) -> None:
    """Method that runs the batch file to start the EGSE tools."""
    global egse_started, egse_log_file
    try:
        logger.info("Starting EB EGSE Tools...")
        interface = get_egse_interface()
        if interface.start_egse():
            egse_started = True
            logger.info("[OK] EGSE tools started successfully")
    except Exception as exc:
        logger.error(f"[ERROR] Error starting EGSE: {exc}")
        egse_started = False

    locate_latest_egse_log()


def stop_egse_tools(logger) -> None:
    """Stop the EGSE tools."""
    global egse_started
    try:
        logger.info("Stopping EB EGSE Tools...")
        interface = get_egse_interface()  #! To be checked after moving EGSEInterface to a separate module
        if interface.stop_egse():
            egse_started = False
            logger.info("[OK] EGSE tools stopped successfully")
    except Exception as e:
        logger.error(f"[ERROR] Error stopping EGSE: {e}")
