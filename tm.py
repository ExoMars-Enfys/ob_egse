# ----Module Imports--------------------------------------------------------------------------------
import logging
from abc import ABC, abstractmethod
from collections import namedtuple

from bitstruct import unpack_from as upf
import bitstruct
import crc8
import serial.rs485
from datetime import datetime

import constants as const
import tmstruct
from cmd_ids import cmd_ids


tm_log = logging.getLogger("tm_log")
info_log = logging.getLogger("info_log")
abs_log = logging.getLogger("abs_log")

# ----Class definitions-----------------------------------------------------------------------------
class Response:
    def __init__(self, raw_bytes):
        self.raw_bytes = raw_bytes
        self.get_cmd_mod_id()
        self.verify_cmd_id()
        self.verify_model_id()
        self.verify_crc()

    def get_cmd_mod_id(self):
        self.mod_id = upf("u3", self.raw_bytes, offset=0)[0]
        self.cmd_id = upf("u5", self.raw_bytes, offset=3)[0]

    def verify_cmd_id(self):
        if self.cmd_id in cmd_ids:
            self.cmd_type = cmd_ids.get(self.cmd_id)
        else:
            self.cmd_type = "UNKOWN"
            tm_log.error(f"CMD ID Not Found. Got:{self.cmd_id}")

    def verify_model_id(self):
        if self.mod_id != const.EXP_MODEL_ID:
            tm_log.error(
                f"Model ID not as expected. Expected:{const.EXP_MODEL_ID}, Got: {self.mod_id}"
            )

    def verify_crc(self):
        self.hash = crc8.crc8()
        if self.hash.update(self.raw_bytes).hexdigest() != "00":
            tm_log.error(
                f"Incorrect CRC8. Calculated: 0x{self.hash.hexdigest()}. "
                f"For Packet {bytes.hex(self.raw_bytes, ' ', 2)}"
            )

class TM:
    def __init__(self, response:Response):
        self.raw_bytes = response.raw_bytes
        self.get_cmd_mod_id = response.get_cmd_mod_id
    
    @abstractmethod
    def check_len(self):
        pass

    def decode_bytes(self, pkt_struct):
        param = bitstruct.unpack_dict(
            "".join(i[1] for i in pkt_struct), [i[0] for i in pkt_struct], self.raw_bytes
        )
        for k, v in param.items():
            setattr(self, k, v)

    def decode_error_byte(self):
        ## Decode bit maps
        # Errors
        self.ERRORS = namedtuple("ERRORS", "".join(i[1] for i in tmstruct.error_struct))
        error_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.error_struct),
            [i[0] for i in tmstruct.error_struct],
            self.ERROR_BYTE.to_bytes(1),
        )
        for k, v in error_param.items():
            setattr(self.ERRORS, k, v)

    def check_errors(self):
        if self.ERROR_BYTE != 0x00:
            tm_log.error(f"HK Error asserted: {self.ERROR_BYTE}")
            if self.ERRORS.UNUSED1:
                tm_log.error(f"OB ERROR UNUSED1 - should always be False!!!")
            if self.ERRORS.TMO:
                tm_log.error(f"OB ERROR TMO - Time Out")
            if self.ERRORS.IOS:
                tm_log.error(f"OB ERROR IOS - Invalid OB State")
            if self.ERRORS.LIM:
                tm_log.error(f"OB ERROR LIM - Motor Rel Lim Exceeded")
            if self.ERRORS.LMO:
                tm_log.error(f"OB ERROR LMO - Motor Monitor Lim Exceeded")
            if self.ERRORS.ICR:
                tm_log.error(f"OB ERROR ICR - Invalid CMD CRC")
            if self.ERRORS.IPA:
                tm_log.error(f"OB ERROR IPA - Invalid Parity Error")
            if self.ERRORS.ICI:
                tm_log.error(f"OB ERROR ICI - Invalid Command ID")

    

class HK(TM):
    def __init__(self, response:Response):
        super().__init__(response)

        const.HK_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        const.HK_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        tm_log.info(f"HK received: {bytes.hex(self.raw_bytes, ' ', 2)}")
        
        # Allocate variables based on tm struct
        self.decode_bytes(tmstruct.hk)
        
        # Motor Flags
        self.MTR_FLAGS = namedtuple(
            "MTR_FLAGS", "".join(i[1] for i in tmstruct.mtr_flag_struct)
        )
        mtr_flags_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_flag_struct),
            [i[0] for i in tmstruct.mtr_flag_struct],
            self.MTR_FLAGS_BYTE.to_bytes(1),
        )
        for k, v in mtr_flags_param.items():
            setattr(self.MTR_FLAGS, k, v)

        tm_log.info(f"CMD Count: {self.CMD_CNT=}")

        self.check_len()
        self.check_errors()
        self.check_unused()

        # Approximate calibrations
        self.approx_cal_3V3 = self.HK_V_3V3 * 4.05 / 4095 * 2
        self.approx_cal_1V5 = self.HK_V_1V5 * 4.05 / 4095
        self.approx_dig_trp = self.DIGITAL_TRP * 4.0 / 4095

        #! TODO Ret of HK
        #! TODO add verify commands

    def check_len(self):
        # TODO: May want to adjust to calculate length based on structure like ACK
        if len(self.raw_bytes) != 66:
            tm_log.error(f"HK Len not 66 bytes as expected. Got: {len(self.raw_bytes)}")

    def check_unused(self):
        if self.UNUSED1 == 0x00:
            tm_log.warning(f"HK Unused1 is not zero actually: {hex(self.UNUSED1)}")


class ACK(TM):
    def __init__(self, response:Response, ack_type):
        super().__init__(response)
        self.ack_type = ack_type

        const.ACK_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        const.ACK_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        tm_log.info(f"ACK received: {bytes.hex(self.raw_bytes, ' ', 2)}")
        info_log.info(f"ACK received: {bytes.hex(self.raw_bytes, ' ', 2)}")

        # Allocate variables based on tm struct
        pkt_strct = tmstruct.ack_hdr + ack_type
        tm_log.debug(pkt_strct)
        
        self.decode_bytes(pkt_strct)
        self.decode_error_byte()
        self.check_len()
        self.check_errors()

    def check_len(self):
        expect_strct = tmstruct.ack_hdr + self.ack_type
        expect_len = (
            bitstruct.calcsize("".join([i[1] for i in expect_strct])) / 8 + 1
        )  # +1 for CRC

        if len(self.raw_bytes) != expect_len:
            tm_log.error(
                f"ACK Len not {expect_len} bytes as expected. Got: {len(self.raw_bytes)}"
            )


class NACK(TM):
    def __init__(self, response:Response):
        super().__init__(response)
        
        const.ACK_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        const.ACK_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        tm_log.error(f"NACK recieved: {bytes.hex(self.raw_bytes, ' ', 2)}")

        self.decode_bytes(tmstruct.nack)
        self.decode_error_byte()
        self.check_len()
        self.check_errors()

    def check_len(self):
        # TODO: May want to adjust to calculate length based on structure like ACK
        if len(self.raw_bytes) != 4:
            tm_log.error(
                f"NACK Len not 4 bytes as expected. Got: {len(self.raw_bytes)}"
            )


def get_response(port: serial.rs485.RS485) -> bytes:
    raw_bytes = port.read(1000)
    info_log.info(f"Response: {bytes.hex(raw_bytes, ' ', 2)}")
    return raw_bytes

def parse_tm(response):
    tm_log.debug(f"Response type: {response.cmd_type}")
    match (response.cmd_type):
        case "HK_Request":
            ack = HK(response)
            # print(f"{ack.approx_cal_3V3:.3f}    {ack.approx_cal_1V5:.3f}")
            # print(f"CMD Count: {hk.CMD_CNT}")
            # print(f"MOVING: {hk.MTR_FLAGS.MOVING}")
            # print(f"DIR: {hk.MTR_FLAGS.DIR}")
            # print(f"CMD Count: {hk.CMD_CNT}")
            # print(f"MOVING: {hk.MTR_FLAGS.MOVING}")
            # print(f"DIR: {hk.MTR_FLAGS.DIR}")
            # print(f"HOMED: {hk.MTR_FLAGS.HOMED}")
            # print(f"BASE: {hk.MTR_FLAGS.BASE}")
            # print(f"OUTER: {hk.MTR_FLAGS.OUTER}")
        case "Power_Control":
            ack = ACK(response, tmstruct.ack_power_control)
        case "Heater_Control":
            ack = ACK(response, tmstruct.ack_heater_control)
        case "Set_Mech_SP":
            ack = ACK(response, tmstruct.ack_set_mech_sp)
        case "Set_Detec_SP":
            ack = ACK(response, tmstruct.ack_set_detec_sp)
        case "Set_MTR_Param":
            ack = ACK(response, tmstruct.ack_set_mtr_param)
        case "Set_MTR_Guard":
            ack = ACK(response, tmstruct.ack_set_mtr_guard)
        case "Set_MTR_Mon":
            ack = ACK(response, tmstruct.ack_set_mtr_mon)
        case "MTR_Homing":
            ack = ACK(response, tmstruct.ack_mtr_homing)
        case "MTR_Mov_Pos":
            ack = ACK(response, tmstruct.ack_mtr_mov_pos)
        case "MTR_Mov_Neg":
            ack = ACK(response, tmstruct.ack_mtr_mov_neg)
        case "MTR_Mov_Abs":
            ack = ACK(response, tmstruct.ack_mtr_mov_abs)
        case "NACK":
            ack = NACK(response)
        case _:
            tm_log.warning(
                f"Response type not defined in parse_tm: {response.cmd_type}"
            )
            ack = "EMPTY"
    return ack
