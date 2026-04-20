# Std library
import logging
import subprocess
import time
import ctypes
from ctypes import windll

# Added packages
from pathlib import Path
from tkinter import filedialog
from typing import Any
import pywinauto
from pywinauto.keyboard import send_keys

# Local modules
# core
from core_modules import config as config

# utilities
from utility_modules import comms as comms
from utility_modules import eb_packet_utility
from utility_modules import tc as tc
from utility_modules import tm as tm

# widgets
from widget_modules import file_dialog_window_widget as window  #! To be populated

info_log = logging.getLogger("info_log")


class EGSEInterface:
    def __init__(self, egse_path: str | Path = r"C:\wdir\EB\EB_EGSE"):
        """Interface class to manage interactions with the EB EGSE tools, including starting/stopping the tools and sending commands via typecasting."""
        self.egse_path = Path(egse_path)
        self.process_handle = None

    @staticmethod
    def _set_clipboard_text(text: str) -> bool:
        """Set Windows clipboard text using CF_UNICODETEXT."""
        try:
            kernel32 = windll.kernel32
            user32 = windll.user32

            # CF_UNICODETEXT payload must be UTF-16LE and null-terminated.
            text_buf = ctypes.create_unicode_buffer(text)
            size_bytes = ctypes.sizeof(text_buf)
            global_handle = kernel32.GlobalAlloc(0x0002, size_bytes)  # GMEM_MOVEABLE

            if not global_handle:
                return False

            ptr = kernel32.GlobalLock(global_handle)
            if not ptr:
                kernel32.GlobalFree(global_handle)
                return False

            ctypes.memmove(ptr, ctypes.addressof(text_buf), size_bytes)
            kernel32.GlobalUnlock(global_handle)

            opened = False
            for _ in range(5):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.02)

            if not opened:
                kernel32.GlobalFree(global_handle)
                return False

            user32.EmptyClipboard()
            # CF_UNICODETEXT = 13
            if not user32.SetClipboardData(13, global_handle):
                user32.CloseClipboard()
                return False

            user32.CloseClipboard()
            return True
        except Exception as e:
            info_log.debug(f"Failed to set clipboard: {e}")
            return False

    @staticmethod
    def _focus_cmdtool_entry(cmd_window: Any) -> None:
        """Focus likely Tkinter command entry by clicking near bottom-left input area."""
        rect = cmd_window.rectangle()
        width = max(rect.width(), 100)
        height = max(rect.height(), 100)

        # Try a few candidate points where Tk command entry is usually located.
        candidates = [
            (int(width * 0.10), int(height * 0.92)),
            (int(width * 0.20), int(height * 0.92)),
            (int(width * 0.35), int(height * 0.92)),
        ]
        for x, y in candidates:
            try:
                cmd_window.click_input(coords=(x, y))
                time.sleep(0.02)
                return
            except Exception:
                continue

        # Last resort: click the window without coords.
        cmd_window.click_input()

    def start_egse(self, script_arg: str | None = None) -> bool:
        """Start the EGSE tools by running the Start_tools.bat script. Optionally, a script argument can be passed to be executed after the tools start."""
        try:
            start_bat = self.egse_path / "Start_tools.bat"
            if not start_bat.exists():
                print(f"[ERROR] Start_tools.bat not found at {start_bat}")
                return False

            cmd_args = ["cmd", "/c", "call", str(start_bat)]
            if script_arg:
                cmd_args.extend(script_arg.split())

            self.process_handle = subprocess.Popen(
                cmd_args,
                cwd=str(self.egse_path),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            time.sleep(0.6)
            rc = self.process_handle.poll()
            if rc not in (None, 0):
                print(f"[ERROR] Start_tools.bat exited early with code {rc}")
                return False
            print(f"[OK] EGSE tools start command sent{' with script: ' + script_arg if script_arg else ''}")
            time.sleep(5)  # Wait for tools to initialize
            return True
        except Exception as e:
            print(f"[ERROR] Error starting EGSE: {e}")
            return False

    def stop_egse(self) -> bool:
        """Stop the EGSE tools by running the Stop_tools.bat script."""
        try:
            stop_bat = self.egse_path / "Stop_tools.bat"
            if not stop_bat.exists():
                print(f"[ERROR] Stop_tools.bat not found at {stop_bat}")
                return False

            subprocess.Popen(
                ["cmd", "/c", "call", str(stop_bat)],
                cwd=str(self.egse_path),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            print("[OK] EGSE tools stop command sent")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"[ERROR] Error stopping EGSE: {e}")
            return False

    def typecast(self, script_path: str | Path, verbose: bool = False) -> bool:
        """Send the script file path to CmdTool as @filepath, not line by line."""
        try:
            script_file = Path(script_path)
            if not script_file.exists():
                print(f"[ERROR] Script file not found: {script_path}")
                return False

            cmd_window = self._connect_cmdtool_window(wait_for_window=2.0)
            if cmd_window is None:
                print("[ERROR] Could not find CmdTool window")
                return False

            # Send @filepath (no quotes) to CmdTool input
            script_cmd = f"@{script_file}"
            if not self._send_text_to_cmdtool_input(
                cmd_window,
                text=script_cmd,
                send_enter=True,
                pause=0.05,
            ):
                print(f"[ERROR] Failed to send script path to CmdTool input")
                return False
            print(f"[OK] Script path sent: {script_cmd}")
            return True
        except Exception as e:
            print(f"[ERROR] Unexpected error in typecast: {e}")
            return False

    def send_command_to_cmdtool(
        self,
        command: str,
        wait_for_window: float = 0.1,
        send_enter: bool = True,
        verbose: bool = False,
    ) -> bool:
        """Send a single command string to the CmdTool input window."""
        text = str(command).strip()
        if not text:
            return False

        cmd_window = self._connect_cmdtool_window(wait_for_window=wait_for_window)

        if cmd_window is None:
            info_log.error("[ERROR] CmdTool window not found; cannot send command.")
            return False

        try:
            sent = self._send_text_to_cmdtool_input(
                cmd_window,
                text=text,
                send_enter=send_enter,
                pause=0.001,
            )
            if not sent:
                info_log.error("[ERROR] Failed to send command to CmdTool input control")
                return False
            if verbose:
                info_log.info("[OK] Sent CmdTool command: %s", text)
            return True
        except Exception as exc:
            info_log.error(f"[ERROR] Failed to send command to CmdTool: {exc}")
            return False

    def _connect_cmdtool_window(self, wait_for_window: float) -> Any | None:
        end_time = time.time() + max(wait_for_window, 0.01)
        last_error = None

        while time.time() < end_time:
            try:
                app = pywinauto.Application().connect(title="CmdTool")
                window = app.window(title="CmdTool")
                info_log.debug("Connected to CmdTool window by exact title")
                return window
            except Exception as e:
                last_error = e
                try:
                    app = pywinauto.Application().connect(title_re="CmdTool")
                    window = app.window(title_re="CmdTool")
                    info_log.debug("Connected to CmdTool window by title regex")
                    return window
                except Exception as e2:
                    last_error = e2
                    time.sleep(0.1)

        info_log.error(f"Failed to connect to CmdTool window after {wait_for_window}s: {last_error}")
        return None

    @staticmethod
    def _resolve_cmdtool_input(cmd_window: Any) -> Any:
        """Resolve the text input control in CmdTool for direct command send."""
        try:
            ctrl = cmd_window.child_window(class_name="Edit").wrapper_object()
            info_log.debug(f"Resolved CmdTool input by class_name='Edit': {type(ctrl)}")
            return ctrl
        except Exception as e:
            info_log.debug(f"Failed to resolve by class_name: {e}")

        try:
            ctrl = cmd_window.child_window(control_type="Edit").wrapper_object()
            info_log.debug(f"Resolved CmdTool input by control_type='Edit': {type(ctrl)}")
            return ctrl
        except Exception as e:
            info_log.debug(f"Failed to resolve by control_type: {e}")

        info_log.warning("Could not resolve CmdTool input control, falling back to window object")
        return cmd_window

    def _send_text_to_cmdtool_input(self, cmd_window: Any, *, text: str, send_enter: bool, pause: float) -> bool:
        """Send text to CmdTool using clipboard + paste (Tkinter-compatible approach).

        CmdTool is built with Tkinter and doesn't have standard Windows Edit controls.
        Clipboard paste is the most reliable method for Tkinter apps.
        Falls back to keyboard typing if clipboard fails.
        """
        try:
            cmd_window.set_focus()
            time.sleep(0.05)
            self._focus_cmdtool_entry(cmd_window)

            # Approach 1: clipboard paste (most reliable for Tkinter)
            try:
                if self._set_clipboard_text(text):
                    info_log.debug(f"Text copied to clipboard: {text[:50]}...")

                    send_keys("^a", pause=pause)
                    time.sleep(0.02)
                    send_keys("^v", pause=pause)
                    time.sleep(0.05)

                    if send_enter:
                        send_keys("{ENTER}", pause=pause)

                    info_log.debug(f"Text sent via clipboard successfully")
                    return True
                else:
                    info_log.debug("Clipboard set failed, trying keyboard approach")
            except Exception as e:
                info_log.debug(f"Clipboard approach failed: {e}, trying keyboard approach")

            # Approach 2: Fallback to direct keyboard typing
            info_log.debug(f"Using keyboard typing approach for text: {text[:50]}...")
            send_keys("^a", pause=pause)
            time.sleep(0.02)

            send_keys(text, with_spaces=True, pause=pause)
            time.sleep(0.05)

            if send_enter:
                send_keys("{ENTER}", pause=pause)

            info_log.debug(f"Text sent via keyboard successfully")
            return True

        except Exception as e:
            info_log.error(f"Failed to send text to CmdTool: {e}")
            return False

    def send_makesafe(self, command: str = "set safe") -> bool:
        """Send MakeSafe sequence into CmdTool and verify SAFE operating state.

        Sequence:
        1) ENFYS_SAFE 0
        2) wait 2000 ms
        3) ENFYS_RET 0 0 0 0 0 0
        """
        _ = command  # Retained for backward compatibility with previous call signature.
        if not self.send_command_to_cmdtool(command="ENFYS_SAFE 0", wait_for_window=2.0, send_enter=True, verbose=True):
            return False
        time.sleep(2)
        return self.send_command_to_cmdtool(
            command="ENFYS_RET 0 0 0 0 0 0",
            wait_for_window=2.0,
            send_enter=True,
            verbose=True,
        )

    def wait_for_safe_state(self, rs422_log: str | Path | None, timeout_s: float = 10.0, poll_s: float = 0.5) -> bool:
        """Poll latest HK from RS422 log until CURRENT_OPERATING_STATE becomes SAFE (0x02)."""
        if not rs422_log:
            return False

        path = Path(rs422_log)
        if not path.exists():
            return False

        end_time = time.time() + max(timeout_s, 0.5)
        while time.time() < end_time:
            try:
                latest_hk, *_ = eb_packet_utility.read_pkt(path, latest_only=True)
                if latest_hk is not None and int(getattr(latest_hk, "CURRENT_OPERATING_STATE", -1)) == 0x02:
                    return True
            except Exception:
                pass
            time.sleep(max(poll_s, 0.1))
        return False


# Global state for EGSE tools management
egse_started = False
egse_script_path = None
egse_log_file = None
egse_tools_path = r"C:\wdir\EB\EB_EGSE"
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
        else:
            egse_started = False
            logger.error(
                "[ERROR] Failed to start EGSE tools. Verify the EGSE tools folder and that Start_tools.bat exists."
            )
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
