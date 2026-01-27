# Std library
import logging
import threading
import serial.rs485
import comms
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
import os
from collections import deque
from hk_sniffer import parse_eb_hk, read_pkt as eb_hk
# Added packages
import constants as const
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import tc
import psu
import scripts.sequences as sq
import time
import send_cmd

event_log = logging.getLogger("event_log")

st.set_page_config(layout="wide")
state_pwr_dict = {"OFF": 0x00, "Mech Only": 0x01, "Detec Only": 0x02, "Both": 0x03}
st.logo(Path("./rsrc/ExoMars_Logo_PNG.png", size="large"))


def st_state_initialise() -> None:
    if "ob_active" not in st.session_state:
        st.session_state.ob_active = False

    if "eb_active" not in st.session_state:
        st.session_state.eb_active = False

    if "state_pwr" not in st.session_state:
        st.session_state.state_pwr = "OFF"

    if "state_htr_sci" not in st.session_state:
        st.session_state.state_htr_sci = False

    if "state_htr_detec_man" not in st.session_state:
        st.session_state.state_htr_detec_man = False

    if "state_htr_detec_auto" not in st.session_state:
        st.session_state.state_htr_detec_auto = False

    if "state_htr_mech_man" not in st.session_state:
        st.session_state.state_htr_mech_man = False

    if "state_htr_mech_auto" not in st.session_state:
        st.session_state.state_htr_mech_auto = False

    if "state_psu" not in st.session_state:
        st.session_state.state_psu = False

    if "state_rs485" not in st.session_state:
        st.session_state.state_rs485 = None
    
    if "psu_data" not in st.session_state:
        st.session_state.psu_data = {
            "ch1_v": "0V", "ch1_i": "0A",
            "ch2_v": "0V", "ch2_i": "0A",
            "ch3_v": "0V", "ch3_i": "0A"
        }
    
    if "psu_monitor_thread" not in st.session_state:
        st.session_state.psu_monitor_thread = None
    
    if "psu_stop_event" not in st.session_state:
        st.session_state.psu_stop_event = None
    
    # Thread-safe shared data (not using st.session_state in thread)
    if "_psu_shared_data" not in st.session_state:
        st.session_state._psu_shared_data = {}
    
    if "_psu_data_lock" not in st.session_state:
        st.session_state._psu_data_lock = threading.Lock()
    
    if "psu_plot_data" not in st.session_state:
        max_readings = 100
        st.session_state.psu_plot_data = {
            'ch1_voltages': deque(maxlen=max_readings),
            'ch1_currents': deque(maxlen=max_readings),
            'ch2_voltages': deque(maxlen=max_readings),
            'ch2_currents': deque(maxlen=max_readings),
            'ch3_voltages': deque(maxlen=max_readings),
            'ch3_currents': deque(maxlen=max_readings),
            'time_points': deque(maxlen=max_readings),
            'start_time': time.time(),
            'plot_counter': 0
        }


def psu_monitor_thread_func(psu_com: serial.Serial, stop_event: threading.Event, shared_data: dict, data_lock: threading.Lock, plot_data: dict = None, interval: float = 0.5):
    
    while not stop_event.is_set():
        try:
            if psu_com and psu_com.is_open:
                ch2_v_raw = psu.psuRead(psu_com, "2", "V", True)
                # Negate CH2 voltage
                if ch2_v_raw.startswith('-'):
                    ch2_v = ch2_v_raw[1:]
                else:
                    ch2_v = '-' + ch2_v_raw
                
                new_data = {
                    "ch1_v": psu.psuRead(psu_com, "1", "V", True),
                    "ch1_i": psu.psuRead(psu_com, "1", "I", True),
                    "ch2_v": ch2_v,
                    "ch2_i": psu.psuRead(psu_com, "2", "I", True),
                    "ch3_v": psu.psuRead(psu_com, "3", "V", True),
                    "ch3_i": psu.psuRead(psu_com, "3", "I", True),
                }
                with data_lock:
                    shared_data.update(new_data)
                
                # Update plot data if provided
                if plot_data is not None:
                    psu.update_psu_plot(plot_data, new_data["ch1_v"], new_data["ch1_i"],
                                       new_data["ch2_v"], new_data["ch2_i"],
                                       new_data["ch3_v"], new_data["ch3_i"])
        except Exception as e:
            event_log.error(f"PSU monitor error: {e}")
        
        time.sleep(interval)

def plot_psu_live_data(data_dict):
    if data_dict is None:
        return
    
    if 'fig' not in data_dict:
        return
    
    fig = data_dict['fig']
    if hasattr(fig, 'canvas') and hasattr(fig.canvas, 'draw'):
        fig.canvas.draw()
    
    st.pyplot(fig, use_container_width=True)

@st.cache_data
def load_psu_live_data(_psu_shared_data, _psu_data_lock):
    """Load PSU live data with caching and auto-refresh on data changes."""
    with _psu_data_lock:
        return _psu_shared_data.copy()

def toggle_cmd_interface():
    st.session_state.ob_active = not st.session_state.ob_active

def toggle_eb_interface():
    st.session_state.eb_active = not st.session_state.eb_active
    
@st.fragment()
def st_comms_config(port: serial.rs485.RS485, psu_com: serial.Serial) -> None:
    # title, gap, buttons = st.columns([1, 3, 1], vertical_alignment="bottom")
    if st.session_state.ob_active:     
    #     buttons.button(
    #         label="Close EGSE Interface for OB",
    #         disabled=not st.session_state.ob_active,
    #         on_click=toggle_cmd_interface(),            
    #         key = "close_ob_interface",
    #     )

        comms.open_comms(port)
        hk_fragment(port)
        st_cmd_interface(port, psu_com)
    else:
        # buttons.button(
        #     label="Open EGSE Interface for OB",
        #     disabled=st.session_state.ob_active,
        #     on_click=toggle_cmd_interface(),
        #     key = "open_ob_interface",
        # )
        comms.close_comms(port)
        st.session_state.state_rs485 = False
        st.session_state.state_psu = False

def st_cmd_pwr(port):
    state_pwr_int = state_pwr_dict.get(st.session_state.state_pwr)
    tc.power_control(port, state_pwr_int)

def st_cmd_htr(port):
    tc.heater_control(
        port,
        st.session_state.state_htr_sci,
        st.session_state.state_htr_detec_man,
        st.session_state.state_htr_detec_auto,
        st.session_state.state_htr_mech_man,
        st.session_state.state_htr_mech_auto,
    )


def st_psu_toggle(psu_com: serial.Serial):    
    if st.session_state.state_psu:
        # Try to open port if it's closed
        if not psu_com.is_open:
            psu.open_psu_comms(psu_com, psu_not_required=False)
        
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
        fig, (ax_voltage, ax_current) = plt.subplots(2, 1, figsize=(14, 5))
        fig.suptitle("PSU Live Monitoring", fontsize=10, fontweight='bold')
        
        ax_voltage.set_title("Voltage (V)", fontsize=8)
        ax_voltage.set_xlabel("Time (s)", fontsize=7)
        ax_voltage.set_ylabel("Voltage (V)", fontsize=7)
        ax_voltage.tick_params(labelsize=6)
        ax_voltage.grid(True, alpha=0.3)
        
        ax_current.set_title("Current (A)", fontsize=8)
        ax_current.set_xlabel("Time (s)", fontsize=7)
        ax_current.set_ylabel("Current (A)", fontsize=7)
        ax_current.tick_params(labelsize=6)
        ax_current.grid(True, alpha=0.3)
        
        line_v_ch1, = ax_voltage.plot([], [], label='+12V', color='red', linewidth=1)
        line_v_ch2, = ax_voltage.plot([], [], label='-12V', color='blue', linewidth=1)
        line_v_ch3, = ax_voltage.plot([], [], label='+5V', color='green', linewidth=1)
        
        line_i_ch1, = ax_current.plot([], [], label='CH1', color='red', linewidth=1)
        line_i_ch2, = ax_current.plot([], [], label='CH2', color='blue', linewidth=1)
        line_i_ch3, = ax_current.plot([], [], label='CH3', color='green', linewidth=1)
        
        ax_voltage.legend(loc='upper left', fontsize=6)
        ax_current.legend(loc='upper left', fontsize=6)
        
        plt.tight_layout(pad=1.5)
        
        st.session_state.psu_plot_data['axes'] = {'voltage': ax_voltage, 'current': ax_current}
        st.session_state.psu_plot_data['lines'] = {
            'v_ch1': line_v_ch1, 'v_ch2': line_v_ch2, 'v_ch3': line_v_ch3,
            'i_ch1': line_i_ch1, 'i_ch2': line_i_ch2, 'i_ch3': line_i_ch3
        }
        st.session_state.psu_plot_data['fig'] = fig
        
        # Start background monitoring thread if not already running
        if st.session_state.psu_monitor_thread is None or not st.session_state.psu_monitor_thread.is_alive():
            st.session_state.psu_stop_event = threading.Event()
            st.session_state.psu_monitor_thread = threading.Thread(
                target=psu_monitor_thread_func,
                args=(psu_com, st.session_state.psu_stop_event, st.session_state._psu_shared_data, st.session_state._psu_data_lock, st.session_state.psu_plot_data),
                daemon=True
            )
            st.session_state.psu_monitor_thread.start()
    else:
        # Stop background monitoring thread
        if st.session_state.psu_stop_event:
            st.session_state.psu_stop_event.set()
        if st.session_state.psu_monitor_thread and st.session_state.psu_monitor_thread.is_alive():
            st.session_state.psu_monitor_thread.join(timeout=1)
        st.session_state.psu_monitor_thread = None
        
        psu.switchPSU(psu_com, st.session_state.state_psu)
        psu.close_psu_comms(psu_com)

@st.fragment(run_every="1.5s")
def psu_display(psu_com):
    # Load cached PSU data and force refresh on changes
    shared_data = load_psu_live_data(st.session_state._psu_shared_data, st.session_state._psu_data_lock)
    
    # Voltage metrics row
    col_v1, col_v2, col_v3 = st.columns(3)
    
    with col_v1:
        st.metric(
            "+12V",
            value=shared_data.get("ch1_v", "0V"),
            delta=None,
            delta_color="normal",
            label_visibility="visible",
            border=True,
        )
    
    with col_v2:
        st.metric(
            "-12V",
            value=shared_data.get("ch2_v", "0V"),
            delta=None,
            delta_color="normal",
            label_visibility="visible",
            border=True,
        )
    
    with col_v3:
        st.metric(
            "+5V",
            value=shared_data.get("ch3_v", "0V"),
            delta=None,
            delta_color="normal",
            label_visibility="visible",
            border=True,
        )
    
    # Current metrics row
    col_i1, col_i2, col_i3 = st.columns(3)
    
    with col_i1:
        st.metric(
            "CH1 Current",
            value=shared_data.get("ch1_i", "0A"),
            delta=None,
            delta_color="normal",
            label_visibility="visible",
            border=False,
        )
    
    with col_i2:
        st.metric(
            "CH2 Current",
            value=shared_data.get("ch2_i", "0A"),
            delta=None,
            delta_color="normal",
            label_visibility="visible",
            border=False,
        )
    
    with col_i3:
        st.metric(
            "CH3 Current",
            value=shared_data.get("ch3_i", "0A"),
            delta=None,
            delta_color="normal",
            label_visibility="visible",
            border=False,
        )
    
    # Plot row - full width with auto-refresh
    st.divider()
    st.rerun()  # Force refresh on each render to capture live updates
    plot_psu_live_data(st.session_state.psu_plot_data)
    
def st_mtr_param(port):
    current = st.session_state.state_current
    speed = st.session_state.state_speed
    tc.set_mtr_param(port, current, 0x20, 0x0F, speed, 0x3200)

def get_hk():
    try:
        last_hk = const.hk_queue.pop()
        st.write(f"HK Data: {bytes.hex(last_hk.raw_bytes, ' ', 2)}")
        col1, col2, col3, empty, errors = st.columns([1, 1, 1, 3, 2])
        col1.metric(
            "Power Status",
            last_hk.PWR_STAT,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col2.metric(
            "Thermal Status",
            last_hk.THRM_STATUS_BYTE,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col3.metric(
            "Last Error",
            last_hk.ERROR_BYTE,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )

        errors.subheader("OB ERRORS")
        if last_hk.ERRORS.TMO == 1:
            TMOvalue = "‼️"
        else:
            TMOvalue = "✅"
        if last_hk.ERRORS.IOS == 1:
            IOSvalue = "‼️"
        else:
            IOSvalue = "✅"
        if last_hk.ERRORS.ICR == 1:
            ICRvalue = "‼️"
        else:
            ICRvalue = "✅"
        if last_hk.ERRORS.IPA == 1:
            IPAvalue = "‼️"
        else:
            IPAvalue = "✅"
        errors.write("TMO")
        errors.write(TMOvalue)
        errors.write("IOS")
        errors.write(IOSvalue)
        errors.write("ICR")
        errors.write(ICRvalue)
        errors.write("IPA")
        errors.write(IPAvalue)
        return last_hk
    except IndexError:
        st.write("No HK data available")

def get_eb_hk(raw_bytes) :
    try:
        
        st.write(f"HK Data: {raw_bytes.hex(' ', 2)}")
        last_hk = parse_eb_hk(raw_bytes)
        col1, col2, col3, empty, errors = st.columns([1, 1, 1, 3, 2])
        col1.metric(
            "Power Status",
            int(last_hk['PWR_STAT']),
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col2.metric(
            "Thermal Status",
            int(last_hk['THRM_STATUS_BYTE']),
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col3.metric(
            "Last Error",
            int(last_hk['ERROR_BYTE']),
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )

        errors.subheader("OB ERRORS")
        if int(last_hk['ERRORS'].TMO) == 1:
            TMOvalue = "‼️"
        else:
            TMOvalue = "✅"
        if int(last_hk['ERRORS'].IOS) == 1:
            IOSvalue = "‼️"
        else:
            IOSvalue = "✅"
        if int(last_hk['ERRORS'].ICR) == 1:
            ICRvalue = "‼️"
        else:
            ICRvalue = "✅"
        if int(last_hk['ERRORS'].IPA) == 1:
            IPAvalue = "‼️"
        else:
            IPAvalue = "✅"
        errors.write("TMO")
        errors.write(TMOvalue)
        errors.write("IOS")
        errors.write(IOSvalue)
        errors.write("ICR")
        errors.write(ICRvalue)
        errors.write("IPA")
        errors.write(IPAvalue)
        return last_hk
    except IndexError:
        st.write("No HK data available")

def get_mtr_hk(port):
    try:
        last_hk = const.hk_queue.pop()
        st.subheader("Motor Settings")
        col1, col2, col3, col4, col5 = st.columns(5)
        current, empty1, empty2, speed, sendmtrparam = st.columns(5, vertical_alignment="bottom")
        col1.metric(
            "Current",
            value=last_hk.MTR_CURRENT,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        current.number_input(
            "mA (RMS)", min_value=15, max_value=90, value=80, step=1, key="state_current", label_visibility="hidden"
        )
        col2.metric(
            "Motor Guard",
            value=last_hk.MTR_GUARD,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col3.metric(
            "Motor Recval",
            value=last_hk.MTR_RECVAL,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col4.metric(
            "Motor Speed",
            value=last_hk.MTR_SPEED,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        speed.number_input(
            label="Speed", min_value=0, max_value=10, value=8, step=1, key="state_speed", label_visibility="hidden"
        )
        col5.metric(
            "Rel Steps Limit",
            value=last_hk.MECH_LIM_REL,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        if sendmtrparam.button("Set Motor Parameters"):
            st_mtr_param(port)
            tc.hk_request(port)
        st.divider()
        st.subheader("Motor Status")
        col1, col2, col3, col4, col5, col6, col7, empty, empty2, empty3, mechtrp, motortrp, abs, rel = st.columns(14)
        with st.container():
            col1.metric(
                "CAL",
                value=last_hk.MTR_FLAGS.CAL,
                delta=None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col2.metric(
                "HOLD",
                value=last_hk.MTR_FLAGS.HOLD,
                delta=None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col3.metric(
                "DIR",
                value=last_hk.MTR_FLAGS.DIR,
                delta=None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col4.metric(
                "OUTER",
                value=last_hk.MTR_FLAGS.OUTER,
                delta=None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col5.metric(
                "BASE",
                value=last_hk.MTR_FLAGS.BASE,
                delta=None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col6.metric(
                "MOVING",
                value=last_hk.MTR_FLAGS.MOVING,
                delta=None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col7.metric(
                "HOMED",
                value=last_hk.MTR_FLAGS.HOMED,
                delta=None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
        mechtrp.metric(
            "Mech TRP",
            value=last_hk.MECH_TRP,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        motortrp.metric(
            "Motor TRP",
            value=last_hk.MOTOR_TRP,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        abs.metric(
            "Abs Steps",
            value=last_hk.MTR_ABS_STEPS,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        rel.metric(
            "Rel Steps",
            value=last_hk.MTR_REL_STEPS,
            delta=None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        mtr_cmds(port, last_hk)

    except IndexError:
        st.write("No HK data available")

def mtr_cmds(port, last_hk):
    col1, col2, col3, col4, col5 = st.columns(5, vertical_alignment="bottom")
    if col1.button(label="Power Up"):
        tc.power_control(port, 0x03)
        send_cmd.cmd_mtr_param(port, 0x40, 0x20, 0x0F, 0x9, 0x3200)
        resp = last_hk
        if (
            resp.MTR_CURRENT != 40
            or resp.MTR_GUARD != 32
            or resp.MTR_RECVAL != 15
            or resp.MTR_SPEED != 9
            or resp.MECH_LIM_REL != 12800
        ):
            event_log.error(
                f"OB Parameters not initialized correctly:"
                + f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 40"
                + f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32"
                + f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15"
                + f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9"
                + f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800"
            )
            # exit
            send_cmd.cmd_mtr_param(port, 0x28, 0x20, 0x0F, 0x9, 0x3200)
            last_hk = tc.hk_request(port)
            resp = last_hk
            if (
                resp.MTR_CURRENT != 40
                or resp.MTR_GUARD != 32
                or resp.MTR_RECVAL != 15
                or resp.MTR_SPEED != 9
                or resp.MECH_LIM_REL != 12800
            ):
                event_log.error(
                    f"OB Parameters not initialized correctly:"
                    + f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 40"
                    + f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32"
                    + f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15"
                    + f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9"
                    + f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800"
                )

    if col2.button(label="Homing Test"):
        event_log.info("HOME to BASE")
        last_hk = tc.hk_request(port)
        resp = last_hk
        send_cmd.cmd_mtr_homing(port, False, False)
        last_hk = tc.hk_request(port)
        resp = last_hk
        if resp.MTR_FLAGS.MOVING == 1:
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                last_hk = tc.hk_request(port)
                resp = last_hk
                event_log.info("Motor still moving ***********")
            event_log.info("Motor movement finished")
        else:
            event_log.error("Motor Did not Move :")
            event_log.error(
                f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}"
                + f"\n CAL : {resp.MTR_FLAGS.CAL}"
                + f"\n HOLD : {resp.MTR_FLAGS.HOLD}"
                + f"\n DIR : {resp.MTR_FLAGS.DIR}"
                + f"\n OUTER : {resp.MTR_FLAGS.OUTER}"
                + f"\n BASE : {resp.MTR_FLAGS.BASE}"
                + f"\n MOVING : {resp.MTR_FLAGS.MOVING}"
                + f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
            )
            event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
            if resp.ERROR_MTR != 0:
                event_log.error(
                    f"Unused : {resp.MTR_ERRORS.UNUSED}"
                    + f"\n CD : {resp.MTR_ERRORS.CD}"
                    + f"\n AB : {resp.MTR_ERRORS.AB}"
                    + f"\n ABS : {resp.MTR_ERRORS.ABS}"
                    + f"\n REL : {resp.MTR_ERRORS.REL}"
                    + f"\n DSE : {resp.MTR_ERRORS.DSE}"
                )

        if resp.MTR_FLAGS.BASE != 1:
            event_log.error(f"BASE Switch Flag not raised : {resp.MTR_FLAGS.BASE}")
        else:
            if resp.MTR_FLAGS.CAL != 0:
                event_log.error(f" Calibration Flag Falsely Asserted : {resp.MTR_FLAGS.CAL}")
            if resp.MTR_FLAGS.DIR != 1:
                event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
            if resp.MTR_ABS_STEPS != 8960:
                event_log.error(
                    f"Motor Steps Do not match expected : " + f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 8960"
                )
            if resp.MTR_REL_STEPS != 0:
                event_log.error(
                    f"Motor Steps Do not match expected : " + f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0"
                )

        # time.sleep(5)
        # event_log.info("HOME to OUTER")
        # last_hk =  tc.hk_request(port)
        # resp = last_hk
        # send_cmd.cmd_mtr_homing(port,False, True)
        # last_hk =  tc.hk_request(port)
        # resp = last_hk
        # if resp.MTR_FLAGS.MOVING == 1 :
        #     while resp.MTR_FLAGS.MOVING == 1:
        #         time.sleep(1)
        #         last_hk =  tc.hk_request(port)
        #         resp = last_hk
        #         event_log.info("Motor still moving ***********")
        #     event_log.info("Motor movement finished")
        # else :
        #     event_log.error("Motor Did not Move :")
        #     event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" +
        #                         f"\n CAL : {resp.MTR_FLAGS.CAL}"+
        #                         f"\n HOLD : {resp.MTR_FLAGS.HOLD}" +
        #                         f"\n DIR : {resp.MTR_FLAGS.DIR}" +
        #                         f"\n OUTER : {resp.MTR_FLAGS.OUTER}" +
        #                         f"\n BASE : {resp.MTR_FLAGS.BASE}" +
        #                         f"\n MOVING : {resp.MTR_FLAGS.MOVING}" +
        #                         f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
        #                         )
        #     event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
        #     if resp.ERROR_MTR != 0:
        #         event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" +
        #                         f"\n CD : {resp.MTR_ERRORS.CD}"+
        #                         f"\n AB : {resp.MTR_ERRORS.AB}" +
        #                         f"\n ABS : {resp.MTR_ERRORS.ABS}" +
        #                         f"\n REL : {resp.MTR_ERRORS.REL}" +
        #                         f"\n DSE : {resp.MTR_ERRORS.DSE}"
        #                         )

        # if resp.MTR_FLAGS.OUTER !=1 :
        #     event_log.error(f"OUTER Switch Flag not raised : {resp.MTR_FLAGS.OUTER}")
        # else:
        #     if resp.MTR_FLAGS.CAL != 0 :
        #         event_log.error(f" Calibration Flag Falsely Asserted : {resp.MTR_FLAGS.CAL}")
        #     if resp.MTR_FLAGS.DIR != 1 :
        #         event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
        #     if (resp.MTR_ABS_STEPS != 100):
        #         event_log.error(f"Motor Steps Do not match expected : " +
        #                         f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 100")
        #     if (resp.MTR_REL_STEPS != 0):
        #         event_log.error(f"Motor Steps Do not match expected : " +
        #                         f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
        # return

    if col3.button(label="Calibration Test"):
        sq.cal_test(port)
    if col4.button(label="Positive Test"):
        sq.positive_test(port)
    if col5.button(label="Negative Test"):
        sq.negative_test(port)

def get_sci():
    try:
        last_sci = const.sci_queue.pop()
        st.write(f"SCI Data: {bytes.hex(last_sci.raw_bytes, ' ', 2)}")
        # col1, col2, col3 = st.columns(3)
        # col1.metric('Power Status', last_sci.PWR_STAT, delta=None, delta_color="normal", help=None, label_visibility="visible", border=False)
        # col2.metric('Thermal Status', last_sci.THRM_STATUS, delta=None, delta_color="normal", help=None, label_visibility="visible", border=False)
        # col3.metric('Last Error', last_sci.ERROR_BYTE, delta=None, delta_color="normal", help=None, label_visibility="visible", border=False)
    except IndexError:
        st.write("No SCI data available")

@st.fragment()
def hk_fragment(port):
    st.subheader("Housekeeping")
    if st.button("Request HK"):
        tc.hk_request(port)
    get_hk()


@st.fragment()
def st_cmd_interface(port, psu_com):
    st.divider()
    st.subheader("PSU CONTROL")
    col1, col2, col3 = st.columns([1, 2, 2])
    col1.toggle(label="PSU Switch", key="state_psu", on_change=st_psu_toggle, args=(psu_com,))
    
    # Display PSU readings inside fragment when active
    if st.session_state.get("state_psu", False):
        st.divider()
        st.subheader("PSU Live Readings")
        psu_display(psu_com)
    
    tab1, tab2, tab3 = st.tabs(["Main Menu", "Detector Board", "Mechanism Board"])

    with tab1:
        st.selectbox(
            label="Power Control",
            options=state_pwr_dict.keys(),
            key="state_pwr",
            on_change=st_cmd_pwr,
            args=(port,),
        )

        st.divider()
        st.subheader("Heater Control")
        col1, col2, col3 = st.columns([2, 2, 1])
        col1.write("Mechanism Heater Control")
        col2.write("Detector Heater Control")
        col3.write("Science Control")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.toggle(
            label="Mech Auto",
            key="state_htr_mech_auto",
            on_change=st_cmd_htr,
            args=(port,),
        )

        col2.toggle(
            label="Mech Manual",
            key="state_htr_mech_man",
            on_change=st_cmd_htr,
            args=(port,),
        )

        col3.toggle(
            label="Detec Auto",
            key="state_htr_detec_auto",
            on_change=st_cmd_htr,
            args=(port,),
        )

        col4.toggle(
            label="Detec Manual",
            key="state_htr_detec_man",
            on_change=st_cmd_htr,
            args=(port,),
        )

        col5.toggle(
            label="Science Toggle",
            key="state_htr_sci",
            on_change=st_cmd_htr,
            args=(port,),
        )
    with tab2:
        st.title("Detector Board")
        if st.button("Request SCI"):
            tc.sci_request(port, 3, 1)
        st.subheader("Science Data")
        get_sci()
        # st.button(
        #     label="Request SWIR Offset",
        #     on_click=tc.sci_request,
        #     args=(port,),
        # )
        # st.button(
        #     label="Request MWIR Offset",
        #     on_click=tc.mwir_request,
        #     args=(port,),
        # )
        # st.button(
        #     label="Request HK Samples",
        #     on_click=tc.hk_samples_request,
        #     args=(port,),
        # )

    with tab3:
        st.subheader("Mechanism Subsystem")
        if st.button("RequestHK"):
            tc.hk_request(port)
        get_mtr_hk(port)

def file_selector(folder_path='.'):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename(
        title="Select log file",
        filetypes=[("Log files", "*.log"), ("All files", "*.*")],
    )
    if file_path:
        last_hk = eb_hk(file_path)
        return last_hk



@st.fragment() 
@st.cache_data
def load_eb_data(file_path):
    """Load EB housekeeping data from file with caching."""
    return eb_hk(file_path)

@st.fragment() 
def eb_mode():
    st.title("EB EGSE V3.0")
    st.write("EB Mode Selected. RS485 interface is inactive.")
    last_hk = file_selector()
    if last_hk:
        # Use cached loading - Streamlit will re-run when file changes
        last_hk = load_eb_data(last_hk)
        get_eb_hk(last_hk)

def streamlit_gui(com_port : serial.rs485.RS485, psu_com : serial.Serial) -> None:
    st_state_initialise()
    option = st.segmented_control(label="EGSE Mode selection", options = ["EB Mode","OB Mode"] , key="egse_mode")    
    if option == "EB Mode" : 
        eb_mode()
    else :
        st_comms_config(com_port, psu_com)

    
    
