# Std libary
import logging

# Added packages
import serial.rs485

# Local modules
import constants as const


def initialise_comms(com_port: str) -> serial.rs485.RS485:
    info_log = logging.getLogger("info_log")
    port = serial.rs485.RS485(
        port=None,  # create a blank class ready to open
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_ODD,
        stopbits=serial.STOPBITS_ONE,
        timeout=1.0,
    )

    port.rs485_mode = serial.rs485.RS485Settings(
        rts_level_for_tx=False,
        rts_level_for_rx=True,
        loopback=False,
        delay_before_tx=const.CMD_SPEED_DICT[const.DEFAULT_CMD_SPEED],
        delay_before_rx=0,
    )

    port.port = com_port  # Assign com_port afterwards to prevent opening immediately
    return port


def open_comms(port: serial.rs485.RS485) -> None:
    port.open()
    except serial.SerialException:
        info_log.error(f"No device found on COM Port {com_port}, try another")
        # raise SystemExit

    port.flushOutput()  # Port Flushing to clear port
    port.flushInput()

    return port


def close_comms(port: serial.rs485.RS485) -> None:
    port.close()
    return
