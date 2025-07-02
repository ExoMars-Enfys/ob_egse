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
    ("UNUSED2", ">u32"),
    ("ERROR_MTR", "u8"),
    ("MTR_ERR_MSK", "u8"),
    ("MTR_FLAGS_BYTE", "u8"),
    ("MTR_ABS_STEPS", ">u16"),
    ("MTR_REL_STEPS", ">s16"),
    ("MTR_CURRENT", "u8"),
    ("MTR_GUARD", "u8"),
    ("MTR_RECVAL", "u8"),
    ("UNUSED3", "u4"),
    ("MTR_SPEED", "u4"),
    ("MECH_LIM_REL", ">u16"),
    ("UNUSED4", ">u72"),
    ("PWR_STAT", "u8"),
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
    ("UNUSED5", ">u40"),
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

ack_struct = [
    ("MOD_ID", "u3"),
    ("UNUSED1", "u1"),
    ("CMD_ID", "u4"),
    ("ERROR_BYTE", "u8"),
    ("PARAM1", "u8"),
    ("PARAM2", "u8"),
    ("PARAM3", "u8"),
    ("PARAM4", "u8"),
    ("PARAM5", "u8"),
    ("PARAM6", "u8"),
    ("CRC8", "u8"),
]

nack = [
    ("MOD_ID", "u3"),
    ("CMD_ID", "u5"),
    ("ERROR_BYTE", "u8"),
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
