# Std library
import logging
import time
from contextlib import nullcontext
from datetime import datetime

# Added packages
import serial

# Local modules
from core_modules import config as config
from core_modules import constants as const
import threading

info_log = logging.getLogger("info_log")
event_log = logging.getLogger("event_log")
psu_log = logging.getLogger("psu_log")

_LAST_CHANNEL_SWITCH: dict[int, tuple[int, float]] = {}


def _mark_transient_toggle(mode_state) -> None:
    """Mark that a user-issued channel toggle occurred so monitor can reset transient timing explicitly."""
    if isinstance(mode_state, dict):
        mode_state["_psu_toggle_epoch"] = int(mode_state.get("_psu_toggle_epoch", 0)) + 1


def set_psu_command_in_flight(mode_state, in_flight: bool) -> None:
    """Mark UI command activity so monitor polling can yield and keep toggle latency low."""
    if isinstance(mode_state, dict):
        mode_state["_psu_command_in_flight"] = bool(in_flight)


def _queue_shutdown_snapshot(active_ebmode: bool) -> None:
    """Publish immediate all-off status so UI toggles reflect protection shutdown without waiting for next poll."""
    if const.psu_queue is None:
        return
    snapshot = {
        "TIME": datetime.now(),
        "STATUS": 0,
        "CH1_STATUS": 0,
        "CH2_STATUS": 0,
        "CH3_STATUS": 0,
        "CH4_STATUS": 0,
    }
    if active_ebmode:
        snapshot.update(
            {
                "PSU_EB_V": None,
                "PSU_EB_I": None,
                "PSU_ROV_HTR_V": None,
                "PSU_ROV_HTR_I": None,
            }
        )
    else:
        snapshot.update(
            {
                "CH1_V": None,
                "CH1_I": None,
                "CH2_V": None,
                "CH2_I": None,
                "CH3_V": None,
                "CH3_I": None,
            }
        )
    const.psu_queue.put(snapshot)


def init_psu_comms(psu_com: str) -> serial.Serial:
    """Initialise an unopened PSU serial port handle."""
    # Keep read timeout short so monitor polling cannot block command writes for long.
    psuport = serial.Serial(port=None, timeout=0.15)
    psuport.port = psu_com  # Assign com_port afterwards to prevent opening immediately
    print(f"Initialized PSU COM port: {psu_com}")
    return psuport


def open_psu_comms(port: serial.Serial, psu_not_required):
    """Open PSU serial comms and verify the expected IDN response."""
    try:
        port.open()
    except serial.SerialException:
        if psu_not_required:
            return
        else:
            info_log.error("No device found on COM Port {port.port}, try another")
            raise SystemExit

    port.reset_output_buffer()  # Clear stale bytes before first transactions
    port.reset_input_buffer()

    port.write("*IDN?\r\n".encode("utf-8"))
    response = port.readline().decode("utf-8")
    info_log.info(f"Connected to PSU *IDN? Response: {response}")

    if "THURLBY THANDAR, MX100QP" not in response:
        info_log.error(f"PSU COM Port available but did not respond with expected IDN. Response: {response}")
        info_log.error("Please check the PSU is connected and powered on, and that the correct COM port is selected.")
        raise SystemExit

    return port


def close_psu_comms(port: serial.Serial) -> None:
    """Return PSU to local mode, flush OS buffers, and safely close the serial port."""
    if port and port.is_open:
        # 1. Clear out any residual data sitting in the buffers
        port.reset_input_buffer()
        port.reset_output_buffer()
        
        # 2. Send the exact working local command
        port.write("LOCAL\n".encode("utf-8"))
        
        # 3. CRITICAL: Force the OS to push the bytes out to the wire right now
        port.flush()
        
        # 4. Give the PSU parser a split second to breathe before killing the port
        time.sleep(0.2)
        
        # 5. Cleanly shut down the port
        port.close()
    return


def psuRead(port, channel, type, output=False):
    """Read a PSU value for a channel and command type."""
    if not output:
        port.write(f"{type}{channel}?\r\n".encode("utf-8"))
        response = port.readline().decode("utf-8")
    else:
        port.write(f"{type}{channel}O?\r\n".encode("utf-8"))
        response = port.readline().decode("utf-8")

    port.reset_output_buffer()  # Clear stale bytes before next transaction
    port.reset_input_buffer()
    return response


def parse_psu_reading(raw_value: str) -> float:
    """Parse raw PSU text readings into float values with safe fallback to 0.0."""
    value = raw_value.strip()
    if not value:
        return 0.0
    if value[-1].isalpha():
        value = value[:-1]
    try:
        return float(value)
    except ValueError:
        return 0.0


def _oob_bounds(ch_cfg: dict, voltage_mode: str) -> tuple[float, float]:
    """Return (lower, upper) OOB voltage bounds centred on the selected set voltage.

    The tolerance window is derived from the NOM-based envelope in BUS_VOLTAGES:
        tol_low  = NOM - MIN
        tol_high = MAX - NOM
    and is then shifted to be centred on the currently set voltage (MIN/NOM/MAX),
    so OOB detection stays proportionally tight regardless of which mode is active.
    """
    v_min = ch_cfg.get("MIN", 0.0)
    v_nom = ch_cfg.get("NOM", 0.0)
    v_max = ch_cfg.get("MAX", 0.0)
    tol_low = v_nom - v_min
    tol_high = v_max - v_nom
    set_v = ch_cfg.get(voltage_mode, v_nom)
    return (set_v - tol_low, set_v + tol_high)


def parse_psu_status(raw_value: str) -> int:
    """Parse PSU ON/OFF status text into int with safe fallback to 0."""
    value = raw_value.strip()
    if not value:
        return 0

    try:
        return int(value)
    except ValueError:
        # Some devices occasionally return value strings (for example "0.0580A")
        # when the serial stream is noisy or misaligned. Treat any non-zero as ON.
        reading = parse_psu_reading(value)
        return 1 if abs(reading) > 0.0 else 0


def psu_monitor_thread(port, ebmode, stop_event, freq, hk_pause_event=None, mode_state=None, port_lock=None):
    """Monitor PSU channels, log telemetry, and shut down on limit violations."""
    if not port:
        return

    last_ch1_status = None
    last_ch2_status = None
    last_ch3_status = None
    last_ch4_status = None
    last_eb_status = None
    last_rov_htr_status = None
    last_mode_is_eb = None
    last_toggle_epoch = None
    last_error_msg = None
    on_since = None

    while not stop_event.is_set():
        try:
            active_ebmode = bool(mode_state.get("ebmode", ebmode)) if isinstance(mode_state, dict) else ebmode
            if isinstance(mode_state, dict) and mode_state.get("_psu_command_in_flight"):
                stop_event.wait(0.01)
                continue
            # Try to get LISN check state from mode_state if present (from UI state)
            lisn_check_enabled = False
            if isinstance(mode_state, dict):
                # Expecting: mode_state["channels"]["psu_ch4"]["lisn_check_enabled"]
                try:
                    lisn_check_enabled = bool(
                        mode_state.get("channels", {}).get("psu_ch4", {}).get("lisn_check_enabled", False)
                    )
                except Exception:
                    lisn_check_enabled = False

                toggle_epoch = int(mode_state.get("_psu_toggle_epoch", 0))
                if last_toggle_epoch is None:
                    last_toggle_epoch = toggle_epoch
                elif toggle_epoch != last_toggle_epoch:
                    # Explicit command edge (including quick OFF->ON) forces a fresh transient window.
                    on_since = time.monotonic()
                    last_toggle_epoch = toggle_epoch

            if last_mode_is_eb is None or last_mode_is_eb != active_ebmode:
                # Reset edge detectors on mode transition so first ON in new mode gets transient delay.
                last_ch1_status = 0
                last_ch2_status = 0
                last_ch3_status = 0
                last_ch4_status = 0
                last_eb_status = 0
                last_rov_htr_status = 0
                on_since = None
                last_mode_is_eb = active_ebmode
            lock_ctx = port_lock if port_lock is not None else nullcontext()
            acquired_port_lock = False
            if port_lock is not None:
                acquired_port_lock = port_lock.acquire(blocking=False)
                if not acquired_port_lock:
                    # Prioritize user command paths over monitor polling to keep toggles responsive.
                    continue
                lock_ctx = nullcontext()
            try:
                with lock_ctx:
                    if active_ebmode:
                        ch1_status = parse_psu_status(psuRead(port, "1", "OP", False))
                        ch2_status = parse_psu_status(psuRead(port, "2", "OP", False))
                        ebstatus = parse_psu_status(psuRead(port, "4", "OP", False))
                        rov_htr_status = parse_psu_status(psuRead(port, "3", "OP", False))
                        eb_was_on = bool(last_eb_status)
                        rov_was_on = bool(last_rov_htr_status)
                        any_enabled = bool(ebstatus or rov_htr_status)

                        if hk_pause_event is not None:
                            if any_enabled:
                                hk_pause_event.clear()
                            else:
                                hk_pause_event.set()

                        if not any_enabled:
                            on_since = None
                            transitioned_off = eb_was_on or rov_was_on
                            if const.psu_queue is not None and transitioned_off:
                                const.psu_queue.put(
                                    {
                                        "TIME": datetime.now(),
                                        "STATUS": 0,
                                        "CH1_STATUS": ch1_status,
                                        "CH2_STATUS": ch2_status,
                                        "CH3_STATUS": rov_htr_status,
                                        "CH4_STATUS": ebstatus,
                                        "PSU_EB_V": None,
                                        "PSU_EB_I": None,
                                        "PSU_ROV_HTR_V": None,
                                        "PSU_ROV_HTR_I": None,
                                    }
                                )

                        # Assign timer for transient protection if either channel just turned on.
                        if ebstatus != 0 and last_eb_status in (None, 0):
                            on_since = time.monotonic()
                        if rov_htr_status != 0 and last_rov_htr_status in (None, 0):
                            on_since = time.monotonic()
                        last_eb_status = ebstatus
                        last_rov_htr_status = rov_htr_status

                        eb_v = parse_psu_reading(psuRead(port, "4", "V", True).rstrip())
                        eb_i = parse_psu_reading(psuRead(port, "4", "I", True).rstrip())

                        rov_htr_v = parse_psu_reading(psuRead(port, "3", "V", True).rstrip())
                        rov_htr_i = parse_psu_reading(psuRead(port, "3", "I", True).rstrip())

                        ch1_v = parse_psu_reading(psuRead(port, "1", "V", True).rstrip())
                        ch1_i = parse_psu_reading(psuRead(port, "1", "I", True).rstrip())
                        ch2_v = parse_psu_reading(psuRead(port, "2", "V", True).rstrip())
                        ch2_i = parse_psu_reading(psuRead(port, "2", "I", True).rstrip())

                        psu_readings = {
                            "TIME": datetime.now(),
                            "STATUS": ebstatus,
                            "CH1_STATUS": ch1_status,
                            "CH2_STATUS": ch2_status,
                            "CH3_STATUS": rov_htr_status,
                            "CH4_STATUS": ebstatus,
                            "PSU_EB_V": eb_v,
                            "PSU_EB_I": eb_i,
                            "PSU_ROV_HTR_V": rov_htr_v,
                            "PSU_ROV_HTR_I": rov_htr_i,
                            "CH1_V": ch1_v,
                            "CH1_I": ch1_i,
                            "CH2_V": ch2_v,
                            "CH2_I": ch2_i,
                            "CH3_V": rov_htr_v,
                            "CH3_I": rov_htr_i,
                            "CH4_V": eb_v,
                            "CH4_I": eb_i,
                        }
                        if const.psu_queue is not None:
                            const.psu_queue.put(psu_readings)

                        psu_log.info(
                            f"CH3(status={rov_htr_status}) {rov_htr_v}\t{rov_htr_i}\tCH4(status={ebstatus}) {eb_v}\t{eb_i}"
                        )

                        ebstatus = parse_psu_status(psuRead(port, "4", "OP", False))
                        rov_htr_status = parse_psu_status(psuRead(port, "3", "OP", False))

                        if on_since is not None and time.monotonic() - on_since < 1:
                            continue

                        # CH3 (ROV HTR) checks always apply
                        _voltage_mode = mode_state.get("voltage_mode", "NOM") if isinstance(mode_state, dict) else "NOM"
                        _eb_v = const.BUS_VOLTAGES.get("EB", {})
                        ch3_min, ch3_max = _oob_bounds(_eb_v.get("CH3", {}), _voltage_mode)
                        ch4_min, ch4_max = _oob_bounds(_eb_v.get("CH4", {}), _voltage_mode)
                        if rov_htr_status and not (ch3_min < rov_htr_v < ch3_max):
                            psu_log.error(f"Voltage out of bounds Ch3 :  {rov_htr_v}")
                            shutdown_psu_outputs(port)
                            _queue_shutdown_snapshot(active_ebmode)

                        if rov_htr_status and (rov_htr_i >= 150):
                            psu_log.error(f"Current out of bounds Ch3 :  {rov_htr_i}")
                            shutdown_psu_outputs(port)
                            _queue_shutdown_snapshot(active_ebmode)

                        # CH4 (EB) checks only if LISN check is enabled
                        if lisn_check_enabled:
                            if ebstatus and not (ch4_min < eb_v < ch4_max):
                                psu_log.error(f"Voltage out of bounds Ch4 :  {eb_v}")
                                shutdown_psu_outputs(port)
                                _queue_shutdown_snapshot(active_ebmode)

                            if ebstatus and (eb_i >= 500):
                                psu_log.error(f"Current out of bounds Ch4 :  {eb_i}")
                                shutdown_psu_outputs(port)
                                _queue_shutdown_snapshot(active_ebmode)

                    else:
                        ch1_status = parse_psu_status(psuRead(port, "1", "OP", False))
                        ch2_status = parse_psu_status(psuRead(port, "2", "OP", False))
                        ch3_status = parse_psu_status(psuRead(port, "3", "OP", False))
                        ch4_status = parse_psu_status(psuRead(port, "4", "OP", False))
                        ch1_was_on = bool(last_ch1_status)
                        ch2_was_on = bool(last_ch2_status)
                        ch3_was_on = bool(last_ch3_status)
                        ch4_was_on = bool(last_ch4_status)
                        ob_status = int(ch1_status or ch2_status or ch3_status or ch4_status)
                        if hk_pause_event is not None:
                            if ob_status:
                                hk_pause_event.clear()
                            else:
                                hk_pause_event.set()
                        if ob_status == 0:
                            on_since = None
                            transitioned_off = ch1_was_on or ch2_was_on or ch3_was_on or ch4_was_on
                            if const.psu_queue is not None and transitioned_off:
                                const.psu_queue.put(
                                    {
                                        "TIME": datetime.now(),
                                        "STATUS": 0,
                                        "CH1_STATUS": ch1_status,
                                        "CH2_STATUS": ch2_status,
                                        "CH3_STATUS": ch3_status,
                                        "CH4_STATUS": ch4_status,
                                        "CH1_V": None,
                                        "CH1_I": None,
                                        "CH2_V": None,
                                        "CH2_I": None,
                                        "CH3_V": None,
                                        "CH3_I": None,
                                        "CH4_V": None,
                                        "CH4_I": None,
                                    }
                                )
                        else:
                            # Assign timer for transient protection if any OB channel just turned on.
                            if (
                                (ch1_status != 0 and last_ch1_status in (None, 0))
                                or (ch2_status != 0 and last_ch2_status in (None, 0))
                                or (ch3_status != 0 and last_ch3_status in (None, 0))
                                or (ch4_status != 0 and last_ch4_status in (None, 0))
                            ):
                                on_since = time.monotonic()

                        last_ch1_status = ch1_status
                        last_ch2_status = ch2_status
                        last_ch3_status = ch3_status
                        last_ch4_status = ch4_status

                        ch1_v = parse_psu_reading(psuRead(port, "1", "V", True).rstrip())
                        ch1_i = parse_psu_reading(psuRead(port, "1", "I", True).rstrip())
                        ch2_v = parse_psu_reading(psuRead(port, "2", "V", True).rstrip())
                        ch2_i = parse_psu_reading(psuRead(port, "2", "I", True).rstrip())
                        ch3_v = parse_psu_reading(psuRead(port, "3", "V", True).rstrip())
                        ch3_i = parse_psu_reading(psuRead(port, "3", "I", True).rstrip())
                        ch4_v = parse_psu_reading(psuRead(port, "4", "V", True).rstrip())
                        ch4_i = parse_psu_reading(psuRead(port, "4", "I", True).rstrip())

                        psu_readings = {
                            "TIME": datetime.now(),
                            "STATUS": ob_status,
                            "CH1_STATUS": ch1_status,
                            "CH2_STATUS": ch2_status,
                            "CH3_STATUS": ch3_status,
                            "CH4_STATUS": ch4_status,
                            "CH1_V": ch1_v,
                            "CH1_I": ch1_i,
                            "CH2_V": ch2_v,
                            "CH2_I": ch2_i,
                            "CH3_V": ch3_v,
                            "CH3_I": ch3_i,
                            "CH4_V": ch4_v,
                            "CH4_I": ch4_i,
                        }
                        if const.psu_queue is not None:
                            const.psu_queue.put(psu_readings)

                        psu_log.info(f"{ch1_v}  \t{ch1_i}  \t{ch2_v}  \t{ch2_i}  \t{ch3_v}  \t{ch3_i}")

                        ob_status = parse_psu_status(psuRead(port, "1", "OP", False))

                        if on_since is not None and time.monotonic() - on_since < 1:
                            continue

                        _voltage_mode = mode_state.get("voltage_mode", "NOM") if isinstance(mode_state, dict) else "NOM"
                        _ob_v = const.BUS_VOLTAGES.get("OB", {})
                        ch1_min, ch1_max = _oob_bounds(_ob_v.get("CH1", {}), _voltage_mode)
                        ch2_min, ch2_max = _oob_bounds(_ob_v.get("CH2", {}), _voltage_mode)
                        ch3_min, ch3_max = _oob_bounds(_ob_v.get("CH3", {}), _voltage_mode)
                        voltage_oob = (
                            (ch1_status and not (ch1_min < float(ch1_v) < ch1_max))
                            or (ch2_status and not (ch2_min < float(ch2_v) < ch2_max))
                            or (ch3_status and not (ch3_min < float(ch3_v) < ch3_max))
                        )
                        if voltage_oob:
                            psu_log.error(
                                f"Voltage out of bounds Ch1(status={ch1_status}) : {ch1_v}\t"
                                f"Ch2(status={ch2_status}) : {ch2_v}\t"
                                f"Ch3(status={ch3_status}) : {ch3_v}"
                            )
                            shutdown_psu_outputs(port)
                            _queue_shutdown_snapshot(active_ebmode)

                        current_oob = (
                            (ch1_status and (float(ch1_i) >= 50))
                            or (ch2_status and (float(ch2_i) >= 50))
                            or (ch3_status and (float(ch3_i) >= 150))
                        )
                        if current_oob:
                            psu_log.error(
                                f"Current out of bounds Ch1(status={ch1_status}) : {ch1_i}\t"
                                f"Ch2(status={ch2_status}) : {ch2_i}\t"
                                f"Ch3(status={ch3_status}) : {ch3_i}"
                            )
                            shutdown_psu_outputs(port)
                            _queue_shutdown_snapshot(active_ebmode)
            finally:
                if acquired_port_lock:
                    if port_lock is not None:
                        port_lock.release()

        except Exception as e:
            err_msg = str(e)
            if err_msg != last_error_msg:
                psu_log.error(f"Error in PSU monitor thread: {e}")
                last_error_msg = err_msg

        stop_event.wait(1 / freq)


def setChannels(port, ebmode, voltage_mode: str = "NOM"):
    """Configure PSU channel voltage/current/OVP limits for OB or EB mode."""
    if port:
        # Force a known safe state at startup/mode switch: all outputs OFF.
        port.write("OPALL 0\r\n".encode("utf-8"))
        port.write("OP4 0\r\n".encode("utf-8"))
        psu_log.info("Initialized PSU outputs to OFF for all channels")

        # Get bus voltages from constants
        bus_voltages = const.BUS_VOLTAGES
        mode_key = "EB" if ebmode else "OB"
        channel_voltages = bus_voltages.get(mode_key, {})

        if not ebmode:
            ch1_ovp = config.CH1_OVP
            ch1_i = config.CH1_I
            ch2_ovp = config.CH2_OVP
            ch2_i = config.CH2_I
            ch3_ovp = config.CH3_OVP
            ch3_i = config.CH3_I
            ch4_ovp = config.ROV_HTR_OVP
            ch4_i = config.ROV_HTR_I

            # Get voltages from BUS_VOLTAGES using the selected voltage mode
            ch1_v = channel_voltages.get("CH1", {}).get(voltage_mode, channel_voltages.get("CH1", {}).get("NOM", 12.0))
            ch2_v = channel_voltages.get("CH2", {}).get(voltage_mode, channel_voltages.get("CH2", {}).get("NOM", 12.0))
            ch3_v = channel_voltages.get("CH3", {}).get(voltage_mode, channel_voltages.get("CH3", {}).get("NOM", 5.0))
            ch4_v = 28.0  # CH4 not used in OB mode typically

            # Set the voltage and current limits for each channel
            psu_log.info(f"Setting PSU Channels: CH1 V: {ch1_v}V OVP: {ch1_ovp}V, CH1 I: {ch1_i}A")
            port.write(f"V1 {ch1_v}\r\n".encode("utf-8"))
            port.write(f"I1 {ch1_i}\r\n".encode("utf-8"))
            port.write(f"OVP1 {ch1_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH2 V: {ch2_v}V OVP: {ch2_ovp}V, CH2 I: {ch2_i}A")
            port.write(f"V2 {ch2_v}\r\n".encode("utf-8"))
            port.write(f"I2 {ch2_i}\r\n".encode("utf-8"))
            port.write(f"OVP2 {ch2_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH3 V: {ch3_v}V OVP: {ch3_ovp}V, CH3 I: {ch3_i}A")
            port.write(f"V3 {ch3_v}\r\n".encode("utf-8"))
            port.write(f"I3 {ch3_i}\r\n".encode("utf-8"))
            port.write(f"OVP3 {ch3_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH4 V: 28V OVP: {ch4_ovp}V, CH4 I: {ch4_i}A")
            port.write(f"V4 {ch4_v}\r\n".encode("utf-8"))
            port.write(f"I4 {ch4_i}\r\n".encode("utf-8"))
            port.write(f"OVP4 {ch4_ovp} 1\r\n".encode("utf-8"))

            psu_log.info("PSU Channels set successfully")
            psu_log.info(
                f"  CH1_V  {ch1_v}V\t   CH1_I {ch1_i}\t  CH2_V {ch2_v}V\t  CH2_I {ch2_i}\t  CH3_V {ch3_v}V\t   CH3_I {ch3_i}\t  CH4_V 28V\t   CH4_I {ch4_i}"
            )
            port.reset_output_buffer()  # Clear stale bytes after transactions
            port.reset_input_buffer()

        else:
            ch3_ovp = config.ROV_HTR_OVP
            ch3_i = config.ROV_HTR_I
            ch4_ovp = config.EB_OVP
            ch4_i = config.EB_I

            # Get voltages from BUS_VOLTAGES for EB mode using the selected voltage mode
            ch3_v = channel_voltages.get("CH3", {}).get(voltage_mode, channel_voltages.get("CH3", {}).get("NOM", 28.0))
            ch4_v = channel_voltages.get("CH4", {}).get(voltage_mode, channel_voltages.get("CH4", {}).get("NOM", 28.0))

            # Set the voltage and current limits for each channel
            psu_log.info("EB Mode: Setting PSU Channels")
            psu_log.info(f"Setting PSU Channels: CH3 V: {ch3_v}V OVP: {ch3_ovp}V, CH3 I: {ch3_i}A")
            port.write(f"V3 {ch3_v}\r\n".encode("utf-8"))
            port.write(f"I3 {ch3_i}\r\n".encode("utf-8"))
            port.write(f"OVP3 {ch3_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH4 V: {ch4_v}V OVP: {ch4_ovp}V, CH4 I: {ch4_i}A")
            port.write(f"V4 {ch4_v}\r\n".encode("utf-8"))
            port.write(f"I4 {ch4_i}\r\n".encode("utf-8"))
            port.write(f"OVP4 {ch4_ovp} 1\r\n".encode("utf-8"))

            psu_log.info("PSU Channels set successfully for EB Mode")
            psu_log.info(f"  CH3_V  {ch3_v}V\t   CH3_I {ch3_i}\t  CH4_V {ch4_v}V\t  CH4_I {ch4_i}")
            port.reset_output_buffer()  # Clear stale bytes after transactions
            port.reset_input_buffer()


def switch_psu_channel(port, channel, state, mode_state=None):
    """Switch a PSU channel on or off."""
    state_int = int(state)
    now = time.monotonic()
    last = _LAST_CHANNEL_SWITCH.get(int(channel))
    if last is not None:
        last_state, last_time = last
        # Suppress accidental duplicate same-state commands emitted back-to-back.
        if last_state == state_int and (now - last_time) < 0.2:
            return

    _LAST_CHANNEL_SWITCH[int(channel)] = (state_int, now)

    if port:
        event_log.info(f"Switching PSU CH{channel} {'ON' if state_int else 'OFF'}")
        port.write(f"OP{channel} {state_int}\r\n".encode("utf-8"))
    _mark_transient_toggle(mode_state)


def switch_all_psu_channels(port, state, mode_state=None):
    """Switch all PSU channels on or off."""
    if port:
        event_log.info(f"Switching all PSU channels {'ON' if state else 'OFF'}")
        port.write(f"OPALL {int(state)}\r\n".encode("utf-8"))
    _mark_transient_toggle(mode_state)


def apply_voltage_mode(port, mode: str, current_mode: str):
    """Apply voltage settings based on MIN/NOM/MAX mode selection."""
    if not port:
        return

    from core_modules import constants as constants_module

    bus_voltages = constants_module.BUS_VOLTAGES
    mode_key = current_mode  # "OB" or "EB"

    if mode_key not in bus_voltages:
        psu_log.error(f"Mode {mode_key} not found in BUS_VOLTAGES")
        return

    if mode not in ["MIN", "NOM", "MAX"]:
        psu_log.error(f"Invalid voltage mode: {mode}. Must be MIN, NOM, or MAX")
        return

    channel_voltages = bus_voltages[mode_key]

    try:
        if current_mode == "OB":
            # Apply voltages for OB channels
            for ch_name in ["CH1", "CH2", "CH3"]:
                if ch_name in channel_voltages:
                    voltage = channel_voltages[ch_name][mode]
                    ch_num = int(ch_name[2:])  # Extract channel number
                    port.write(f"V{ch_num} {voltage}\r\n".encode("utf-8"))
                    psu_log.info(f"Set CH{ch_num} voltage to {voltage}V ({mode})")

        elif current_mode == "EB":
            # Apply voltages for EB channels
            for ch_name in ["CH3", "CH4"]:
                if ch_name in channel_voltages:
                    voltage = channel_voltages[ch_name][mode]
                    ch_num = int(ch_name[2:])  # Extract channel number
                    port.write(f"V{ch_num} {voltage}\r\n".encode("utf-8"))
                    psu_log.info(f"Set CH{ch_num} voltage to {voltage}V ({mode})")

        event_log.info(f"Applied voltage mode {mode} for {current_mode}")
    except Exception as e:
        psu_log.error(f"Error applying voltage mode: {e}")
        event_log.error(f"Error applying voltage mode: {e}")


def shutdown_psu_outputs(port: serial.Serial) -> None:
    """Cut all PSU outputs and return to local mode, but keep the serial port open.

    Use this for protection trips (OOB / MMS) where the operator may want to
    recover without reconnecting.  Call emergencyShutDown (or close_psu_comms)
    only when the EGSE itself is closing.
    """
    if port and port.is_open:
        port.write("OPALL 0\n".encode("utf-8"))
        port.flush()
        time.sleep(0.1)
        port.reset_input_buffer()
        port.reset_output_buffer()
        port.write("LOCAL\n".encode("utf-8"))
        port.flush()
        psu_log.warning("PSU outputs shut down (port kept open for recovery).")


def emergencyShutDown(port: serial.Serial, stop_event: threading.Event = None, psu_thread: threading.Thread = None) -> None:
    """Safely halts the background telemetry monitoring, clears channels, and releases local control."""
    
    # 1. Force the thread loop condition to evaluate to False immediately
    if stop_event is not None:
        stop_event.set()
        
    # 2. Wait for the background thread to safely exit its active reading block
    if psu_thread is not None and psu_thread.is_alive():
        psu_thread.join(timeout=1.0)
        
    if port and port.is_open:
        # 3. Suppress all outputs safely
        port.write("OPALL 0\n".encode("utf-8"))
        port.flush()
        time.sleep(0.1) # Give the hardware relay coils time to open
        
        # 4. Clear python serial device pipelines
        port.reset_input_buffer()
        port.reset_output_buffer()
        
        # 5. Issue the clean Local directive
        port.write("LOCAL\n".encode("utf-8"))
        port.flush()
        
        # 6. Sleep briefly to ensure the local directive clears the physical TX line entirely
        time.sleep(0.2)
        
        # 7. Safe teardown
        port.close()
        print("PSU Comm Link Closed & Panel Returned to Local Operating Mode.")
    return


def reconnect_psu(port: serial.Serial, ebmode: bool, voltage_mode: str = "NOM") -> bool:
    """Reopen a previously closed PSU serial port and reconfigure channels.

    Returns True on success, False if the port could not be reopened.
    Does not perform an IDN check — the PSU is assumed to be the same device.
    """
    if port is None:
        psu_log.error("reconnect_psu: no port object available")
        return False
    try:
        if not port.is_open:
            port.open()
        port.reset_output_buffer()
        port.reset_input_buffer()
        psu_log.info(f"PSU port reopened: {port.port}")
        setChannels(port, ebmode, voltage_mode)
        return True
    except Exception as exc:
        psu_log.error(f"PSU reconnect failed: {exc}")
        return False


# TODO: Report the link status
