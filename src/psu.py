# Std library
from datetime import datetime
import logging

# Added packages
import serial

# Local modules
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
        response = port.read(8).decode("utf-8")
    else:
        port.write(f"{type}{channel}O?\r\n".encode("utf-8"))
        response = port.read(8).decode("utf-8")

    port.flushOutput()
    port.flushInput()
    return response


def psu_monitor_thread(port, stop_event, freq, hk_pause_event=None):
    if not port:
        return

    last_status = None
    on_since = None

    while not stop_event.is_set():
        try:
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

            if (float(ch1_i.strip("A")) >= 150) or (float(ch2_i.strip("A")) >= 90) or (float(ch3_i.strip("A")) >= 150):
                psu_log.error(f"Current out of bounds Ch1 :  {ch1_i}\t Ch2 : {ch2_i}\t Ch3 : {ch3_i} ")
                emergencyShutDown(port)

        except Exception as e:
            psu_log.error(f"Error in PSU monitor thread: {e}")

        stop_event.wait(1 / freq)


def setChannels(port, ch1_ovp, ch1_i, ch2_ovp, ch2_i, ch3_ovp, ch3_i):
    if port:
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
        psu_log.info("  CH1_V \t   CH1_I \t  CH2_V \t  CH2_I \t  CH3_V \t   CH3_I")
        port.flushOutput()
        port.flushInput()


def switchPSU(port, state):
    if port:
        event_log.info(f"Switching PSU {'ON' if state else 'OFF'}")
        port.write(f"OPALL {int(state)}\r\n".encode("utf-8"))


def emergencyShutDown(port):
    if port:
        port.write(f"OPALL 0\r\n".encode("utf-8"))
        event_log.info(f"Closing all channels")
        psu_log.info(f"Closing all channels")
        port.write(f"LOCAL\r\n".encode("utf-8"))
        event_log.info(f"Setting to Local control")
        psu_log.info(f"Setting to Local control")
        port.flushOutput()
        port.flushInput()


# TODO: Report the link status
