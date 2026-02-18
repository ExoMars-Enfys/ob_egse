
from types import SimpleNamespace
from typing import Any, cast
import bitstruct
import logging
import math
import tmstruct
from datetime import datetime
import constants as const
info_log = logging.getLogger("info_log")

def read_pkt(file_path, latest_only: bool = False):    
    with open(file_path, "r", encoding="utf-8") as handle:
        all_lines = [line.strip() for line in handle]

    tm_indices = [i for (i, line) in enumerate(all_lines) if line.startswith("Telemetry Data:")]
    last_hk = None
    last_post_hk = None
    last_index = None

    indices = [tm_indices[-1]] if (latest_only and tm_indices) else tm_indices
    for tm_index in reversed(indices) if latest_only else indices:
        if tm_index + 1 >= len(all_lines):
            continue
        byte_string = all_lines[tm_index + 1]
        if not byte_string:
            continue
        byte_array = bytes(int(x, 16) for x in byte_string.split())
        tm_type_id = (byte_array[5] >> 2) & 0x3F
        if tm_type_id in (0x1, 0x2):
            hk = parse_eb_hk(byte_array)
            hk = decode_warning_flags(hk)
            hk = decode_error_flags(hk)
            hk = decode_fdir_alarms(hk)
            hk = decode_fdir_warnings(hk)
            hk.TIME = datetime.now()
            const.hk_queue.put(hk)
            last_hk = hk
            last_index = tm_index
        elif tm_type_id == 0x3:
            post_hk = decode_post_hk(byte_array)
            post_hk.TIME = datetime.now()
            const.eb_post_queue.put(post_hk)
            last_post_hk = post_hk
        else:
            continue

        if latest_only:
            break

    return last_hk, last_post_hk, last_index


def parse_eb_hk(packet_data):
    parsed = decode_bytes(packet_data)
    parsed = decode_errors(parsed)
    parsed = decode_mtr_error_byte(parsed)
    parsed = decode_thrm_status_byte(parsed)
    parsed = decode_mtr_flags_byte(parsed)
    parsed = decode_instrument_status_flags(parsed)
    return parsed

def decode_bytes(raw_bytes, struct = tmstruct.eb_hk):
        param_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            raw_bytes,
        ))
        # Convert dict to SimpleNamespace to allow dot notation access
        param = SimpleNamespace(**param_dict)
        return param

def decode_errors(param):
    error_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.error_struct),
        [i[0] for i in tmstruct.error_struct],
        bytes([param.OB_LAST_ERROR]),
    ))
    # Convert error dict to SimpleNamespace and assign to param
    param.ERRORS = SimpleNamespace(**error_dict)
    return param

def decode_mtr_error_byte(param):
        mtr_error_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.mtr_error_struct),
        [i[0] for i in tmstruct.mtr_error_struct],
        bytes([param.OB_MOTOR_ERROR]),
    ))
        param.MTR_ERRORS = SimpleNamespace(**mtr_error_dict)
        return param

def decode_thrm_status_byte(param):
    ## Decode bit maps
    # Thermal Status
    thrm_status_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.thrm_status_struct),
        [i[0] for i in tmstruct.thrm_status_struct],
        bytes([param.OB_THERMAL_STATUS]),
    ))
    param.THRM_STATUS = SimpleNamespace(**thrm_status_dict)
    return param

def decode_mtr_flags_byte(param):
    ## Decode bit maps
    # Thermal Status
    mtr_flag_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.mtr_flag_struct),
        [i[0] for i in tmstruct.mtr_flag_struct],
        bytes([param.OB_MOTOR_STATUS_FLAGS]),
    ))
    param.MTR_FLAGS = SimpleNamespace(**mtr_flag_dict)
    return param

def decode_instrument_status_flags(param):
    instr_status_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.eb_instrument_status_flags),
        [i[0] for i in tmstruct.eb_instrument_status_flags],
        (param.INSTRUMENT_STATUS_FLAGS.to_bytes(2, 'big')),
    ))
    param.INSTR_STATUS_FLAGS = SimpleNamespace(**instr_status_dict)
    return param

def decode_warning_flags(param):
    warning_flags_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.eb_warning_flags),
        [i[0] for i in tmstruct.eb_warning_flags],
        (param.WARNING_FLAGS.to_bytes(2, 'big')),
    ))
    param.WARNING_FLAGS_BITS = SimpleNamespace(**warning_flags_dict)
    return param

def decode_error_flags(param):
    error_flags_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.eb_warning_flags),
        [i[0] for i in tmstruct.eb_warning_flags],
        (param.ERROR_FLAGS.to_bytes(2, 'big')),
    ))
    param.ERROR_FLAGS_BITS = SimpleNamespace(**error_flags_dict)
    return param

def decode_fdir_warnings(param):
    fdir_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.eb_fdir_flags),
        [i[0] for i in tmstruct.eb_fdir_flags],
        (param.FDIR_WARNING_FLAGS.to_bytes(4, 'big')),
    ))
    param.FDIR_WARNING_FLAGS_BITS = SimpleNamespace(**fdir_dict)
    return param

def decode_fdir_alarms(param):
    fdir_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.eb_fdir_flags),
        [i[0] for i in tmstruct.eb_fdir_flags],
        (param.FDIR_ALARM_FLAGS.to_bytes(4, 'big')),
    ))
    param.FDIR_ALARM_FLAGS_BITS = SimpleNamespace(**fdir_dict)
    return param

def decode_post_hk(packet_data, struct = tmstruct.post_hk):
    param_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            packet_data,
        ))
        # Convert dict to SimpleNamespace to allow dot notation access
    param = SimpleNamespace(**param_dict)
    return param

def decode_ob_trps(adu):
    res = (adu / (4095 - adu))*1000
    temp = (0.2559552953839863*res) - 255.7247996594076
    return temp

def thermistor_adu_to_temp(adu: int) -> float:
    """Convert ADU reading to temperature in Celsius using B parameter equation.
    
    Args:
        adu: Digital ADU value from thermistor reading
        
    Returns:
        Temperature in degrees Celsius
    """
    # Constants
    T0 = 298  # K
    R0 = 5000  # Ω
    B = 3891
    
    # Calculate resistance: R = 1000 * (2^16 / (2^16 - ADU) - 1)
    if adu >= 2**16 or adu < 0:
        return float('nan')  # Avoid division by zero or invalid values
    
    R = 1000 * ((2**16 / (2**16 - adu)) - 1)
    
    # Check for invalid resistance values
    if R <= 0:
        return float('nan')
    
    # B parameter equation: T = 1 / (1/T0 + (1/B) * ln(R/R0))
    T_kelvin = 1 / ((1 / T0) + (1 / B) * math.log(R / R0))
    
    # Convert to Celsius
    T_celsius = T_kelvin - 273.15
    
    return T_celsius

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
    file_path = "C:\\wdir\\IFM\\EB\\RS422if_log\\RS422if_2026-01-22_10-09-12.log"
    last_hk, last_post_hk, tm_index = read_pkt(file_path, latest_only=True)