# Get packing formats print(''.join(i[1] for i in hk))
# Get names print(''.join(i[1] for i in hk))

#! TODO Same for science
# HK starting from byte 0
# Bitfields have the suffix "_Byte" to indicate they'll be unpacked elsewhere in the code.
hk = [
    ("MOD_ID", "u3"),
    ("UNUSED1", "u1"),
    ("CMD_ID", "u4"),
    ("CMD_CNT", "u8"),
    ("ERROR_BYTE", "u8"),
    ("ERROR_MTR", "u8"),
    ("PWR_STAT", "u8"),
    ("UNUSED2", ">u32"),
    ("MTR_ABS_STEPS", ">u16"),
    ("MTR_REL_STEPS", ">u16"),
    ("MTR_FLAGS_BYTE", "u8"),
    ("MTR_GUARD", "u8"),
    ("UNUSED3", ">u32"),
    ("MTR_RECVAL", "u8"),
    ("MECH_LIM_REL", ">u16"),
    ("MTR_CURRENT", "u8"),
    ("UNUSED4", "u8"),
    ("MTR_SPEED", "u8"),
    ("MTR_ERR_MSK", "u8"),
    ("UNUSED5", ">u32"),
    ("THRM_STATUS", "u8"),
    ("THRM_MECH_OFF_SP", ">u16"),
    ("THRM_MECH_ON_SP", ">u16"),
    ("THRM_DET_OFF_SP", ">u16"),
    ("THRM_DET_ON_SP", ">u16"),
    ("SWIR_OFFSET", ">u16"),
    ("MWIR_OFFSET", ">u16"),
    ("HK_V_3V3", ">u16"),
    ("HK_V_1V5", ">u16"),
    ("DIGITAL_TRP", ">u16"),
    ("DETEC_TRP", ">u16"),
    ("MECH_TRP", ">u16"),
    ("MOTOR_TRP", ">u16"),
    ("HK_MECH_CUR", ">u16"),
    ("UNUSED_ADC", ">u16"),
    ("HK_SAMPLES", "u8"),
    ("UNUSED6", ">u32"),
    ("CRC8", "u8"),
]


#TODO: Determine if MSB or LSB

error_struct = [
    ("UNUSED1", "u1"),
    ("TMO", "u1"),
    ("IOS", "u1"),
    ("LIM", "u1"),
    ("LMO", "u1"),
    ("ICR", "u1"),
    ("IPA", "u1"),
    ("ICI", "u1"),
]

mtr_flag_struct = [
    ("UNUSED1", "u1"),
    ("CAL", "u1"),
    ("HOLD", "u1"),
    ("DIR", "u1"),
    ("OUTER", "u1"),
    ("BASE", "u1"),
    ("MOVING", "u1"),
    ("HOMED", "u1"),
]

ack_hdr = [
    ("MOD_ID", "u3"),
    ("CMD_ID", "u5"),
    ("ERROR_BYTE", "u8"),
]

nack = [
    ("MOD_ID", "u3"),
    ("CMD_ID", "u5"),
    ("ERROR_BYTE", "u8"),
]

ack_clear_errors = [()]

# TODO ack_set_errors = [()]

ack_power_control = [("PWR_STAT", "u8")]

ack_heater_control = [("HTR_STAT", "u8")]

ack_set_mech_sp = [("THRM_MECH_OFF_SP", "u16"), ("THRM_MECH_ON_SP", "u16")]

ack_set_detec_sp = [("THRM_DETEC_OFF_SP", "u16"), ("THRM_DETEC_ON_SP", "u16")]

ack_set_mtr_param = [
    ("MTR_CURRENT", "u8"),
    ("MTR_GUARD", "u8"),    
    ("MTR_RECVAL", "u8"),
    ("UNUSED1", "u1"),
    ("UNUSED2", "u1"),
    ("UNUSED3", "u1"),
    ("UNUSED4", "u1"),
    ("MTR_SPEED", "u4"),
    ("MECH_LIM_REL", ">u16")
]

ack_mtr_mov_pos = [
    ("UNUSED" , "u1"),
    ("MTR_POS_STEPS", ">u15")
]

ack_mtr_mov_neg = [
    ("UNUSED" , "u1"),
    ("MTR_NEG_STEPS", ">u15")
]

ack_mtr_halt = [()]

ack_mtr_homing = [
    ("UNUSED1", "u1"),
    ("UNUSED2", "u1"),
    ("UNUSED3", "u1"),
    ("UNUSED4", "u1"),
    ("UNUSED5", "u1"),
    ("UNUSED6", "u1"),
    ("CAL", "u1"),
    ("DIR", "u1")]

ack_hk_samples = [
    ("HK_ADC_SAMP", "u8")
]

ack_sci_offset = [
    ("SWIR_OFFSET", ">u16"),
    ("MWIR_OFFSET", ">u16")
]

sci = [
    ("MOD_ID", "u3"),
    ("UNUSED1", "u1"),
    ("CMD_ID", "u4"),
    ("CMD_CNT", "u8"),
    ("ERROR_BYTE", "u8"),
    ("MTR_ABS_STEPS", ">u16"),
    ("THRM_STATUS", "u8"),
    ("SWIR_OFFSET", ">u16"),
    ("MWIR_OFFSET", ">u16"),
    ("SCI_ADC_SAMPLES", "u8"),
    ("SCI_ADC_SKIP", "u8"),
    ("SWIR_HIGH", ">u16"),
    ("SWIR_MED", ">u16"),
    ("SWIR_LOW", ">u16"),
    ("MWIR_HIGH", ">u16"),
    ("MWIR_MED", ">u16"),
    ("MWIR_LOW", ">u16"),
    ("HT_SINK_TEMP", ">u16"),
    ("SWIR_TEMP", ">u16"),
    ("CRC","u8")
]
