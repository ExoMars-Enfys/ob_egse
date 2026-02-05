# Std library
import logging
import serial.rs485
import comms
from pathlib import Path

# Added packages
import constants as const
import pandas as pd
import streamlit as st
from streamlit_extras.grid import grid

# Project imports
import tc as tc

state_pwr_dict = {"OFF" : 0, "Mech Only": 1, "Detec Only": 2, "Both": 3}

event_log = logging.getLogger("event_log")

st.set_page_config(layout="wide")


def st_state_initialise() -> None:
    if "comms_active" not in st.session_state:
        st.session_state.comms_active = False
    if "count" not in st.session_state:
        st.session_state.count = 0


def init(rs485port) -> None:
    """Initialises the streamlit GUI"""
    st_state_initialise()
    st.session_state.rs485port = rs485port

    main_gui()
    with st.sidebar:
        st.image(Path("./rsrc/Enfys_logo.jpg", size="large", width=100))
        st.header("OB EGSE V3.2", divider=True)
        check_for_new_tm()


@st.fragment(run_every=10)
def check_for_new_tm() -> None:
    try:
        last_hk = const.hk_queue.pop()
        top_level_status(last_hk)
    except IndexError:
        return

def on_pills_change_pwr():
    # Write to new power state
    selected_key = st.session_state.pwr_pill
    if selected_key:
        pwr_value = state_pwr_dict[selected_key]
        tc.power_control(st.session_state.rs485port, pwr_value)



@st.fragment()
def main_gui() -> None:
    st.write("PSU Status")
    col1, col2, col3 = st.columns(3)
    col1.metric("+12V", f"{12.00:.2f}V")
    col2.metric("-12V", f"{-12.00:.2f}V")
    col3.metric("+5V", f"{+5.00:.2f}V")
    st.divider()

    coltc, coltm = st.columns([0.3, 0.7])
    coltc.button("Hello World")

    age = coltm.slider("How old are you?", 0, 130, 25)

    pwr_options = list(state_pwr_dict.keys())
    selection = st.pills("Power Options", pwr_options, selection_mode="single", key="pwr_pill", on_change=on_pills_change_pwr)


def top_level_status(last_hk) -> None:
    col1a, col2a, col3a = st.columns(3)

    col1a.metric("CMD Count", f"{last_hk.CMD_CNT}")
    col2a.metric("3V3 [V]", f"{(2 * last_hk.HK_V_3V3 / 1000 / 2**4):.2f}")
    col3a.metric("1V5 [V]", f"{(last_hk.HK_V_1V5 / 1000 / 2**4):.2f}")
    st.session_state.count += 1

    # Power and Heater Status
    stat_grid = grid(2, 2, 1, 2, 2, vertical_align="center")
    write_pwr_stat(last_hk, stat_grid)

    st.divider()
    st.markdown("**Errors**")
    err_cols = st.columns(6)
    write_errors(last_hk, err_cols)


def write_errors(last_hk, err_cols) -> None:
    if last_hk.ERRORS.IPI == 1:
        IPIvalue = "‼️"
    else:
        IPIvalue = "✅"

    if last_hk.ERRORS.IOS == 1:
        IOSvalue = "‼️"
    else:
        IOSvalue = "✅"

    if last_hk.ERRORS.ICR == 1:
        ICRvalue = "‼️"
    else:
        ICRvalue = "✅"

    if last_hk.ERRORS.MOR == 1:
        MORvalue = "‼️"
    else:
        MORvalue = "✅"

    if last_hk.ERRORS.TMO == 1:
        TMOvalue = "‼️"
    else:
        TMOvalue = "✅"

    if last_hk.ERRORS.IPA == 1:
        IPAvalue = "‼️"
    else:
        IPAvalue = "✅"

    err_cols[0].write("IPI")
    err_cols[0].write(IPIvalue)
    err_cols[1].write("IOS")
    err_cols[1].write(IOSvalue)
    err_cols[2].write("ICR")
    err_cols[2].write(ICRvalue)
    err_cols[3].write("MOR")
    err_cols[3].write(MORvalue)
    err_cols[4].write("TMO")
    err_cols[4].write(TMOvalue)
    err_cols[5].write("IPA")
    err_cols[5].write(IPAvalue)

    if last_hk.MTR_ERRORS.CD == 1:
        CDvalue = "‼️"
    else:
        CDvalue = "✅"

    if last_hk.MTR_ERRORS.AB == 1:
        ABvalue = "‼️"
    else:
        ABvalue = "✅"

    if last_hk.MTR_ERRORS.ABS == 1:
        ABSvalue = "‼️"
    else:
        ABSvalue = "✅"

    if last_hk.MTR_ERRORS.DSE == 1:
        DSEvalue = "‼️"
    else:
        DSEvalue = "✅"

    err_cols[2].write("CD")
    err_cols[2].write(CDvalue)
    err_cols[3].write("AB")
    err_cols[3].write(ABvalue)
    err_cols[4].write("ABS")
    err_cols[4].write(ABSvalue)
    err_cols[5].write("DSE")
    err_cols[5].write(DSEvalue)


def write_pwr_stat(last_hk, grid) -> None:
    st_mec = ":grey-badge[MECH OFF]" if (last_hk.PWR_STAT & 0x01) == 0 else ":green-badge[MECH ON]"
    st_det = ":gray-badge[DETEC OFF]" if (last_hk.PWR_STAT & 0x02) == 0 else ":green-badge[DETEC ON]"
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
