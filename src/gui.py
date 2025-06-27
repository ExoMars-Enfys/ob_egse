# Std library
import logging
import serial.rs485
import comms
from pathlib import Path
import math
# Added packages
import constants as const
import streamlit as st
import tc
import psu
import sequences as sq
import time
import send_cmd

event_log = logging.getLogger("event_log")

st.set_page_config(layout='wide')
state_pwr_dict = {"OFF": 0x00, "Mech Only": 0x01, "Detec Only": 0x02, "Both": 0x03}
st.logo(Path("./rsrc/ExoMars_Logo_PNG.png",size = "large"))

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
        title,gap,rs485 = st.columns([1,3,1],vertical_alignment = "bottom")
        title.title("OB EGSE V3.0")
        rs485.button(
            label="Close RS485",
            disabled=not st.session_state.ob_active,
            on_click=toggle_cmd_interface(),
        )        
        comms.open_comms(port)
        st_cmd_interface(port)
    else:
        title,gap,rs485 = st.columns([1,3,1],vertical_alignment = "bottom")
        title.title("OB EGSE V3.0")
        rs485.button(
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

def  st_psu_cmd() : 
    psu.setChannels(
        st.session_state.state_12vChannel, 
        st.session_state.state_htrChannel, 
        st.session_state.state_5vChannel
        )
    
def st_mtr_param(port):
    current = st.session_state.state_current
    speed = st.session_state.state_speed
    tc.set_mtr_param(
        port,
        current,
        0x20,
        0x0F,
        speed,
        0x3200
    )

def get_hk():
    try:
        last_hk = const.hk_queue.pop()
        st.write(f"HK Data: {bytes.hex(last_hk.raw_bytes, ' ', 2)}")
        col1, col2,col3 = st.columns(3)
        col1.metric('Power Status', last_hk.PWR_STAT, delta=None, delta_color="normal", help=None, label_visibility="visible", border=False)
        col2.metric('Thermal Status', last_hk.THRM_STATUS, delta=None, delta_color="normal", help=None, label_visibility="visible", border=False)
        col3.metric('Last Error', last_hk.ERROR_BYTE, delta=None, delta_color="normal", help=None, label_visibility="visible", border=False)
        st.subheader("OB ERRORS")
        # col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        # col1.metric("Time Out",value = last_hk.ERRORS.TMO,delta = None,delta_color="normal",help=None,label_visibility="visible",border=True)
        # col2.metric("Invalid OB State",value = last_hk.ERRORS.IOS,delta = None,delta_color="normal",help=None,label_visibility="visible",border=True)
        # col3.metric("Rel Limit Reached",value = last_hk.ERRORS.LIM,delta = None,delta_color="normal",help=None,label_visibility="visible",border=True)
        # col4.metric("Monitor Limit Reached",value = last_hk.ERRORS.LMO,delta = None,delta_color="normal",help=None,label_visibility="visible",border=True)
        # col5.metric("Invalid CRC",value = last_hk.ERRORS.ICR,delta = None,delta_color="normal",help=None,label_visibility="visible",border=True)
        # col6.metric("Invalid Parity",value = last_hk.ERRORS.IPA,delta = None,delta_color="normal",help=None,label_visibility="visible",border=True)
        # col7.metric("Invalid Command ID",value = last_hk.ERRORS.ICI,delta = None,delta_color="normal",help=None,label_visibility="visible",border=True)
        return last_hk
    except IndexError:
        st.write("No HK data available")

def get_mtr_hk(port,last_hk) : 
    try:
        st.subheader("Motor Settings")
        col1, col2, col3, col4, col5= st.columns(5)
        current,empty1,empty2,speed,sendmtrparam = st.columns(5,vertical_alignment= "bottom")
        col1.metric(
            "Current",
            value = last_hk.MTR_CURRENT,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        current.number_input("mA (RMS)", min_value=15, max_value = 90, value = 80,step =  1,key="state_current", label_visibility="hidden")
        col2.metric(
            "Motor Guard",
            value = last_hk.MTR_GUARD,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col3.metric(
            "Motor Recval",
            value = last_hk.MTR_RECVAL,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        col4.metric(
            "Motor Speed",
            value = last_hk.MTR_SPEED,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=False,
        )
        speed.number_input(label = "Speed",min_value=0, max_value = 10, value = 8,step =  1, key="state_speed", label_visibility="hidden")
        col5.metric(
            "Rel Steps Limit",
            value = last_hk.MECH_LIM_REL,
            delta = None,
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
        col1, col2, col3, col4, col5, col6, col7,empty,empty2,empty3,mechtrp,motortrp,abs,rel = st.columns(14)
        with st.container():
            col1.metric(
                "CAL",
                value = last_hk.MTR_FLAGS.CAL,
                delta = None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col2.metric(
                "HOLD",
                value = last_hk.MTR_FLAGS.HOLD,
                delta = None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col3.metric(
                "DIR",
                value = last_hk.MTR_FLAGS.DIR,
                delta = None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col4.metric(
                "OUTER",
                value = last_hk.MTR_FLAGS.OUTER,
                delta = None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col5.metric(
                "BASE",
                value = last_hk.MTR_FLAGS.BASE,
                delta = None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col6.metric(
                "MOVING",
                value = last_hk.MTR_FLAGS.MOVING,
                delta = None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
            col7.metric(
                "HOMED",
                value = last_hk.MTR_FLAGS.HOMED,
                delta = None,
                delta_color="normal",
                help=None,
                label_visibility="visible",
                border=False,
            )
        mechtrp.metric(
            "Mech TRP",
            value = last_hk.MECH_TRP,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        motortrp.metric(
            "Motor TRP",
            value = last_hk.MOTOR_TRP,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        abs.metric(
            "Abs Steps",
            value = last_hk.MTR_ABS_STEPS,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        rel.metric(
            "Rel Steps",
            value = last_hk.MTR_REL_STEPS,
            delta = None,
            delta_color="normal",
            help=None,
            label_visibility="visible",
            border=True,
        )
        return last_hk
    except IndexError:
        st.write("No HK data available")

def mtr_cmds(port,last_hk):
    col1,col2,col3,col4,col5 = st.columns(5,vertical_alignment="bottom")
    if col1.button(label = "Power Up") :
        tc.power_control(port,0x03)
        send_cmd.cmd_mtr_param(port,0x40,0x20,0x0F,0x9,0x3200)
        resp = last_hk
        if (
        resp.MTR_CURRENT != 40
        or resp.MTR_GUARD != 32
        or resp.MTR_RECVAL != 15
        or resp.MTR_SPEED != 9
        or resp.MECH_LIM_REL != 12800):
            event_log.error(f"OB Parameters not initialized correctly:"+
                            f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 40" +
                            f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32" +
                            f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15" +
                            f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9" +
                            f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800")
            # exit
            send_cmd.cmd_mtr_param(port,0x28,0x20,0x0F,0x9,0x3200)
            last_hk = tc.hk_request(port)
            resp = last_hk
            if (
            resp.MTR_CURRENT != 40
            or resp.MTR_GUARD != 32
            or resp.MTR_RECVAL != 15
            or resp.MTR_SPEED != 9
            or resp.MECH_LIM_REL != 12800):
                event_log.error(f"OB Parameters not initialized correctly:"+
                                f"\n Current : {resp.MTR_CURRENT}                ~ Expected : 40" +
                                f"\n Motor_guard : {resp.MTR_GUARD}            ~ Expected : 32" +
                                f"\n Motor Rec_Val : {resp.MTR_RECVAL}          ~ Expected : 15" +
                                f"\n Speed : {resp.MTR_SPEED}                   ~ Expected : 9" +
                                f"\n Relative Steps Limit : {resp.MECH_LIM_REL}    ~ Expected : 12800")

    if col2.button(label = "Homing Test"):
        event_log.info("HOME to BASE")
        last_hk =  tc.hk_request(port)
        resp = last_hk
        send_cmd.cmd_mtr_homing(port,False, False)    
        last_hk =  tc.hk_request(port)
        resp = last_hk
        if resp.MTR_FLAGS.MOVING == 1 : 
            while resp.MTR_FLAGS.MOVING == 1:
                time.sleep(1)
                last_hk =  tc.hk_request(port)
                resp = last_hk
                event_log.info("Motor still moving ***********")
            event_log.info("Motor movement finished")
        else : 
            event_log.error("Motor Did not Move :")
            event_log.error(f"MTR Flags : \nUnused : {resp.MTR_FLAGS.UNUSED1}" + 
                                f"\n CAL : {resp.MTR_FLAGS.CAL}"+
                                f"\n HOLD : {resp.MTR_FLAGS.HOLD}" + 
                                f"\n DIR : {resp.MTR_FLAGS.DIR}" + 
                                f"\n OUTER : {resp.MTR_FLAGS.OUTER}" + 
                                f"\n BASE : {resp.MTR_FLAGS.BASE}" +
                                f"\n MOVING : {resp.MTR_FLAGS.MOVING}" + 
                                f"\n HOMED : {resp.MTR_FLAGS.HOMED}"
                                )
            event_log.error(f"\nMotor Error Flags : {resp.ERROR_MTR}")
            if resp.ERROR_MTR != 0:
                event_log.error(f"Unused : {resp.MTR_ERRORS.UNUSED}" + 
                                f"\n CD : {resp.MTR_ERRORS.CD}"+
                                f"\n AB : {resp.MTR_ERRORS.AB}" + 
                                f"\n ABS : {resp.MTR_ERRORS.ABS}" + 
                                f"\n REL : {resp.MTR_ERRORS.REL}" + 
                                f"\n DSE : {resp.MTR_ERRORS.DSE}"
                                )
        
        if resp.MTR_FLAGS.BASE !=1 : 
            event_log.error(f"BASE Switch Flag not raised : {resp.MTR_FLAGS.BASE}")
        else:
            if resp.MTR_FLAGS.CAL != 0 : 
                event_log.error(f" Calibration Flag Falsely Asserted : {resp.MTR_FLAGS.CAL}")
            if resp.MTR_FLAGS.DIR != 1 : 
                event_log.error(f" Calibration Dir not to Outer : {resp.MTR_FLAGS.DIR}")
            if (resp.MTR_ABS_STEPS != 8960):
                event_log.error(f"Motor Steps Do not match expected : " + 
                                f"\n ABS : {resp.MTR_ABS_STEPS} , Expected : 8960")
            if (resp.MTR_REL_STEPS != 0):
                event_log.error(f"Motor Steps Do not match expected : " + 
                                f"\n REL : {resp.MTR_REL_STEPS} , Expected : 0")
        
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

    if col3.button(label = "Calibration Test"):
        sq.cal_test(port)
    if col4.button(label = "Positive Test"):
        sq.positive_test(port)
    if col5.button(label = "Negative Test"):
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
def st_cmd_interface(port):
    
    tab1,tab2,tab3 = st.tabs(["Main Menu","Detector Board","Mechanism Board"])
    
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
        col1,col2,col3 = st.columns([2,2,1])
        col1.write("Mechanism Heater Control")
        col2.write("Detector Heater Control")
        col3.write("Science Control")
        col1,col2,col3,col4,col5 = st.columns(5)
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
        st.divider()
        st.subheader("Housekeeping")
        if st.button("Request HK"):
            tc.hk_request(port)
        get_hk()
    with tab2:
        st.title("Detector Board")
        if st.button("Request SCI"):
            tc.sci_request(port,3,1)
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
        tc.hk_request(port)
        last_hk = get_hk()
        get_mtr_hk(port,last_hk)
        mtr_cmds(port,last_hk)
        

    

    st.divider()
    st.subheader("PSU CONTROL")
    # col1,col2,col3 = st.columns(3)
    # col1.write("+12V Channel")
    # col1.metric("Voltage", value = psu.psuRead("1","V"), delta= None , delta_color="normal", help=None, label_visibility="visible", border=False)
    # col1.metric("Current", value = psu.psuRead("1","I"), delta= None , delta_color="normal", help=None, label_visibility="visible", border=False)
    # col2.write("-12V Channel")
    # col2.metric("Voltage", value = psu.psuRead("2","V"), delta= None , delta_color="normal", help=None, label_visibility="visible", border=False)
    # col2.metric("Current", value = psu.psuRead("2","I"), delta= None , delta_color="normal", help=None, label_visibility="visible", border=False)
    # col3.write("+5V Channel")
    # col3.metric("Voltage", value = psu.psuRead("3","V"), delta= None , delta_color="normal", help=None, label_visibility="visible", border=False)
    # col3.metric("Current", value = psu.psuRead("3","I"), delta= None , delta_color="normal", help=None, label_visibility="visible", border=False)

    # col1.toggle(
    #         label="+12V Channel",
    #         key="state_12vChannel",
    #         on_change=st_psu_cmd,
    #     )
    # col2.toggle(
    #         label="Heater Channel",
    #         key="state_htrChannel",
    #         on_change=st_psu_cmd,
    #     )
    # col3.toggle(
    #         label="+5V Channel",
    #         key="state_5vChannel",
    #         on_change=st_psu_cmd,
    #     )

    

def streamlit_gui(com_port: str) -> None:
    st_state_initialise()
    port = comms.initialise_comms(com_port)
    st_comms_config(port)