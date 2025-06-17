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
v12Channel = "1"
v12V = "12"
v12I = "0.376"

#-12V Channel
vHTRChannel = 2
vHTRV = 12
vHTRI = 0.09

#5V Channel
v5Channel = 3
v5V = 5
v5I = 0.05

def initialise_psu_mx100qp_comms(com_port: str) -> serial.Serial:
    port = serial.Serial("COM" + str(com_port), timeout=1.0)
    return port
    
def setChannels(port: serial.Serial, HTR : bool, v12 : bool , v5 : bool):
    if HTR : 
        port.write(f"V{vHTRChannel} {vHTRV}\r\n".encode('utf-8'))
        port.read(15)
        port.write(f"I{vHTRChannel} {vHTRI}\r\n".encode('utf-8'))
        port.read(15)
        port.write(f"V{vHTRChannel}?\r\n".encode('utf-8'))
        responseV = port.read(15)
        event_log.info(f"Response: {responseV}")
        port.write(f"I{vHTRChannel}?\r\n".encode('utf-8'))
        responseI = port.read(15)
        event_log.info(f"Setting Heater Channel to {responseV} Volts and {responseI} Amps")
        port.write(f"OP{vHTRChannel} 1\r\n".encode('utf-8'))
        port.read(15)

def psuRead(port,channel , type , dir) : 
        port.write(f"{type}{channel}{dir}?\r\n".encode('utf-8'))
        response= port.read(10)
        return response
        
        
        # if HTR : 
        #     port.write(f"V{vHTRChannel} {vHTRV}\r\n".encode('utf-8'))
        #     port.write(f"I{vHTRChannel} {vHTRV}\r\n".encode('utf-8' ))
        # event_log.info("writing to PSU")
        # response = port.write("OP1 ?\r\n".encode("utf-8"))
        # psu_log.info("Powered on Channel one " + response)
        # port.write("OP1 0\r\n".encode('utf-8'))
        # event_log.info("writing to PSU")
        # response = port.write("OP1 ?\r\n".encode("utf-8"))
        # psu_log.info("Powered on Channel one " + response)
## TODO: Create a log for this - 
# #?Done
## TODO: Create a clear settings file, Voltages to be set, Current limits
## TODO: Add monitoring, such that we have warning current limits and alarm limits
## TODO: If alarm limit, automatically shutdown
## TODO: Close the comms
## TODO: Report the link status
## TODO: Loop through every 1s (async?)
