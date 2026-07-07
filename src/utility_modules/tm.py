# ----Module Imports--------------------------------------------------------------------------------
# Std library
import logging

# Additional libraries
from abc import abstractmethod
from datetime import datetime
from collections import namedtuple
from bitstruct import unpack_from as upf
import bitstruct
import crc8
import serial.rs485

# Local modules
# core
from core_modules import cmd_ids as cmd_ids
from core_modules import config as config
from core_modules import constants as const
from core_modules import tmstruct as tmstruct

# utilities
from utility_modules import comms as comms
from utility_modules import tc as tc
from utility_modules import tm as tm


info_log = logging.getLogger("info_log")


# ----Class definitions-----------------------------------------------------------------------------
class Response:
    """Class Definition for the raw response received from the serial port."""

    def __init__(self, raw_bytes):
        self.raw_bytes = raw_bytes
        self.get_cmd_mod_id()
        self.verify_cmd_id()
        self.verify_model_id()
        self.verify_crc()

    def get_cmd_mod_id(self):
        """Extract the command and module IDs from the raw bytes."""
        self.mod_id = upf("u3", self.raw_bytes, offset=0)[0]
        self.cmd_id = upf("u4", self.raw_bytes, offset=4)[0]

    def verify_cmd_id(self):
        """Verify that the command ID matches one of the expected values and set the command type accordingly."""
        if self.cmd_id in cmd_ids.cmd_ids:
            self.cmd_type = cmd_ids.cmd_ids.get(self.cmd_id)
        else:
            self.cmd_type = "UNKOWN"
            info_log.error(f"CMD ID Not Found. Got:{self.cmd_id}")

    def verify_model_id(self):
        """Verify that the model ID matches the expected value."""
        if self.mod_id != config.EXP_MODEL_ID:
            info_log.error(f"Model ID not as expected. Expected:{config.EXP_MODEL_ID}, Got: {self.mod_id}")

    def verify_crc(self):
        """Calculate the CRC8 of the raw bytes and compare it to the expected value. The CRC8 should be 0x00 if the data is correct."""
        self.hash = crc8.crc8()
        if self.hash.update(self.raw_bytes).hexdigest() != "00":
            info_log.error(
                f"Incorrect CRC8. Calculated: 0x{self.hash.hexdigest()}. For Packet {bytes.hex(self.raw_bytes, ' ', 2)}"
            )


class TM:
    """Parent Class Definition for all TM responses. Reads the raw bytes from the response and parses them based on the dictionary defined in tmstruct.py"""

    # TODO Be consistent with how the bytes are named when they unpacked to the flags
    def __init__(self, response: Response):
        self.raw_bytes = response.raw_bytes
        self.get_cmd_mod_id = response.get_cmd_mod_id

    @abstractmethod
    def check_len(self):
        pass

    def decode_bytes(self, pkt_struct):
        """Read the raw bytes and decode them into the appropriate variables using the dictionary defined in tmstruct.py"""
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
        """Read the error byte and decode it into the appropriate flags using the dictionary defined in tmstruct.py"""
        ## Decode bit maps
        # Errors
        self.ERRORS = namedtuple("ERRORS", "".join(i[0] for i in tmstruct.error_struct))
        error_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.error_struct),
            [i[0] for i in tmstruct.error_struct],
            self.ERROR_BYTE.to_bytes(1),
        )
        for k, v in error_param.items():
            setattr(self.ERRORS, str(k), v)

    def decode_mtr_error_byte(self):
        """Read the motor error byte and decode it into the appropriate flags using the dictionary defined in tmstruct.py"""
        ## Decode bit maps
        # Motor Errors
        self.MTR_ERRORS = namedtuple("MTR_ERRORS", "".join(i[0] for i in tmstruct.mtr_error_struct))
        mtr_error_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_error_struct),
            [i[0] for i in tmstruct.mtr_error_struct],
            self.ERROR_MTR.to_bytes(1),
        )
        for k, v in mtr_error_param.items():
            setattr(self.MTR_ERRORS, str(k), v)

    def decode_thrm_status_byte(self):
        """Read the thermal status byte and decode it into the appropriate flags using the dictionary defined in tmstruct.py"""
        ## Decode bit maps
        # Thermal Status
        self.THRM_STATUS = namedtuple("THRM_STATUS", "".join(i[0] for i in tmstruct.thrm_status_struct))
        thrm_status_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.thrm_status_struct),
            [i[0] for i in tmstruct.thrm_status_struct],
            self.THRM_STATUS_BYTE.to_bytes(1),
        )
        for k, v in thrm_status_param.items():
            setattr(self.THRM_STATUS, str(k), v)

    def check_errors(self):
        """Check the error byte and log any errors that are asserted"""
        if self.ERROR_BYTE != 0x00:
            info_log.error(f"HK Error asserted: {self.ERROR_BYTE}")
            if self.ERRORS.IPI:
                info_log.error("OB ERROR IPI - Invalid Parameter Input")
            if self.ERRORS.IOS:
                info_log.error("OB ERROR IOS - Invalid OB State")
            if self.ERRORS.ICR:
                info_log.error("OB ERROR ICR - Invalid CMD CRC")
            if self.ERRORS.UNUSED1:
                info_log.error("OB ERROR UNUSED1 - Should always be 0!!!")
            if self.ERRORS.MOR:
                info_log.error("OB ERROR MOR - Error in Motor Error Byte")
            if self.ERRORS.UNUSED2:
                info_log.error("OB ERROR UNUSED2 - Should always be 0!!!")
            if self.ERRORS.TMO:
                info_log.error("OB ERROR TMO - Time Out")
            if self.ERRORS.IPA:
                info_log.error("OB ERROR IPA - Invalid Parity Error")

    def csv_header(self, param_list=None, separator=","):
        """Return a CSV header line with the field names for this object"""
        if param_list is None or len(param_list) == 0:
            param_list = self.params
        return separator.join(param_list)

    def csv(self, param_list=None, separator=","):
        """Return a CSV line with the data values for this object"""
        if param_list is None or len(param_list) == 0:
            param_list = self.params
        return separator.join(str(getattr(self, p)) for p in param_list)


class HK(TM):
    """HK Class Definition. Reads the HK response and parses it based on the dictionary defined in tmstruct.py"""

    def __init__(self, response: Response):
        super().__init__(response)

        if const.HK_LOG_FH is not None:
            const.HK_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            const.HK_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        info_log.info(f"HK received: {bytes.hex(self.raw_bytes, ' ', 2)}")
        self.TIME = datetime.now()

        # Allocate variables based on tm struct
        self.decode_bytes(tmstruct.hk)
        self.decode_error_byte()
        self.decode_mtr_error_byte()
        self.decode_thrm_status_byte()

        # Motor Flags
        self.MTR_FLAGS = namedtuple("MTR_FLAGS", "".join(i[0] for i in tmstruct.mtr_flag_struct))
        mtr_flags_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_flag_struct),
            [i[0] for i in tmstruct.mtr_flag_struct],
            self.MTR_FLAGS_BYTE.to_bytes(1),
        )
        for k, v in mtr_flags_param.items():
            setattr(self.MTR_FLAGS, str(k), v)

        # Motor ERROR Masks
        self.MTR_ERR_MSK = namedtuple("MTR_ERR_MSK", "".join(i[0] for i in tmstruct.mtr_err_msk_struct))
        mtr_err_msk_param = bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_err_msk_struct),
            [i[0] for i in tmstruct.mtr_err_msk_struct],
            self.MTR_ERR_MSK_BYTE.to_bytes(1),
        )
        for k, v in mtr_err_msk_param.items():
            setattr(self.MTR_ERR_MSK, str(k), v)

        info_log.info(f"CMD Count: {self.CMD_CNT=}")

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
        """Check the length of the HK message"""
        # TODO: May want to adjust to calculate length based on structure like ACK
        if len(self.raw_bytes) != 66:
            info_log.error(f"HK Len not 66 bytes as expected. Got: {len(self.raw_bytes)}")

    def check_unused(self):
        """Check the unused bytes in the HK message. These should always be 0."""
        if self.UNUSED1 != 0x00:
            info_log.warning(f"HK Unused1 is not zero actually: {hex(self.UNUSED1)}")


class ACK(TM):
    """ACK Class Definition. Reads the ACK response and parses it based on the dictionary defined in tmstruct.py"""

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
        """Check the length of the ACK message"""
        expect_strct = tmstruct.ack_struct
        expect_len = bitstruct.calcsize("".join([i[1] for i in expect_strct])) / 8
        if len(self.raw_bytes) != expect_len:
            info_log.error(f"ACK Len not {expect_len} bytes as expected. Got: {len(self.raw_bytes)}")


class SCI(TM):
    """SCI Class Definition. Reads the SCI response and parses it based on the dictionary defined in tmstruct.py"""

    def __init__(self, response: Response):
        super().__init__(response)

        if const.SCI_LOG_FH is not None:
            const.SCI_LOG_FH.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            const.SCI_LOG_FH.write(f" - {bytes.hex(self.raw_bytes, ' ', 2)}\n")
        info_log.info(f"SCI received: {bytes.hex(self.raw_bytes, ' ', 2)}")
        self.TIME = datetime.now()

        # Allocate variables based on tm struct
        self.decode_bytes(tmstruct.sci)
        self.decode_error_byte()

        self.check_len()
        self.check_errors()

    def check_len(self):
        """Check the length of the SCI message"""
        if len(self.raw_bytes) != 29:
            info_log.error(f"SCI Len not 29 bytes as expected. Got: {len(self.raw_bytes)}")


class NACK(TM):
    """NACK Class Definition. Reads the NACK response and parses it based on the dictionary defined in tmstruct.py"""

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
        """Check the length of the NACK message"""
        # TODO: May want to adjust to calculate length based on structure like ACK
        if len(self.raw_bytes) != 9:
            info_log.error(f"NACK Len not 9 bytes as expected. Got: {len(self.raw_bytes)}")


def get_response(port: serial.rs485.RS485, no_of_bytes: int = 1000) -> bytes:
    """Read the raw bytes from the serial port and return them"""
    raw_bytes = port.read(no_of_bytes)
    info_log.info(f"Response: {bytes.hex(raw_bytes, ' ', 2)}")
    return raw_bytes


def parse_tm(response):
    """Parse the raw bytes from the TM response and return the appropriate object based on the CMD ID"""
    info_log.debug(f"Response type: {response.cmd_type}")

    if response.cmd_type == "HK_Request":
        ack = HK(response)
        const.hk_queue.put(ack)
    elif response.cmd_type == "SCI_Request":
        ack = SCI(response)
        const.sci_queue.put(ack)
        info_log.warning(
            f"SCI Received: SWIR_HIGH:{ack.SWIR_HIGH >> 4}, SWIR_MED:{ack.SWIR_MED >> 4}, SWIR_LOW:{ack.SWIR_LOW >> 4}, MWIR_HIGH:{ack.MWIR_HIGH >> 4}, MWIR_MED:{ack.MWIR_MED >> 4}, MWIR_LOW:{ack.MWIR_LOW >> 4}, HT_SINK_TEMP:{ack.HT_SINK_TEMP >> 4}, SWIR_TEMP:{ack.SWIR_TEMP >> 4}"
        )
    elif response.cmd_type == "NACK":
        ack = NACK(response)
    else:
        match response.cmd_type:
            case "Clear_Errors":
                ack = ACK(response)
            case "Set_Errors":
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
            case "Set_HK_Samples":
                ack = ACK(response)
            case "SCI_Offset":
                ack = ACK(response)
            case _:
                info_log.warning(f"Response type not defined in parse_tm: {response.cmd_type}")
                ack = "EMPTY"
    return ack
