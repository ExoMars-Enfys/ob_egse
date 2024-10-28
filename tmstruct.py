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
    ("UNUSED2", ">u24"),
    ("THRM_STATUS", "u8"),
    ("THRM_MECH_MAX", ">u16"),
    ("THRM_MECH_MIN", ">u16"),
    ("THRM_DET_MAX", ">u16"),
    ("THRM_DET_MIN", ">u16"),
    ("UNUSED3", ">u32"),
    ("HK_SAMPLES", "u8"),
    ("HK_V_3V3", ">u16"),
    ("HK_V_1V5", ">u16"),
    ("DIGITAL_TRP", ">u16"),
    ("DETEC_TRP", ">u16"),
    ("MECH_TRP", ">u16"),
    ("MOTOR_TRP", ">u16"),
    ("HK_MECH_CUR", ">u16"),
    ("UNUSED_ADC", ">u16"),
    ("UNUSED4", ">u40"),
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

# TODO ack_heater_control = [()]

# ack_set_mech_sp = [()]

# ack_set_detec_sp = [()]

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
