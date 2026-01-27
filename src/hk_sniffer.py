from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import filedialog
from altair import param
import bitstruct
import sys
import logging
import constants as const
import tm
import tmstruct
import scripts.analysis as ana
import time


import tmstruct
info_log = logging.getLogger("info_log")

def read_pkt(file_path):    
    with open(file_path, 'r') as f:
        all_lines = [line.strip() for line in f]
        tm_indices = [i for (i, line) in enumerate(all_lines) if line.startswith("Telemetry Data:")]
        raw_bytes = None
        tm_index = -1
        packet_ids_found = set()
        for tm_index in tm_indices:
            # Check if there's a next line available
            if tm_index + 1 >= len(all_lines):
                continue
            byte_string = all_lines[tm_index + 1]
            byte_array = bytes([int(x, 16) for x in byte_string.split()])
            tm_type_id = (byte_array[5] >> 2) & 0x3F  # TM Type ID - bits 7-2 of byte 5
            packet_ids_found.add(tm_type_id)
            if tm_type_id in (0x1, 0x3):  # HK packet IDs
                raw_bytes = byte_array
        
                
    
    return raw_bytes, tm_index


def parse_eb_hk(packet_data):
    parsed = decode_bytes(packet_data)
    parsed = decode_errors(parsed)
    parsed = decode_mtr_error_byte(parsed)
    parsed = decode_thrm_status_byte(parsed)
    parsed = decode_mtr_flags_byte(parsed)
    parsed = decode_instrument_status_flags(parsed)
    return parsed

def decode_eb_bytes(raw_bytes, struct = tmstruct.eb_hk):
        param_dict = bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            raw_bytes,
        )
        # Convert dict to SimpleNamespace to allow dot notation access
        param = SimpleNamespace(**param_dict)
        return param

def decode_bytes(raw_bytes, struct = tmstruct.eb_hk):
        param_dict = bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            raw_bytes,
        )
        # Convert dict to SimpleNamespace to allow dot notation access
        param = SimpleNamespace(**param_dict)
        return param

def decode_errors(param):
    error_dict = bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.error_struct),
        [i[0] for i in tmstruct.error_struct],
        bytes([param.OB_LAST_ERROR]),
    )
    # Convert error dict to SimpleNamespace and assign to param
    param.ERRORS = SimpleNamespace(**error_dict)
    return param

def decode_mtr_error_byte(param):
        mtr_error_dict = bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.mtr_error_struct),
        [i[0] for i in tmstruct.mtr_error_struct],
        bytes([param.OB_MOTOR_ERROR]),
    )
        param.MTR_ERRORS = SimpleNamespace(**mtr_error_dict)
        return param

def decode_thrm_status_byte(param):
    ## Decode bit maps
    # Thermal Status
    thrm_status_dict = bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.thrm_status_struct),
        [i[0] for i in tmstruct.thrm_status_struct],
        bytes([param.OB_THERMAL_STATUS]),
    )
    param.THRM_STATUS = SimpleNamespace(**thrm_status_dict)
    return param

def decode_mtr_flags_byte(param):
    ## Decode bit maps
    # Thermal Status
    mtr_flag_dict = bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.mtr_flag_struct),
        [i[0] for i in tmstruct.mtr_flag_struct],
        bytes([param.OB_MOTOR_STATUS_FLAGS]),
    )
    param.MTR_FLAGS = SimpleNamespace(**mtr_flag_dict)
    return param

def decode_instrument_status_flags(param):
    instr_status_dict = bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.eb_instrument_status_flags),
        [i[0] for i in tmstruct.eb_instrument_status_flags],
        (param.INSTRUMENT_STATUS_FLAGS.to_bytes(2, 'big')),
    )
    param.INSTR_STATUS_FLAGS = SimpleNamespace(**instr_status_dict)
    return param
def hk_checker(pkt):
    print(
        f" PACKET_ID: {pkt.PACKET_ID}"
        + f"\n TCS_ACCEPTED: {pkt.TCS_ACCEPTED}"
        + f"\n TCS_REJECTED: {pkt.TCS_REJECTED}"
        + f"\n INSTRUMENT_STATUS_FLAGS: {pkt.INSTRUMENT_STATUS_FLAGS}"
        + f"\n ONGOING_PROCESS_FLAGS: {pkt.ONGOING_PROCESS_FLAGS}"
        + f"\n ERROR_FLAGS: {pkt.ERROR_FLAGS}"
        + f"\n WARNING_FLAGS: {pkt.WARNING_FLAGS}"
        + f"\n CURRENT_OPERATING_STATE: {pkt.CURRENT_OPERATING_STATE}"
        + f"\n FDIR_ALARM_FLAGS: {pkt.FDIR_ALARM_FLAGS}"
        + f"\n FDIR_WARNING_FLAGS: {pkt.FDIR_WARNING_FLAGS}"
        + f"\n LAST_RECEIVED_RET_S: {pkt.LAST_RECEIVED_RET_S}"
        + f"\n LAST_RECEIVED_RET_MS: {pkt.LAST_RECEIVED_RET_MS}"
        + f"\n TCS_RECEIVED: {pkt.TCS_RECEIVED}"
        + f"\n LAST_TC_TYPE: {pkt.LAST_TC_TYPE}"
        + f"\n LAST_OB_TC_TYPE: {pkt.LAST_OB_TC_TYPE}"
        + f"\n LAST_OB_TC_ERROR: {pkt.LAST_OB_TC_ERROR}"
        + f"\n SOFTWARE_MAJOR_VERSION: {pkt.SOFTWARE_MAJOR_VERSION}"
        + f"\n SOFTWARE_MINOR_VERSION: {pkt.SOFTWARE_MINOR_VERSION}"
        + f"\n SOFTWARE_PATCH_VERSION: {pkt.SOFTWARE_PATCH_VERSION}"
        + f"\n HK_PACKETS_SENT: {pkt.HK_PACKETS_SENT}"
        + f"\n CURRENT_HK_TIME_INTERVAL: {pkt.CURRENT_HK_TIME_INTERVAL}"
        + f"\n SCIENCE_PACKETS_SENT: {pkt.SCIENCE_PACKETS_SENT}"
        + f"\n TEC_SETPOINT: {pkt.TEC_SETPOINT}"
        + f"\n EB_MEAS_MAIN_12V: {pkt.EB_MEAS_MAIN_12V}"
        + f"\n EB_MEAS_MAIN_NEG12V: {pkt.EB_MEAS_MAIN_NEG12V}"
        + f"\n EB_MEAS_5V: {pkt.EB_MEAS_5V}"
        + f"\n EB_MEAS_3V3: {pkt.EB_MEAS_3V3}"
        + f"\n EB_MEAS_TEC_RAIL: {pkt.EB_MEAS_TEC_RAIL}"
        + f"\n EB_MCU_INTERNAL_TEMP: {pkt.EB_MCU_INTERNAL_TEMP}"
        + f"\n EB_PELTIER_TEMP: {pkt.EB_PELTIER_TEMP}"
        + f"\n EB_INTERNAL_TRP_TEMP: {pkt.EB_INTERNAL_TRP_TEMP}"
        + f"\n EB_TEC_DRIVE_CURRENT: {pkt.EB_TEC_DRIVE_CURRENT}"
        + f"\n OB_HK_ID: {pkt.OB_HK_ID}"
        + f"\n OB_COMMAND_COUNT: {pkt.OB_COMMAND_COUNT}"
        + f"\n OB_LAST_ERROR: {pkt.OB_LAST_ERROR}"
        + f"\n OB_POWER_STATUS: {pkt.OB_POWER_STATUS}"
        + f"\n OB_MOTOR_ERROR: {pkt.OB_MOTOR_ERROR}"
        + f"\n OB_MOTOR_ABS_STEPS: {pkt.OB_MOTOR_ABS_STEPS}"
        + f"\n OB_MOTOR_REL_STEPS: {pkt.OB_MOTOR_REL_STEPS}"
        + f"\n OB_MOTOR_STATUS_FLAGS: {pkt.OB_MOTOR_STATUS_FLAGS}"
        + f"\n OB_MOTOR_PWM_DUTY: {pkt.OB_MOTOR_PWM_DUTY}"
        + f"\n OB_MOTOR_CURRENT: {pkt.OB_MOTOR_CURRENT}"
        + f"\n OB_SPEED: {pkt.OB_SPEED}"
        + f"\n OB_MOTOR_ERROR_MASK: {pkt.OB_MOTOR_ERROR_MASK}"
        + f"\n OB_THERMAL_STATUS: {pkt.OB_THERMAL_STATUS}"
        + f"\n OB_THERMAL_MECH_MAX: {pkt.OB_THERMAL_MECH_MAX}"
        + f"\n OB_THERMAL_MECH_MIN: {pkt.OB_THERMAL_MECH_MIN}"
        + f"\n OB_THERMAL_DET_MAX: {pkt.OB_THERMAL_DET_MAX}"
        + f"\n OB_THERMAL_DET_MIN: {pkt.OB_THERMAL_DET_MIN}"
        + f"\n OB_3V3_VOLTAGE: {pkt.OB_3V3_VOLTAGE}"
        + f"\n OB_1V5_VOLTAGE: {pkt.OB_1V5_VOLTAGE}"
        + f"\n OB_DIGITAL_TRP: {pkt.OB_DIGITAL_TRP}"
        + f"\n OB_DETECTOR_TRP: {pkt.OB_DETECTOR_TRP}"
        + f"\n OB_MECHANISM_TRP: {pkt.OB_MECHANISM_TRP}"
        + f"\n OB_MOTOR_TRP: {pkt.OB_MOTOR_TRP}"
        + f"\n OB_MECH_CURRENT: {pkt.OB_MECH_CURRENT}"
        + f"\n HK_PACKET_CRC: {pkt.HK_PACKET_CRC}"
        + f"\n PADDING: {pkt.PADDING}"
    )
    
    # Print decoded error flags
    print(
        "\n--- ERRORS ---"
        + f"\n IPI: {pkt.ERRORS.IPI}"
        + f"\n IOS: {pkt.ERRORS.IOS}"
        + f"\n ICR: {pkt.ERRORS.ICR}"
        + f"\n MOR: {pkt.ERRORS.MOR}"
        + f"\n TMO: {pkt.ERRORS.TMO}"
        + f"\n IPA: {pkt.ERRORS.IPA}"
    )
    
    # Print decoded motor errors
    print(
        "\n--- MOTOR ERRORS ---"
        + f"\n CD: {pkt.MTR_ERRORS.CD}"
        + f"\n AB: {pkt.MTR_ERRORS.AB}"
        + f"\n ABS: {pkt.MTR_ERRORS.ABS}"
        + f"\n DSE: {pkt.MTR_ERRORS.DSE}"
    )
    
    # Print decoded motor flags
    print(
        "\n--- MOTOR FLAGS ---"
        + f"\n HOMING: {pkt.MTR_FLAGS.HOMING}"
        + f"\n MOVING: {pkt.MTR_FLAGS.MOVING}"
        + f"\n BASE: {pkt.MTR_FLAGS.BASE}"
        + f"\n OUTER: {pkt.MTR_FLAGS.OUTER}"
        + f"\n DIR: {pkt.MTR_FLAGS.DIR}"
        + f"\n CAL: {pkt.MTR_FLAGS.CAL}"
    )
    
    # Print decoded thermal status
    print(
        "\n--- THERMAL STATUS ---"
        + f"\n MA: {pkt.THRM_STATUS.MA}"
        + f"\n MM: {pkt.THRM_STATUS.MM}"
        + f"\n DA: {pkt.THRM_STATUS.DA}"
        + f"\n DM: {pkt.THRM_STATUS.DM}"
        + f"\n S: {pkt.THRM_STATUS.S}"
        + f"\n HMS: {pkt.THRM_STATUS.HMS}"
        + f"\n HDS: {pkt.THRM_STATUS.HDS}"
    )
    
    # Print power status
    print(
        "\n--- POWER STATUS ---"
        + f"\n OB_POWER_STATUS: {pkt.OB_POWER_STATUS}"
        + f"\n Power State: {pkt.OB_POWER_STATUS & 0x03}"
    )


if __name__ == '__main__':
    file_path = "C:\\wdir\\IFM\\EB\\EGSE\\RS422if_log\\RS422if_2026-01-22_10-09-12.log"
    raw_bytes, tm_index = read_pkt(file_path)