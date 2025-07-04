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

def init_psu_comms(psu_com: str) -> serial.Serial:
    psuport = serial.Serial(port=None, timeout=1.0)
    psuport.port = psu_com  # Assign com_port afterwards to prevent opening immediately
    return psuport

def open_psu_comms(psu_com: serial.Serial) -> None:
    try:    
        psu_com.open()
    except serial.SerialException:
        info_log.error(f"No device found on COM Port {psu_com.port}, try another")
        # raise SystemExit

    psu_com.flushOutput()  # Port Flushing to clear port
    psu_com.flushInput()

    return psu_com

def close_psu_comms(psu_com: serial.Serial) -> None:
    psu_com.close()
    return

def psuRead(psu_com, channel, type,output=False) :
    if output == False : 
        psu_com.write(f"{type}{channel}?\r\n".encode('utf-8'))
        response= psu_com.read(8).decode('utf-8')
    else   :
        psu_com.write(f"{type}{channel}O?\r\n".encode('utf-8'))
        response= psu_com.read(8).decode('utf-8') 
    psu_com.flushOutput()
    psu_com.flushInput()
    return response

def setChannels(psu_com,ch1_ovp,ch1_i,ch2_ovp,ch2_i,ch3_ovp,ch3_i):
    psu_com.write(f"V1 12\r\n".encode('utf-8'))
    psu_com.write(f"I1 {ch1_i}\r\n".encode('utf-8'))
    psu_com.write(f"OVP1 {ch1_ovp} 1\r\n".encode('utf-8'))
    psu_com.write(f"V2 12\r\n".encode('utf-8'))
    psu_com.write(f"I2 {ch2_i}\r\n".encode('utf-8'))
    psu_com.write(f"OVP2 {ch2_ovp} 1\r\n".encode('utf-8'))
    psu_com.write(f"V3 5\r\n".encode('utf-8'))
    psu_com.write(f"I3 {ch3_i}\r\n".encode('utf-8'))
    psu_com.write(f"OVP3 {ch3_ovp} 1\r\n".encode('utf-8'))
    psu_com.flushOutput()
    psu_com.flushInput()

def switchPSU(psu_com,state) :
    # psu_status = int(psuRead(psu_com, "1", "OP",False))
    # psu_status = not psu_status
    psu_com.write(f"OPALL {int(state)}\r\n".encode('utf-8'))

def emergencyShutDown(psu_com) : 
    psu_com.write(f"OPALL 0\r\n".encode('utf-8'))
    psu_com.flushOutput()
    psu_com.flushInput()
    psu_com.close()
        
## TODO: Create a log for this - 
# #?Done
## TODO: Create a clear settings file, Voltages to be set, Current limits
# ?Done in the constants file
## TODO: Add monitoring, such that we have warning current limits and alarm limits
## TODO: If alarm limit, automatically shutdown
## TODO: Close the comms
## TODO: Report the link status
## TODO: Loop through every 1s (async?)
