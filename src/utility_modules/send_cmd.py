# Std library
import logging
# Added packages
import sys
from contextlib import nullcontext
# Local modules
#core
from core_modules import config as config
#utilities
from utility_modules import comms as comms
from utility_modules import tc as tc
info_log = logging.getLogger("info_log")

def cmd_repeat(port, cmd_func, *args, repeat=True, exit_if_error=False, **kwargs):
    """Retry a TC once after clearing errors when the first attempt fails."""
    resp = cmd_func(port, *args)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        info_log.error(f"{cmd_func.__name__} exit on error asserted")
        sys.exit(1)

    if repeat:
        info_log.warning("Clearing errors")
        tc.clear_errors(port)
        info_log.warning(f"Repeating {cmd_func.__name__} command")
        resp = cmd_repeat(port, cmd_func, *args, repeat=False, exit_if_error=True, **kwargs)

    return resp


#!TODO - Chat with Barry for the poll_hk function to see what is needed there
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
