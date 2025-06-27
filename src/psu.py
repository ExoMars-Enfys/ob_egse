# Std library
import logging

# Added packages
import serial

# Local modules
import constants as const
import time
info_log = logging.getLogger("info_log")
event_log = logging.getLogger("event_log")
psu_log = logging.getLogger("psu_log")


# Initialising Voltage constants
#-12V Channel
v12Channel = 1
v12V = 12
v12I = 0.150

#-12V Channel
vHTRChannel = 2
vHTRV = 12
vHTRI = 0.09

#5V Channel
v5Channel = 3
v5V = 5
v5I = 0.05

def init_psu_comms(psu_port: str) -> serial.Serial:
    psuport = serial.Serial(port=None, timeout=1.0)
    psuport.port = psu_port  # Assign com_port afterwards to prevent opening immediately
    return psuport
def open_psu_comms(psuport: serial.Serial) -> None:
    try:    
        psuport.open()
    except serial.SerialException:
        info_log.error(f"No device found on COM Port {psuport.port}, try another")
        # raise SystemExit

    psuport.flushOutput()  # Port Flushing to clear port
    psuport.flushInput()

    return psuport

def close_psu_comms(psuport: serial.Serial) -> None:
    psuport.close()
    return

def setChannels( v12 : bool ,HTR : bool, v5 : bool):
    psuport = init_psu_comms("COM10")
    psuport.open()
    psuport.write(f"V{v12Channel} {v12V}\r\n".encode('utf-8'))
    psuport.write(f"I{v12Channel} {v12I}\r\n".encode('utf-8'))
    psuport.write(f"OP{v12Channel} {int(v12)}\r\n".encode('utf-8'))
    psuport.write(f"V{vHTRChannel} {vHTRV}\r\n".encode('utf-8'))
    psuport.write(f"I{vHTRChannel} {vHTRI}\r\n".encode('utf-8'))
    psuport.write(f"OP{vHTRChannel} {int(HTR)}\r\n".encode('utf-8'))
    psuport.write(f"V{v5Channel} {v5V}\r\n".encode('utf-8'))
    psuport.write(f"I{v5Channel} {v5I}\r\n".encode('utf-8'))
    psuport.write(f"OP{v5Channel} {int(v5)}\r\n".encode('utf-8'))
    psuport.flushOutput()
    psuport.flushInput()

def psuRead(channel, type) :        
    psuport = init_psu_comms("COM10")
    psuport.open()
    psuport.write(f"{type}{channel}O?\r\n".encode('utf-8'))
    response= psuport.read(8).decode('utf-8')    
    psuport.flushOutput()
    psuport.flushInput()
    return response
        
## TODO: Create a log for this - 
# #?Done
## TODO: Create a clear settings file, Voltages to be set, Current limits
## TODO: Add monitoring, such that we have warning current limits and alarm limits
## TODO: If alarm limit, automatically shutdown
## TODO: Close the comms
## TODO: Report the link status
## TODO: Loop through every 1s (async?)
