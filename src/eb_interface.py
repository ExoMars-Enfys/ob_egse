import subprocess
import time
from pathlib import Path
from tkinter import filedialog, Tk


class EGSEInterface:
    
    def __init__(self, egse_path: str = r"C:\wdir\IFM\EB"):
        self.egse_path = Path(egse_path)
        self.process_handle = None
    
    def start_egse(self, script_arg: str | None = None) -> bool:
        try:
            start_bat = self.egse_path / "Start_tools.bat"
            if not start_bat.exists():
                print(f"Start_tools.bat not found at {start_bat}")
                return False
            
            # Build command with optional script argument
            cmd = str(start_bat)
            if script_arg:
                cmd = f'"{cmd}" {script_arg}'
            
            self.process_handle = subprocess.Popen(
                cmd,
                shell=True,
                cwd=str(self.egse_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"EGSE tools started{' with script: ' + script_arg if script_arg else ''}")
            time.sleep(5)  # Wait for tools to initialize
            return True
        except Exception as e:
            print(f"Error starting EGSE: {e}")
            return False
    
    def stop_egse(self) -> bool:
        try:
            stop_bat = self.egse_path / "Stop_tools.bat"
            if not stop_bat.exists():
                print(f"Stop_tools.bat not found at {stop_bat}")
                return False
            
            subprocess.Popen(
                str(stop_bat),
                shell=True,
                cwd=str(self.egse_path)
            )
            print("EGSE tools stopped")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Error stopping EGSE: {e}")
            return False
    
    def send_command_to_cmdtool(
        self,
        command: str,
        wait_for_window: float = 2.0,
        send_enter: bool = True,
        verbose: bool = False,
    ) -> bool:
        try:
            import pywinauto
            import time as time_module
            import subprocess

            def _log(message: str) -> None:
                if verbose:
                    print(message)

            _log(f"[send_command] Waiting {wait_for_window}s for window...")
            time_module.sleep(wait_for_window)

            # Try to connect to CmdTool window
            window = None
            try:
                _log("[send_command] Attempting to connect to CmdTool...")
                app = pywinauto.Application().connect(title="CmdTool")
                window = app.window(title="CmdTool")
                _log("[send_command] Connected to CmdTool window")
            except Exception as e1:
                _log(f"[send_command] Exact title match failed: {e1}")
                try:
                    _log("[send_command] Trying regex match...")
                    app = pywinauto.Application().connect(title_re="CmdTool")
                    windows = app.windows()
                    if windows:
                        window = windows[0]
                        _log("[send_command] Connected via regex")
                except Exception as e2:
                    _log(f"[send_command] Could not find CmdTool window: {e2}")
                    return False

            if not window:
                _log("[send_command] Window is None after connection attempts")
                return False

            try:
                _log("[send_command] Setting focus to window...")
                window.set_focus()
                time_module.sleep(0.3)

                # Find all edit controls (input fields)
                _log("[send_command] Looking for input fields...")
                found_input = False
                try:
                    # Get all descendant controls
                    descendants = window.descendants()
                    _log(f"[send_command] Found {len(descendants)} controls in window")

                    # Look for edit controls
                    for idx, control in enumerate(descendants):
                        try:
                            class_name = control.class_name()
                            _log(f"[send_command] Control {idx}: {class_name}")

                            # Print additional info for TkChild controls
                            if class_name == 'TkChild':
                                try:
                                    rect = control.rectangle()
                                    _log(f"[send_command]   TkChild {idx} rect: {rect}")
                                except Exception:
                                    pass

                            # Look for Edit, RichEdit, or other text input controls
                            if class_name in ['Edit', 'RichEdit20W', 'EDIT', 'RichEdit']:
                                _log(f"[send_command] Found input field: {class_name}")
                                control.set_focus()
                                time_module.sleep(0.2)

                                # Copy command to clipboard
                                _log(f"[send_command] Copying to clipboard: {command}")
                                safe_command = command.replace('"', '\\"')
                                powershell_cmd = f'powershell -Command "Set-Clipboard -Value \'{safe_command}\'"'
                                result = subprocess.run(powershell_cmd, shell=True, capture_output=True, timeout=5)
                                _log(f"[send_command] Clipboard copy result: {result.returncode}")
                                time_module.sleep(0.2)

                                # Paste into the field
                                _log("[send_command] Pasting with Ctrl+V...")
                                control.type_keys('^v')
                                time_module.sleep(0.2)

                                if send_enter:
                                    _log("[send_command] Pressing Enter...")
                                    control.type_keys('{ENTER}')

                                _log(f"[send_command] SUCCESS: Sent command to input field: {command}")
                                found_input = True
                                return True
                        except Exception:
                            pass  # Continue searching

                    if not found_input:
                        _log("[send_command] No input field found, trying direct window paste...")

                except Exception as e:
                    _log(f"[send_command] Error searching for controls: {e}")

                # Fallback: type directly to window
                _log("[send_command] Attempting to type command directly...")
                window.set_focus()
                time_module.sleep(0.5)

                # Click on the input field control
                _log("[send_command] Searching for input field TkChild control...")
                try:
                    # Get all TkChild controls
                    tk_children = [ctrl for ctrl in descendants if ctrl.class_name() == 'TkChild']
                    _log(f"[send_command] Found {len(tk_children)} TkChild controls")

                    # Control 10 in descendants is the input field at the bottom
                    # When filtered to only TkChild, it becomes index 8 (0-7 are first 8 TkChild, then 2 Buttons are skipped, then Control 10 is the 9th TkChild = index 8)
                    if len(tk_children) > 8:
                        input_control = tk_children[8]
                        _log("[send_command] Using TkChild at index 8 (original Control 10 - the input field)...")
                        input_control.click_input()
                        time_module.sleep(0.5)
                    else:
                        _log("[send_command] Not enough controls found, using last TkChild...")
                        if tk_children:
                            tk_children[-1].click_input()
                            time_module.sleep(0.5)
                        else:
                            window.click()
                            time_module.sleep(0.5)
                except Exception as e:
                    _log(f"[send_command] Error finding input control: {e}")
                    window.click()
                    time_module.sleep(0.5)

                # Type the command directly using SendKeys
                _log(f"[send_command] Typing command with SendKeys: {command}")
                try:
                    from pywinauto.keyboard import send_keys
                    send_keys(command, pause=0.05)
                    _log("[send_command] Command typed using SendKeys")
                    time_module.sleep(0.3)

                    if send_enter:
                        _log("[send_command] Pressing Enter with SendKeys...")
                        send_keys('{ENTER}')
                        _log("[send_command] Enter key pressed")
                except Exception as e:
                    _log(f"[send_command] Error typing with SendKeys: {e}")
                    import traceback
                    traceback.print_exc()
                    return False

                _log(f"[send_command] SUCCESS: Typed command to CmdTool window: {command}")
                return True

            except Exception as e:
                _log(f"[send_command] Error interacting with window: {e}")
                import traceback
                traceback.print_exc()
                return False

        except ImportError:
            if verbose:
                print("[send_command] pywinauto not installed")
            return False
        except Exception as e:
            if verbose:
                print(f"[send_command] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False


# Global state for EGSE tools management
egse_started = False
egse_script_path = None
egse_log_file = None
egse_tools_path = r"C:\wdir\IFM\EB\EGSE"
egse_interface = None
rs422_log_path: str | None = None
_egse_log_state: dict[str, object] = {"path": None, "mtime": None}
_rs422_log_state: dict[str, object] = {"path": None, "mtime": None}


def locate_latest_egse_log() -> Path | None:
    """Locate the newest EB EGSE log file."""
    base = Path(egse_tools_path)
    log_files: list[Path] = []
    seen: set[Path] = set()
    if not base.exists():
        return None
    for path in base.glob("*.log"):
        if path not in seen:
            log_files.append(path)
            seen.add(path)
    for path in base.glob("*.LOG"):
        if path not in seen:
            log_files.append(path)
            seen.add(path)

    if not log_files:
        return None

    return max(log_files, key=lambda path: path.stat().st_mtime)


def locate_latest_rs422_log() -> Path | None:
    """Return only the RS422if log file selected by the user."""
    if not rs422_log_path:
        return None

    candidate = Path(rs422_log_path)
    if candidate.exists():
        return candidate
    return None


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


def _get_egse_interface() -> EGSEInterface:
    global egse_interface
    if egse_interface is None:
        egse_interface = EGSEInterface(egse_tools_path)
    return egse_interface


def _update_egse_interface_path(new_path: str) -> None:
    global egse_interface
    if egse_interface is None:
        egse_interface = EGSEInterface(new_path)
    else:
        egse_interface.egse_path = Path(new_path)


def _create_dialog_root() -> Tk:
    root = Tk()
    root.withdraw()
    root.lift()
    root.attributes("-topmost", True)
    root.focus_force()
    root.update_idletasks()
    return root


def select_egse_folder(logger) -> None:
    """Open folder picker to set the EGSE tools directory."""
    global egse_tools_path

    root = None
    try:
        root = _create_dialog_root()
        selected_dir = filedialog.askdirectory(
            title="Select EGSE tools folder",
            initialdir=egse_tools_path,
            parent=root,
        )

        if selected_dir:
            egse_tools_path = selected_dir
            _update_egse_interface_path(egse_tools_path)
            logger.info(f"EGSE tools folder set to: {egse_tools_path}")
    except Exception as exc:
        logger.error(f"[ERROR] Error selecting EGSE tools folder: {exc}")
    finally:
        if root is not None:
            root.destroy()


def select_rs422_log(logger) -> bool:
    """Open file picker to select an RS422if log file."""
    global rs422_log_path

    root = None
    try:
        root = _create_dialog_root()
        file_path = filedialog.askopenfilename(
            title="Select RS422if log file",
            filetypes=[("RS422if log", "RS422if_*.log"), ("RS422if log", "RS422if_*.LOG"), ("Text files", "*.txt")],
            initialdir=egse_tools_path,
            parent=root,
        )

        if file_path:
            rs422_log_path = file_path
            logger.info(f"RS422if log set to: {rs422_log_path}")
            return True
    except Exception as exc:
        logger.error(f"[ERROR] Error selecting RS422if log file: {exc}")
    finally:
        if root is not None:
            root.destroy()

    return False


def start_egse_tools(logger) -> None:
    """Start the EGSE tools and locate the latest log file."""
    global egse_started, egse_log_file
    try:
        logger.info("Starting EB EGSE Tools...")
        interface = _get_egse_interface()
        if interface.start_egse():
            egse_started = True
            logger.info("[OK] EGSE tools started successfully")
        else:
            egse_started = False
            logger.error("[ERROR] Failed to start EGSE tools")

        # TODO: Wait 5 seconds for tools to initialize
        # time.sleep(5)

        # TODO: Look for latest RS422if log file
        # egse_log_file = locate_latest_egse_log()
    except Exception as exc:
        logger.error(f"[ERROR] Error starting EGSE: {exc}")
        egse_started = False


def stop_egse_tools(logger) -> None:
    """Stop the EGSE tools."""
    global egse_started
    try:
        logger.info("Stopping EB EGSE Tools...")
        interface = _get_egse_interface()
        if interface.stop_egse():
            egse_started = False
            logger.info("[OK] EGSE tools stopped successfully")
        else:
            logger.error("[ERROR] Failed to stop EGSE tools")
    except Exception as exc:
        logger.error(f"[ERROR] Error stopping EGSE: {exc}")


def select_egse_script(logger) -> None:
    """Open file picker to select an EGSE script, with warning if tools not started."""
    global egse_started, egse_script_path

    if not egse_started:
        logger.warning("[WARN] EGSE tools must be started before selecting a script")
        return

    root = None
    try:
        root = _create_dialog_root()
        file_path = filedialog.askopenfilename(
            title="Select EGSE script file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=egse_tools_path,
            parent=root,
        )

        if file_path:
            egse_script_path = file_path
            script_filename = Path(file_path).name
            logger.info(f"Selected script: {script_filename}")
            interface = _get_egse_interface()
            tools_path = Path(egse_tools_path).resolve()
            script_path = Path(file_path).resolve()
            if hasattr(script_path, "is_relative_to"):
                in_tools_dir = script_path.is_relative_to(tools_path)
            else:
                in_tools_dir = str(script_path).startswith(str(tools_path))
            cmd_arg = f"@{script_filename}" if in_tools_dir else f"@{script_path}"
            if not interface.send_command_to_cmdtool(
                cmd_arg,
                wait_for_window=0.5,
                send_enter=True,
            ):
                logger.error("[ERROR] Failed to send script to CmdTool")
    except Exception as exc:
        logger.error(f"[ERROR] Error selecting script: {exc}")
    finally:
        if root is not None:
            root.destroy()
