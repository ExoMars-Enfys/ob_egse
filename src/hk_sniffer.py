from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import bitstruct
import sys
import logging
import constants as const
import tm
import tmstruct

test_line = "0x37 0x7 0x0 0x0 0x2 0x6f 0xa4 0x80 0x0 0xd2 0x0 0x0 0x0 0x1 0x0 0x2 0x0 0x0 0x0 0x0 0x2 0x0 0x0 0x0 0x0"
sys.path.append(str(Path(__file__).parent.parent))
import tmstruct
info_log = logging.getLogger("info_log")

def read_pkt(file_path):
    with open(file_path, 'r') as f:
        all_lines = [line.strip() for line in f]
        tm_indices = [i for (i, line) in enumerate(all_lines) if line.startswith("Telemetry Data:")]
        for tm_index in tm_indices:
            byte_string = all_lines[tm_index + 1]
            byte_array = bytes([int(x, 16) for x in byte_string.split()])
            if byte_array[5] == 0x7:
                parsed = parse_eb_hk(byte_array)
                hk_checker(parsed)
    
    return parsed
    
def parse_eb_hk(packet_data):
    parsed = decode_bytes(raw_bytes = packet_data[136:202])
    return parsed

def decode_bytes(raw_bytes, struct = tmstruct.hk):
        param = bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            raw_bytes,
        )
        return param

def hk_checker(pkt):
    info_log.info(
        f" MOD_ID :{pkt['MOD_ID']}"
        + f"\n Unused1 : {pkt['UNUSED1']}"
        + f"\n CMD_ID :{pkt['CMD_ID']}"
        + f"\n CMD_CNT : {pkt['CMD_CNT']}"
        + f"\n ERROR_BYTE : {pkt['ERROR_BYTE']}"
        + f"\n UNUSED2 :{pkt['UNUSED2']}"
        + f"\n ERROR_MTR :{pkt['ERROR_MTR']}"
        + f"\n MTR_ERR_MSK : {pkt['MTR_ERR_MSK_BYTE']}"
        + f"\n MTR_FLAGS_BYTE :{pkt['MTR_FLAGS_BYTE']}"
        + f"\n MTR_ABS_STEPS : {pkt['MTR_ABS_STEPS']}"
        + f"\n MTR_REL_STEPS : {pkt['MTR_REL_STEPS']}"
        + f"\n UNUSED3 :{pkt['UNUSED3']}"
        + f"\n MTR_CURRENT :{pkt['MTR_CURRENT']}"        
        + f"\n UNUSED4 :{pkt['UNUSED4']}"
        + f"\n MTR_GUARD_SELECT : {pkt['MTR_GUARD_SELECT']}"
        + f"\n MTR_CHOP : {pkt['MTR_CHOP']}"
        + f"\n UNUSED5 : {pkt['UNUSED5']}"
        + f"\n MTR_SPEED :{pkt['MTR_SPEED']}"
        + f"\n UNUSED6 : {pkt['UNUSED6']}"
        + f"\n PWR_STAT : {pkt['PWR_STAT']}"
        + f"\n THRM_STATUS_BYTE :{pkt['THRM_STATUS_BYTE']}"
        + f"\n THRM_MECH_OFF_SP : {pkt['THRM_MECH_OFF_SP']}"
        + f"\n THRM_MECH_ON_SP : {pkt['THRM_MECH_ON_SP']}"
        + f"\n THRM_DET_OFF_SP :{pkt['THRM_DET_OFF_SP']}"
        + f"\n THRM_DET_ON_SP : {pkt['THRM_DET_ON_SP']}"
        + f"\n SWIR_OFFSET : {pkt['SWIR_OFFSET']}"
        + f"\n MWIR_OFFSET : {pkt['MWIR_OFFSET']}"
        + f"\n HK_V_3V3 : {pkt['HK_V_3V3']}"
        + f"\n HK_V_1V5 :{pkt['HK_V_1V5']}"
        + f"\n DIGITAL_TRP : {pkt['DIGITAL_TRP']}"
        + f"\n DETEC_TRP :{pkt['DETEC_TRP']}"
        + f"\n MECH_TRP : {pkt['MECH_TRP']}"
        + f"\n MOTOR_TRP : {pkt['MOTOR_TRP']}"
        + f"\n HK_MECH_CUR :{pkt['HK_MECH_CUR']}"
        + f"\n UNUSED_ADC : {pkt['UNUSED_ADC']}"
        + f"\n HK_SAMPLES : {pkt['HK_SAMPLES']}"
        + f"\n UNUSED7 :{pkt['UNUSED7']}"
        + f"\n CRC8 : {pkt['CRC8']}"
    )