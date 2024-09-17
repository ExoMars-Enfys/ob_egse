# Get packing formats print(''.join(i[1] for i in hk))
# Get names print(''.join(i[1] for i in hk))

#! TODO Same for science
hk = [
    ('CMD_ID', 'u5'),
    ('MOD_ID', 'u3'),
    ('CMD_CNT', 'u8'),
    ('ERROR', 'u8'),
    ('UNUSED1', '>u48'),
    ('ERROR_MTR', 'u8'),
    ('MTR_ABS_STEPS', '>u16'),
    ('MTR_REL_STEPS', '>u16'),
    ('MTR_FLAGS', 'u8'),
    ('MTR_GUARD', '>u16'),
    ('MTR_PWM_DUTY', 'u8'),
    ('MTR_PWM_RATE', '>u16'),
    ('MTR_RECVAL', 'u8'),
    ('MTR_SPISPSEL', '>u16'),
    ('MTR_CURRENT', '>u16'),
    ('SPEED', 'u8'),
    ('MTR_ERR_MSK', 'u8'),
    ('UNUSED2', '>u32'),
    ('THRM_STATUS', 'u8'),
    ('THRM_MECH_MAX', '>u16'),
    ('THRM_MECH_MIN', '>u16'),
    ('THRM_DET_MAX', '>u16'),
    ('THRM_DET_MIN', '>u16'),
    ('UNUSED3', '>u48'),
    ('HK_V_3V3', '>u16'),
    ('HK_V_1V5', '>u16'),
    ('DIGITAL_TRP', '>u16'),
    ('DETEC_TRP', '>u16'),
    ('MECH_TRP', '>u16'),
    ('MOTOR_TRP', '>u16'),
    ('HK_MECH_CUR', '>u16'),
    ('UNUSED_ADC', '>u16'),
    ('HK_SAMPLES', 'u8'),
    ('UNUSED4', '>u64'),
    ('CRC8', 'u8')
]

