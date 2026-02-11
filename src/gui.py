# Std library
import logging
import os
import glob
import html
import traceback
from datetime import datetime
from tkinter import filedialog
import serial
import comms
import time
from pathlib import Path
from collections import deque
import tkinter as tk
import math
from pywinauto.findwindows import find_window
from pywinauto import Application

# Added packages
import constants as const
import streamlit as st
from streamlit_extras.grid import grid
import matplotlib.pyplot as plt
import threading

# Project imports
import tc as tc
import psu
import hk_sniffer as eb
from eb_interface import EGSEInterface
import sys
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from scripts import eb_sft_checks


def convert_thermistor_b_parameter(adu):
    T0 = 298.0  # K
    R0 = 5000.0  # Ω
    B = 3891.0
    
    # Calculate resistance from ADU
    if adu >= 65536:
        return float('nan')  # Invalid ADU
    
    R = 1000.0 * ((65536.0 / (65536.0 - adu)) - 1.0)
    
    # Calculate temperature using B-parameter equation
    inv_T = (1.0 / T0) + (1.0 / B) * math.log(R / R0)
    T_kelvin = 1.0 / inv_T
    T_celsius = T_kelvin - 273.15
    
    return T_celsius


st.logo("./rsrc/ExoMars_Logo_PNG.png")
state_pwr_dict = {"OFF" : 0, "Mech Only": 1, "Detec Only": 2, "Both": 3}

event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")

# Initialize EGSE interface
egse_interface = EGSEInterface(r"C:\wdir\IFM\EB")

st.set_page_config(page_title = "Enfys EGSE v3.0" , page_icon="./rsrc/ExoMars_Logo_PNG.png",initial_sidebar_state="expanded", layout="wide")

# Global State Initialisation ----------------------------------------------------------------------
def st_state_initialise() -> None:
    if "comms_active" not in st.session_state:
        st.session_state.comms_active = False
    if "count" not in st.session_state:
        st.session_state.count = 0
    if "psu_lock" not in st.session_state:
        st.session_state.psu_lock = threading.Lock()
    if "state_psu" not in st.session_state:
        st.session_state.state_psu = False
    if "state_eb_psu" not in st.session_state:
        st.session_state.state_eb_psu = False
    if "state_rov_htr_psu" not in st.session_state:
        st.session_state.state_rov_htr_psu = False
    if "sft_mode" not in st.session_state:
        st.session_state.sft_mode = None
    if "ob_model_options" not in st.session_state:
        st.session_state.ob_model_options = {
            "DEV (Model ID 0)": 0,
            "IFM (Model ID 1)": 1,
            "BB2 (Model ID 2)": 2,
            "Firmware TB (Model ID 3)": 3,
            "EM (Model ID 4)": 4,
            "FM (Model ID 5)": 5,
            "FS (Model ID 6)": 6,
            "CMOD EGSE (Model ID 7)": 7,
        }
    if "selected_ob_model" not in st.session_state:
        st.session_state.selected_ob_model = "BB2 (Model ID 2)"
    if "show_egse_psu_warning" not in st.session_state:
        st.session_state.show_egse_psu_warning = False
    if "show_egse_script_warning" not in st.session_state:
        st.session_state.show_egse_script_warning = False
    if "psu_data" not in st.session_state:
        st.session_state.psu_data = {
            "ch1_v": "0V", "ch1_i": "0A",
            "ch2_v": "0V", "ch2_i": "0A",
            "ch3_v": "0V", "ch3_i": "0A"
        }
    if "psu_monitor_thread" not in st.session_state:
        st.session_state.psu_monitor_thread = None
    if "stop_event" not in st.session_state:
        st.session_state.stop_event = None
    if "psu_queue" not in st.session_state:
        st.session_state.psu_queue = {}
    if "last_hk" not in st.session_state:
        st.session_state.last_hk = None
    if "eb_filepath" not in st.session_state:
        st.session_state.eb_filepath = None
    if "last_tm_index" not in st.session_state:
        st.session_state.last_tm_index = -1
    if "last_post_index" not in st.session_state:
        st.session_state.last_post_index = -1
    if "last_log_mtime" not in st.session_state:
        st.session_state.last_log_mtime = 0
    if "log_pause_detected" not in st.session_state:
        st.session_state.log_pause_detected = False
    if "last_mtime_update_time" not in st.session_state:
        st.session_state.last_mtime_update_time = time.time()
    if "rov_htr_state" not in st.session_state:
        st.session_state.rov_htr_state = False
    if "psu_channel_state" not in st.session_state:
        st.session_state.psu_channel_state = {"ch3": False, "ch4": False}
    if "psu_toggle_time" not in st.session_state:
        st.session_state.psu_toggle_time = None
    if "psu_pending_activation" not in st.session_state:
        st.session_state.psu_pending_activation = False
    if "warning_dismissed" not in st.session_state:
        st.session_state.warning_dismissed = False
    if "psu_log_request" not in st.session_state:
        st.session_state.psu_log_request = {"requested": False, "request_id": 0}
    if "psu_log_lock" not in st.session_state:
        st.session_state.psu_log_lock = threading.Lock()
    if "previous_warning_state" not in st.session_state:
        st.session_state.previous_warning_state = False
    if "previous_warning_reasons" not in st.session_state:
        st.session_state.previous_warning_reasons = []
@st.cache_resource
def port_init(rs485_com, psu_com, nopsu):
    rs485port = comms.initialise_comms(rs485_com)
    rs485port = comms.open_comms(rs485port)        
    psuport = psu.init_psu_comms(psu_com)
    psuport = psu.open_psu_comms(psuport, nopsu)
    return rs485port, psuport

# Streamlit Page setup -----------------------------------------------------------------------------
def init(ebmode, nopsu, rs485_com, psu_com) -> None:
    st_state_initialise()
    st.session_state.rs485port, st.session_state.psuport = port_init(rs485_com, psu_com , nopsu)
    st.session_state.ebmode = ebmode    
    main_gui()
    with st.sidebar:
        st.image(Path("./rsrc/Enfys_logo.jpg"), width=150)
        warning_light_monitor()
        check_for_new_tm()

@st.fragment(run_every="0.5s")
def warning_light_monitor():
    """Monitor system health and display warning light for critical conditions."""
    warning_triggered = False
    warning_reasons = []
    
    # Check PSU voltage and current bounds
    if st.session_state.psu_queue:
        latest_psu_data = st.session_state.psu_queue[-1]
        ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i, ch4_v, ch4_i = latest_psu_data
        
        # Helper function to safely convert to float
        def safe_float(value):
            try:
                if isinstance(value, str):
                    if value == "N/A" or not value or value.isspace():
                        return None
                    cleaned = value.strip("VAva")
                    if cleaned and not cleaned.isspace():
                        return float(cleaned)
                    return None
                return float(value) if value else None
            except (ValueError, AttributeError):
                return None
        
        ch1_v_val = safe_float(ch1_v)
        ch1_i_val = safe_float(ch1_i)
        ch2_v_val = safe_float(ch2_v)
        ch2_i_val = safe_float(ch2_i)
        ch3_v_val = safe_float(ch3_v)
        ch3_i_val = safe_float(ch3_i)
        ch4_v_val = safe_float(ch4_v)
        ch4_i_val = safe_float(ch4_i)
        
        # Check CH3: ROV HTR (26-30V nominal) - only if enabled
        if st.session_state.state_rov_htr_psu:
            if ch3_v_val is not None and not (26.0 <= ch3_v_val <= 30.0):
                warning_triggered = True
                warning_reasons.append(f"ROV_HTR Voltage: {ch3_v_val:.2f}V (out of range 26.0-30.0V)")
            
            if ch3_i_val is not None and not (0 <= ch3_i_val <= const.ROV_HTR_I):
                warning_triggered = True
                warning_reasons.append(f"ROV_HTR Current: {ch3_i_val:.3f}A (exceeds {const.ROV_HTR_I}A)")
        
        # Check CH4: EB Power (EB_OVP limit) - only if enabled
        if st.session_state.state_eb_psu:
            if ch4_v_val is not None and not (0 <= ch4_v_val <= const.EB_OVP):
                warning_triggered = True
                warning_reasons.append(f"EB Voltage: {ch4_v_val:.2f}V (exceeds {const.EB_OVP}V)")
            
            if ch4_i_val is not None and not (0 <= ch4_i_val <= const.EB_I):
                warning_triggered = True
                warning_reasons.append(f"EB Current: {ch4_i_val:.3f}A (exceeds {const.EB_I}A)")
    
    # Check for FDIR warnings in HK packet
    last_hk = st.session_state.get("last_hk")
    if last_hk:
        # Check FDIR_WARNING_FLAGS - if non-zero, system has warnings
        if last_hk.FDIR_WARNING_FLAGS != 0:
            warning_triggered = True
            warning_reasons.append(f"FDIR_WARNING_FLAGS: 0x{last_hk.FDIR_WARNING_FLAGS:08X} (Failure Detection, Isolation, and Recovery flags triggered)")
        
        # Check OB error flags - if non-zero, errors detected
        if last_hk.OB_LAST_ERROR != 0:
            warning_triggered = True
            error_code = last_hk.OB_LAST_ERROR
            warning_reasons.append(f"OB_LAST_ERROR: 0x{error_code:04X} (OB module reported error code {error_code})")
    
    # Display warning light
    col1, col2 = st.columns([1, 5])
    
    with col1:
        if warning_triggered:
            # Red warning light
            st.markdown("""
                <div style="
                    width: 80px;
                    height: 80px;
                    background-color: #ff4444;
                    border-radius: 50%;
                    box-shadow: 0 0 20px rgba(255, 68, 68, 0.8), inset 0 0 10px rgba(0, 0, 0, 0.3);
                    animation: pulse 0.6s infinite;
                "></div>
                <style>
                    @keyframes pulse {
                        0%, 100% { box-shadow: 0 0 20px rgba(255, 68, 68, 0.8), inset 0 0 10px rgba(0, 0, 0, 0.3); }
                        50% { box-shadow: 0 0 30px rgba(255, 68, 68, 1), inset 0 0 10px rgba(0, 0, 0, 0.3); }
                    }
                </style>
            """, unsafe_allow_html=True)
        else:
            # Green safe light
            st.markdown("""
                <div style="
                    width: 80px;
                    height: 80px;
                    background-color: #44ff44;
                    border-radius: 50%;
                    box-shadow: 0 0 20px rgba(68, 255, 68, 0.6), inset 0 0 10px rgba(0, 0, 0, 0.3);
                "></div>
            """, unsafe_allow_html=True)
    
    with col2:
        if warning_triggered:
            # Only show alert if warning state changed (new warning or different warnings)
            warning_changed = (not st.session_state.previous_warning_state or 
                             warning_reasons != st.session_state.previous_warning_reasons)
            
            if not st.session_state.warning_dismissed:
                warning_message = "⚠️ **SYSTEM WARNING - CRITICAL CHECK FAILURE**\n\n**Failed Checks:**\n"
                for i, reason in enumerate(warning_reasons, 1):
                    warning_message += f"{i}. {reason}\n"
                warning_message += "\n⚡ Review failures above and take corrective action before proceeding."
                st.error(warning_message)
            
            # Add dismiss button
            if st.button("Dismiss Warning", key="dismiss_warning_btn"):
                st.session_state.warning_dismissed = True
                st.rerun()
            
            # Update previous state
            st.session_state.previous_warning_state = warning_triggered
            st.session_state.previous_warning_reasons = warning_reasons
        else:
            # Clear dismissed state when warnings resolve
            if st.session_state.warning_dismissed:
                st.session_state.warning_dismissed = False
            
            # Show success toast only if transitioning from warning to OK
            if st.session_state.previous_warning_state:
                st.toast("✓ System OK", icon="✅")
            
            # Update previous state
            st.session_state.previous_warning_state = warning_triggered
            st.session_state.previous_warning_reasons = []

@st.dialog("EGSE Tools Required")
def show_egse_warning_dialog():
    st.markdown("**EGSE tools must be started before enabling the EB PSU.**")
    st.markdown("Please start the EGSE tools first, then try again.")
    if st.button("OK"):
        st.session_state.show_egse_psu_warning = False
        st.rerun()

@st.dialog("EGSE Tools Required")
def show_egse_script_warning_dialog():
    st.markdown("**EGSE tools must be started before selecting an EGSE script.**")
    st.markdown("Please start the EGSE tools first, then try again.")
    if st.button("OK"):
        st.session_state.show_egse_script_warning = False
        st.rerun()
@st.fragment()
def  main_gui() -> None:
    if st.session_state.ebmode: 
        if st.session_state.show_egse_psu_warning:
            show_egse_warning_dialog()
        if st.session_state.show_egse_script_warning:
            show_egse_script_warning_dialog()
        st.title("Enfys EGSE v3.0")               
        col1, col2, col3, col4 = st.columns(4)            
        col1.toggle(label="ROV HTR PSU Switch", key="state_rov_htr_psu", on_change=rov_htr_psu_toggle, args=(st.session_state.psuport,))
        col2.toggle(label="EB PSU Switch", key="state_eb_psu", on_change=eb_psu_toggle, args=(st.session_state.psuport,))
        col3.button("Log PSU", on_click=log_psu_state)
        psu_display_fragment(st.session_state.psuport)
        eb_Fragment()
            
        
    else:
        st.write("PSU Status")    
        col1, col2, col3 = st.columns(3)
        col1.toggle(label="PSU Switch", key="state_psu", on_change=psu_toggle, args=(st.session_state.psuport,))
        if st.session_state.state_psu:
            eb_psu_display(st.session_state.psuport)
        else:
            st.write("PSU is OFF")
        st.divider()  

        coltc, coltm = st.columns([0.3, 0.7])

        pwr_options = list(state_pwr_dict.keys())
        st.pills("Power Options", pwr_options, selection_mode="single", key="pwr_pill", on_change=on_pills_change_pwr)

# TM BackEnd Handling ------------------------------------------------------------------------------
@st.fragment(run_every=1)
def check_for_new_tm() -> None:
    try:
        if not st.session_state.ebmode:
            st.session_state.last_hk = const.hk_queue.pop()
        else:
            # For EB mode, parse log file to get HK data
            if st.session_state.eb_filepath is not None:
                eb_log_parser(st.session_state.eb_filepath)
        
        if st.session_state.last_hk is not None:
            top_level_status(st.session_state.last_hk)
    except IndexError:
        return
def top_level_status(last_hk) -> None:
    write_hk_dashboard(last_hk)
    # Power and Heater Status
    
    write_pwr_stat(last_hk)

    st.divider()
    write_errors(last_hk)
def write_hk_dashboard(last_hk):
    dashboard_grid = grid(1,6,1,1,5,1,1,6,1,1,6,gap="small", vertical_align="center")
    dashboard_grid.write("Voltages")
    dashboard_grid.markdown(f"+12V:\n\n {(last_hk.EB_MEAS_MAIN_12V * 0.000400543):.2f}V", width="content")
    dashboard_grid.markdown(f"-12V:\n\n {(last_hk.EB_MEAS_MAIN_NEG12V * 0.00038147):.2f}V", width="content")
    dashboard_grid.markdown(f"+5V:\n\n {(last_hk.EB_MEAS_5V * 0.000152829):.2f}V", width="content")
    dashboard_grid.markdown(f"+3V3:\n\n {(2 *last_hk.OB_3V3_VOLTAGE /1000):.2f}V", width="content")
    dashboard_grid.markdown(f"+1V5:\n\n {(last_hk.OB_1V5_VOLTAGE / 1000):.2f}V", width="content")
    dashboard_grid.markdown(f"TEC I:\n\n {(last_hk.EB_TEC_DRIVE_CURRENT * 0.0000162):.4f}A", width="content")
    dashboard_grid.divider()
    dashboard_grid.write("Temperatures")
    dashboard_grid.markdown(f"Digital:\n\n {(last_hk.OB_DIGITAL_TRP / 100):.2f}°C", width="content")
    dashboard_grid.markdown(f"Detector:\n\n {(last_hk.OB_DETECTOR_TRP / 100):.2f}°C", width="content")
    dashboard_grid.markdown(f"Mechanism:\n\n {(last_hk.OB_MECHANISM_TRP / 100):.2f}°C", width="content")
    dashboard_grid.markdown(f"Motor:\n\n {(last_hk.OB_MOTOR_TRP / 100):.2f}°C", width="content")
    dashboard_grid.markdown(f"Peltier:\n\n {((last_hk.EB_PELTIER_TEMP * -0.001830011) + 51.27039922):.2f}°C", width="content")
    dashboard_grid.divider()
    dashboard_grid.write("Hk snapshot")
    
    # Operating State mapping
    op_state_map = {0x00: "INITIALISING", 0x02: "SAFE", 0x04: "STANDBY", 0x08: "ACQUISITION"}
    op_state_name = op_state_map.get(last_hk.CURRENT_OPERATING_STATE, f"UNKNOWN(0x{last_hk.CURRENT_OPERATING_STATE:02X})")
    op_state_color = {0x00: "gray", 0x02: "blue", 0x04: "green", 0x08: "violet"}.get(last_hk.CURRENT_OPERATING_STATE, "red")
    dashboard_grid.markdown(f"Operating State:\n\n :{op_state_color}-badge[{op_state_name}]", width="content")    
    badge_color = "green" if (last_hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01) == 1 else "red"
    dashboard_grid.markdown(f"OB Power Status:\n\n :{badge_color}-badge[{"ENABLED" if (last_hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01) == 1 else "DISABLED"}]", width="content")  
    dashboard_grid.markdown(f"CMD Count:\n\n {last_hk.OB_COMMAND_COUNT}", width="content")
    dashboard_grid.markdown(f"ABS Steps:\n\n {last_hk.OB_MOTOR_ABS_STEPS}", width="content")
    homing_complete_badge = ":green-badge[Homing Complete]" if (last_hk.INSTR_STATUS_FLAGS.HOMING_COMPLETE & 0x01) == 1 else ":gray-badge[Not Complete]"
    dashboard_grid.markdown(f"Motor Homing:\n\n {homing_complete_badge}", width="content")
    dashboard_grid.divider()
    dashboard_grid.write("Motor Status")
    dashboard_grid.markdown(":green-badge[Calibrated]" if (last_hk.MTR_FLAGS.CAL & 0x01) == 1 else ":gray-badge[Not Calibrated]", width="content")
    dashboard_grid.markdown(":violet-badge[Towards Base]" if (last_hk.MTR_FLAGS.DIR & 0x01) == 1 else ":blue-badge[Towards Outer]", width="content")
    dashboard_grid.markdown(":green-badge[At Outer]" if (last_hk.MTR_FLAGS.OUTER & 0x01) == 1 else ":gray-badge[At Outer]", width="content")
    dashboard_grid.markdown(":green-badge[At Base]" if (last_hk.MTR_FLAGS.BASE & 0x01) == 1 else ":gray-badge[At Base]", width="content")
    dashboard_grid.markdown(":green-badge[Motor Moving]" if (last_hk.MTR_FLAGS.MOVING & 0x01) == 1 else ":gray-badge[Motor Stationary]", width="content")    
    dashboard_grid.markdown(":green-badge[Homing]" if (last_hk.MTR_FLAGS.HOMING & 0x01) == 1 else ":gray-badge[Not Homing]", width="content")
    dashboard_grid.divider()
def write_errors(last_hk):
    err_grid = grid(1,6,1,1,6,gap = "small",vertical_align="center")
    err_grid.write("Error Status")
    err_grid.markdown(":green-badge[IPI]" if (last_hk.ERRORS.IPI & 0x01) == 0 else ":red-badge[IPI]")
    err_grid.markdown(":green-badge[IOS]" if (last_hk.ERRORS.IOS & 0x01) == 0 else ":red-badge[IOS]")
    err_grid.markdown(":green-badge[ICR]" if (last_hk.ERRORS.ICR & 0x01) == 0 else ":red-badge[ICR]")
    err_grid.markdown(":green-badge[MOR]" if (last_hk.ERRORS.MOR & 0x01) == 0 else ":red-badge[MOR]")
    err_grid.markdown(":green-badge[TMO]" if (last_hk.ERRORS.TMO & 0x01) == 0 else ":red-badge[TMO]")
    err_grid.markdown(":green-badge[IPA]" if (last_hk.ERRORS.IPA & 0x01) == 0 else ":red-badge[IPA]")
    err_grid.divider()
    err_grid.write("Motor Error Status")
    err_grid.markdown(":green-badge[CD]" if (last_hk.MTR_ERRORS.CD & 0x01) == 0 else ":red-badge[CD]")
    err_grid.markdown(":green-badge[AB]" if (last_hk.MTR_ERRORS.AB & 0x01) == 0 else ":red-badge[AB]")
    err_grid.markdown(":green-badge[ABS]" if (last_hk.MTR_ERRORS.ABS & 0x01) == 0 else ":red-badge[ABS]")
    err_grid.markdown(":green-badge[DSE]" if (last_hk.MTR_ERRORS.DSE & 0x01) == 0 else ":red-badge[DSE]")
def write_pwr_stat(last_hk) -> None:
    stat_grid = grid(1,1,3,1,1,2,4, gap="small", vertical_align="center")
    
    st_det_htr = (
        ":gray-badge[DETEC HTR OFF]" if (last_hk.THRM_STATUS.HDS & 0x01) == 0 else ":red-badge[DETEC HTR ON]"
    )
    st_sci = ":gray-badge[SCI TOG OFF]" if (last_hk.THRM_STATUS.S & 0x01) == 0 else ":blue-badge[SCI TOG ON]"

    st_mec_man = (
        ":gray-badge[MEC MAN OFF]" if (last_hk.THRM_STATUS.MM & 0x01) == 0 else ":blue-badge[MECH MAN ON]"
    )
    st_mec_auto = (
        ":gray-badge[MEC AUTO OFF]" if (last_hk.THRM_STATUS.MA & 0x01) == 0 else ":blue-badge[MECH AUTO ON]"
    )

    st_det_man = ":gray-badge[DET MAN OFF]" if (last_hk.THRM_STATUS.DM & 0x01) == 0 else ":blue-badge[DET MAN ON]"
    st_det_auto = (
        ":gray-badge[DET AUTO OFF]" if (last_hk.THRM_STATUS.DA & 0x01) == 0 else ":blue-badge[DET AUTO ON]"
    )

    stat_grid.write("Mechanism Power and Heater Status")
    stat_grid.markdown(":grey-badge[MECH OFF]" if (last_hk.OB_POWER_STATUS & 0x01) == 0 else ":green-badge[MECH ON]")
    stat_grid.markdown(":gray-badge[MECH HTR OFF]" if (last_hk.THRM_STATUS.HMS & 0x01) == 0 else ":red-badge[MECH HTR ON]")
    stat_grid.markdown(st_mec_man)
    stat_grid.markdown(st_mec_auto)
    stat_grid.divider()

    stat_grid.write("Detector Power and Heater Status")
    stat_grid.markdown(":gray-badge[DETEC OFF]" if (last_hk.OB_POWER_STATUS & 0x02) == 0 else ":green-badge[DETEC ON]")
    stat_grid.markdown(st_sci)
    stat_grid.markdown(st_det_htr)
    stat_grid.markdown(st_det_man)
    stat_grid.markdown(st_det_auto)

# TC Pills Handling --------------------------------------------------------------------------------
def on_pills_change_pwr():
    # Write to new power state
    selected_key = st.session_state.pwr_pill
    if selected_key:
        pwr_value = state_pwr_dict[selected_key]
        tc.power_control(st.session_state.rs485port, pwr_value)

# PSU BackEnd Handling -----------------------------------------------------------------------------
@st.fragment(run_every="0.5s")
def psu_display_fragment(psu_com):
    """Fragment that handles PSU display and monitoring without blocking the main page."""
    
    
    if st.session_state.state_eb_psu or st.session_state.state_rov_htr_psu:
        if st.session_state.psu_monitor_thread is None or not st.session_state.psu_monitor_thread.is_alive():
            st.session_state.stop_event = threading.Event()
            st.session_state.psu_monitor_thread = threading.Thread(
                target=psu.psu_monitor_thread,
                args=(
                    st.session_state.psuport,
                    st.session_state.stop_event,
                    const.PSU_LOGGING_FREQ,
                    True,
                    st.session_state.psu_lock,
                    st.session_state.psu_channel_state,
                    psu.psu_log_request,
                    psu.psu_log_lock,
                ),
                daemon=True,
            )
            st.session_state.psu_monitor_thread.start()
        st.session_state.psu_queue = const.psu_queue
        eb_psu_display(st.session_state.psuport)
    else:
        st.write("PSU is OFF")
        if st.session_state.stop_event is not None:
            st.session_state.stop_event.set()
            if st.session_state.psu_monitor_thread and st.session_state.psu_monitor_thread.is_alive():
                st.session_state.psu_monitor_thread.join(timeout=1.0)

def log_psu_state():
    """Log the current PSU state to the SFT Check LOG."""
    # Update module-level log request used by PSU monitor thread
    with psu.psu_log_lock:
        if not psu.psu_log_request.get("requested", False):
            psu.psu_log_request["request_id"] = psu.psu_log_request.get("request_id", 0) + 1
            psu.psu_log_request["requested"] = True

def eb_psu_toggle(psu_com: serial.Serial):
    if not st.session_state.ebmode:
        return
    
    # Check if EGSE tools are started before allowing EB PSU to turn on
    if st.session_state.state_eb_psu and not st.session_state.get("egse_started", False):
        st.session_state.show_egse_psu_warning = True
        st.session_state.state_eb_psu = False
        return

    if st.session_state.state_eb_psu:
        # Turning ON - activate immediately
        st.session_state.psu_channel_state["ch4"] = True
        with st.session_state.psu_lock:
            if not psu_com.is_open:
                psu.open_psu_comms(psu_com, psu_not_required=False)
            psu.setChannels(psu_com, rov_htrs=False, ebmode=True)
            psu.switchPSU(psu_com, True, rov_htrs=False, ebmode=True)
    else:
        # Turning OFF - do it immediately
        st.session_state.psu_channel_state["ch4"] = False
        with st.session_state.psu_lock:
            if psu_com.is_open:
                psu.switchPSU(psu_com, False, rov_htrs=False, ebmode=True)
            if not st.session_state.state_rov_htr_psu:
                if st.session_state.stop_event:
                    st.session_state.stop_event.set()
                if st.session_state.psu_monitor_thread and st.session_state.psu_monitor_thread.is_alive():
                    st.session_state.psu_monitor_thread.join(timeout=1)
                time.sleep(0.25)
                psu.close_psu_comms(psu_com)
def rov_htr_psu_toggle(psu_com: serial.Serial):
    if not st.session_state.ebmode:
        return

    st.session_state.rov_htr_state = st.session_state.state_rov_htr_psu
    st.session_state.psu_channel_state["ch3"] = st.session_state.state_rov_htr_psu

    with st.session_state.psu_lock:
        if st.session_state.state_rov_htr_psu:
            if not psu_com.is_open:
                psu.open_psu_comms(psu_com, psu_not_required=False)
            psu.setChannels(psu_com, rov_htrs=True, ebmode=True)
            psu.switchPSU(psu_com, True, rov_htrs=True, ebmode=True)
        else:
            if psu_com.is_open:
                psu.switchPSU(psu_com, False, rov_htrs=True, ebmode=True)
            if not st.session_state.state_eb_psu:
                if st.session_state.stop_event:
                    st.session_state.stop_event.set()
                if st.session_state.psu_monitor_thread and st.session_state.psu_monitor_thread.is_alive():
                    st.session_state.psu_monitor_thread.join(timeout=1)
                time.sleep(0.25)
                psu.close_psu_comms(psu_com)
def psu_toggle(psu_com: serial.Serial):
    if st.session_state.ebmode:
        return

    if st.session_state.state_psu:
        # Try to open port if it's closed
        if not psu_com.is_open:
            psu.open_psu_comms(psu_com, psu_not_required=False)

        psu.setChannels(psu_com, st.session_state.ebmode)
        psu.switchPSU(psu_com, st.session_state.state_psu)

        # Initialize plot data dictionary with figure and axes
        st.session_state.psu_plot_data = {
            'ch1_voltages': deque(),
            'ch1_currents': deque(),
            'ch2_voltages': deque(),
            'ch2_currents': deque(),
            'ch3_voltages': deque(),
            'ch3_currents': deque(),
            'time_points': deque(),
            'start_time': time.time(),
            'plot_counter': 0
        }

        # Initialize plot figure and axes
        fig, (ax_voltage, ax_current) = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle("PSU Live Monitoring", fontsize=10, fontweight='light')

        ax_voltage.set_title("Voltage (V)", fontsize=8)
        ax_voltage.set_xlabel("Time (s)", fontsize=7)
        ax_voltage.set_ylabel("Voltage (V)", fontsize=7)
        ax_voltage.tick_params(labelsize=6)
        ax_voltage.grid(True, alpha=0.1)

        ax_current.set_title("Current (A)", fontsize=8)
        ax_current.set_xlabel("Time (s)", fontsize=7)
        ax_current.set_ylabel("Current (A)", fontsize=7)
        ax_current.tick_params(labelsize=6)
        ax_current.grid(True, alpha=0.1)

        line_v_ch1, = ax_voltage.plot([], [], label='+12V', color='red', linewidth=1)
        line_v_ch2, = ax_voltage.plot([], [], label='-12V', color='blue', linewidth=1)
        line_v_ch3, = ax_voltage.plot([], [], label='+5V', color='green', linewidth=1)

        line_i_ch1, = ax_current.plot([], [], label='CH1', color='red', linewidth=1)
        line_i_ch2, = ax_current.plot([], [], label='CH2', color='blue', linewidth=1)
        line_i_ch3, = ax_current.plot([], [], label='CH3', color='green', linewidth=1)

        ax_voltage.legend(loc='upper left', fontsize=6)
        ax_current.legend(loc='upper left', fontsize=6)

        plt.tight_layout(pad=5)

        st.session_state.psu_plot_data['axes'] = {'voltage': ax_voltage, 'current': ax_current}
        st.session_state.psu_plot_data['lines'] = {
            'v_ch1': line_v_ch1, 'v_ch2': line_v_ch2, 'v_ch3': line_v_ch3,
            'i_ch1': line_i_ch1, 'i_ch2': line_i_ch2, 'i_ch3': line_i_ch3
        }
        st.session_state.psu_plot_data['fig'] = fig

        # Start background monitoring thread if not already running
        if st.session_state.psu_monitor_thread is None or not st.session_state.psu_monitor_thread.is_alive():
            st.session_state.stop_event = threading.Event()
            st.session_state.psu_monitor_thread = threading.Thread(
                target=psu.psu_monitor_thread,
                args=(
                    psu_com,
                    st.session_state.stop_event,
                    st.session_state.shared_data,
                    st.session_state._psu_data_lock,
                    st.session_state.psu_plot_data,
                    None,
                    None,
                ),
                daemon=True
            )
            st.session_state.psu_monitor_thread.start()
    else:
        # Stop background monitoring thread
        if st.session_state.stop_event:
            st.session_state.stop_event.set()
        if st.session_state.psu_monitor_thread and st.session_state.psu_monitor_thread.is_alive():
            st.session_state.psu_monitor_thread.join(timeout=1)
        time.sleep(0.25)  # Allow some time for thread to stop
        psu.switchPSU(psu_com, st.session_state.state_psu, st.session_state.rov_htr_state, st.session_state.ebmode)
        psu.close_psu_comms(psu_com)
@st.fragment(run_every="1s")
def eb_psu_display(psu_com):
    # Only render the expander if PSU is actually on
    if not (st.session_state.state_eb_psu or st.session_state.state_rov_htr_psu):
        return
    
    with st.expander("PSU Live Data", expanded=True):
        if st.session_state.ebmode:
            # Extract most recent values from deque (list format: [ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i, ch4_v, ch4_i])
            latest_data = st.session_state.psu_queue[-1] if st.session_state.psu_queue else [0] * 8
            ch3_v = latest_data[4]  # ROV HTR Voltage
            ch3_i = latest_data[5]  # ROV HTR Current
            ch4_v = latest_data[6]  # EB Voltage
            ch4_i = latest_data[7]  # EB Current
            
            # Prepare sparkline data
            ch3_v_sparkline = None
            ch3_v_delta = None
            ch3_i_sparkline = None
            ch3_i_delta = None
            ch4_v_sparkline = None
            ch4_v_delta = None
            ch4_i_sparkline = None
            ch4_i_delta = None
            
            if st.session_state.psu_queue:
                try:
                    data = list(st.session_state.psu_queue)
                    
                    def safe_float(value):
                        try:
                            if isinstance(value, str):
                                if value == "N/A" or not value or value.isspace():
                                    return 0.0
                                cleaned = value.strip("VAva")
                                if cleaned and not cleaned.isspace():
                                    return float(cleaned)
                                return 0.0
                            return float(value) if value else 0.0
                        except (ValueError, AttributeError):
                            return 0.0
                    
                    ch3_v_list = [safe_float(reading[4]) for reading in data if len(reading) > 4]
                    ch3_i_list = [safe_float(reading[5]) for reading in data if len(reading) > 5]
                    ch4_v_list = [safe_float(reading[6]) for reading in data if len(reading) > 6]
                    ch4_i_list = [safe_float(reading[7]) for reading in data if len(reading) > 7]
                    
                    if len(ch3_v_list) > 1:
                        ch3_v_delta = round(ch3_v_list[-1] - ch3_v_list[0], 2)
                        ch3_v_sparkline = ch3_v_list
                    if len(ch3_i_list) > 1:
                        ch3_i_delta = round(ch3_i_list[-1] - ch3_i_list[0], 2)
                        ch3_i_sparkline = ch3_i_list
                    if len(ch4_v_list) > 1:
                        ch4_v_delta = round(ch4_v_list[-1] - ch4_v_list[0], 2)
                        ch4_v_sparkline = ch4_v_list
                    if len(ch4_i_list) > 1:
                        ch4_i_delta = round(ch4_i_list[-1] - ch4_i_list[0], 2)
                        ch4_i_sparkline = ch4_i_list
                except (IndexError, TypeError, AttributeError, ValueError):
                    pass
            
            # ROV Heater Metrics - Only show if toggle is on
            if st.session_state.state_rov_htr_psu:
                st.markdown("**ROV Heater (CH3)**")
                rov_col1, rov_col2 = st.columns(2, gap="small", vertical_alignment="center")
                
                with rov_col1:
                    st.metric(
                        "ROV HTR Voltage",
                        value=ch3_v,
                        delta=ch3_v_delta,
                        label_visibility="visible",
                        border=True,
                    )
                
                with rov_col2:
                    st.metric(
                        "ROV HTR Current",
                        value=ch3_i,
                        delta=ch3_i_delta,
                        label_visibility="visible",
                        border=True,
                    )
                
                # ROV Sparkline graphs
                rov_graph1, rov_graph2 = st.columns(2, gap="small")
                
                with rov_graph1:
                    if ch3_v_sparkline and len(ch3_v_sparkline) > 1:
                        fig, ax = plt.subplots(figsize=(5, 1.2), dpi=80)
                        fig.patch.set_alpha(0)
                        ax.patch.set_alpha(0)
                        ax.plot(ch3_v_sparkline, marker='o', color='#ff7f0e', linewidth=1, markersize=1.5)
                        ax.grid(True, alpha=0.2, linestyle='--', color='white')
                        ax.set_xlabel("Reading", fontsize=6, color='white')
                        ax.set_ylabel("V", fontsize=6, color='white')
                        ax.set_ylim(20, 30)
                        ax.tick_params(labelsize=5, colors='white')
                        ax.spines['bottom'].set_color('white')
                        ax.spines['left'].set_color('white')
                        ax.spines['top'].set_visible(False)
                        ax.spines['right'].set_visible(False)
                        st.pyplot(fig, width='content')
                        plt.close(fig)
                
                with rov_graph2:
                    if ch3_i_sparkline and len(ch3_i_sparkline) > 1:
                        fig, ax = plt.subplots(figsize=(5, 1.2), dpi=80)
                        fig.patch.set_alpha(0)
                        ax.patch.set_alpha(0)
                        ax.plot(ch3_i_sparkline, marker='o', color='#d62728', linewidth=1, markersize=1.5)
                        ax.grid(True, alpha=0.2, linestyle='--', color='white')
                        ax.set_xlabel("Reading", fontsize=6, color='white')
                        ax.set_ylabel("A", fontsize=6, color='white')
                        ax.tick_params(labelsize=5, colors='white')
                        ax.spines['bottom'].set_color('white')
                        ax.spines['left'].set_color('white')
                        ax.spines['top'].set_visible(False)
                        ax.spines['right'].set_visible(False)
                        st.pyplot(fig, width='content')
                        plt.close(fig)
                
                st.divider()
            
            # EB Metrics - Only show if toggle is on
            if st.session_state.state_eb_psu:
                st.markdown("**Electronics Box (CH4)**")
                eb_col1, eb_col2 = st.columns(2, gap="small", vertical_alignment="center")
                
                with eb_col1:
                    st.metric(
                        "EB Voltage",
                        value=ch4_v,
                        delta=ch4_v_delta,
                        label_visibility="visible",
                        border=True,
                    )
                
                with eb_col2:
                    st.metric(
                        "EB Current",
                        value=ch4_i,
                        delta=ch4_i_delta,
                        label_visibility="visible",
                        border=True,
                    )
                
                # EB Sparkline graphs
                eb_graph1, eb_graph2 = st.columns(2, gap="small")
                
                with eb_graph1:
                    if ch4_v_sparkline and len(ch4_v_sparkline) > 1:
                        fig, ax = plt.subplots(figsize=(5, 1.2), dpi=80)
                        fig.patch.set_alpha(0)
                        ax.patch.set_alpha(0)
                        ax.plot(ch4_v_sparkline, marker='o', color='#1f77b4', linewidth=1, markersize=1.5)
                        ax.grid(True, alpha=0.2, linestyle='--', color='white')
                        ax.set_xlabel("Reading", fontsize=6, color='white')
                        ax.set_ylabel("V", fontsize=6, color='white')
                        ax.set_ylim(20, 30)
                        ax.tick_params(labelsize=5, colors='white')
                        ax.spines['bottom'].set_color('white')
                        ax.spines['left'].set_color('white')
                        ax.spines['top'].set_visible(False)
                        ax.spines['right'].set_visible(False)
                        st.pyplot(fig, width='content')
                        plt.close(fig)
                
                with eb_graph2:
                    if ch4_i_sparkline and len(ch4_i_sparkline) > 1:
                        fig, ax = plt.subplots(figsize=(5, 1.2), dpi=80)
                        fig.patch.set_alpha(0)
                        ax.patch.set_alpha(0)
                        ax.plot(ch4_i_sparkline, marker='o', color='#2ca02c', linewidth=1, markersize=1.5)
                        ax.grid(True, alpha=0.2, linestyle='--', color='white')
                        ax.set_xlabel("Reading", fontsize=6, color='white')
                        ax.set_ylabel("A", fontsize=6, color='white')
                        ax.set_ylim(0, 0.4)
                        ax.tick_params(labelsize=5, colors='white')
                        ax.spines['bottom'].set_color('white')
                        ax.spines['left'].set_color('white')
                        ax.spines['top'].set_visible(False)
                        ax.spines['right'].set_visible(False)
                        st.pyplot(fig, width='content')
                        plt.close(fig)
        
        else:
            # Extract most recent values from deque (list format: [ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i, ch4_v, ch4_i])
            latest_data = st.session_state.psu_queue[-1] if st.session_state.psu_queue else [0] * 8
            ch1_v = latest_data[0]
            ch1_i = latest_data[1]
            ch2_v = latest_data[2]
            ch2_i = latest_data[3]
            ch3_v = latest_data[4]
            ch3_i = latest_data[5]
            
            # Voltage metrics row
            col_v1, col_v2, col_v3 = st.columns(3)
            
            with col_v1:
                st.metric(
                    "+12V",
                    value=ch1_v,
                    label_visibility="visible",
                )
            
            with col_v2:
                st.metric(
                    "-12V",
                    value=ch2_v,
                    label_visibility="visible",
                )
            
            with col_v3:
                st.metric(
                    "+5V",
                    value=ch3_v,
                    label_visibility="visible",
                )
            
            # Current metrics row
            col_i1, col_i2, col_i3 = st.columns(3)
            
            with col_i1:
                st.metric(
                    "CH1 Current",
                    value=ch1_i,
                    label_visibility="visible",
                )
            
            with col_i2:
                st.metric(
                    "CH2 Current",
                    value=ch2_i,
                    label_visibility="visible",
                )
            
            with col_i3:
                st.metric(
                    "CH3 Current",
                    value=ch3_i,
                    label_visibility="visible",
                )
            
            # Plot row - full width (only redraw if data changed)
            st.divider()

            if st.session_state.psu_queue:
                data = list(st.session_state.psu_queue)
                
                def safe_float(value):
                    try:
                        if isinstance(value, str):
                            if value == "N/A" or not value or value.isspace():
                                return 0.0
                            # Try to strip units and convert
                            cleaned = value.strip("VAva")
                            if cleaned and not cleaned.isspace():
                                return float(cleaned)
                            return 0.0
                        return float(value) if value else 0.0
                    except (ValueError, AttributeError):
                        return 0.0
                
                ch1_v_history = [safe_float(reading[0]) for reading in data]
                ch1_i_history = [safe_float(reading[1]) for reading in data]
                ch2_v_history = [safe_float(reading[2]) for reading in data]
                ch2_i_history = [safe_float(reading[3]) for reading in data]
                ch3_v_history = [safe_float(reading[4]) for reading in data]
                ch3_i_history = [safe_float(reading[5]) for reading in data]
                
                fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, figsize=(16, 10))
        
                # Channel 1 Voltage plot
                ax1.plot(ch1_v_history, marker='o', color='red', linewidth=2)
                ax1.set_title("CH1 Voltage Over Time")
                ax1.set_ylabel("Voltage (V)")
                ax1.set_xlabel("Reading #")
                ax1.grid(True, alpha=0.1)
                ax1.axhline(y=12, color='r', linestyle='--', alpha=0.1, label='Target: 12V')
                ax1.legend()
                
                # Channel 1 Current plot
                ax2.plot(ch1_i_history, marker='o', color='red', linewidth=2)
                ax2.set_title("CH1 Current Over Time")
                ax2.set_ylabel("Current (A)")
                ax2.set_xlabel("Reading #")
                ax2.grid(True, alpha=0.3)
                ax2.legend()
                
                # Channel 2 Voltage plot
                ax3.plot(ch2_v_history, marker='o', color='blue', linewidth=2)
                ax3.set_title("CH2 Voltage Over Time")
                ax3.set_ylabel("Voltage (V)")
                ax3.set_xlabel("Reading #")
                ax3.grid(True, alpha=0.1)
                ax3.axhline(y=-12, color='b', linestyle='--', alpha=0.1, label='Target: -12V')
                ax3.legend()
                
                # Channel 2 Current plot
                ax4.plot(ch2_i_history, marker='o', color='blue', linewidth=2)
                ax4.set_title("CH2 Current Over Time")
                ax4.set_ylabel("Current (A)")
                ax4.set_xlabel("Reading #")
                ax4.grid(True, alpha=0.3)
                ax4.legend()
                
                # Channel 3 Voltage plot
                ax5.plot(ch3_v_history, marker='o', color='green', linewidth=2)
                ax5.set_title("CH3 Voltage Over Time")
                ax5.set_ylabel("Voltage (V)")
                ax5.set_xlabel("Reading #")
                ax5.grid(True, alpha=0.1)
                ax5.axhline(y=5, color='g', linestyle='--', alpha=0.1, label='Target: 5V')
                ax5.legend()
                
                # Channel 3 Current plot
                ax6.plot(ch3_i_history, marker='o', color='green', linewidth=2)
                ax6.set_title("CH3 Current Over Time")
                ax6.set_ylabel("Current (A)")
                ax6.set_xlabel("Reading #")
                ax6.grid(True, alpha=0.3)
                ax6.legend()
                
                st.pyplot(fig)

# EB Log File Handling -----------------------------------------------------------------------------
@st.fragment(run_every="0.25s")
def eb_log_parser(file_path):
    
    # Only proceed if a valid file path is provided
    if st.session_state.eb_filepath is not None:
        # Read packets from the log file
        result = eb.read_pkt(st.session_state.eb_filepath)
        if result is not None:
            raw_bytes, post_bytes, tm_index = result
            # Check if this is a new packet (different index than last one)
            if raw_bytes is not None and tm_index != st.session_state.last_tm_index:                 
                parsed = eb.parse_eb_hk(raw_bytes)
                if parsed is not None:
                    # Store the parsed data in session state, don't display here
                    st.session_state.last_hk = parsed
                    st.session_state.last_tm_index = tm_index
            if post_bytes is not None and tm_index != st.session_state.last_post_index:                 
                parsed = eb.decode_post_hk(post_bytes)
                if parsed is not None:
                    # Store the parsed data in session state, don't display here
                    st.session_state.last_post = parsed
                    st.session_state.last_post_index = tm_index
    else:
        st.write("No log file selected")
def eb_log_filepicker():
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Bring dialog to front
        dir_path = filedialog.askdirectory(
            title="Select log file directory",
        )
        root.destroy()
        if dir_path:
            st.session_state.eb_log_directory = dir_path
    except Exception as e:
        st.error(f"Error opening directory dialog: {e}")

def select_egse_script():
    if not st.session_state.get("egse_started", False):
        st.session_state.show_egse_script_warning = True
        return
    egse_script_filepicker()
def egse_script_filepicker():
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Bring dialog to front
        file_path = filedialog.askopenfilename(
            title="Select EGSE script file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        root.destroy()
        if file_path:
            st.session_state.egse_script_path = file_path
            
            # Extract filename and send command to CmdTool
            script_filename = Path(file_path).name
            script_arg = f"@{script_filename}"
            
            # Send the command to CmdTool
            egse_interface.send_command_to_cmdtool(script_arg, wait_for_window=0.5, send_enter=True)
    except Exception:
        pass
@st.fragment(run_every="0.5s")
def display_post_info():
    if st.session_state.eb_filepath:
        st.write(f"Current EB Log File: {st.session_state.eb_filepath}")
        
        last_hk = st.session_state.get("last_hk")
        if last_hk:
            sft_mode = st.session_state.get("sft_mode")
            checks_enabled = sft_mode in ["Safe Mode Checks", "Standby Mode Checks"]
            expected_state_label = "STANDBY" if sft_mode == "Standby Mode Checks" else "SAFE"
            tcs_accepted_expected = 2 if sft_mode == "Standby Mode Checks" else 1
            instr_status_expected = 25604 if sft_mode == "Standby Mode Checks" else 6
            include_software_versions = sft_mode != "Standby Mode Checks"

            st.subheader("📊 Regular HK Packet Parameters")
            
            # Operating state mapping
            op_state_map = {0x00: "INITIALISING", 0x02: "SAFE", 0x04: "STANDBY", 0x08: "ACQUISITION"}
            op_state_name = op_state_map.get(last_hk.CURRENT_OPERATING_STATE, f"UNKNOWN(0x{last_hk.CURRENT_OPERATING_STATE:02X})")
            
            # Create check list with raw values and conversion factors
            hk_raw_data = [
                ("TC's Accepted", last_hk.TCS_ACCEPTED, tcs_accepted_expected, "==", None),
                ("TC's Rejected", last_hk.TCS_REJECTED, 0, "==", None),
                ("Instrument Status Flags", last_hk.INSTRUMENT_STATUS_FLAGS, instr_status_expected, "==", None),
                ("Current Operating State", op_state_name, expected_state_label, "==", None),
                ("Error Flags", last_hk.ERROR_FLAGS, 0, "==", None),
                ("Warning Flags", last_hk.WARNING_FLAGS, 0, "==", None),
                ("EB +12V (V)", last_hk.EB_MEAS_MAIN_12V, (11.0, 13.0), "range", 0.0004005),
                (
                    "EB -12V (V)",
                    last_hk.EB_MEAS_MAIN_NEG12V,
                    (-13.0, -11.0),
                    "range",
                    0.00038147,
                ),
                ("EB +5V (V)", last_hk.EB_MEAS_5V, (4.5, 5.5), "range", 0.000153),
                ("EB +3V3 (V)", last_hk.EB_MEAS_3V3, (2.8, 3.8), "range", 0.0000763),
                ("EB TEC_V (V)", last_hk.EB_MEAS_TEC_RAIL, (-0.5, 0.5), "range", 0.0000763),
                ("EB 0V (V)", last_hk.EB_0V_ADC_READING, (-0.5, 0.5), "range", 0.0000763),
                ("EB MCU Internal Temp (°C)", last_hk.EB_MCU_INTERNAL_TEMP, (18.0, 43.0), "mcu_temp", None),
                ("EB Peltier Temp (°C)", last_hk.EB_PELTIER_TEMP, (18.0, 43.0), "peltier_temp", None),
                ("EB Internal TRP Temp (°C)", last_hk.EB_INTERNAL_TRP_TEMP, (18.0, 43.0), "thermistor", None),
                ("EB PSU Board Temp (°C)", last_hk.EB_PSU_BOARD_TEMP, (18.0, 43.0), "thermistor", None),
                ("EB TEC Drive Current (A)", last_hk.EB_TEC_DRIVE_CURRENT, (-0.1, 0.1), "range", 0.0000162),
            ]

            if include_software_versions:
                hk_raw_data.extend([
                    ("Software Major Version", last_hk.SOFTWARE_MAJOR_VERSION, 2, "==", None),
                    ("Software Minor Version", last_hk.SOFTWARE_MINOR_VERSION, 0, "==", None),
                    ("Software Patch Version", last_hk.SOFTWARE_PATCH_VERSION, 4, "==", None),
                ])
            if sft_mode == "Standby Mode Checks":
                selected_label = st.session_state.get("selected_ob_model")
                selected_model_id = st.session_state.ob_model_options.get(selected_label)
                expected_ob_hk_id = (selected_model_id << 5) if selected_model_id is not None else None
                ob_hk_id = getattr(last_hk, "OB_HK_ID", None)
                if ob_hk_id is not None:
                    actual_model_id = (ob_hk_id >> 5) & 0x7
                else:
                    actual_model_id = None
                hk_raw_data.extend([
                    ("Software Major Version", last_hk.SOFTWARE_MAJOR_VERSION, 3, "==", None),
                    ("Software Minor Version", last_hk.SOFTWARE_MINOR_VERSION, 2, "==", None),
                    ("Software Patch Version", last_hk.SOFTWARE_PATCH_VERSION, 8, "==", None),
                    ("OB HK ID", ob_hk_id, expected_ob_hk_id, "==", None),
                    ("OB Model ID", actual_model_id, selected_model_id, "==", None),
                    ("OB Command Count", last_hk.OB_COMMAND_COUNT, 8, "==", None),
                ])
            
            # Process checks and determine pass/fail
            all_hk_passed = True
            hk_display_data = []
            
            for param_name, value, expected, check_type, conversion in hk_raw_data:
                if check_type == "==":
                    within_limits = value == expected
                    display_value = str(value)
                    display_expected = str(expected)
                elif check_type == "range":
                    converted_value = value * conversion
                    # Negate -12V for proper display and comparison
                    if "-12V" in param_name:
                        converted_value = -converted_value
                    # Peltier sign depends on selected SFT mode
                    if "Peltier" in param_name and sft_mode != "Standby Mode Checks":
                        converted_value = -converted_value
                    min_val, max_val = expected
                    within_limits = min_val <= converted_value <= max_val
                    
                    # Extract unit from parameter name (everything after last parenthesis)
                    if "(" in param_name and ")" in param_name:
                        unit = param_name[param_name.rfind("(")+1:param_name.rfind(")")]
                    else:
                        unit = ""
                    
                    display_value = f"{converted_value:.4g} {unit}".strip()
                    display_expected = f"{min_val} - {max_val} {unit}".strip()
                elif check_type == "thermistor":
                    # Use B-parameter equation for thermistor conversion
                    converted_value = convert_thermistor_b_parameter(value)
                    min_val, max_val = expected
                    within_limits = min_val <= converted_value <= max_val
                    
                    # Extract unit from parameter name
                    if "(" in param_name and ")" in param_name:
                        unit = param_name[param_name.rfind("(")+1:param_name.rfind(")")]
                    else:
                        unit = ""
                    
                    display_value = f"{converted_value:.4g} {unit}".strip()
                    display_expected = f"{min_val} - {max_val} {unit}".strip()
                elif check_type == "mcu_temp":
                    # MCU internal temperature conversion: (ADU * 0.01637198) - 273
                    converted_value = (value * 0.01637198) - 273
                    min_val, max_val = expected
                    within_limits = min_val <= converted_value <= max_val
                    
                    # Extract unit from parameter name
                    if "(" in param_name and ")" in param_name:
                        unit = param_name[param_name.rfind("(")+1:param_name.rfind(")")]
                    else:
                        unit = ""
                    
                    display_value = f"{converted_value:.4g} {unit}".strip()
                    display_expected = f"{min_val} - {max_val} {unit}".strip()
                elif check_type == "peltier_temp":
                    # EB Peltier temperature conversion: (ADU * -0.001830011) + 51.27039922
                    converted_value = (value * -0.001830011) + 51.27039922
                    min_val, max_val = expected
                    within_limits = min_val <= converted_value <= max_val
                    
                    # Extract unit from parameter name
                    if "(" in param_name and ")" in param_name:
                        unit = param_name[param_name.rfind("(")+1:param_name.rfind(")")]
                    else:
                        unit = ""
                    
                    display_value = f"{converted_value:.4g} {unit}".strip()
                    display_expected = f"{min_val} - {max_val} {unit}".strip()
                else:
                    within_limits = False
                    display_value = str(value)
                    display_expected = str(expected)
                
                if not checks_enabled:
                    within_limits = None
                else:
                    if not within_limits:
                        all_hk_passed = False
                
                hk_display_data.append((param_name, display_value, display_expected, within_limits))
            
            # Display test result at top
            if checks_enabled:
                if all_hk_passed:
                    st.success("✅ HK TEST PASSED")
                else:
                    st.error("❌ HK TEST FAILED")
            else:
                st.info("ℹ️ HK checks not selected")
            
            # Create columns for table display
            col1, col2, col3 = st.columns([2, 1.5, 1.5])
            with col1:
                st.write("**Parameter**")
            with col2:
                st.write("**Recorded**")
            with col3:
                st.write("**Expected**")
            
            st.divider()
            
            for param_name, display_value, display_expected, within_limits in hk_display_data:
                col1, col2, col3 = st.columns([2, 1.5, 1.5])
                with col1:
                    st.write(param_name)
                with col2:
                    if within_limits is None:
                        badge = f":violet-badge[{display_value}]"
                    else:
                        badge = f":green-badge[{display_value}]" if within_limits else f":red-badge[{display_value}]"
                    st.markdown(badge)
                with col3:
                    st.write(display_expected)
        else:
            st.info("⏳ Waiting for HK packet...")
        
        # Display POST packet checks (from SAFE mode CSV)
        st.divider()
        st.subheader("📦 POST Packet Parameters")
        last_post = st.session_state.get("last_post")
        if last_post:
            
            post_checks = [
                ("POST Warning Flags", last_post.POST_WARNING_FLAGS, 0, "=="),
                ("POST Error Flags", last_post.POST_ERROR_FLAGS, 0, "=="),
                ("Num Bad Flash Blocks", last_post.NUM_BAD_FLASH_BLOCKS, 0, "=="),
                ("Num Bad SRAM Blocks", last_post.NUM_BAD_SRAM_BLOCKS, 0, "=="),
                ("ASW Image#1 CRC", f"0x{last_post.ASW_IMAGE_1_CRC:04X}", "0xBAF7", "=="),
                ("ASW Image#2 CRC", f"0x{last_post.ASW_IMAGE_2_CRC:04X}", "0x5C55", "=="),
                ("ASW Image#3 CRC", f"0x{last_post.ASW_IMAGE_3_CRC:04X}", "0x01CB", "=="),
                ("ASW Image#4 CRC", f"0x{last_post.ASW_IMAGE_4_CRC:04X}", "0x5318", "=="),
                ("ASW Image#5 CRC", f"0x{last_post.ASW_IMAGE_5_CRC:04X}", "0xDCAE", "=="),
                ("BSW Image CRC", f"0x{last_post.BSW_IMAGE_CRC:04X}", "0xD2D7", "=="),
                ("Measurement Table CRC", f"0x{last_post.MEASUREMENT_TABLE_CRC:04X}", "0x9D9B", "=="),
            ]
            
            # Process checks and determine pass/fail
            all_post_passed = True
            post_display_data = []
            
            for param_name, recorded, expected, check_type in post_checks:
                within_limits = str(recorded).lower() == str(expected).lower()
                if not checks_enabled:
                    within_limits = None
                else:
                    if not within_limits:
                        all_post_passed = False
                post_display_data.append((param_name, str(recorded), str(expected), within_limits))
            
            # Display test result at top
            if checks_enabled:
                if all_post_passed:
                    st.success("✅ POST TEST PASSED")
                else:
                    st.error("❌ POST TEST FAILED")
            else:
                st.info("ℹ️ POST checks not selected")
            
            # Create columns for table display
            col1, col2, col3 = st.columns([2, 1.5, 1.5])
            with col1:
                st.write("**Parameter**")
            with col2:
                st.write("**Recorded**")
            with col3:
                st.write("**Expected**")
            
            st.divider()
            
            for param_name, recorded, expected, within_limits in post_display_data:
                col1, col2, col3 = st.columns([2, 1.5, 1.5])
                with col1:
                    st.write(param_name)
                with col2:
                    if within_limits is None:
                        badge = f":violet-badge[{recorded}]"
                    else:
                        badge = f":green-badge[{recorded}]" if within_limits else f":red-badge[{recorded}]"
                    st.markdown(badge)
                with col3:
                    st.write(expected)
        else:
            st.info("⏳ Waiting for POST HK packet...")
def start_egse_tools():
    try:
        button_press_time = time.time()
        if egse_interface.start_egse():
            st.success("✓ EGSE tools started successfully")
            st.session_state.egse_started = True
            
            # Wait 5 seconds for tools to initialize and create log file
            time.sleep(5)
            
            # Look for the latest RS422if log file created after button press
            log_folder = egse_interface.egse_path / "RS422if_log"
            
            if log_folder.exists():
                log_files = sorted(log_folder.glob("RS422if_*.log"), key=os.path.getmtime, reverse=True)
                # Filter for files created after the button was pressed
                recent_logs = [f for f in log_files if os.path.getmtime(f) > button_press_time]
                
                if recent_logs:
                    latest_log = recent_logs[0]
                    st.session_state.eb_filepath = str(latest_log)
                    st.info(f"📋 Using latest log: {latest_log.name}")
                elif log_files:
                    # Fallback to latest if no recent logs found
                    latest_log = log_files[0]
                    st.session_state.eb_filepath = str(latest_log)
                    st.warning(f"⚠ Using existing log (no new log created): {latest_log.name}")
                else:
                    st.warning(f"⚠ No RS422if log files found in {log_folder}")
            else:
                st.warning(f"⚠ Log folder not found: {log_folder}")
        else:
            st.error("✗ Failed to start EGSE tools")
    except Exception as e:
        traceback.print_exc()
        st.error(f"✗ Error starting EGSE: {str(e)}")
def get_cmdtool_display():
    try:
        # Get the EGSE path
        egse_path = egse_interface.egse_path
        
        # Look for .log files in the EGSE directory
        log_files = glob.glob(os.path.join(egse_path, "*.log"))
        
        if not log_files:
            return "⚠ No log files found in EGSE directory"
        
        # Get the most recent log file by modification time
        latest_log = max(log_files, key=os.path.getmtime)
        log_filename = os.path.basename(latest_log)
        
        # Get file modification time for display
        mod_time = os.path.getmtime(latest_log)
        mod_datetime = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        
        # Read all lines of the log file
        try:
            with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
                # Get all lines and ensure proper line endings
                # Strip trailing whitespace from each line and rejoin with \n
                # Also escape HTML characters for safe display
                content = '\n'.join(html.escape(line.rstrip('\r\n')) for line in lines)
                
                header = f"📋 {html.escape(log_filename)}\n🕒 Last modified: {mod_datetime}\n📊 Showing {len(lines)} lines\n{'='*60}\n"
                return header + content
        except Exception as e:
            return f"❌ Error reading log file: {str(e)}"
        
    except Exception as e:
        traceback.print_exc()
        return f"❌ Error finding log file: {str(e)}"
def stop_egse_tools():
    try:
        if egse_interface.stop_egse():
            st.success("✓ EGSE tools stopped successfully")
            st.session_state.egse_started = False
        else:
            st.error("✗ Failed to stop EGSE tools")
    except Exception as e:
        st.error(f"✗ Error stopping EGSE: {str(e)}")
def resume_cmdtool():
    try:
        # Find CmdTool window
        try:
            window = find_window(title_re="CmdTool")
        except Exception:
            return
        
        # Connect to the window
        try:
            app = Application(backend='uia').connect(handle=window)
            main_window = app.window(handle=window)
            
            # Bring window to foreground
            main_window.set_focus()
            time.sleep(0.3)
            
            # Get all descendants
            descendants = main_window.descendants()
            
            # Find Button controls (Controls 8 and 9 should be Pause and Abort)
            button_controls = [ctrl for ctrl in descendants if ctrl.class_name() == 'Button']
            
            if button_controls:
                # Click the second button (Pause/Resume) - first is Abort
                pause_button = button_controls[1]
                pause_button.click_input()
                time.sleep(0.5)
        except Exception:
            pass
    except Exception:
        pass
@st.fragment(run_every="0.25s")
def cmd_tool_display_monitor():
    if st.session_state.get('egse_started', False):
            # Get and display CmdTool content
            cmdtool_text = get_cmdtool_display()
            
            # Track modification time for display and pause detection
            egse_path = egse_interface.egse_path
            log_files = glob.glob(os.path.join(egse_path, "*.log"))
            
            if log_files:
                latest_log = max(log_files, key=os.path.getmtime)
                current_mtime = os.path.getmtime(latest_log)
                
                # Detect pause: if mtime hasn't changed for more than 2 seconds, it's paused
                if current_mtime == st.session_state.last_log_mtime:
                    # Log file hasn't been updated
                    time_since_update = time.time() - st.session_state.last_mtime_update_time
                    
                    # If 2+ seconds have passed without update and pause not yet detected, run SFT checks
                    if time_since_update >= 2.0 and not st.session_state.log_pause_detected:
                        st.session_state.log_pause_detected = True
                        
                        # Run SFT checks if we have HK data
                        if st.session_state.last_hk is not None:
                            post_hk = st.session_state.get('last_post', None)
                            sft_mode = st.session_state.get("sft_mode")
                            selected_label = st.session_state.get("selected_ob_model")
                            selected_model_id = st.session_state.ob_model_options.get(selected_label)
                            sft_pass, sft_message = eb_sft_checks.check_sft(
                                st.session_state.last_hk,
                                post_hk,
                                mode=sft_mode,
                                expected_model_id=selected_model_id,
                            )
                            
                            # Display SFT check result
                            if sft_pass:
                                st.success(f"✓ SFT Check PASSED: {sft_message}")
                            else:
                                st.error(f"✗ SFT Check FAILED: {sft_message}")
                else:
                    # Log file was updated, reset pause detection
                    st.session_state.last_log_mtime = current_mtime
                    st.session_state.last_mtime_update_time = time.time()
                    st.session_state.log_pause_detected = False
            
            # Create a scrollable container with auto-scroll to bottom
            st.markdown("""
                <style>
                .scrollable-log {
                    height: 400px;
                    overflow-y: auto;
                    background-color: #0e1117;
                    border: 1px solid #262730;
                    border-radius: 5px;
                    padding: 10px;
                    font-family: monospace;
                    font-size: 12px;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    color: #fafafa;
                }
                </style>
            """, unsafe_allow_html=True)
            
            # Display with scrollable div, using a unique key to force scroll to bottom
            scroll_key = st.session_state.get('last_log_mtime', 0)
            st.markdown(
                f'<div class="scrollable-log" id="log-{scroll_key}">{cmdtool_text}</div>',
                unsafe_allow_html=True
            )
            
            # Auto-scroll to bottom using JavaScript
            st.markdown(f"""
                <script>
                    var element = document.getElementById('log-{scroll_key}');
                    if (element) {{
                        element.scrollTop = element.scrollHeight;
                    }}
                </script>
            """, unsafe_allow_html=True)
    else:
        st.info("ℹ️ Start EGSE tools first to view display")
  
def eb_Fragment():
    st.divider()
    col1, col2, col3, col4 = st.columns(4, vertical_alignment="center", gap ="small")
    col1.button("Select EGSE Script", key = "egse_script", on_click=select_egse_script)
    col2.button("Start EB EGSE Tools", key = "start_tools", on_click=start_egse_tools)
    col3.button("Stop EB EGSE Tools", key = "stop_tools", on_click=stop_egse_tools)
    col4.button("Resume", key="resume_btn", on_click=resume_cmdtool)
    
    # Display selected script
    if hasattr(st.session_state, 'egse_script_path') and st.session_state.egse_script_path:
        st.caption(f"Script: {Path(st.session_state.egse_script_path).name}")
    else:
        st.caption("No script selected")

    with st.expander("EB TM Info", expanded=True):
        st.pills(
            "SFT Mode",
            ["Safe Mode Checks", "Standby Mode Checks"],
            selection_mode="single",
            key="sft_mode",
        )
        ob_model_labels = list(st.session_state.ob_model_options.keys())
        st.selectbox(
            "OB Model",
            ob_model_labels,
            key="selected_ob_model",
        )
        if st.session_state.eb_filepath:
            display_post_info()
        else:
            st.write("No EB Log File Selected")

    # CmdTool display monitor
    with st.expander("CmdTool Display Monitor", expanded=True):
        cmd_tool_display_monitor()
    
# Main execution
if __name__ == "__main__":
    # Default parameters - modify as needed
    init(ebmode=True, nopsu=True, rs485_com="COM5", psu_com="COM4")