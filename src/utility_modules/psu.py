# Std library
from datetime import datetime
import logging
# Added packages
import serial
import time
# Local modules
from core_modules import config as config
from core_modules import constants as const


info_log = logging.getLogger("info_log")
event_log = logging.getLogger("event_log")
psu_log = logging.getLogger("psu_log")

def init_psu_comms(psu_com: str) -> serial.Serial:
    """Initialise an unopened PSU serial port handle."""
    psuport = serial.Serial(port=None, timeout=1.0)
    psuport.port = psu_com  # Assign com_port afterwards to prevent opening immediately
    print("Initialized PSU COM port: {psu_com}")
    return psuport

def open_psu_comms(port: serial.Serial , psu_not_required):
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
    """Return PSU to local mode, clear buffers, and close the serial port."""
    if port:
        port.reset_output_buffer()  # Clear stale bytes before first transactions
        port.reset_input_buffer()
        port.write("LOCAL\r\n".encode("utf-8"))
        time.sleep(0.5)
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

def psu_monitor_thread(port, ebmode, stop_event, freq, hk_pause_event=None):
    """Monitor PSU channels, log telemetry, and shut down on limit violations."""
    if not port:
        return

    last_status = None
    last_eb_status = None
    last_rov_htr_status = None
    on_since = None

    while not stop_event.is_set():
        try:
            #Read the status of the PSU channels, and set stop event accordingly
            if ebmode:
                ebstatus = int(psuRead(port, "4", "OP", False).rstrip())
                rov_htr_status = int(psuRead(port, "3", "OP", False).rstrip())
                if hk_pause_event is not None:
                    if ebstatus == 0 and rov_htr_status == 0:
                        hk_pause_event.set()
                    else:
                        hk_pause_event.clear()
                #Assign timer for transient protection if either channel just turned on
                if ebstatus != 0 and last_eb_status == 0:
                    on_since = time.monotonic()
                if rov_htr_status != 0 and last_rov_htr_status == 0:
                    on_since = time.monotonic()
                last_eb_status = ebstatus
                last_rov_htr_status = rov_htr_status

                # Read the voltage and current for each channel and parse the readings to floats
                eb_v = parse_psu_reading(psuRead(port, "4", "V", True).rstrip())
                eb_i = parse_psu_reading(psuRead(port, "4", "I", True).rstrip())

                rov_htr_v = parse_psu_reading(psuRead(port, "3", "V", True).rstrip())
                rov_htr_i = parse_psu_reading(psuRead(port, "3", "I", True).rstrip())

                #Populate PSU Queue with dictionary
                psu_readings = {
                    "TIME": datetime.now(),
                    "STATUS": ebstatus,
                    "PSU_EB_V": eb_v,
                    "PSU_EB_I": eb_i,
                    "PSU_ROV_HTR_V": rov_htr_v,
                    "PSU_ROV_HTR_I": rov_htr_i,
                }
                const.psu_queue.put(psu_readings)

                # Log only the channels that are on and push to the queue
                log_parts = []
                if rov_htr_status:
                    log_parts.append("CH3 {rov_htr_v}  \t{rov_htr_i}")
                if ebstatus:
                    log_parts.append(f"CH4 {eb_v}  \t{eb_i}")
                if log_parts:
                    psu_log.info("  \t".join(log_parts))

                # Check status again in case toggled during reads
                ebstatus = int(psuRead(port, "4", "OP", False).rstrip())
                rov_htr_status = int(psuRead(port, "3", "OP", False).rstrip())
                if ebstatus == 0 and rov_htr_status == 0:
                    if hk_pause_event is not None:
                        hk_pause_event.set()
                    continue

                #Check for transients if either channel is switched on
                if on_since is not None and time.monotonic() - on_since < 1:
                    continue

                if rov_htr_status and not (26 < rov_htr_v < 30):
                    psu_log.error(f"Voltage out of bounds Ch3 :  {rov_htr_v}")
                    emergencyShutDown(port)

                if ebstatus and not (26 < eb_v < 30):
                    psu_log.error(f"Voltage out of bounds Ch4 :  {eb_v}")
                    emergencyShutDown(port)

                if rov_htr_status and (rov_htr_i >= 150):
                    psu_log.error(f"Current out of bounds Ch3 :  {rov_htr_i}")
                    emergencyShutDown(port)

                if ebstatus and (eb_i >= 500):
                    psu_log.error(f"Current out of bounds Ch4 :  {eb_i}")
                    emergencyShutDown(port)

            else:
                #Read the status of the PSU channels, and set stop event accordingly
                ob_status = int(psuRead(port, "1", "OP", False).rstrip())
                if ob_status == 0:
                    if hk_pause_event is not None:
                        hk_pause_event.set()
                    on_since = None
                    stop_event.wait(1 / freq)
                else:
                    #Assign timer for transient protection if channels just turned on
                    if hk_pause_event is not None:
                        hk_pause_event.clear()
                    if last_status == 0:
                        on_since = time.monotonic()

                last_status = ob_status

                # Read the voltage and current for each channel and parse the readings to floats
                ch1_v = parse_psu_reading(psuRead(port, "1", "V", True).rstrip())
                ch1_i = parse_psu_reading(psuRead(port, "1", "I", True).rstrip())
                ch2_v = parse_psu_reading(psuRead(port, "2", "V", True).rstrip())
                ch2_i = parse_psu_reading(psuRead(port, "2", "I", True).rstrip())
                ch3_v = parse_psu_reading(psuRead(port, "3", "V", True).rstrip())
                ch3_i = parse_psu_reading(psuRead(port, "3", "I", True).rstrip())

                #Populate PSU Queue with dictionary
                psu_readings = {
                    "TIME": datetime.now(),
                    "STATUS": ob_status,
                    "CH1_V": ch1_v,
                    "CH1_I": ch1_i,
                    "CH2_V": ch2_v,
                    "CH2_I": ch2_i,
                    "CH3_V": ch3_v,
                    "CH3_I": ch3_i,
                }
                const.psu_queue.put(psu_readings)

                # Log the readings
                psu_log.info(f"{ch1_v}  \t{ch1_i}  \t{ch2_v}  \t{ch2_i}  \t{ch3_v}  \t{ch3_i}")

                # Check status again in case toggled during reads
                ob_status = int(psuRead(port, "1", "OP", False).rstrip())
                if not ob_status:
                    if hk_pause_event is not None:
                        hk_pause_event.set()
                    continue

                #Check for transients if channels just switched on
                if on_since is not None and time.monotonic() - on_since < 0.5:
                    continue

                if (
                    not (11.2 < float(ch1_v) < 13.2)
                    or not (11.2 < float(ch2_v) < 13.2)
                    or not (4.8 < float(ch3_v) < 5.5)
                ):
                    psu_log.error(f"Voltage out of bounds Ch1 :  {ch1_v}\t Ch2 : {ch2_v}\t Ch3 : {ch3_v} ")
                    emergencyShutDown(port)

                if (
                    (float(ch1_i) >= 150)
                    or (float(ch2_i) >= 90)
                    or (float(ch3_i) >= 150)
                ):
                    psu_log.error(f"Current out of bounds Ch1 :  {ch1_i}\t Ch2 : {ch2_i}\t Ch3 : {ch3_i} ")
                    emergencyShutDown(port)

        except Exception as e:
            psu_log.error(f"Error in PSU monitor thread: {e}")

        stop_event.wait(1 / freq)

def setChannels(port, ebmode):
    """Configure PSU channel voltage/current/OVP limits for OB or EB mode."""
    if port:
        if not ebmode:
            ch1_ovp = config.CH1_OVP
            ch1_i = config.CH1_I
            ch2_ovp = config.CH2_OVP
            ch2_i = config.CH2_I
            ch3_ovp = config.CH3_OVP
            ch3_i = config.CH3_I
            # Set the voltage and current limits for each channel
            psu_log.info(f"Setting PSU Channels: CH1 V: 12V OVP: {ch1_ovp}V, CH1 I: {ch1_i}A")
            port.write("V1 12\r\n".encode("utf-8"))
            port.write(f"I1 {ch1_i}\r\n".encode("utf-8"))
            port.write(f"OVP1 {ch1_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH2 V: 12V OVP: {ch2_ovp}V, CH2 I: {ch2_i}A")
            port.write("V2 12\r\n".encode("utf-8"))
            port.write(f"I2 {ch2_i}\r\n".encode("utf-8"))
            port.write(f"OVP2 {ch2_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH3 V: 5V OVP: {ch3_ovp}V, CH3 I: {ch3_i}A")
            port.write("V3 5\r\n".encode("utf-8"))
            port.write(f"I3 {ch3_i}\r\n".encode("utf-8"))
            port.write(f"OVP3 {ch3_ovp} 1\r\n".encode("utf-8"))

            psu_log.info("PSU Channels set successfully")
            psu_log.info(f"  CH1_V  12V\t   CH1_I {ch1_i}\t  CH2_V -12V\t  CH2_I {ch2_i}\t  CH3_V 5V\t   CH3_I {ch3_i}")
            port.reset_output_buffer()  # Clear stale bytes after transactions
            port.reset_input_buffer()

        else:
            ch3_ovp = config.ROV_HTR_OVP
            ch3_i = config.ROV_HTR_I
            ch4_ovp = config.EB_OVP
            ch4_i = config.EB_I

            # Set the voltage and current limits for each channel
            psu_log.info("EB Mode: Setting PSU Channels")
            psu_log.info(f"Setting PSU Channels: CH3 V: 28V OVP: {ch3_ovp}V, CH3 I: {ch3_i}A")
            port.write("V3 28\r\n".encode("utf-8"))
            port.write(f"I3 {ch3_i}\r\n".encode("utf-8"))
            port.write(f"OVP3 {ch3_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH4 V: 28V OVP: {ch4_ovp}V, CH4 I: {ch4_i}A")
            port.write("V4 28\r\n".encode("utf-8"))
            port.write(f"I4 {ch4_i}\r\n".encode("utf-8"))
            port.write(f"OVP4 {ch4_ovp} 1\r\n".encode("utf-8"))

            psu_log.info("PSU Channels set successfully for EB Mode")
            psu_log.info(f"  CH3_V  28V\t   CH3_I {ch3_i}\t  CH4_V 28V\t  CH4_I {ch4_i}")
            port.reset_output_buffer()  # Clear stale bytes after transactions
            port.reset_input_buffer()

def switch_psu_channel(port, channel, state):
    """Switch a PSU channel on or off."""
    if port:
        event_log.info(f"Switching PSU CH{channel} {'ON' if state else 'OFF'}")
        port.write(f"OP{channel} {int(state)}\r\n".encode("utf-8"))

def emergencyShutDown(port):
    """Perform emergency PSU shutdown and hand control back to local front panel."""
    if port:
        port.write("OPALL 0\r\n".encode("utf-8"))
        port.write("OP4 0\r\n".encode("utf-8"))
        event_log.info("Closing all channels")
        psu_log.info("Closing all channels")
        port.write("LOCAL\r\n".encode("utf-8"))
        event_log.info("Setting to Local control")
        psu_log.info("Setting to Local control")
        port.reset_output_buffer()  # Clear stale bytes after transactions
        port.reset_input_buffer()


# TODO: Report the link status
