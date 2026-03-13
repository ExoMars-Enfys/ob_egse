"""
This module is used for generally sending commands. These are one step higher level than the TC
module which is mainly used to handle generation of the bytes over the RS-485. This module
implements simple logic to verify that it has properly executed and will generally attempt one
command retry.
"""

import logging
from contextlib import nullcontext

import tc

info_log = logging.getLogger("info_log")


def send_cmd(port, cmd_func, *args, repeat=True, exit_if_error=False, **kwargs):
    """A generic command sender, will automatically check the response of the command for an error
    and if one is found and repeat is set, it will clear the errors and try again.

    The function returns "ERROR" if the command failed, which can be used as part of the test logic
    to halt the script and allow for manual intervention.

    Example usage:  resp = send_cmd(port, tc.mtr_mov_pos, 0x20)
    """
    resp = cmd_func(port, *args, verify_ack=True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        info_log.error(f"{cmd_func.__name__} exit on error asserted")
        return "ERROR"

    if repeat:
        info_log.warning("Clearing errors")
        tc.clear_errors(port)
        info_log.warning(f"Repeating {cmd_func.__name__} command")
        resp = send_cmd(port, cmd_func, *args, repeat=False, exit_if_error=True, **kwargs)

    return resp


def poll_hk(port, stop_event, port_lock=None, pause_event=None):
    if not port:
        return

    lock_ctx = port_lock if port_lock is not None else nullcontext()

    while not stop_event.is_set():
        if pause_event is not None and pause_event.is_set():
            stop_event.wait(1)
            continue
        try:
            with lock_ctx:
                tc.hk_request(port)
        except Exception as e:
            info_log.error(f"Error in HK poll thread {e}")

        stop_event.wait(1)  # Poll every 1 second
