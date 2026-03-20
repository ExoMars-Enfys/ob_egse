# EB Interface Module Breakdown

This document explains what `src/utility_modules/eb_interface.py` does, function by function, and how it connects to other files in this project.

## Purpose

`eb_interface.py` is the runtime bridge between the NiceGUI application and external EB EGSE tooling on Windows. It centralizes:

- Starting and stopping EGSE tools via batch files
- Sending script/command text into the EGSE CmdTool window
- Selecting filesystem paths with native dialogs (EGSE folder and RS422 log)
- Tracking log file changes and providing tail snapshots for UI display

## High-Level Responsibilities

1. Process control
- Launches `Start_tools.bat`
- Launches `Stop_tools.bat`

2. GUI automation
- Uses `pywinauto` to find the `CmdTool` window
- Sends commands either by paste into input control or keyboard fallback

3. File/path selection
- Uses `tkinter.filedialog` to select EGSE folder and RS422 log file

4. Log state tracking
- Keeps in-memory path/mtime state to avoid unnecessary rereads

## Global Runtime State

The module stores global state used by the UI:

- `egse_started`: whether tools are considered running by this module
- `egse_script_path`: last selected script path
- `egse_log_file`: declared but currently not actively used
- `egse_tools_path`: active EGSE folder
- `egse_interface`: lazily-created singleton `EGSEInterface`
- `rs422_log_path`: user-selected RS422 log file
- `_egse_log_state`: cache for EGSE log path + mtime
- `_rs422_log_state`: cache for RS422 log path + mtime

## Class: EGSEInterface

### `__init__(egse_path: str = r"C:\wdir\IFM\EB")`

Initializes the interface object with a base path and a process handle placeholder.

- Inputs: `egse_path`
- Sets: `self.egse_path`, `self.process_handle`

### `start_egse(script_arg: str | None = None) -> bool`

Starts EGSE tools by running `Start_tools.bat` from `self.egse_path`.

Behavior:

- Verifies batch file exists
- Builds command string, optionally appending `script_arg`
- Starts process with `subprocess.Popen(..., shell=True)`
- Waits 5 seconds for tool initialization
- Returns `True` on success, otherwise `False`

Notes:

- Captures stdout/stderr pipes but does not consume them later in this module
- Uses `print` for status/error reporting

### `stop_egse() -> bool`

Stops EGSE tools by running `Stop_tools.bat`.

Behavior:

- Verifies batch file exists
- Runs stop script with `subprocess.Popen(..., shell=True)`
- Waits 2 seconds
- Returns success/failure as boolean

### `send_command_to_cmdtool(command, wait_for_window=2.0, send_enter=True, verbose=False) -> bool`

Attempts to send command text into the EGSE CmdTool window.

Primary strategy:

- Connect to a window titled `CmdTool`
- Fallback to regex title matching (`title_re="CmdTool"`)
- Enumerate descendant controls and look for input-like controls:
  - `Edit`, `EDIT`, `RichEdit`, `RichEdit20W`
- If input control found:
  - Copy command to clipboard using a PowerShell `Set-Clipboard` command
  - Paste with `Ctrl+V`
  - Optionally send Enter

Fallback strategy:

- If no expected edit control is found:
  - Locate `TkChild` controls
  - Click probable input control (hard-coded index heuristic)
  - Type with `pywinauto.keyboard.send_keys`
  - Optionally send Enter

Returns:

- `True` when command appears successfully sent
- `False` for import errors, window lookup failures, or interaction failures

Dependencies:

- Requires `pywinauto` to be installed
- Assumes a Windows desktop session with CmdTool visible/focusable

## Module-Level Functions

### `locate_latest_egse_log() -> Path | None`

Scans `egse_tools_path` for `*.log` and `*.LOG`, deduplicates matches, and returns newest file by mtime.

Used by:

- `get_egse_log_snapshot`

### `locate_latest_rs422_log() -> Path | None`

Returns only the currently selected RS422 log path if it exists.

Important behavior:

- Does not auto-scan directories
- Relies on `rs422_log_path` set by `select_rs422_log`

### `rs422_log_changed(log_path: Path | None) -> bool`

Detects whether RS422 log source changed since last check.

Behavior:

- If `log_path` is `None`, resets state and returns `False`
- Compares path and mtime against `_rs422_log_state`
- Updates cache when changed and returns `True`

Used by UI polling loop to avoid parsing same log repeatedly.

### `get_egse_log_snapshot(max_lines: int, force: bool = False) -> tuple[bool, str | None, list[str], str | None]`

Returns a recent EGSE log snapshot only when changed (unless `force=True`).

Tuple format:

- `changed`: whether UI should refresh output
- `header`: path label string like `EB EGSE log: <path>`
- `lines`: last `max_lines` log lines
- `error`: user-facing error string, if any

Behavior details:

- Uses `locate_latest_egse_log`
- Maintains `_egse_log_state` path/mtime cache
- Reads file with `encoding="utf-8", errors="replace"`

### `_get_egse_interface() -> EGSEInterface`

Lazy singleton getter for `egse_interface`.

### `_update_egse_interface_path(new_path: str) -> None`

Updates singleton interface object path when user changes EGSE folder.

### `_create_dialog_root() -> Tk`

Creates a temporary topmost hidden Tk root for native dialogs.

### `select_egse_folder(logger) -> None`

Opens folder picker and updates `egse_tools_path`.

Behavior:

- Sets selected directory as EGSE tools path
- Calls `_update_egse_interface_path`
- Logs result via provided logger

### `select_rs422_log(logger) -> bool`

Opens file picker for RS422 log and stores chosen path in `rs422_log_path`.

Returns:

- `True` if a file was selected
- `False` otherwise

### `start_egse_tools(logger) -> None`

High-level start wrapper used by GUI callbacks.

Behavior:

- Logs start attempt
- Calls `_get_egse_interface().start_egse()`
- Updates `egse_started` flag
- Logs success/failure

### `stop_egse_tools(logger) -> None`

High-level stop wrapper used by GUI callbacks.

Behavior:

- Logs stop attempt
- Calls `_get_egse_interface().stop_egse()`
- Updates `egse_started` on success

### `select_egse_script(logger) -> None`

Lets user choose a script and sends it to CmdTool as an `@` command.

Behavior:

- Requires `egse_started == True`; otherwise logs warning and exits
- Opens script file picker
- Stores selected path in `egse_script_path`
- Builds command argument:
  - `@filename` when script is inside EGSE folder
  - `@absolute_path` otherwise
- Sends command through `send_command_to_cmdtool(..., wait_for_window=0.5)`

## Connections To Other Files

## 1) UI entry points and callbacks

File: `src/widget_modules/ebgui.py`

- Imports module: `import eb_interface`
- Wires buttons/callbacks to:
  - `start_egse_tools`
  - `stop_egse_tools`
  - `select_egse_folder`
  - `select_egse_script`
  - `select_rs422_log`

This is the main upstream caller of `eb_interface.py`.

## 2) RS422 polling -> packet decoding pipeline

File: `src/widget_modules/ebgui.py`

Runtime flow:

1. UI loop calls `locate_latest_rs422_log()`
2. UI loop gates on `rs422_log_changed(...)`
3. On change, UI calls `eb_sniffer.read_pkt(rs422_log, latest_only=True)`

File: `src/utility_modules/eb_packet_utility.py`

- Provides `read_pkt(...)` used in the flow above
- Parses telemetry packets from the selected RS422 log
- Pushes decoded objects to queues in constants

This means `eb_interface.py` does not decode telemetry itself. It only selects and tracks the log source that decoding uses.

## 3) Queue/state consumers

File: `src/core_modules/constants.py`

- Defines queues (`hk_queue`, `sci_queue`, etc.) that decoded packet modules populate
- `eb_interface.py` does not write these queues directly, but it enables the input file updates that trigger queue production

## 4) EGSE log viewer path

File: `src/widget_modules/ebgui.py`

- Calls `get_egse_log_snapshot(...)` during log panel refresh
- Displays returned header, lines, and errors in the GUI log widget

## Data and Control Flow Summary

1. User clicks Start Tools in GUI
2. `ebgui.py` calls `start_egse_tools(logger)`
3. `EGSEInterface.start_egse()` launches EGSE scripts externally
4. User selects RS422 log via `select_rs422_log(logger)`
5. UI loop checks `rs422_log_changed(...)`
6. On change, UI triggers packet parse (`eb_packet_utility.read_pkt`)
7. Decoded results propagate to queues and UI widgets

In parallel:

- User can select a script via `select_egse_script(logger)`
- Module sends `@script` command into CmdTool using UI automation
- GUI can show EGSE tool logs via `get_egse_log_snapshot(...)`

## Platform and Dependency Assumptions

- Intended for Windows desktop operation
- External EGSE batch scripts must exist in selected folder
- `pywinauto` must be available for command sending automation
- Active GUI desktop session required for focus/click/keystroke automation

## Current Design Tradeoffs

1. Module-level global state
- Simple to wire into GUI callbacks
- Harder to unit test and reason about concurrent use

2. UI automation heuristics for CmdTool
- Flexible fallback logic exists
- Tk control index assumptions may be brittle if CmdTool layout changes

3. `shell=True` process launching
- Practical for `.bat` scripts
- Worth careful path validation in environments with untrusted input

4. Logging style
- Mixes `print` (class methods) and injected `logger` (module wrappers)
- Consistent logger-only strategy would simplify diagnostics

## Suggested Future Improvements

- Add type hints for `logger` (e.g., `logging.Logger`)
- Replace hard-coded TkChild index heuristic with stronger control identification
- Normalize to one logging path (prefer logger over print)
- Introduce small state object/dataclass instead of module globals
- Add unit tests around mtime/path cache logic and path command formatting

## Quick Reference

- Start EGSE tools: `start_egse_tools(logger)`
- Stop EGSE tools: `stop_egse_tools(logger)`
- Pick EGSE tools folder: `select_egse_folder(logger)`
- Pick RS422 log file: `select_rs422_log(logger)`
- Pick and send EGSE script: `select_egse_script(logger)`
- Tail EGSE log text: `get_egse_log_snapshot(max_lines, force=False)`
