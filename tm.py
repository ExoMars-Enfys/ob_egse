# ----Module Imports---------------------------------------------------------------------------------
import logging

from bitstruct import unpack_from as upf
import bitstruct
import crc8
import serial.rs485

import tmstruct
from cmd_ids import cmd_ids
from constants import EXP_MODEL_ID

tm_log = logging.getLogger("tm_log")


# ----Test Functions---------------------------------------------------------------------------------
def approx_cal_3V3(raw):
    return raw * 4.05 / 4095 * 2


def approx_cal_1V5(raw):
    return raw * 4.05 / 4095


def approx_dig_trp(raw):
    return raw * 4.0 / 4095


# ----Class definitions------------------------------------------------------------------------------


class getResponse:
    def __init__(self, port: serial.rs485.RS485):
        self.raw_bytes = port.read(1000)
        tm_log.info(f"Response: {bytes.hex(self.raw_bytes, ' ', 2)}")
        self.get_cmd_mod_id(self.raw_bytes)
        self.verify_cmd_id()
        self.verify_model_id()
        self.verify_crc()

    def get_cmd_mod_id(self, bytes):
        self.mod_id = upf("u3", bytes, offset=0)[0]
        self.cmd_id = upf("u5", bytes, offset=3)[0]
        # print("model : " , self.mod_id," Command ID" ,self.cmd_id)

    def verify_cmd_id(self):
        if self.cmd_id in cmd_ids:
            self.cmd_type = cmd_ids.get(self.cmd_id)
        else:
            self.cmd_type = "UNKOWN"
            tm_log.error(f"CMD ID Not Found. Got:{self.cmd_id}")

    def verify_model_id(self):
        if self.mod_id != EXP_MODEL_ID:
            tm_log.error(
                f"Model ID not as expected. Expected:{EXP_MODEL_ID}, Got: {self.mod_id}"
            )

    def verify_crc(self):
        self.hash = crc8.crc8()
        if self.hash.update(self.raw_bytes).hexdigest() != "00":
            tm_log.error(
                f"Incorrect CRC8. Calculated: 0x{self.hash.hexdigest()}. "
                f"For Packet {bytes.hex(self.raw_bytes, ' ', 2)}"
            )


class HK(getResponse):
    def __init__(self, raw_bytes):
        self.raw_bytes = raw_bytes
        # print(bytes.hex(self.raw_bytes, ' ', 2))
        self.get_cmd_mod_id(self.raw_bytes)

        self.check_len()

        self.param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.hk), [i[0] for i in tmstruct.hk], raw_bytes
        )

        for k, v in self.param.items():
            setattr(self, k, v)

        # tm_log.info(f"{self.CMD_CNT=}")

        self.check_errors()
        self.check_unused()

        #! TODO Ret of HK
        #! TODO add verify commands

    def check_len(self):
        if len(self.raw_bytes) != 66:
            tm_log.error(f"HK Len not 66 bytes as expected. Got: {len(self.raw_bytes)}")

    def check_errors(self):
        if self.ERROR != 0x00:
            tm_log.error(f"HK Error asserted: {self.ERROR}")
            #! TODO Decode bit struct here

    def check_unused(self):
        if self.UNUSED1 == 0x00:
            tm_log.warning(f"HK Unused1 is not zero actually: {hex(self.UNUSED1)}")


class ACK(getResponse):
    def __init__(self, raw_bytes):
        self.raw_bytes = raw_bytes
        self.get_cmd_mod_id(self.raw_bytes)
        # self.check_len() -- removed until we can resolve variable ACK length
        tm_log.info(f"ACK received: {bytes.hex(self.raw_bytes, ' ', 2)}")
        param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.ack), [i[0] for i in tmstruct.ack], raw_bytes
        )
        for k, v in param.items():
            setattr(self, k, v)

        self.check_errors()

    def check_len(self):
        if len(self.raw_bytes) != 9:
            tm_log.error(f"ACK Len not 9 bytes as expected. Got: {len(self.raw_bytes)}")

    def check_errors(self):
        if self.ERROR != 0x00:
            tm_log.error(f"HK Error asserted: {self.ERROR}")


def parse_tm(response):
    match (response.cmd_type):
        case "HK_Request":
            hk = HK(response.raw_bytes)
            # print(f"{hk.MTR_PWM_DUTY=}")
            # print(f"{hk.MTR_CURRENT=}")
            # print(f"{hk.SPEED=}")
            # print(f"{hk.HK_V_3V3=}")
            # print(f"{hex(hk.HK_V_3V3)}")
            # print(f"{bytes.hex(hk.raw_bytes[46:48], ' ', 2)}")
            # print(f"{hk.HK_SAMPLES=}")
            cal_hk_3v3 = approx_cal_3V3(hk.HK_V_3V3)
            cal_hk_1v5 = approx_cal_1V5(hk.HK_V_1V5)
            cal_dig_trp = approx_dig_trp(hk.DIGITAL_TRP)
            print(f"{cal_hk_3v3:.3f}    {cal_hk_1v5:.3f}    {cal_dig_trp:.3f}")
            return hk
        case _:
            ack = ACK(response.raw_bytes)
