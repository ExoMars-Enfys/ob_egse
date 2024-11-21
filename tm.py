# ----Module Imports---------------------------------------------------------------------------------
import logging
from collections import namedtuple

from bitstruct import unpack_from as upf
import bitstruct
import crc8
import serial.rs485

import tmstruct
from cmd_ids import cmd_ids
from constants import EXP_MODEL_ID

tm_log = logging.getLogger("tm_log")

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
        tm_log.info(f"HK received: {bytes.hex(self.raw_bytes, ' ', 2)}")

        param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.hk), [i[0] for i in tmstruct.hk], raw_bytes
        )

        for k, v in param.items():
            setattr(self, k, v)

        self.MTR_FLAGS = namedtuple(
            "MTR_FLAGS", "".join(i[1] for i in tmstruct.mtr_flag_struct)
        )

        ## Decode bit maps
        # Motor Flags
        mtr_flags_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_flag_struct),
            [i[0] for i in tmstruct.mtr_flag_struct],
            self.MTR_FLAGS_BYTE.to_bytes(1),
        )

        for k, v in mtr_flags_param.items():
            setattr(self.MTR_FLAGS, k, v)

        tm_log.info(f"CMD Count: {self.CMD_CNT=}")

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

    def check_errors(self):
        if self.ERROR != 0x00:
            tm_log.error(f"HK Error asserted: {self.ERROR}")
            #! TODO Decode bit struct here

    def check_unused(self):
        if self.UNUSED1 == 0x00:
            tm_log.warning(f"HK Unused1 is not zero actually: {hex(self.UNUSED1)}")


class ACK(getResponse):
    def __init__(self, raw_bytes, ack_type):
        self.raw_bytes = raw_bytes
        self.ack_type = ack_type
        self.get_cmd_mod_id(self.raw_bytes)

        self.check_len()
        tm_log.info(f"ACK received: {bytes.hex(self.raw_bytes, ' ', 2)}")

        pkt_strct = tmstruct.ack_hdr + ack_type
        tm_log.debug(pkt_strct)
        param = bitstruct.unpack_dict(
            "".join(i[1] for i in pkt_strct), [i[0] for i in pkt_strct], raw_bytes
        )
        for k, v in param.items():
            setattr(self, k, v)

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

    def check_errors(self):
        if self.ERROR != 0x00:
            tm_log.error(f"HK Error asserted: {self.ERROR}")


def parse_tm(response):
    tm_log.debug(f"Response type: {response.cmd_type}")
    match (response.cmd_type):
        case "HK_Request":
            hk = HK(response.raw_bytes)
            # print(
            #     f"{hk.approx_cal_3V3:.3f}    {hk.approx_cal_1V5:.3f}    {hk.approx_cal_1V5:.3f}"
            # )
            print(f"CMD Count: {hk.CMD_CNT}")
            print(f"MOVING: {hk.MTR_FLAGS.MOVING}")
            print(f"DIR: {hk.MTR_FLAGS.DIR}")
            print(f"HOMED: {hk.MTR_FLAGS.HOMED}")
            print(f"BASE: {hk.MTR_FLAGS.BASE}")
            print(f"OUTER: {hk.MTR_FLAGS.OUTER}")
            return hk
        case "Power_Control":
            ack = ACK(response.raw_bytes, tmstruct.ack_power_control)
            return ack
        case "Heater_Control":
            ack = ACK(response.raw_bytes, tmstruct.ack_heater_control)
            return ack
        case "Set_Mech_SP":
            ack = ACK(response.raw_bytes, tmstruct.ack_set_mech_sp)
            return ack
        case "Set_Detec_SP":
            ack = ACK(response.raw_bytes, tmstruct.ack_set_detec_sp)
            return ack
        case "Set_MTR_Param":
            ack = ACK(response.raw_bytes, tmstruct.ack_set_mtr_param)
            return ack
        case "Set_MTR_Guard":
            ack = ACK(response.raw_bytes, tmstruct.ack_set_mtr_guard)
            return ack
        case "Set_MTR_Mon":
            ack = ACK(response.raw_bytes, tmstruct.ack_set_mtr_mon)
            return ack
        case _:
            tm_log.warning(
                f"Response type not defined in parse_tm: {response.cmd_type}"
            )
