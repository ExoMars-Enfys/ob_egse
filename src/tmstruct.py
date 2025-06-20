# Get packing formats print(''.join(i[1] for i in hk))
# Get names print(''.join(i[1] for i in hk))

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
    ("MTR_REL_STEPS", ">s16"),
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

mtr_error_struct = [
    ("UNUSED", "u3"),
    ("CD","u1"),
    ("AB","u1"),
    ("ABS","u1"),
    ("REL","u1"),
    ("DSE","u1"),
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

ack_template = [
    ("UNUSED2", "u8"),
    ("UNUSED3", "u8"),
    ("UNUSED4", "u8"),
    ("UNUSED5", "u8"),
    ("UNUSED6", "u8"),
    ("UNUSED7", "u8"),
    ("CRC", "u8")
]

ack_hdr = [
    ("MOD_ID", "u3"),
    ("UNUSED1", "u1"),
    ("CMD_ID", "u4"),
    ("ERROR_BYTE", "u8"),
]

nack = [
    ("MOD_ID", "u3"),
    ("CMD_ID", "u5"),
    ("ERROR_BYTE", "u8"),
]

# ACK Structures for commands
ack_clear_errors = ack_hdr + ack_template
ack_set_errors = ack_hdr +[("UNUSED1","u8"),("UNUSED2","u8"),("COIL","u8")]+ ack_template[3:]
# TODO ack_set_errors = [()]

ack_power_control = ack_hdr + [("PWR_STAT", "u8")] + ack_template[1:]

ack_heater_control = ack_hdr + [("HEATER_STAT", "u8")] + ack_template[1:]

ack_set_mech_sp = ack_hdr + [("THRM_MECH_OFF_SP", "u16"), ("THRM_MECH_ON_SP", "u16")] + ack_template[4:]

ack_set_detec_sp = ack_hdr + [("THRM_DETEC_OFF_SP", "u16"), ("THRM_DETEC_ON_SP", "u16")] + ack_template[4:]

ack_set_mtr_param = ack_hdr + [
    ("MTR_CURRENT", "u8"),
    ("MTR_GUARD", "u8"),    
    ("MTR_RECVAL", "u8"),
    ("UNUSED1", "u4"),
    ("MTR_SPEED", "u4"),
    ("MECH_LIM_REL", ">u16")
] + ack_template[6:]

ack_mtr_mov_pos = ack_hdr + [("UNUSED" , "u1"), ("MTR_POS_STEPS", ">u15")] + ack_template[2:]

ack_mtr_mov_neg = ack_hdr + [("UNUSED" , "u1"), ("MTR_NEG_STEPS", ">u15")] + ack_template[2:]

ack_mtr_halt = ack_hdr + ack_template

ack_mtr_homing = ack_hdr + [("UNUSED1", "u6"), ("CAL", "u1"), ("DIR", "u1")] + ack_template[1:]

ack_hk_samples = ack_hdr + [("HK_ADC_SAMP", "u8")] + ack_template[1:]

ack_sci_offset = ack_hdr + [("UNUSED1", "u4"), ("SWIR_OFFSET", ">u12"), ("UNUSED2", "u4"), ("MWIR_OFFSET", ">u12")] + ack_template[4:]

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
