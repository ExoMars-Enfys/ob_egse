# Std library
from datetime import datetime
import logging

# Added packages
import serial

# Local modules
import config
import constants as const
import time

info_log = logging.getLogger("info_log")
event_log = logging.getLogger("event_log")
psu_log = logging.getLogger("psu_log")


def init_psu_comms(psu_com: str) -> serial.Serial:
    psuport = serial.Serial(port=None, timeout=1.0)
    psuport.port = psu_com  # Assign com_port afterwards to prevent opening immediately
    return psuport


def open_psu_comms(port: serial.Serial, psu_not_required) -> None:
    try:
        port.open()
    except serial.SerialException:
        if psu_not_required:
            return
        else:
            info_log.error(f"No device found on COM Port {port.port}, try another")
            raise SystemExit

    port.flushOutput()  # Port Flushing to clear port
    port.flushInput()

    return port


def close_psu_comms(port: serial.Serial) -> None:
    if port:
        port.write(f"LOCAL\r\n".encode("utf-8"))
        time.sleep(0.5)
        port.close()
    return


def psuRead(port, channel, type, output=False):
    if output == False:
        port.write(f"{type}{channel}?\r\n".encode("utf-8"))
        response = port.readline().decode("utf-8")
    else:
        port.write(f"{type}{channel}O?\r\n".encode("utf-8"))
        response = port.readline().decode("utf-8")

    port.flushOutput()
    port.flushInput()
    return response


def _parse_psu_reading(raw_value: str) -> float:
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
    if not port:
        return

    last_status = None
    last_eb_status = None
    last_rov_htr_status = None
    on_since = None

    while not stop_event.is_set():
        try:
            if ebmode:
                ebstatus = int(psuRead(port, "4", "OP", False).rstrip())
                rov_htr_status = int(psuRead(port, "3", "OP", False).rstrip())
                if hk_pause_event is not None:
                    if ebstatus == 0 and rov_htr_status == 0:
                        hk_pause_event.set()
                    else:
                        hk_pause_event.clear()
                if ebstatus != 0 and last_eb_status == 0:
                    on_since = time.monotonic()
                if rov_htr_status != 0 and last_rov_htr_status == 0:
                    on_since = time.monotonic()

                last_eb_status = ebstatus
                last_rov_htr_status = rov_htr_status

                # Read the voltage and current for each channel
                eb_v = psuRead(port, "4", "V", True).rstrip()
                eb_i = psuRead(port, "4", "I", True).rstrip()

                rov_htr_v = psuRead(port, "3", "V", True).rstrip()
                rov_htr_i = psuRead(port, "3", "I", True).rstrip()

                eb_v_val = _parse_psu_reading(eb_v)
                eb_i_val = _parse_psu_reading(eb_i)
                rov_htr_v_val = _parse_psu_reading(rov_htr_v)
                rov_htr_i_val = _parse_psu_reading(rov_htr_i)

                psu_readings = {
                    "TIME": datetime.now(),
                    "STATUS": ebstatus,
                    "PSU_EB_V": eb_v_val,
                    "PSU_EB_I": eb_i_val,
                    "PSU_ROV_HTR_V": rov_htr_v_val,
                    "PSU_ROV_HTR_I": rov_htr_i_val,
                }

                const.psu_queue.put(psu_readings)

                # Log only the channels that are on
                log_parts = []
                if rov_htr_status:
                    log_parts.append(f"CH3 {rov_htr_v}  \t{rov_htr_i}")
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

                if on_since is not None and time.monotonic() - on_since < 1:
                    continue

                if rov_htr_status and not (26 < rov_htr_v_val < 30):
                    psu_log.error(f"Voltage out of bounds Ch3 :  {rov_htr_v}")
                    emergencyShutDown(port)

                if ebstatus and not (26 < eb_v_val < 30):
                    psu_log.error(f"Voltage out of bounds Ch4 :  {eb_v}")
                    emergencyShutDown(port)

                if rov_htr_status and (rov_htr_i_val >= 150):
                    psu_log.error(f"Current out of bounds Ch3 :  {rov_htr_i}")
                    emergencyShutDown(port)

                if ebstatus and (eb_i_val >= 90):
                    psu_log.error(f"Current out of bounds Ch4 :  {eb_i}")
                    emergencyShutDown(port)

            else:
                # First check the output is enabled
                status = int(psuRead(port, "1", "OP", False).rstrip())
                if status == 0:
                    if hk_pause_event is not None:
                        hk_pause_event.set()
                    on_since = None
                    stop_event.wait(1 / freq)
                else:
                    if hk_pause_event is not None:
                        hk_pause_event.clear()
                    if last_status == 0:
                        on_since = time.monotonic()

                last_status = status

                # Read the voltage and current for each channel
                ch1_v = psuRead(port, "1", "V", True).rstrip()
                ch1_i = psuRead(port, "1", "I", True).rstrip()
                ch2_v = psuRead(port, "2", "V", True).rstrip()
                ch2_i = psuRead(port, "2", "I", True).rstrip()
                ch3_v = psuRead(port, "3", "V", True).rstrip()
                ch3_i = psuRead(port, "3", "I", True).rstrip()

                psu_readings = {
                    "TIME": datetime.now(),
                    "STATUS": status,
                    "CH1_V": float(ch1_v[:-1]),  # Remove the trailing 'V' and convert to float
                    "CH1_I": float(ch1_i[:-1]),  # Remove the trailing 'A' and convert to float
                    "CH2_V": float(ch2_v[:-1]),
                    "CH2_I": float(ch2_i[:-1]),
                    "CH3_V": float(ch3_v[:-1]),
                    "CH3_I": float(ch3_i[:-1]),
                }

                const.psu_queue.put(psu_readings)

                # Log the readings
                psu_log.info(f"{ch1_v}  \t{ch1_i}  \t{ch2_v}  \t{ch2_i}  \t{ch3_v}  \t{ch3_i}")

                # Check status again in case toggled during reads
                status = int(psuRead(port, "1", "OP", False).rstrip())
                if status == 0:
                    if hk_pause_event is not None:
                        hk_pause_event.set()
                    continue

                if on_since is not None and time.monotonic() - on_since < 0.5:
                    continue

                if (
                    not (11.2 < float(ch1_v.strip("V")) < 13.2)
                    or not (11.2 < float(ch2_v.strip("V")) < 13.2)
                    or not (4.8 < float(ch3_v.strip("V")) < 5.5)
                ):
                    psu_log.error(f"Voltage out of bounds Ch1 :  {ch1_v}\t Ch2 : {ch2_v}\t Ch3 : {ch3_v} ")
                    emergencyShutDown(port)

                if (
                    (float(ch1_i.strip("A")) >= 150)
                    or (float(ch2_i.strip("A")) >= 90)
                    or (float(ch3_i.strip("A")) >= 150)
                ):
                    psu_log.error(f"Current out of bounds Ch1 :  {ch1_i}\t Ch2 : {ch2_i}\t Ch3 : {ch3_i} ")
                    emergencyShutDown(port)

        except Exception as e:
            psu_log.error(f"Error in PSU monitor thread: {e}")

        stop_event.wait(1 / freq)


def setChannels(port, ebmode):
    if port:
        if not ebmode:
            ch1_ovp = config.CH1_OVP
            ch1_i = config.CH1_I
            ch2_ovp = config.CH2_OVP
            ch2_i = config.CH2_I
            ch3_ovp = config.CH3_OVP
            ch3_i = config.CH3_I
            # Set the voltage and current limits for each channel
            psu_log.info(f"Setting PSU Channels: CH1 V: {12}V OVP: {ch1_ovp}V, CH1 I: {ch1_i}A")
            port.write(f"V1 12\r\n".encode("utf-8"))
            port.write(f"I1 {ch1_i}\r\n".encode("utf-8"))
            port.write(f"OVP1 {ch1_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH2 V: {12}V OVP: {ch2_ovp}V, CH2 I: {ch2_i}A")
            port.write(f"V2 12\r\n".encode("utf-8"))
            port.write(f"I2 {ch2_i}\r\n".encode("utf-8"))
            port.write(f"OVP2 {ch2_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH3 V: {5}V OVP: {ch3_ovp}V, CH3 I: {ch3_i}A")
            port.write(f"V3 5\r\n".encode("utf-8"))
            port.write(f"I3 {ch3_i}\r\n".encode("utf-8"))
            port.write(f"OVP3 {ch3_ovp} 1\r\n".encode("utf-8"))

            psu_log.info("PSU Channels set successfully")
            psu_log.info(f"  CH1_V  12V\t   CH1_I {ch1_i}\t  CH2_V -12V\t  CH2_I {ch2_i}\t  CH3_V 5V\t   CH3_I {ch3_i}")
            port.flushOutput()
            port.flushInput()

        else:
            ch3_ovp = config.ROV_HTR_OVP
            ch3_i = config.ROV_HTR_I
            ch4_ovp = config.EB_OVP
            ch4_i = config.EB_I

            psu_log.info("EB Mode: Setting PSU Channels")
            psu_log.info(f"Setting PSU Channels: CH3 V: {28}V OVP: {ch3_ovp}V, CH3 I: {ch3_i}A")
            port.write(f"V3 28\r\n".encode("utf-8"))
            port.write(f"I3 {ch3_i}\r\n".encode("utf-8"))
            port.write(f"OVP3 {ch3_ovp} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH4 V: {28}V OVP: {ch4_ovp}V, CH4 I: {ch4_i}A")
            port.write(f"V4 28\r\n".encode("utf-8"))
            port.write(f"I4 {ch4_i}\r\n".encode("utf-8"))
            port.write(f"OVP4 {ch4_ovp} 1\r\n".encode("utf-8"))

            psu_log.info("PSU Channels set successfully for EB Mode")
            psu_log.info(f"  CH3_V  28V\t   CH3_I {ch3_i}\t  CH4_V 28V\t  CH4_I {ch4_i}")
            port.flushOutput()
            port.flushInput()


def switchPSU(port, ebmode, state):
    if port:
        if not ebmode:
            event_log.info(f"Switching PSU {'ON' if state else 'OFF'}")
            port.write(f"OPALL {int(state)}\r\n".encode("utf-8"))
        else:
            event_log.info(f"Switching PSU {'ON' if state else 'OFF'}")
            port.write(f"OP3 {int(state)}\r\n".encode("utf-8"))
            port.write(f"OP4 {int(state)}\r\n".encode("utf-8"))


def switch_psu_channel(port, channel, state):
    if port:
        event_log.info(f"Switching PSU CH{channel} {'ON' if state else 'OFF'}")
        port.write(f"OP{channel} {int(state)}\r\n".encode("utf-8"))


def emergencyShutDown(port):
    if port:
        port.write(f"OPALL 0\r\n".encode("utf-8"))
        port.write(f"OP4 0\r\n".encode("utf-8"))
        event_log.info(f"Closing all channels")
        psu_log.info(f"Closing all channels")
        port.write(f"LOCAL\r\n".encode("utf-8"))
        event_log.info(f"Setting to Local control")
        psu_log.info(f"Setting to Local control")
        port.flushOutput()
        port.flushInput()


# TODO: Report the link status
