# Std library
import bitstruct
import logging
import math
# Added packages
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

# Local modules
#core
from core_modules import config as config
from core_modules import constants as const
from core_modules import tmstruct as tmstruct 
#utilities
from utility_modules import comms as comms
from utility_modules import tc as tc
from utility_modules import tm as tm
info_log = logging.getLogger("info_log")

#Packet Intake
def read_pkt(file_path, latest_only: bool = False):
    """Reads packet from EB RS422_if.log files."""
    with open(file_path, "r", encoding="utf-8") as handle:
        all_lines = [line.strip() for line in handle]

    # Find all telemetry data lines and their indices
    tm_indices = [i for (i, line) in enumerate(all_lines) if line.startswith("Telemetry Data:")]
    last_hk = None
    last_post_hk = None
    last_dump = None
    last_cscience_data = None
    last_ncscience_data = None
    last_index = None

    if latest_only:
        hk_found = False
        post_found = False
        dump_found = False
        csc_found = False
        ncsc_found = False
        indices = reversed(tm_indices)
    else:
        indices = tm_indices

    #Iterate through TM Indices and process packets based on TM_TYPE_ID
    for tm_index in indices:
        if tm_index + 1 >= len(all_lines):
            continue
        byte_string = all_lines[tm_index + 1]
        if not byte_string:
            continue
        byte_array = bytes(int(x, 16) for x in byte_string.split())
        tm_type_id = (byte_array[5] >> 2) & 0x3F

        #Proccess HK packets (Regular and Response packets)
        if tm_type_id in (0x1, 0x2):
            if latest_only and hk_found:
                continue
            hk = parse_eb_hk(byte_array)
            hk.TIME = datetime.now()
            const.hk_queue.put(hk)
            last_hk = hk
            last_index = tm_index
            if latest_only:
                hk_found = True

        #Proccess POST HK packets
        elif tm_type_id == 0x3:
            if latest_only and post_found:
                continue
            post_hk = decode_post_hk(byte_array)
            post_hk.TIME = datetime.now()
            const.eb_post_queue.put(post_hk)
            last_post_hk = post_hk
            if latest_only:
                post_found = True

        #Proccess Dump packets
        elif tm_type_id == 0x4:
            if latest_only and dump_found:
                continue
            dump_data = decode_dump_data(byte_array)
            dump_data = merge_sci_data_packet(dump_data)
            dump_data.TIME = datetime.now()
            last_dump = dump_data
            if latest_only:
                dump_found = True

        #Proccess Science packets (Critical)
        elif tm_type_id == 0x5:
            if latest_only and csc_found:
                continue
            cscience_data = decode_cscience_data(byte_array)
            cscience_data = merge_sci_data_packet(cscience_data)
            cscience_data.TM_TYPE_ID = tm_type_id
            cscience_data.SCI_PACKET_CRITICALITY = "Critical"
            cscience_data.TIME = datetime.now()
            const.sci_queue.put(cscience_data)
            last_cscience_data = cscience_data
            if latest_only:
                csc_found = True

        #Proccess Science packets (Non-Critical)
        elif tm_type_id == 0x6:
            if latest_only and ncsc_found:
                continue
            ncscience_data = decode_ncscience_data(byte_array)
            ncscience_data = merge_sci_data_packet(ncscience_data)
            ncscience_data.TM_TYPE_ID = tm_type_id
            ncscience_data.SCI_PACKET_CRITICALITY = "Non-Critical"
            ncscience_data.TIME = datetime.now()
            const.sci_queue.put(ncscience_data)
            last_ncscience_data = ncscience_data
            if latest_only:
                ncsc_found = True
        else:
            continue

        if latest_only and hk_found and post_found and dump_found and csc_found and ncsc_found:
            break

    return last_hk, last_post_hk, last_dump, last_cscience_data, last_ncscience_data, last_index

def read_block_length(packet_data: bytes) -> int | None:
    """Read the block length from bytes 12-13 of the packet data. Returns None if packet is too short."""
    if len(packet_data) < 14:
        return None
    return int.from_bytes(packet_data[12:14], "big")

def trim_sci_packet_by_block_length(packet_data: bytes) -> bytes:
    """Trims Science packet to header + block length if block length is present and packet is long enough. Otherwise returns original packet data."""
    block_length = read_block_length(packet_data)
    if block_length is None:
        return packet_data
    expected_len = 14 + block_length
    if expected_len <= len(packet_data):
        return packet_data[:expected_len]
    info_log.warning(
        "SCI packet shorter than block length. Got %d bytes, expected %d.",
        len(packet_data),
        expected_len,
    )
    return packet_data

#Housekeeping Handling and Parsing
#HK Regular and Response packets
def parse_eb_hk(packet_data):
    """Parse EB Housekeeping packet data and decode all relevant fields, using the defined dictionaries from TMStruct"""
    def decode_bytes(raw_bytes, struct = tmstruct.eb_hk):
        """Parses raw HK bytestring using the defined dictionary from TMStruct for eb_hk"""
        param_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            raw_bytes,
        ))
        # Convert dict to SimpleNamespace to allow dot notation access
        param = SimpleNamespace(**param_dict)
        return param
    
    def decode_errors(param):
        """Parses OB error bytestring using the defined dictionary from TMStruct for error_struct"""
        error_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.error_struct),
            [i[0] for i in tmstruct.error_struct],
            bytes([param.OB_LAST_ERROR]),
        ))
        # Convert error dict to SimpleNamespace and assign to param
        param.ERRORS = SimpleNamespace(**error_dict)
        return param
    
    def decode_mtr_error_byte(param):
        """Parses OB motor error bytestring using the defined dictionary from TMStruct for mtr_error_struct"""
        mtr_error_dict = cast(dict[str, Any], bitstruct.unpack_dict(
        "".join(i[1] for i in tmstruct.mtr_error_struct),
        [i[0] for i in tmstruct.mtr_error_struct],
        bytes([param.OB_MOTOR_ERROR]),
        ))
        param.MTR_ERRORS = SimpleNamespace(**mtr_error_dict)
        return param
    
    def decode_thrm_status_byte(param):
        """Parses OB thermal status bytestring using the defined dictionary from TMStruct for thrm_status_struct"""
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
        """Parses OB motor status flag bytestring using the defined dictionary from TMStruct for mtr_flag_struct"""
        ## Decode bit maps
        # Motor Status Flags
        mtr_flag_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.mtr_flag_struct),
            [i[0] for i in tmstruct.mtr_flag_struct],
            bytes([param.OB_MOTOR_STATUS_FLAGS]),
        ))
        param.MTR_FLAGS = SimpleNamespace(**mtr_flag_dict)
        return param

    def decode_instrument_status_flags(param):
        """Parses OB instrument status flag bytestring using the defined dictionary from TMStruct for eb_instrument_status_flags"""
        instr_status_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.eb_instrument_status_flags),
            [i[0] for i in tmstruct.eb_instrument_status_flags],
            (param.INSTRUMENT_STATUS_FLAGS.to_bytes(2, 'big')),
        ))
        param.INSTR_STATUS_FLAGS = SimpleNamespace(**instr_status_dict)
        return param
    
    def decode_ongoing_process_flags(param):
        """Parses OB ongoing process flag bytestring using the defined dictionary from TMStruct for eb_ongoing_process_flags"""
        raw_flags = int(getattr(param, "ONGOING_PROCESS_FLAGS", 0)) & 0xFFFF
        process_flags = {f"BIT_{bit}": (raw_flags >> bit) & 0x01 for bit in range(16)}
        process_flags["ANY"] = 1 if raw_flags != 0 else 0
        param.ONGOING_PROCESS_FLAGS_BITS = SimpleNamespace(**process_flags)
        return param

    def decode_warning_flags(param):
        """"Parses OB warning flag bytestring using the defined dictionary from TMStruct for eb_warning_flags"""
        warning_flags_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.eb_warning_flags),
            [i[0] for i in tmstruct.eb_warning_flags],
            (param.WARNING_FLAGS.to_bytes(2, 'big')),
        ))
        param.WARNING_FLAGS_BITS = SimpleNamespace(**warning_flags_dict)
        return param

    def decode_error_flags(param):
        """Parses OB error flag bytestring using the defined dictionary from TMStruct for eb_warning_flags"""
        error_flags_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.eb_warning_flags),
            [i[0] for i in tmstruct.eb_warning_flags],
            (param.ERROR_FLAGS.to_bytes(2, 'big')),
        ))
        param.ERROR_FLAGS_BITS = SimpleNamespace(**error_flags_dict)
        return param

    def decode_fdir_warnings(param):
        """Parses OB FDIR warning flag bytestring using the defined dictionary from TMStruct for eb_fdir_flags"""
        fdir_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.eb_fdir_flags),
            [i[0] for i in tmstruct.eb_fdir_flags],
            (param.FDIR_WARNING_FLAGS.to_bytes(4, 'big')),
        ))
        param.FDIR_WARNING_FLAGS_BITS = SimpleNamespace(**fdir_dict)
        return param
    
    def decode_fdir_alarms(param):
        """Parses OB FDIR alarm flag bytestring using the defined dictionary from TMStruct for eb_fdir_flags"""
        fdir_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.eb_fdir_flags),
            [i[0] for i in tmstruct.eb_fdir_flags],
            (param.FDIR_ALARM_FLAGS.to_bytes(4, 'big')),
        ))
        param.FDIR_ALARM_FLAGS_BITS = SimpleNamespace(**fdir_dict)
        return param

    parsed = decode_bytes(packet_data)
    parsed = decode_errors(parsed)
    parsed = decode_mtr_error_byte(parsed)
    parsed = decode_thrm_status_byte(parsed)
    parsed = decode_mtr_flags_byte(parsed)
    parsed = decode_instrument_status_flags(parsed)
    parsed = decode_ongoing_process_flags(parsed)
    parsed = decode_warning_flags(parsed)
    parsed = decode_error_flags(parsed)
    parsed = decode_fdir_warnings(parsed)
    parsed = decode_fdir_alarms(parsed)
    return parsed

#POST HK packets
def decode_post_hk(packet_data, struct = tmstruct.post_hk):
    param_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            packet_data,
        ))
        # Convert dict to SimpleNamespace to allow dot notation access
    param = SimpleNamespace(**param_dict)
    return param

#Dump Data SCI packets
def decode_dump_data(packet_data, struct = tmstruct.dump_data):
    """Decodes Dump Data SCI packet using the defined dictionary from TMStruct for dump_data"""
    param_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            packet_data,
        ))
        # Convert dict to SimpleNamespace to allow dot notation access
    param = SimpleNamespace(**param_dict)
    return param

#Science Data SCI packets (Critical and Non-Critical)
def decode_cscience_data(packet_data, struct = tmstruct.eb_sci_header):
    """Decodes Critical Science Data SCI packet using the defined dictionary from TMStruct for eb_sci_header, and trims packet to header + block length if block length is present."""
    packet_data = trim_sci_packet_by_block_length(packet_data)
    param_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            packet_data,
        ))
        # Convert dict to SimpleNamespace to allow dot notation access
    sci = SimpleNamespace(**param_dict)
    header_bits = bitstruct.calcsize("".join(i[1] for i in struct))
    header_bytes = header_bits // 8
    sci.SCI_DATA = packet_data[header_bytes:]
    return sci

def decode_ncscience_data(packet_data, struct = tmstruct.eb_sci_header):
    """Decodes Non-Critical Science Data SCI packet using the defined dictionary from TMStruct for eb_sci_header, and trims packet to header + block length if block length is present."""
    packet_data = trim_sci_packet_by_block_length(packet_data)
    param_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            packet_data,
        ))
        # Convert dict to SimpleNamespace to allow dot notation access
    sci = SimpleNamespace(**param_dict)
    header_bits = bitstruct.calcsize("".join(i[1] for i in struct))
    header_bytes = header_bits // 8
    sci.SCI_DATA = packet_data[header_bytes:]
    return sci

#SCI Data Point Handling
def decode_sci_data_points(param) -> list[SimpleNamespace]:
    """Decodes SCI data points from a decoded SCI packet, returning a list of SimpleNamespace objects."""
    sci_bits = bitstruct.calcsize("".join(i[1] for i in tmstruct.sci_data))
    sci_bytes_len = sci_bits // 8

    if hasattr(param, "SCI_DATA"):
        raw_data = param.SCI_DATA
    elif hasattr(param, "DUMP_DATA"):
        raw_data = param.DUMP_DATA
    else:
        info_log.warning("No SCI_DATA or DUMP_DATA field found for SCI decode.")
        return []

    if isinstance(raw_data, int):
        if raw_data < 0:
            return []
        byte_len = max(1, (raw_data.bit_length() + 7) // 8)
        sci_payload = raw_data.to_bytes(byte_len, "big", signed=False)
    else:
        sci_payload = bytes(raw_data)

    if len(sci_payload) < sci_bytes_len:
        info_log.warning(
            "SCI_DATA shorter than one point. Got %d bytes, expected at least %d.",
            len(sci_payload),
            sci_bytes_len,
        )
        return []

    point_count = len(sci_payload) // sci_bytes_len
    remainder = len(sci_payload) % sci_bytes_len
    if remainder:
        info_log.warning(
            "SCI_DATA has %d trailing bytes beyond %d-byte points; ignoring remainder.",
            remainder,
            sci_bytes_len,
        )

    points: list[SimpleNamespace] = []
    for point_index in range(point_count):
        start = point_index * sci_bytes_len
        end = start + sci_bytes_len
        point_bytes = sci_payload[start:end]
        sci_dict = cast(dict[str, Any], bitstruct.unpack_dict(
            "".join(i[1] for i in tmstruct.sci_data),
            [i[0] for i in tmstruct.sci_data],
            point_bytes,
        ))
        point = SimpleNamespace(**sci_dict)
        point.POINT_INDEX = point_index
        points.append(point)

    return points

def merge_sci_data_packet(param):
    """Decodes SCI data points from a decoded SCI packet, and merges decoded SCI data point fields with base packet fields."""
    sci_points = decode_sci_data_points(param)
    base_fields: dict[str, Any] = {}
    if hasattr(param, "__dict__"):
        base_fields = dict(param.__dict__)

    if not sci_points:
        if hasattr(param, "SCI_DATA"):
            raw_data = param.SCI_DATA
        elif hasattr(param, "DUMP_DATA"):
            raw_data = param.DUMP_DATA
        else:
            raw_data = b""
        sci = SimpleNamespace(**base_fields)
        sci.SCI_DATA = raw_data
        sci.SCI_POINT_COUNT = 0
        sci.SCI_POINTS = []
        return sci

    point_fields = dict(sci_points[0].__dict__)
    merged_fields = {**base_fields, **point_fields}
    sci = SimpleNamespace(**merged_fields)
    sci.SCI_POINTS = sci_points
    sci.SCI_POINT_COUNT = len(sci_points)
    if hasattr(param, "SCI_DATA"):
        sci.SCI_DATA = param.SCI_DATA
    elif hasattr(param, "DUMP_DATA"):
        sci.SCI_DATA = param.DUMP_DATA
    else:
        sci.SCI_DATA = b""
    return sci

#Utility functions for ADU to temp conversion of specific fields
#OB
def decode_ob_trps(adu):
    """Convert a thermistor ADU value to temperature in Celsius using the linear conversion defined by the HKREF voltage divider circuitry and an estimation formula using a PT1000 table."""
    res = (adu / (4095 - adu))*1000
    temp = (0.2559552953839863*res) - 255.7247996594076
    return temp

#EB
def decode_eb_trps(adu: int) -> float:
    """Convert a thermistor ADU value to temperature in Celsius using the B-parameter equation."""
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
