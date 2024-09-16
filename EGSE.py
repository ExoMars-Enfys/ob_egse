#----Module Imports---------------------------------------------------------------------------------
import logging

import serial
import serial.rs485

from crc8Function import crc8Calculate
import TMs

#----Loggers----------------------------------------------------------------------------------------
formatter = logging.Formatter("{levelname} - {message}", style="{")

tm_log = logging.getLogger("tm_log")
hdlr_1 = logging.StreamHandler()
hdlr_1.setFormatter(formatter)
tm_log.setLevel(logging.DEBUG)
tm_log.addHandler(hdlr_1)


#----FPGA Boot and Connect--------------------------------------------------------------------------
port = serial.rs485.RS485(port = "COM10",  #Serial Port Initialisation
                    baudrate=115200,
                    bytesize = serial.EIGHTBITS,
                    parity = serial.PARITY_ODD,
                    stopbits = serial.STOPBITS_ONE,
                    timeout = 0.5)
port.rs485_mode = serial.rs485.RS485Settings(
    rts_level_for_tx= False,
    rts_level_for_rx= True,
    loopback= False,
    delay_before_tx = 0,
    delay_before_rx= 0
)
# port.flushOutput() #Port Flushing to clear port
# port.flushInput()

#----


hk = "00" * 7 #HK request
pwr = "04030000000000"
mtr_par =  "0A303900060FFF" #Set Motor Default Param
cmd = hk
cmd_tc = crc8Calculate(cmd)
#cmd_tc = crc8InjectErr(cmd)
print(f"CMD_TC: {bytes.hex(cmd_tc, ' ', 2)}")
port.write(cmd_tc)

response = TMs.Raw(port.read(1000))

match(response.cmd_type):
    case 'HK_Request':
        hk = TMs.HK(response.raw_bytes)
        # print(f"{hk.MTR_CURRENT=}")
        # print(f"{hk.MTR_PWM_DUTY=}")
        print(f"{hk.HK_V_3V3=}")
        print(f"{hk.DIGITAL_TRP=}")
    case _:
        print("testing")