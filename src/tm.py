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


info_log = logging.getLogger("info_log")


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
        self.cmd_id = upf("u4", self.raw_bytes, offset=4)[0]

    def verify_cmd_id(self):
        if self.cmd_id in cmd_ids:
            self.cmd_type = cmd_ids.get(self.cmd_id)
        else:
            self.cmd_type = "UNKOWN"
            info_log.error(f"CMD ID Not Found. Got:{self.cmd_id}")

    def verify_model_id(self):
        if self.mod_id != const.EXP_MODEL_ID:
            info_log.error(f"Model ID not as expected. Expected:{const.EXP_MODEL_ID}, Got: {self.mod_id}")

    def verify_crc(self):
        self.hash = crc8.crc8()
        if self.hash.update(self.raw_bytes).hexdigest() != "00":
            info_log.error(
                f"Incorrect CRC8. Calculated: 0x{self.hash.hexdigest()}. For Packet {bytes.hex(self.raw_bytes, ' ', 2)}"
            )


class TM:
    # TODO Be consistent with how the bytes are named when they unpacked to the flags
    def __init__(self, response: Response):
        self.raw_bytes = response.raw_bytes
        self.get_cmd_mod_id = response.get_cmd_mod_id

    @abstractmethod
    def check_len(self):
        pass
    
    def decode_bytes(self, pkt_struct):
        param = bitstruct.unpack_dict(
            "".join(i[1] for i in pkt_struct),
            [i[0] for i in pkt_struct],
            self.raw_bytes,
        )
        self.params = []
        for k, v in param.items():
            self.params.append(k)
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

    def decode_mtr_error_byte(self):
        ## Decode bit maps
        # Motor Errors
        self.MTR_ERRORS = namedtuple("MTR_ERRORS", "".join(i[1] for i in tmstruct.mtr_error_struct))
        mtr_error_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_error_struct),
            [i[0] for i in tmstruct.mtr_error_struct],
            self.ERROR_MTR.to_bytes(1),
        )
        for k, v in mtr_error_param.items():
            setattr(self.MTR_ERRORS, k, v)

    def check_errors(self):
        if self.ERROR_BYTE != 0x00:
            info_log.error(f"HK Error asserted: {self.ERROR_BYTE}")
            if self.ERRORS.UNUSED1:
                info_log.error(f"OB ERROR UNUSED1 - should always be False!!!")
            if self.ERRORS.TMO:
                info_log.error(f"OB ERROR TMO - Time Out")
            if self.ERRORS.IOS:
                info_log.error(f"OB ERROR IOS - Invalid OB State")
            if self.ERRORS.LIM:
                info_log.error(f"OB ERROR LIM - Motor Rel Lim Exceeded")
            if self.ERRORS.LMO:
                info_log.error(f"OB ERROR LMO - Motor Monitor Lim Exceeded")
            if self.ERRORS.ICR:
                info_log.error(f"OB ERROR ICR - Invalid CMD CRC")
            if self.ERRORS.IPA:
                info_log.error(f"OB ERROR IPA - Invalid Parity Error")
            if self.ERRORS.ICI:
                info_log.error(f"OB ERROR ICI - Invalid Command ID")

    def csv_header(self, *param_list, separator=','):
        if not param_list:
            param_list = self.params
        return separator.join(param_list)

    def csv(self, *param_list, separator=","):
        if not param_list:
            param_list = self.params
        return separator.join(str(getattr(self, p)) for p in param_list)


class HK(TM):
    def __init__(self, response: Response):
        super().__init__(response)

        if const.HK_LOG_FH is not None:
            const.HK_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            const.HK_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        info_log.info(f"HK received: {bytes.hex(self.raw_bytes, ' ', 2)}")

        # Allocate variables based on tm struct
        self.decode_bytes(tmstruct.hk)
        self.decode_error_byte()
        self.decode_mtr_error_byte()

        # Motor Flags
        self.MTR_FLAGS = namedtuple("MTR_FLAGS", "".join(i[1] for i in tmstruct.mtr_flag_struct))
        mtr_flags_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_flag_struct),
            [i[0] for i in tmstruct.mtr_flag_struct],
            self.MTR_FLAGS_BYTE.to_bytes(1),
        )
        for k, v in mtr_flags_param.items():
            setattr(self.MTR_FLAGS, k, v)

        info_log.info(f"CMD Count: {self.CMD_CNT=}")

        self.check_len()
        self.check_errors()
        self.check_unused()

        # Approximate calibrations
        self.approx_cal_3V3 = self.HK_V_3V3 * 4.05 / 4095 * 2
        self.approx_cal_1V5 = self.HK_V_1V5 * 4.05 / 4095
        self.approx_dig_trp = self.DIGITAL_TRP * 4.0 / 4095

        # Add these to self.params so they'll be available in CSV data.
        self.params.append("approx_cal_3V3")
        self.params.append("approx_cal_1V5")
        self.params.append("approx_dig_trp")

        #! TODO Ret of HK
        #! TODO add verify commands

    def check_len(self):
        # TODO: May want to adjust to calculate length based on structure like ACK
        if len(self.raw_bytes) != 66:
            info_log.error(f"HK Len not 66 bytes as expected. Got: {len(self.raw_bytes)}")

    def check_unused(self):
        if self.UNUSED1 != 0x00:
            info_log.warning(f"HK Unused1 is not zero actually: {hex(self.UNUSED1)}")


class ACK(TM):
    def __init__(self, response: Response):
        super().__init__(response)

        if const.ACK_LOG_FH is not None:
            const.ACK_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            const.ACK_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        info_log.info(f"TM log ACK received: {bytes.hex(self.raw_bytes, ' ', 2)}")

        self.decode_bytes(tmstruct.ack_struct)
        self.decode_error_byte()
        self.check_len()
        self.check_errors()

        # TODO Check CRC

    def check_len(self):
        expect_strct = tmstruct.ack_struct
        expect_len = bitstruct.calcsize("".join([i[1] for i in expect_strct])) / 8
        if len(self.raw_bytes) != expect_len:
            info_log.error(f"ACK Len not {expect_len} bytes as expected. Got: {len(self.raw_bytes)}")

class SCI(TM):
    def __init__(self, response: Response):
        super().__init__(response)

        if const.SCI_LOG_FH is not None:
            const.SCI_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            const.SCI_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        info_log.info(f"SCI received: {bytes.hex(self.raw_bytes, ' ', 2)}")

        # Allocate variables based on tm struct
        self.decode_bytes(tmstruct.sci)
        self.decode_error_byte()

        self.check_len()
        self.check_errors()

    def check_len(self):
        if len(self.raw_bytes) != 29:
            info_log.error(f"SCI Len not 29 bytes as expected. Got: {len(self.raw_bytes)}")

class NACK(TM):
    def __init__(self, response: Response):
        super().__init__(response)

        if const.ACK_LOG_FH is not None:
            const.ACK_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            const.ACK_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        info_log.error(f"NACK recieved: {bytes.hex(self.raw_bytes, ' ', 2)}")

        self.decode_bytes(tmstruct.nack)
        self.decode_error_byte()
        self.check_len()
        self.check_errors()

    def check_len(self):
        # TODO: May want to adjust to calculate length based on structure like ACK
        if len(self.raw_bytes) != 4:
            info_log.error(f"NACK Len not 4 bytes as expected. Got: {len(self.raw_bytes)}")

def get_response(port: serial.rs485.RS485, no_of_bytes: int = 1000) -> bytes:
    raw_bytes = port.read(no_of_bytes)
    info_log.info(f"Response: {bytes.hex(raw_bytes, ' ', 2)}")
    return raw_bytes

def parse_tm(response):

    info_log.debug(f"Response type: {response.cmd_type}")
    
    if response.cmd_type == "HK_Request":
        ack = HK(response)
        const.hk_queue.append(ack)
    elif response.cmd_type == "SCI_Request":
        ack = SCI(response)
    elif response.cmd_type == "NACK":
        ack = NACK(response)
    else:        
        match response.cmd_type:
            case "Clear_Errors":
                ack = ACK(response)
            case "Power_Control":
                ack = ACK(response)
            case "Heater_Control":
                ack = ACK(response)
            case "Set_Mech_SP":
                ack = ACK(response)
            case "Set_Detec_SP":
                ack = ACK(response)
            case "Set_MTR_Param":
                ack = ACK(response)
            case "MTR_Mov_Pos":
                ack = ACK(response)
            case "MTR_Mov_Neg":
                ack = ACK(response)
            case "MTR_Halt":
                ack = ACK(response)
            case "MTR_Homing":
                ack = ACK(response)
            case "HK_Samples":
                ack = ACK(response)
            case "SCI_Offset":
                ack = ACK(response)
            case _:
                info_log.warning(
                    f"Response type not defined in parse_tm: {response.cmd_type}"
                )
                ack = "EMPTY"
    return ack
