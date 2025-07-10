# Std library
import logging
import threading

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

def open_psu_comms(psu_com: serial.Serial,nopsurequired) -> None:
    try:
        psu_com.open()
    except serial.SerialException:
        if nopsurequired : 
            return
        else :  
            info_log.error(f"No device found on COM Port {psu_com.port}, try another")
            raise SystemExit

    psu_com.flushOutput()  # Port Flushing to clear port
    psu_com.flushInput()

    return psu_com

def close_psu_comms(psu_com: serial.Serial) -> None:
    psu_com.close()
    return

def psuRead(psu_com, channel, type,output=False,) :
    if output == False : 
        psu_com.write(f"{type}{channel}?\r\n".encode('utf-8'))
        response= psu_com.read(8).decode('utf-8')
    else   :
        psu_com.write(f"{type}{channel}O?\r\n".encode('utf-8'))
        response= psu_com.read(8).decode('utf-8')
        
    psu_com.flushOutput()
    psu_com.flushInput()
    return response

def psu_monitor_thread(psu_com, stop_event,freq,nopsurequired):
    while psu_com:
        while not stop_event.is_set():
            try:
                # Read the voltage and current for each channel
                ch1_v = psuRead(psu_com, "1", "V",True).rstrip()
                ch1_i = psuRead(psu_com, "1", "I",True).rstrip()
                ch2_v = psuRead(psu_com, "2", "V",True).rstrip()
                ch2_i = psuRead(psu_com, "2", "I",True).rstrip()
                ch3_v = psuRead(psu_com, "3", "V",True).rstrip()
                ch3_i = psuRead(psu_com, "3", "I",True).rstrip()
                
                # Log the readings
                psu_log.info(f"{ch1_v}  \t{ch1_i}  \t{ch2_v}  \t{ch2_i}  \t{ch3_v}  \t{ch3_i}")
                if (not(11.2 < float(ch1_v.strip("V")) < 13.2) or not(11.2 < float(ch2_v.strip("V")) < 13.2) or not(4.8 <float(ch3_v.strip("V")) <5.5)):
                    psu_log.error(f"Voltage out of bounds Ch1 :  {ch1_v}\t Ch2 : {ch2_v}\t Ch3 : {ch3_v} ")
                    emergencyShutDown(psu_com,nopsurequired)          

                if (float(ch1_i.strip("A")) >=150) or (float(ch2_i.strip("A")) >=90)or (float(ch3_i.strip("A")) >=150):
                    psu_log.error(f"Current out of bounds Ch1 :  {ch1_i}\t Ch2 : {ch2_i}\t Ch3 : {ch3_i} ")
                    emergencyShutDown(psu_com)  

            except Exception as e:
                psu_log.error(f"Error in PSU monitor thread: {e}")
            waitTime = 1/(freq)
            stop_event.wait(waitTime)  # Sleep for 200 ms before the next reading

def setChannels(psu_com,ch1_ovp,ch1_i,ch2_ovp,ch2_i,ch3_ovp,ch3_i):
    while psu_com : 
        # Set the voltage and current limits for each channel
        psu_log.info(f"Setting PSU Channels: CH1 V: {12}V OVP: {ch1_ovp}V, CH1 I: {ch1_i}A")
        psu_com.write(f"V1 12\r\n".encode('utf-8'))
        psu_com.write(f"I1 {ch1_i}\r\n".encode('utf-8'))
        psu_com.write(f"OVP1 {ch1_ovp} 1\r\n".encode('utf-8'))

        psu_log.info(f"Setting PSU Channels: CH2 V: {12}V OVP: {ch2_ovp}V, CH2 I: {ch2_i}A")
        psu_com.write(f"V2 12\r\n".encode('utf-8'))
        psu_com.write(f"I2 {ch2_i}\r\n".encode('utf-8'))
        psu_com.write(f"OVP2 {ch2_ovp} 1\r\n".encode('utf-8'))

        psu_log.info(f"Setting PSU Channels: CH3 V: {5}V OVP: {ch3_ovp}V, CH3 I: {ch3_i}A")
        psu_com.write(f"V3 5\r\n".encode('utf-8'))
        psu_com.write(f"I3 {ch3_i}\r\n".encode('utf-8'))
        psu_com.write(f"OVP3 {ch3_ovp} 1\r\n".encode('utf-8'))

        psu_log.info("PSU Channels set successfully")
        psu_log.info("  CH1_V \t   CH1_I \t  CH2_V \t  CH2_I \t  CH3_V \t   CH3_I")
        psu_com.flushOutput()
        psu_com.flushInput()

def switchPSU(psu_com,state) :
    # psu_status = int(psuRead(psu_com, "1", "OP",False))
    # psu_status = not psu_status
    while psu_com : 
        psu_com.write(f"OPALL {int(state)}\r\n".encode('utf-8'))

def emergencyShutDown(psu_com) : 
    while psu_com : 
        psu_com.write(f"OPALL 0\r\n".encode('utf-8'))
        psu_log.error(f"Closing all channels")
        psu_com.write(f"LOCAL\r\n".encode('utf-8'))
        psu_log.error(f"Setting to Local control")
        psu_com.flushOutput()
        psu_com.flushInput()
        psu_com.close()
        
## TODO: Create a log for this - 
# #?Done
## TODO: Create a clear settings file, Voltages to be set, Current limits
# ?Done in the constants file
## TODO: Add monitoring, such that we have warning current limits and alarm limits
## TODO: If alarm limit, automatically shutdown
# ?Done using emergency shut down function - closes outputs and switches to local control before closing comms
## TODO: Close the comms
# ?See above
## TODO: Report the link status
## TODO: Loop through every 1s (async?)
# ?Done with threading
