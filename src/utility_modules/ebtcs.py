# Std library
import logging
import time

# Added packages
from datetime import datetime

# Local modules
# core
from core_modules import constants as const
from core_modules import cmd_ids as cmd_ids

info_log = logging.getLogger("info_log")

"""
The verify used in the EB TC functions is limited to simple HK ACK-like checks.
Any broader flow validation should happen at script/runtime-controller level.
"""


_TC_DEFS = dict(cmd_ids.enfys_tc_defs)


_SEND_SHOULD_PAUSE = None
_SEND_SHOULD_ABORT = None
_SEND_POLL_S = 0.0
_POLL_T = 0.0

_OPERATING_STATE_BY_TC = {
    "SAFE": 0x02,
    "STANDBY": 0x04,
    "ACQUISITION": 0x08,
}

_PENDING_STATE_CHECK = None


_NAME_INDEX = {}
for _key, _spec in _TC_DEFS.items():
    _NAME_INDEX[_key.upper()] = _key
    _NAME_INDEX[_spec["cmdtool_name"].upper()] = _key
    for _alias in _spec.get("aliases", ()):  # aliases in cmd_ids
        _NAME_INDEX[str(_alias).upper()] = _key


def _resolve_tc_name(name):
    key = _NAME_INDEX.get(str(name).strip().upper())
    if key is None:
        raise KeyError(f"Unknown EB TC: {name}")
    return key


def _build_ebtc_line(name, *args):
    tc_name = _resolve_tc_name(name)
    spec = _TC_DEFS[tc_name]
    min_args, max_args = spec["arg_count"]

    if (len(args) < min_args) or (len(args) > max_args):
        if min_args == max_args:
            raise ValueError(f"{tc_name} expects {min_args} args, got {len(args)}")
        raise ValueError(f"{tc_name} expects between {min_args} and {max_args} args, got {len(args)}")

    return " ".join([spec["cmdtool_name"], *[str(arg) for arg in args]])


def update_tc_t(t):
    """Update the sleep time after sending a TC command, allowing dynamic adjustment based on expected response times."""
    _POLL_T = max(float(t), 0.0)  # No enforced minimum sleep
    return _POLL_T


def send_tc(interface, cmd_line: str, cmd_type="EBTC", t=_POLL_T):
    """Method to send an EB TC command to CmdTool and write command log."""
    text = str(cmd_line).strip()
    if not text:
        return "ERROR"

    if _gate_send() == "ERROR":
        return "ERROR"

    cmd_log_fh = getattr(const, "CMD_LOG_FH", None)
    if cmd_log_fh is not None:
        try:
            cmd_log_fh.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
            cmd_log_fh.write(f"{cmd_type} - {text}\n")
        except Exception:
            info_log.warning("Failed to write EB TC command to CMD_LOG_FH")

    sent = bool(interface.send_command_to_cmdtool(text, wait_for_window=2.0, send_enter=True, verbose=True))
    if not sent:
        info_log.error(f"Failed to send EB TC command: {text}")
        return "ERROR"

    # No sleep for fastest possible command send
    return


def configure_send_flow_control(*, should_pause=None, should_abort=None, poll_s: float = 0.5):
    """Configure optional external flow-control hooks for script execution."""
    global _SEND_SHOULD_PAUSE, _SEND_SHOULD_ABORT, _SEND_POLL_S
    _SEND_SHOULD_PAUSE = should_pause if callable(should_pause) else None
    _SEND_SHOULD_ABORT = should_abort if callable(should_abort) else None
    _SEND_POLL_S = max(float(poll_s), 0.0)


def clear_send_flow_control():
    """Disable external flow-control hooks."""
    configure_send_flow_control(should_pause=None, should_abort=None)


def _gate_send():
    """Block or reject sends based on configured pause/abort hooks."""
    try:
        while _SEND_SHOULD_PAUSE is not None and bool(_SEND_SHOULD_PAUSE()):
            if _SEND_SHOULD_ABORT is not None and bool(_SEND_SHOULD_ABORT()):
                return "ERROR"
            # No sleep for fastest possible flow
        if _SEND_SHOULD_ABORT is not None and bool(_SEND_SHOULD_ABORT()):
            return "ERROR"
    except Exception:
        return "ERROR"
    return None


def verify_ack_hdr(before_hk, after_hk, expected_tc_type=None, expected_tc_qualifier=None):
    """Verify basic TC acknowledgement fields from HK snapshots."""
    if after_hk is None:
        info_log.error("No HK packet available for EB TC verification.")
        return

    # Removed TCS_ACCEPTED increment check as requested

    if expected_tc_type is not None:
        raw = getattr(after_hk, "LAST_TC_TYPE", None)
        actual_type = int(raw) if raw is not None else -1
        if actual_type != int(expected_tc_type):
            info_log.error(
                f"LAST_TC_TYPE does not match expected. Got: 0x{actual_type:02X}, Expected: 0x{int(expected_tc_type):02X}"
            )

    if expected_tc_qualifier is not None:
        raw = getattr(after_hk, "LAST_TC_QUALIFIER", None)
        actual_qualifier = int(raw) if raw is not None else -1
        if actual_qualifier != int(expected_tc_qualifier):
            info_log.error(
                f"LAST_TC_QUALIFIER does not match expected. Got: 0x{actual_qualifier:02X}, Expected: 0x{int(expected_tc_qualifier):02X}"
            )
    return


def verify_blank_ack_params(after_hk, field_names=()):
    """Verify optional fields are zero, mirroring tc.py blank ACK checks."""
    if after_hk is None:
        return

    for name in field_names:
        if not hasattr(after_hk, name):
            info_log.error(f"ACK {name} not found in parsed HK response.")
            continue
        value = getattr(after_hk, name)
        if value != 0:
            info_log.error(f"ACK {name} does not match expected. Got: {value}, Expected: 0")


def _verify_field_equals(packet, field_name, expected_value):
    if packet is None:
        info_log.error(f"No HK packet available to verify {field_name}.")
        return

    if not hasattr(packet, field_name):
        info_log.error(f"HK field {field_name} not found for verification.")
        return

    actual_value = getattr(packet, field_name)
    if int(actual_value) != int(expected_value):
        info_log.error(f"{field_name} does not match expected. Got: {actual_value}, Expected: {expected_value}")


def _verify_flag_equals(packet, namespace_name, flag_name, expected_value):
    if packet is None:
        info_log.error(f"No HK packet available to verify {flag_name}.")
        return

    namespace = getattr(packet, namespace_name, None)
    if namespace is None or not hasattr(namespace, flag_name):
        info_log.error(f"HK flag {namespace_name}.{flag_name} not found for verification.")
        return

    actual_value = bool(getattr(namespace, flag_name))
    expected_bool = bool(expected_value)
    if actual_value != expected_bool:
        info_log.error(
            f"{namespace_name}.{flag_name} does not match expected. Got: {actual_value}, Expected: {expected_bool}"
        )


def _read_latest_hk_and_index():
    """Read latest HK and its line index from currently selected RS422 log."""
    try:
        from utility_modules import eb_interface
        from utility_modules import eb_packet_utility

        log_path = getattr(eb_interface, "rs422_log_path", None)
        if not log_path:
            return None, None

        latest_hk, _, _, _, _, last_index = eb_packet_utility.read_pkt(log_path, latest_only=True)
        return latest_hk, last_index
    except Exception:
        return None, None


def _wait_for_response_hk(prev_index, timeout_s: float = 2.5, poll_s: float = 0.1):
    """Wait for a newer HK packet after command send."""
    end_time = time.time() + timeout_s

    fast_poll_s = 0.01
    while time.time() < end_time:
        hk, idx = _read_latest_hk_and_index()
        if hk is not None and (prev_index is None or (idx is not None and idx > prev_index)):
            return hk
        time.sleep(fast_poll_s)

    return None


def _verify_tc(name, before_hk, after_hk):
    spec = _TC_DEFS[_resolve_tc_name(name)]
    if after_hk is None:
        info_log.error(f"No newer HK/TM response received for {name}.")
        return

    verify = spec.get("verify") or {}

    verify_ack_hdr(
        before_hk,
        after_hk,
        expected_tc_type=verify.get("last_tc_type"),
        expected_tc_qualifier=verify.get("last_tc_qualifier"),
    )

    tc_name = _resolve_tc_name(name)
    if tc_name in _OPERATING_STATE_BY_TC:
        global _PENDING_STATE_CHECK
        _PENDING_STATE_CHECK = _OPERATING_STATE_BY_TC[tc_name]


def _verify_tc_applied(name, after_hk, args):
    tc_name = _resolve_tc_name(name)
    if after_hk is None:
        return

    if tc_name == "SET_HK_RATE":
        _verify_field_equals(after_hk, "CURRENT_HK_TIME_INTERVAL", int(args[1]))
    elif tc_name == "SET_TEC_SETPOINT":
        _verify_field_equals(after_hk, "TEC_SETPOINT", int(args[1]))
    elif tc_name == "SET_MOTOR_CONFIGS":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "MOTOR_CONFIGS_SET", True)
    elif tc_name == "SET_HEATER_CONFIGS":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "HEATER_CONFIGS_SET", True)
    elif tc_name == "SET_ACQ_CONFIGS":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "MEASUREMENT_CONFIGS_SET", True)
    elif tc_name == "EN_MECH_BOARD":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "OB_MECHANISM_BOARD_ENABLED", bool(args[0]))
    elif tc_name == "EN_DET_BOARD":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "OB_DETECTOR_BOARD_ENABLED", bool(args[0]))
    elif tc_name == "EN_MECH_HEATER":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "OB_MECHANISM_HEATER_ENABLED", bool(args[0]))
    elif tc_name == "EN_DET_HEATER":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "OB_DETECTOR_HEATER_ENABLED", bool(args[0]))
    elif tc_name == "EN_OB5V":
        _verify_flag_equals(after_hk, "INSTR_STATUS_FLAGS", "OB_5V_ENABLED", bool(args[0]))


def _send_named_tc(interface, tc_name, *args):
    before_hk, before_index = _read_latest_hk_and_index()
    cmd_line = _build_ebtc_line(tc_name, *args)
    status = send_tc(interface, cmd_line, cmd_type=tc_name)
    # if status == "ERROR":
    #     return "ERROR"

    # after_hk = _wait_for_response_hk(before_index)
    # if after_hk is None:
    #     info_log.error(f"{tc_name} did not produce a newer HK/TM response within timeout.")
    #     return "ERROR"

    # _verify_tc(tc_name, before_hk, after_hk)
    # _verify_tc_applied(tc_name, after_hk, args)

    return


def ret(interface, mode, p1, p2, p3, p4, p5):
    result = _send_named_tc(interface, "RET", mode, p1, p2, p3, p4, p5)
    global _PENDING_STATE_CHECK
    if _PENDING_STATE_CHECK is not None and result != "ERROR":
        hk, _ = _read_latest_hk_and_index()
        # _verify_field_equals(hk, "CURRENT_OPERATING_STATE", _PENDING_STATE_CHECK)
        _PENDING_STATE_CHECK = None
    return result


def hk_request(interface, source):
    return _send_named_tc(interface, "REQUEST_HK", source)


def patch(interface, target, address, *payload):
    return _send_named_tc(interface, "PATCH", target, address, *payload)


def dump(interface, source, start, count):
    return _send_named_tc(interface, "DUMP", source, start, count)


def set_hk_rate(interface, source, period_ms):
    return _send_named_tc(interface, "SET_HK_RATE", source, period_ms)


def monitor_addr(interface, source, address):
    return _send_named_tc(interface, "MONITOR_ADDR", source, address)


def abort(interface, reason):
    return _send_named_tc(interface, "ABORT", reason)


def generic_tc(interface, target, cmd, *params):
    return _send_named_tc(interface, "GENERIC_TC", target, cmd, *params)


def safe(interface, source):
    result = _send_named_tc(interface, "SAFE", source)
    # Always send RET after SAFE to complete state transition
    _send_named_tc(interface, "RET", 0, 0, 0, 0, 0, 0)
    return result


def standby(interface, source, submode):
    result = _send_named_tc(interface, "STANDBY", source, submode)
    # Always send RET after STANDBY to complete state transition
    _send_named_tc(interface, "RET", 0, 0, 0, 0, 0, 0)
    return result


def acquisition(interface, source):
    return _send_named_tc(interface, "ACQUISITION", source)


def set_motor_configs(interface, *args):
    return _send_named_tc(interface, "SET_MOTOR_CONFIGS", *args)


def set_heater_configs(interface, *args):
    return _send_named_tc(interface, "SET_HEATER_CONFIGS", *args)


def set_acq_configs(interface, *args):
    return _send_named_tc(interface, "SET_ACQ_CONFIGS", *args)


def set_tec_setpoint(interface, source, setpoint):
    return _send_named_tc(interface, "SET_TEC_SETPOINT", source, setpoint)


def set_fdir(interface, *args):
    return _send_named_tc(interface, "SET_FDIR", *args)


def en_mech_board(interface, enabled):
    return _send_named_tc(interface, "EN_MECH_BOARD", enabled)


def en_det_board(interface, enabled):
    return _send_named_tc(interface, "EN_DET_BOARD", enabled)


def en_mech_heater(interface, enabled):
    return _send_named_tc(interface, "EN_MECH_HEATER", enabled)


def en_det_heater(interface, enabled):
    return _send_named_tc(interface, "EN_DET_HEATER", enabled)


def en_ob5v(interface, enabled):
    return _send_named_tc(interface, "EN_OB5V", enabled)


def ob_park(interface, mode):
    return _send_named_tc(interface, "OB_PARK", mode)


def ob_homing(interface, mode):
    return _send_named_tc(interface, "OB_HOMING", mode)


def ob_hk(interface, selector):
    return _send_named_tc(interface, "OB_HK", selector)


def check_memory(interface, source, address, count):
    return _send_named_tc(interface, "CHECK_MEMORY", source, address, count)


def goto(interface, source, address):
    return _send_named_tc(interface, "GOTO", source, address)


def copy_memory(interface, source, src_addr, dst_addr, count):
    return _send_named_tc(interface, "COPY_MEMORY", source, src_addr, dst_addr, count)


def switch_rs422(interface, lane):
    return _send_named_tc(interface, "SWITCH_RS422", lane)


def set_tec_current(interface, source, current):
    return _send_named_tc(interface, "SET_TEC_CURRENT", source, current)
