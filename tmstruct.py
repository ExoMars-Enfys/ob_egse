# Get packing formats print(''.join(i[1] for i in hk))
# Get names print(''.join(i[1] for i in hk))

#! TODO Same for science
hk = [
    ("MOD_ID", "u3"),
    ("CMD_ID", "u5"),
    ("CMD_CNT", "u8"),
    ("ERROR", "u8"),
    ("PWR_STAT", "u8"),
    ("UNUSED1", ">u32"),
    ("ERROR_MTR", "u8"),
    ("MTR_ABS_STEPS", ">u16"),
    ("MTR_REL_STEPS", ">u16"),
    ("MTR_FLAGS", "u8"),
    ("MTR_GUARD", ">u16"),
    ("MTR_PWM_DUTY", "u8"),
    ("MTR_PWM_RATE", ">u16"),
    ("MTR_RECVAL", "u8"),
    ("MTR_SPISPSEL", ">u16"),
    ("MTR_CURRENT", ">u16"),
    ("MTR_SPEED", "u8"),
    ("MTR_ERR_MSK", "u8"),
    ("MTR_RECIRC", "u8"),
    ("MTR_SW_OFFSET", ">u16"),
    ("UNUSED2", "u8"),
    ("THRM_STATUS", "u8"),
    ("THRM_MECH_OFF_SP", ">u16"),
    ("THRM_MECH_ON_SP", ">u16"),
    ("THRM_DET_OFF_SP", ">u16"),
    ("THRM_DET_ON_SP", ">u16"),
    ("UNUSED3", ">u32"),
    ("HK_V_3V3", ">u16"),
    ("HK_V_1V5", ">u16"),
    ("DIGITAL_TRP", ">u16"),
    ("DETEC_TRP", ">u16"),
    ("MECH_TRP", ">u16"),
    ("MOTOR_TRP", ">u16"),
    ("HK_MECH_CUR", ">u16"),
    ("UNUSED_ADC", ">u16"),
    ("HK_SAMPLES", "u8"),
    ("UNUSED4", ">u32"),
    ("CRC8", "u8"),
]

ack_hdr = [
    ("MOD_ID", "u3"),
    ("CMD_ID", "u5"),
    ("ERROR", "u8"),
]

ack_clear_errors = [()]

# TODO ack_set_errors = [()]

ack_power_control = [("PWR_STAT", "u8")]

ack_heater_control = [("HTR_STAT", "u8")]

ack_set_mech_sp = [("THRM_MECH_OFF_SP", "u16"), ("THRM_MECH_ON_SP", "u16")]

ack_set_detec_sp = [("THRM_DETEC_OFF_SP", "u16"), ("THRM_DETEC_ON_SP", "u16")]

ack_set_mtr_param = [
    ("MTR_CURRENT", ">u16"),
    ("MTR_PWM_RATE", ">u16"),
    ("MTR_SPEED", "u8"),
    ("MTR_PWM_DUTY", "u8"),
]

ack_set_mtr_guard = [
    ("MTR_RECIRC", "u8"),
    ("MTR_GUARD", ">u16"),
    ("MTR_RECVAL", "u8"),
    ("MTR_SPISEL", ">u16"),
]

ack_set_mtr_mon = [
    ("MTR_ABS_STEPS", ">u16"),
    ("MTR_REL_STEPS", ">u16"),
    # TODO: Check offset not in structure
]
