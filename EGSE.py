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

#----Test Functions---------------------------------------------------------------------------------
def approx_cal_3V3(raw):
    return raw * 4.05/4095 * 2

def approx_cal_1V5(raw):
    return raw * 4.05/4095

def approx_dig_trp(raw):
    return raw * 4.0/4095


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
sci =      "1F000000000000"
pwr =      "04030000000000"

mtr_par =  "0A61A800060FFF" #Set Motor Default Param
mtr_grd =  "0B7F0064380005" #Set Motor Drive Guards
mtr_p100 = "10010000000000" #Move x0100 steps forward
mtr_mask = "0DFF0000000000"
mtr_home = "13070000000000"

hk_sam =   "1B010000000000"

cmd = hk_sam
cmd_tc = crc8Calculate(cmd)

# for i in range(10):
#cmd_tc = crc8InjectErr(cmd)
print(f"CMD_TC: {bytes.hex(cmd_tc, ' ', 2)}")
port.write(cmd_tc)

response = TMs.Raw(port.read(1000))



match(response.cmd_type):
    case 'HK_Request':
        hk = TMs.HK(response.raw_bytes)
        # print(f"{hk.MTR_PWM_DUTY=}")
        #print(f"{hk.MTR_CURRENT=}")
        #print(f"{hk.SPEED=}")
        #print(f"{hk.HK_V_3V3=}")
        #print(f"{hex(hk.HK_V_3V3)}")
        #print(f"{bytes.hex(hk.raw_bytes[46:48], ' ', 2)}")
        #print(f"{hk.HK_SAMPLES=}")
        cal_hk_3v3 = approx_cal_3V3(hk.HK_V_3V3)
        cal_hk_1v5 = approx_cal_1V5(hk.HK_V_1V5)
        cal_dig_trp = approx_dig_trp(hk.DIGITAL_TRP)
        print(f"{cal_hk_3v3:.3f}    {cal_hk_1v5:.3f}    {cal_dig_trp:.3f}")

    case _:
        print("testing")