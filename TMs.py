#----Module Imports---------------------------------------------------------------------------------
import logging

from bitstruct import unpack_from as upf
import bitstruct
import crc8

import tmstruct
from CMD_IDs import CMD_IDs
from constants import EXP_MODEL_ID

tm_log = logging.getLogger("tm_log")

class Raw:
    def __init__(self, raw_bytes):
        self.raw_bytes = raw_bytes
        self.get_cmd_mod_id(self.raw_bytes)
        self.verify_cmd_id()
        self.verify_model_id()
        self.verify_crc()

    def get_cmd_mod_id(self, bytes):
        self.cmd_id = upf('u5', bytes, offset=0)[0]
        self.mod_id = upf('u3', bytes, offset=5)[0]

    def verify_cmd_id(self):
        if self.cmd_id in CMD_IDs:
            self.cmd_type = CMD_IDs.get(self.cmd_id)
        else:
            tm_log.error(f"CMD ID Not Found. Got:{self.cmd_id}")

    def verify_model_id(self):
        if self.mod_id != EXP_MODEL_ID:
            tm_log.error(f"Model ID not as expected. Expected:{EXP_MODEL_ID}, Got: {self.mod_id}")

    def verify_crc(self):
        self.hash = crc8.crc8()
        if self.hash.update(self.raw_bytes).hexdigest() != '00':
            tm_log.error(f'Incorrect CRC8. Calculated: 0x{self.hash.hexdigest()}. '
                         f'For Packet {bytes.hex(self.raw_bytes, ' ', 2)}'
                        )

class HK(Raw):
    def __init__(self, raw_bytes):
        self.raw_bytes = raw_bytes
        #print(bytes.hex(self.raw_bytes, ' ', 2))
        self.get_cmd_mod_id(self.raw_bytes)

        self.param = bitstruct.unpack_dict(
            ''.join(i[1] for i in tmstruct.hk), 
            [i[0] for i in tmstruct.hk],
            raw_bytes
            )

        for k, v in self.param.items():
            setattr(self, k, v)

        #tm_log.info(f"{self.CMD_CNT=}")

        # self.cmd_cnt = upf('u8', self.raw_bytes, offset=(0+1*8))[0]

        # self.error = upf('u8', self.raw_bytes, offset=(0+2*8))[0]
        # self.unused1 = upf('u48', self.raw_bytes, offset=(0+3*8))[0]

        # self.error_mtr = upf('u8', self.raw_bytes, offset=(0+9*8))[0]
        
        # self.mtr_abs_steps = upf('u16', self.raw_bytes, offset=(0+10*8))[0]
        # self.mtr_rel_steps = upf('u16', self.raw_bytes, offset=(0+12*8))[0]
        # self.mtr_flags = upf('u8', self.raw_bytes, offset=(0+14*8))[0]
        # self.mtr_guard = upf('u16', self.raw_bytes, offset=(0+15*8))[0]
        # self.mtr_pwm_duty = upf('u16', self.raw_bytes, offset=(0+17*8))[0]
        
        # self.mtr_current = upf('u16', self.raw_bytes, offset=(0+23*8))[0]

        self.check_errors()
        self.check_unused()
        
        #! TODO Ret of HK
        #! TODO add verify commands

    def check_errors(self):
        if self.ERROR != 0x00:
            tm_log.error(f"HK Error asserted: {self.ERROR}")
            #! TODO Decode bit struct here
    
    def check_unused(self):
        if self.UNUSED1 == 0x00:
            tm_log.warning(f"HK Unused1 is not zero actually: {hex(self.UNUSED1)}")