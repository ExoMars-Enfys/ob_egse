import subprocess
import time
from pathlib import Path


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
    
    def send_command_to_cmdtool(self, command: str, wait_for_window: float = 2.0, send_enter: bool = True) -> bool:
        try:
            import pywinauto
            import time as time_module
            import subprocess
            
            print(f"[send_command] Waiting {wait_for_window}s for window...")
            time_module.sleep(wait_for_window)
            
            # Try to connect to CmdTool window
            window = None
            try:
                print("[send_command] Attempting to connect to CmdTool...")
                app = pywinauto.Application().connect(title="CmdTool")
                window = app.window(title="CmdTool")
                print("[send_command] Connected to CmdTool window")
            except Exception as e1:
                print(f"[send_command] Exact title match failed: {e1}")
                try:
                    print("[send_command] Trying regex match...")
                    app = pywinauto.Application().connect(title_re="CmdTool")
                    windows = app.windows()
                    if windows:
                        window = windows[0]
                        print("[send_command] Connected via regex")
                except Exception as e2:
                    print(f"[send_command] Could not find CmdTool window: {e2}")
                    return False
            
            if not window:
                print("[send_command] Window is None after connection attempts")
                return False
            
            try:
                print("[send_command] Setting focus to window...")
                window.set_focus()
                time_module.sleep(0.3)
                
                # Find all edit controls (input fields)
                print("[send_command] Looking for input fields...")
                found_input = False
                try:
                    # Get all descendant controls
                    descendants = window.descendants()
                    print(f"[send_command] Found {len(descendants)} controls in window")
                    
                    # Look for edit controls
                    for idx, control in enumerate(descendants):
                        try:
                            class_name = control.class_name()
                            print(f"[send_command] Control {idx}: {class_name}")
                            
                            # Print additional info for TkChild controls
                            if class_name == 'TkChild':
                                try:
                                    rect = control.rectangle()
                                    print(f"[send_command]   TkChild {idx} rect: {rect}")
                                except Exception:
                                    pass
                            
                            # Look for Edit, RichEdit, or other text input controls
                            if class_name in ['Edit', 'RichEdit20W', 'EDIT', 'RichEdit']:
                                print(f"[send_command] Found input field: {class_name}")
                                control.set_focus()
                                time_module.sleep(0.2)
                                
                                # Copy command to clipboard
                                print(f"[send_command] Copying to clipboard: {command}")
                                safe_command = command.replace('"', '\\"')
                                powershell_cmd = f'powershell -Command "Set-Clipboard -Value \'{safe_command}\'"'
                                result = subprocess.run(powershell_cmd, shell=True, capture_output=True, timeout=5)
                                print(f"[send_command] Clipboard copy result: {result.returncode}")
                                time_module.sleep(0.2)
                                
                                # Paste into the field
                                print("[send_command] Pasting with Ctrl+V...")
                                control.type_keys('^v')
                                time_module.sleep(0.2)
                                
                                if send_enter:
                                    print("[send_command] Pressing Enter...")
                                    control.type_keys('{ENTER}')
                                
                                print(f"[send_command] SUCCESS: Sent command to input field: {command}")
                                found_input = True
                                return True
                        except Exception:
                            pass  # Continue searching
                    
                    if not found_input:
                        print("[send_command] No input field found, trying direct window paste...")
                
                except Exception as e:
                    print(f"[send_command] Error searching for controls: {e}")
                
                # Fallback: type directly to window
                print("[send_command] Attempting to type command directly...")
                window.set_focus()
                time_module.sleep(0.5)
                
                # Click on the input field control
                print("[send_command] Searching for input field TkChild control...")
                try:
                    # Get all TkChild controls
                    tk_children = [ctrl for ctrl in descendants if ctrl.class_name() == 'TkChild']
                    print(f"[send_command] Found {len(tk_children)} TkChild controls")
                    
                    # Control 10 in descendants is the input field at the bottom
                    # When filtered to only TkChild, it becomes index 8 (0-7 are first 8 TkChild, then 2 Buttons are skipped, then Control 10 is the 9th TkChild = index 8)
                    if len(tk_children) > 8:
                        input_control = tk_children[8]
                        print("[send_command] Using TkChild at index 8 (original Control 10 - the input field)...")
                        input_control.click_input()
                        time_module.sleep(0.5)
                    else:
                        print("[send_command] Not enough controls found, using last TkChild...")
                        if tk_children:
                            tk_children[-1].click_input()
                            time_module.sleep(0.5)
                        else:
                            window.click()
                            time_module.sleep(0.5)
                except Exception as e:
                    print(f"[send_command] Error finding input control: {e}")
                    window.click()
                    time_module.sleep(0.5)
                
                # Type the command directly using SendKeys
                print(f"[send_command] Typing command with SendKeys: {command}")
                try:
                    from pywinauto.keyboard import send_keys
                    send_keys(command, pause=0.05)
                    print("[send_command] Command typed using SendKeys")
                    time_module.sleep(0.3)
                    
                    if send_enter:
                        print("[send_command] Pressing Enter with SendKeys...")
                        send_keys('{ENTER}')
                        print("[send_command] Enter key pressed")
                except Exception as e:
                    print(f"[send_command] Error typing with SendKeys: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
                
                print(f"[send_command] SUCCESS: Typed command to CmdTool window: {command}")
                return True
                    
            except Exception as e:
                print(f"[send_command] Error interacting with window: {e}")
                import traceback
                traceback.print_exc()
                return False
            
        except ImportError:
            print("[send_command] pywinauto not installed")
            return False
        except Exception as e:
            print(f"[send_command] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False
