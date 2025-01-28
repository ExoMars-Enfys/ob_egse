"""
This module is used for generally sending commands. These are one step higher level than the TC
module which is mainly used to handle generation of the bytes over the RS-485. This module 
implements simple logic to verify that it has properly executed and will generally attempt one 
command retry.
"""
import logging

import tc

tc_log = logging.getLogger("tc_log")

def cmd_mtr_mov_pos(port, pos_steps, repeat=True, exit_if_error=False):
    resp = tc.mtr_mov_pos(port, pos_steps, verify=True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("MTR_MOV_POS exit on error asserted")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating MTR_MOV_POS command")
        resp = cmd_mtr_mov_pos(port, pos_steps, repeat=False, exit_if_error=True)

    return resp