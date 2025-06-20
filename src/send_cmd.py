"""
This module is used for generally sending commands. These are one step higher level than the TC
module which is mainly used to handle generation of the bytes over the RS-485. This module
implements simple logic to verify that it has properly executed and will generally attempt one
command retry.
"""

import logging

import tc

tc_log = logging.getLogger("tc_log")

def cmd_hk(port, repeat=True, exit_if_error=False):
    resp = tc.hk_request(port,verify=True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("HK Exit on Error i set")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating HK command")
        cmd_hk(port, repeat=True, exit_if_error=False)

    return resp

def cmd_power_control(port, pwr_stat, repeat=True, exit_if_error=False):
    resp = tc.power_control(port, pwr_stat, verify=True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("Power Control Exit on Error i set")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating Power Control command")
        cmd_power_control(port, pwr_stat, repeat=True, exit_if_error=False)

    return resp

def cmd_heater_control(port,htr_sci_tog,htr_detec_man,htr_detec_auto,htr_mech_man,htr_mech_auto, repeat=True, exit_if_error=False):
    resp = tc.heater_control(port,htr_sci_tog,htr_detec_man,htr_detec_auto,htr_mech_man,htr_mech_auto,verify = True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("Heater Control Exit on Error i set")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating Power Control command")
        cmd_heater_control(port,htr_sci_tog,htr_detec_man,htr_detec_auto,htr_mech_man,htr_mech_auto, repeat=False, exit_if_error=False)

    return resp

def cmd_mtr_param(port, peak_current, mtr_guard, mtr_recval,mtr_speed, mech_lim_rel, repeat=True, exit_if_error = False):
    resp = tc.set_mtr_param(port,peak_current, mtr_guard, mtr_recval,mtr_speed, mech_lim_rel, verify = True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("Set Motor Params exit on error asserted")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating Set Motor Paramscommand")
        resp = cmd_mtr_mov_pos(port,peak_current, mtr_guard, mtr_recval,mtr_speed, mech_lim_rel, verify = True)

    return resp

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

def cmd_mtr_mov_neg(port, neg_steps, repeat=True, exit_if_error=False):
    resp = tc.mtr_mov_neg(port, neg_steps, verify=True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("MTR_MOV_POS exit on error asserted")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating MTR_MOV_POS command")
        resp = cmd_mtr_mov_neg(port, neg_steps, repeat=False, exit_if_error=True)

    return resp

def cmd_mtr_halt(port, repeat = True, exit_if_error=True):
    resp = tc.mtr_halt(port, verify=True)

    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("MTR HALT exit on error asserted")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating MTR HALT command")
        resp = cmd_mtr_halt(port,repeat=False, exit_if_error=True)

    return resp

#TODO Finish this
def cmd_mtr_homing(port, cal:bool, outer:bool, repeat = True, exit_if_error=True):
    resp = tc.mtr_homing(port,cal , outer, verify=True)
    if resp != "ERROR":
        return resp

    if exit_if_error:
        tc_log.error("MTR HALT exit on error asserted")
        return "ERROR"

    if repeat:
        tc_log.warning("Clearing errors")
        tc.clear_errors(port)
        tc_log.warning("Repeating MTR Homing command")
        resp = cmd_mtr_homing(port,repeat=False, exit_if_error=True)

    return resp