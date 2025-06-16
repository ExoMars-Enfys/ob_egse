# Std library
import logging
import serial.rs485
import comms
from pathlib import Path

# Added packages
import constants as const
import streamlit as st
import tc
import psu

state_pwr_dict = {"OFF": 0x00, "Mech Only": 0x01, "Detec Only": 0x02, "Both": 0x03}


def st_state_initialise() -> None:
    if "ob_active" not in st.session_state:
        st.session_state.ob_active = False

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

    if "state_rs485" not in st.session_state:
        st.session_state.state_rs485 = None


def toggle_cmd_interface():
    st.session_state.ob_active = not st.session_state.ob_active


@st.fragment()
def st_comms_config(port: serial.rs485.RS485) -> None:
    if st.session_state.ob_active:
        st.button(
            label="Close RS485",
            disabled=not st.session_state.ob_active,
            on_click=toggle_cmd_interface(),
        )
        comms.open_comms(port)
        st_cmd_interface(port)
    else:
        st.button(
            label="Initialise RS485",
            disabled=st.session_state.ob_active,
            on_click=toggle_cmd_interface(),
        )
        comms.close_comms(port)
        st.session_state.state_rs485 = False


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


def get_hk():
    try:
        last_hk = const.hk_queue.pop()
        st.write(f"HK Data: {bytes.hex(last_hk.raw_bytes, ' ', 2)}")
        st.write(f"Power Status: {last_hk.PWR_STAT}")
        st.write(f"Thermal Status: {last_hk.THRM_STATUS}")
    except IndexError:
        st.write("No HK data available")


@st.fragment()
def st_cmd_interface(port):
    if st.button("Request HK"):
        tc.hk_request(port)

    st.selectbox(
        label="Power Control",
        options=state_pwr_dict.keys(),
        key="state_pwr",
        on_change=st_cmd_pwr,
        args=(port,),
    )

    st.divider()
    st.subheader("Heater Control")

    st.toggle(
        label="Mech Auto",
        key="state_htr_mech_auto",
        on_change=st_cmd_htr,
        args=(port,),
    )

    st.toggle(
        label="Mech Manual",
        key="state_htr_mech_man",
        on_change=st_cmd_htr,
        args=(port,),
    )

    st.toggle(
        label="Detec Auto",
        key="state_htr_detec_auto",
        on_change=st_cmd_htr,
        args=(port,),
    )

    st.toggle(
        label="Detec Manual",
        key="state_htr_detec_man",
        on_change=st_cmd_htr,
        args=(port,),
    )

    st.toggle(
        label="Science Toggle",
        key="state_htr_sci",
        on_change=st_cmd_htr,
        args=(port,),
    )

    st.divider()
    st.subheader("Housekeeping")
    get_hk()

    st.metric(
        "-12V Channel", value, delta=None, delta_color="normal", help=None, label_visibility="visible", border=False)


def streamlit_gui(com_port: str) -> None:
    st_state_initialise()
    port = comms.initialise_comms(com_port)
    st.title("OB EGSE 3")

    st_comms_config(port)
