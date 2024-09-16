#--------------------------Module Imports---------------------------#
import serial
import serial.rs485
from crc8Function import crc8Calculate, crc8InjectErr
import crc8
from hk import Housekeeping_Parser
from binascii import unhexlify

#-------------------------Initialisation----------------------------#
output = ""
port=""
inputCmd = ""
response =""
filename = ""
speed = 0.005

hash = crc8.crc8()

prev_cmd_cnt = 0
hk_cmd_cnt = 0
resp_types = {0 : 'HK', 31: 'Sci'}

exp_model_id = 0x01

#---------------------FPGA Boot and Connect-------------------------#
port = serial.rs485.RS485(port = "COM14",                                                    #Serial Port Initialisation
                    baudrate=115200,
                    bytesize = serial.EIGHTBITS,
                    parity = serial.PARITY_ODD,
                    stopbits = serial.STOPBITS_ONE,
                    timeout = 0.5)
# port.rs485_mode = serial.rs485.RS485Settings(
#     rts_level_for_tx= False,
#     rts_level_for_rx= True,
#     loopback= False,
#     delay_before_tx = 0,
#     delay_before_rx= 0
# )
# port.flushOutput() #Port Flushing to clear port
# port.flushInput()

hk = "00" * 7 #HK request
#hk = "00" * 6 + "AB"
sci =      "1F000000000000"
pwr =      "04030000000000"
mtr_par =  "0A61A800060FFF" #Set Motor Default Param
mtr_grd =  "0B7F0064380005" #Set Motor Drive Guards
mtr_p100 = "10010000000000" #Move x0100 steps forward
mtr_mask = "0DFF0000000000"
mtr_home = "13070000000000"

cmd = hk
cmd_tc = crc8Calculate(cmd)
#cmd_tc = crc8InjectErr(cmd)
print(f"CMD_TC: {bytes.hex(cmd_tc, ' ', 2)}")
port.write(cmd_tc)
response = port.read(1000)

if not response:
    print("No response exit")
    exit(0)

if hash.reset().update(response).hexdigest() != '00':
    print("!!!!Error!!!! incorrect CRC")

model_id = response[0] & 0x01
if model_id != exp_model_id:
    print(f"!!!!Error!!!! incorrect Model ID. Got: {model_id}")

resp_type = response[0] >> 3 # Remove Model ID
print(f"Resp: {bytes.hex(response, ' ', 2)}")
print(f"Resp Type: {resp_types.get(resp_type, 'ACK')}")

if resp_type == 0: #Type HK
    # Check length
    if len(response) != 72:
        print(f"Error Length not 72 bytes as expected, Len: {len(response)}")

    hk_cmd_cnt = response[1]
    hk_error = response[2]
    hk_mtr_error = response[3]
    hk_mtr_abs_steps = response[4:6]

    print(f"Cmd Count: {hk_cmd_cnt}")
    # if hk_cmd_cnt - prev_cmd_cnt != 1:
    #     print(f"CMD Count Error! Prev Count: {prev_cmd_cnt}, Cur Count: {hk_cmd_cnt}")

    prev_cmd_cnt = hk_cmd_cnt
    # TODO some way to check if first command and ignore
    
    # Motor Relative Steps
    hk_mtr_rel = response[12:14]
    print(f"MTR_REL: {bytes.hex(hk_mtr_rel)}")
    # Motor Status
    hk_mtr_flags = response[14]
    print(f"MTR_STATUS: {hk_mtr_flags}")
    # Motor Guard
    hk_mtr_guard = response[15:17]
    print(f"MTR_GUARD: {bytes.hex(hk_mtr_guard)}")
    # Motor PWM Duty
    hk_pwm_duty = response[17]
    print(f"MTR_PWM_DUTY: {hk_pwm_duty}")
    # Motor PWM Rate
    hk_pwm_rate = response[18]
    print(f"MTR_PWM_RATE: {hk_pwm_rate}")
    # Check HK Samples
    hk_hk_samples = response[46]
    print(f"HK Samples: {hk_hk_samples}")
    # HK ADC 0
    hk_adc_0 = response[46:48]
    print(f"HK ADC CH0: {bytes.hex(hk_adc_0)}")
    cal_3v3 = int.from_bytes(hk_adc_0) * 4.05/4095 *2
    print(cal_3v3)

    

else:
    if response[1] == 0:
        print(f"No error")
    else:
        print(f"!!!!Error in ACK: {hex(response[1])}")