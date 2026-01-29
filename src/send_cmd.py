import logging
import sys

import tc

info_log = logging.getLogger("info_log")


def cmd_repeat(port, cmd_func, *args, repeat=True, exit_if_error=False, **kwargs):
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
