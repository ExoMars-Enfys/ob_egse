# Std library
import logging
from tkinter import filedialog
import serial.rs485
import comms
import time
from pathlib import Path
from collections import deque
import tkinter as tk

# Added packages
import constants as const
import pandas as pd
import streamlit as st
from streamlit_extras.grid import grid
import matplotlib.pyplot as plt
import threading

# Project imports
import tc as tc
import psu
import hk_sniffer as eb

state_pwr_dict = {"OFF" : 0, "Mech Only": 1, "Detec Only": 2, "Both": 3}

event_log = logging.getLogger("event_log")
info_log = logging.getLogger("info_log")

st.set_page_config(page_title = "Enfys EGSE v3.0" , page_icon="./rsrc/ExoMars_Logo_PNG.png",initial_sidebar_state="expanded", layout="wide")

# Global State Initialisation ----------------------------------------------------------------------
def st_state_initialise() -> None:
    if "comms_active" not in st.session_state:
        st.session_state.comms_active = False
    if "count" not in st.session_state:
        st.session_state.count = 0
    if "state_psu" not in st.session_state:
        st.session_state.state_psu = False
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

@st.cache_resource
def port_init(rs485_com, psu_com):
    rs485port = comms.initialise_comms(rs485_com)
    rs485port = comms.open_comms(rs485port)        
    psuport = psu.init_psu_comms(psu_com)
    psuport = psu.open_psu_comms(psuport, False)
    return rs485port, psuport
# Streamlit Page setup -----------------------------------------------------------------------------
def init(ebmode, rs485_com, psu_com) -> None:
    
    """Initialises the streamlit GUI"""
    st_state_initialise()
    st.session_state.rs485port, st.session_state.psuport = port_init(rs485_com, psu_com)
    st.session_state.ebmode = ebmode    
    main_gui()
    with st.sidebar:
        st.image(Path("./rsrc/Enfys_logo.jpg", size="small", width=50))
        if not st.session_state.ebmode:
            check_for_new_tm()
        else:
            eb_log_parser(st.session_state.eb_filepath)
            check_for_new_tm()

@st.fragment()
def  main_gui() -> None:
    if st.session_state.ebmode: 
        st.title("Enfys EGSE v3.0")               
        col1, col2, col3 = st.columns(3)             
        col1.write("EB PSU Status")
        col1.toggle(label="PSU Switch", key="state_psu", on_change=psu_toggle, args=(st.session_state.psuport,))
        time.sleep(1)
        if st.session_state.state_psu:
            
            st.session_state.stop_event = threading.Event()
            st.session_state.psu_thread = threading.Thread(
                target=psu.psu_monitor_thread, args=(st.session_state.psuport, st.session_state.stop_event,const.PSU_LOGGING_FREQ, True), daemon=True
            )
            st.session_state.psu_thread.start()
            st.session_state.psu_queue = const.psu_queue
            psu_display(st.session_state.psuport)
        else:
            st.write("PSU is OFF")
            if st.session_state.stop_event is not None:
                st.session_state.stop_event.set()
                st.session_state.psu_thread.join(timeout=1.0)  # Wait for the PSU monitor thread to finish
        eb_Fragment()
            
        
    else:
        st.write("PSU Status")    
        col1, col2, col3 = st.columns(3)
        col1.toggle(label="PSU Switch", key="state_psu", on_change=psu_toggle, args=(st.session_state.psuport,))
        if st.session_state.state_psu:
            psu_display(st.session_state.psuport)
        else:
            st.write("PSU is OFF")
        st.divider()  

        coltc, coltm = st.columns([0.3, 0.7])
        age = coltm.slider("How old are you?", 0, 130, 25)

        pwr_options = list(state_pwr_dict.keys())
        selection = st.pills("Power Options", pwr_options, selection_mode="single", key="pwr_pill", on_change=on_pills_change_pwr)

# TM BackEnd Handling ------------------------------------------------------------------------------
@st.fragment(run_every=1)
def check_for_new_tm() -> None:
    try:
        if not st.session_state.ebmode:
            st.session_state.last_hk = const.hk_queue.pop()
        # For EB mode, last_hk is already set by eb_log_parser()
        if st.session_state.last_hk is not None:
            top_level_status(st.session_state.last_hk)
    except IndexError:
        return

def top_level_status(last_hk) -> None:
    dashboard_grid = grid(1,6,1,4,1,4,1,6,gap="small", vertical_align="center")
    dashboard_grid.write("Voltages")
    dashboard_grid.markdown(f"+12V:\n {(last_hk.EB_MEAS_MAIN_12V * 0.000400543):.2f}V", width="content")
    dashboard_grid.markdown(f"-12V:\n {(last_hk.EB_MEAS_MAIN_NEG12V * 0.00038147):.2f}V", width="content")
    dashboard_grid.markdown(f"+5V:\n {(last_hk.EB_MEAS_5V * 0.000152829):.2f}V", width="content")
    dashboard_grid.markdown(f"+3V3:\n {(2 *last_hk.OB_3V3_VOLTAGE /1000):.2f}V", width="content")
    dashboard_grid.markdown(f"+1V5:\n {(last_hk.OB_1V5_VOLTAGE / 1000):.2f}V", width="content")
    dashboard_grid.markdown(f"0V:\n {(last_hk.EB_0V_ADC_READING / 1000):.2f}V", width="content")
    dashboard_grid.write("Temperatures")
    dashboard_grid.markdown(f"Digital:\n {(last_hk.OB_DIGITAL_TRP / 100):.2f}°C", width="content")
    dashboard_grid.markdown(f"Detector:\n {(last_hk.OB_DETECTOR_TRP / 100):.2f}°C", width="content")
    dashboard_grid.markdown(f"Mechanism:\n {(last_hk.OB_MECHANISM_TRP / 100):.2f}°C", width="content")
    dashboard_grid.markdown(f"Motor:\n {(last_hk.OB_MOTOR_TRP / 100):.2f}°C", width="content")
    dashboard_grid.write("Hk snapshot")
    dashboard_grid.markdown(":green-badge[OB Enabled]" if (last_hk.INSTR_STATUS_FLAGS.OB_5V_ENABLED & 0x01) == 1 else ":gray-badge[OB Disabled]", width="content")    
    dashboard_grid.markdown(f"CMD Count:\n {last_hk.OB_COMMAND_COUNT}", width="content")
    dashboard_grid.markdown(f"Rel Steps:\n {last_hk.OB_MOTOR_REL_STEPS}", width="content")
    dashboard_grid.markdown(f"ABS Steps:\n {last_hk.OB_MOTOR_ABS_STEPS}", width="content")
    dashboard_grid.write("Motor Status")
    dashboard_grid.markdown(":green-badge[Calibrated]" if (last_hk.MTR_FLAGS.CAL & 0x01) == 1 else ":gray-badge[Not Calibrated]", width="content")
    dashboard_grid.markdown(":purple-badge[Towards Base]") if (last_hk.MTR_FLAGS.DIR & 0x01) == 1 else dashboard_grid.markdown(":blue-badge[Towards Outer]", width="content")
    dashboard_grid.markdown(":green-badge[At Outer]" if (last_hk.MTR_FLAGS.OUTER & 0x01) == 1 else ":gray-badge[At Outer]", width="content")
    dashboard_grid.markdown(":green-badge[At Base]" if (last_hk.MTR_FLAGS.BASE & 0x01) == 1 else ":gray-badge[At Base]", width="content")
    dashboard_grid.markdown(":green-badge[Motor Moving]" if (last_hk.MTR_FLAGS.MOVING & 0x01) == 1 else ":gray-badge[Motor Stationary]", width="content")    
    dashboard_grid.markdown(":green-badge[Homing]" if (last_hk.MTR_FLAGS.HOMING & 0x01) == 1 else ":gray-badge[Not Homing]", width="content")
    # Power and Heater Status
    stat_grid = grid(2, 2, 1, 2, 2, vertical_align="center")
    write_pwr_stat(last_hk, stat_grid)

    st.divider()
    st.markdown("**Errors**")
    err_grid = grid(6,6,gap = "small",vertical_align="center")
    write_errors(last_hk, err_grid)

def write_errors(last_hk, err_grid) -> None:

    err_ipi = ":green-badge[IPI]" if (last_hk.ERRORS.IPI & 0x01) == 0 else ":red-badge[IPI]"
    err_ios = ":green-badge[IOS]" if (last_hk.ERRORS.IOS & 0x01) == 0 else ":red-badge[IOS]"
    err_icr = ":green-badge[ICR]" if (last_hk.ERRORS.ICR & 0x01) == 0 else ":red-badge[ICR]"
    err_mor = ":green-badge[MOR]" if (last_hk.ERRORS.MOR & 0x01) == 0 else ":red-badge[MOR]"
    err_tmo = ":green-badge[TMO]" if (last_hk.ERRORS.TMO & 0x01) == 0 else ":red-badge[TMO]"
    err_ipa = ":green-badge[IPA]" if (last_hk.ERRORS.IPA & 0x01) == 0 else ":red-badge[IPA]"

    err_grid.markdown(err_ipi)
    err_grid.markdown(err_ios)
    err_grid.markdown(err_icr)
    err_grid.markdown(err_mor)
    err_grid.markdown(err_tmo)
    err_grid.markdown(err_ipa)

    err_cd = ":green-badge[CD]" if (last_hk.MTR_ERRORS.CD & 0x01) == 0 else ":red-badge[CD]"
    err_ab = ":green-badge[AB]" if (last_hk.MTR_ERRORS.AB & 0x01) == 0 else ":red-badge[AB]"
    err_abs = ":green-badge[ABS]" if (last_hk.MTR_ERRORS.ABS & 0x01) == 0 else ":red-badge[ABS]"
    err_dse = ":green-badge[DSE]" if (last_hk.MTR_ERRORS.DSE & 0x01) == 0 else ":red-badge[DSE]"

    err_grid.markdown(err_cd)
    err_grid.markdown(err_ab)
    err_grid.markdown(err_abs)
    err_grid.markdown(err_dse)


def write_pwr_stat(last_hk, grid) -> None:
    st_mec = ":grey-badge[MECH OFF]" if (last_hk.OB_POWER_STATUS & 0x01) == 0 else ":green-badge[MECH ON]"
    st_det = ":gray-badge[DETEC OFF]" if (last_hk.OB_POWER_STATUS & 0x02) == 0 else ":green-badge[DETEC ON]"
    st_mec_htr = (
        ":gray-badge[MECH HTR OFF]" if (last_hk.THRM_STATUS.HMS & 0x01) == 0 else ":red-badge[MECH HTR ON]"
    )
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

    grid.markdown(st_mec)
    grid.markdown(st_det)
    # Row 2
    grid.markdown(st_mec_htr)
    grid.markdown(st_det_htr)
    # Row 3
    grid.markdown(st_sci)
    # Row 4
    grid.markdown(st_mec_man)
    grid.markdown(st_mec_auto)
    # Row 5
    grid.markdown(st_det_man)
    grid.markdown(st_det_auto)

# TC Pills Handling --------------------------------------------------------------------------------
def on_pills_change_pwr():
    # Write to new power state
    selected_key = st.session_state.pwr_pill
    if selected_key:
        pwr_value = state_pwr_dict[selected_key]
        tc.power_control(st.session_state.rs485port, pwr_value)

# PSU BackEnd Handling -----------------------------------------------------------------------------
def psu_toggle(psu_com: serial.Serial):    
    if st.session_state.state_psu:
        # Try to open port if it's closed
        if not psu_com.is_open:
            psu.open_psu_comms(psu_com, psu_not_required=False)
        
        if not st.session_state.ebmode:
            psu.setChannels(psu_com, const.CH1_OVP, const.CH1_I, const.CH2_OVP, const.CH2_I, const.CH3_OVP, const.CH3_I)
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
                    target=psu_monitor_thread_func,
                    args=(psu_com, st.session_state.stop_event, st.session_state.shared_data, st.session_state._psu_data_lock, st.session_state.psu_plot_data),
                    daemon=True
                )
                st.session_state.psu_monitor_thread.start()
        else : 
            psu.setChannels(psu_com,st.session_state.ebmode)
            psu.switchPSU(psu_com, st.session_state.state_psu,st.session_state.ebmode)    
    else:
        # Stop background monitoring thread
        if st.session_state.stop_event:
            st.session_state.stop_event.set()
        if st.session_state.psu_monitor_thread and st.session_state.psu_monitor_thread.is_alive():
            st.session_state.psu_monitor_thread.join(timeout=1)
        time.sleep(0.25)  # Allow some time for thread to stop
        psu.switchPSU(psu_com, st.session_state.state_psu, st.session_state.ebmode)
        psu.close_psu_comms(psu_com)

@st.fragment(run_every="1s")
def psu_display(psu_com):
    with st.expander("PSU Live Data", expanded=True):
        if st.session_state.ebmode : 
            # Extract most recent values from deque (list format: [ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i, ch4_v, ch4_i])
            latest_data = st.session_state.psu_queue[-1] if st.session_state.psu_queue else [0] * 8
            ch4_v = latest_data[6]
            ch4_i = latest_data[7]
            
            # Prepare sparkline data for +28V and CH4 Current
            ch4_v_sparkline = None
            ch4_v_delta = None
            ch4_i_sparkline = None
            ch4_i_delta = None
            if st.session_state.psu_queue:
                data = list(st.session_state.psu_queue)
                ch4_v_list = [float(reading[6].strip("V")) if isinstance(reading[6], str) else reading[6] for reading in data]
                ch4_i_list = [float(reading[7].strip("A")) if isinstance(reading[7], str) else reading[7] for reading in data]
                
                # Calculate deltas for sparklines
                if len(ch4_v_list) > 1:
                    ch4_v_delta = round(ch4_v_list[-1] - ch4_v_list[0], 2)
                    ch4_v_sparkline = ch4_v_list
                if len(ch4_i_list) > 1:
                    ch4_i_delta = round(ch4_i_list[-1] - ch4_i_list[0], 2)
                    ch4_i_sparkline = ch4_i_list
            
            # Voltage metrics row
            col1, col2 = st.columns(2, gap="small", vertical_alignment="center")
            
            with col1:
                st.metric(
                    "+28V",
                    value=ch4_v,
                    delta=ch4_v_delta,
                    label_visibility="visible",
                    border=True,
                )
            
            with col2:
                st.metric(
                    "CH4 Current",
                    value=ch4_i,
                    delta=ch4_i_delta,
                    label_visibility="visible",
                    border=True,
                )
            
            # Sparkline graphs row
            graph1, graph2 = st.columns(2, gap="small")
            
            with graph1:
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
            
            with graph2:
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
            # Plot row - full width (only redraw if data changed)
            st.divider()

            # if st.session_state.psu_queue:
            #     data = list(st.session_state.psu_queue)
            #     ch4_v_history = [float(reading[6].strip("V")) if isinstance(reading[6], str) else reading[6] for reading in data]
            #     ch4_i_history = [float(reading[7].strip("A")) if isinstance(reading[7], str) else reading[7] for reading in data]
                
            #     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 4))
        
            #     # Voltage plot
            #     ax1.plot(ch4_v_history, marker='o', color='blue', linewidth=1, label='Voltage')
            #     ax1.set_title("CH4 Voltage Over Time", fontsize=6)
            #     ax1.xaxis.set_tick_params(labelsize=6)
            #     ax1.yaxis.set_tick_params(labelsize=6)
            #     ax1.set_ylabel("Voltage (V)", fontsize=6)
            #     ax1.set_xlabel("Reading #", fontsize=6)
            #     ax1.grid(True, alpha=0.1)
            #     ax1.axhline(y=28, color='r', linestyle='--', alpha=0.1, label='Target: 28V')
            #     ax1.legend()
                
            #     # Current plot
            #     ax2.plot(ch4_i_history, marker='o', color='green', linewidth=1, label='Current')
            #     ax2.set_title("CH4 Current Over Time", fontsize=6)
            #     ax2.xaxis.set_tick_params(labelsize=6)
            #     ax2.yaxis.set_tick_params(labelsize=6)
            #     ax2.set_ylabel("Current (A)", fontsize=6)
            #     ax2.set_xlabel("Reading #", fontsize=6)
            #     ax2.grid(True, alpha=0.1)
            #     ax2.legend()
                
            #     col2.pyplot(fig)

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
                ch1_v_history = [float(reading[0].strip("V")) if isinstance(reading[0], str) else reading[0] for reading in data]
                ch1_i_history = [float(reading[1].strip("A")) if isinstance(reading[1], str) else reading[1] for reading in data]
                ch2_v_history = [float(reading[2].strip("V")) if isinstance(reading[2], str) else reading[2] for reading in data]
                ch2_i_history = [float(reading[3].strip("A")) if isinstance(reading[3], str) else reading[3] for reading in data]
                ch3_v_history = [float(reading[4].strip("V")) if isinstance(reading[4], str) else reading[4] for reading in data]
                ch3_i_history = [float(reading[5].strip("A")) if isinstance(reading[5], str) else reading[5] for reading in data]
                
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
            raw_bytes, tm_index = result
            # Check if this is a new packet (different index than last one)
            if raw_bytes is not None and tm_index != st.session_state.last_tm_index:                 
                parsed = eb.parse_eb_hk(raw_bytes)
                if parsed is not None:
                    # Store the parsed data in session state, don't display here
                    st.session_state.last_hk = parsed
                    st.session_state.last_tm_index = tm_index
    else:
        st.write("No log file selected")

def eb_log_filepicker():
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Bring dialog to front
        file_path = filedialog.askopenfilename(
            title="Select log file",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        root.destroy()
        if file_path:
            st.session_state.eb_filepath = file_path
    except Exception as e:
        st.error(f"Error opening file dialog: {e}")

@st.fragment()
def eb_Fragment():
    st.divider()
    st.button("Select EB Log File", key = "eb_log", on_click=eb_log_filepicker)
    with st.expander("EB Log File Info", expanded=True):
        if st.session_state.eb_filepath:
            st.write(f"Current EB Log File: {st.session_state.eb_filepath}")

        else:
            st.write("No EB Log File Selected")
        