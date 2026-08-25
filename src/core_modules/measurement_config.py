"""Measurement limits used by automated OB FFT verification.

Keep qualification thresholds here rather than in ``constants.py`` so they can
be updated without changing protocol/application constants.
"""

HK_REQUIRED_FIELDS = (
    "ERROR_BYTE",
    "ERROR_MTR",
    "PWR_STAT",
    "THRM_STATUS",
    "MTR_FLAGS",
    "MTR_ABS_STEPS",
    "MTR_REL_STEPS",
)

SCI_REQUIRED_FIELDS = (
    "MOD_ID",
    "UNUSED1",
    "CMD_ID",
    "CMD_CNT",
    "ERROR_BYTE",
    "MTR_ABS_STEPS",
    "THRM_STATUS_BYTE",
    "SWIR_OFFSET",
    "MWIR_OFFSET",
    "SCI_ADC_SAMPLES",
    "SCI_ADC_SKIP",
    "SWIR_HIGH",
    "SWIR_MED",
    "SWIR_LOW",
    "MWIR_HIGH",
    "MWIR_MED",
    "MWIR_LOW",
    "HT_SINK_TEMP",
    "SWIR_TEMP",
    "CRC",
)

MOTOR_NOMINAL_CURRENT = 64
MOTOR_NOMINAL_GUARD = 0
MOTOR_NOMINAL_CHOPPER = 60
MOTOR_NOMINAL_SPEED = 8
MOTOR_BOOT_CURRENT = 64
MOTOR_BOOT_GUARD = 0
MOTOR_BOOT_CHOPPER = 32
MOTOR_BOOT_SPEED = 9
MOTOR_BOOT_PARAMS = (
    MOTOR_BOOT_CURRENT,
    MOTOR_BOOT_GUARD,
    MOTOR_BOOT_CHOPPER,
    MOTOR_BOOT_SPEED,
)
MOTOR_NOMINAL_PARAMS = (
    MOTOR_NOMINAL_CURRENT,
    MOTOR_NOMINAL_GUARD,
    MOTOR_NOMINAL_CHOPPER,
    MOTOR_NOMINAL_SPEED,
)

MOTOR_HOME_TIMEOUT_S = 30
MOTOR_POLL_INTERVAL_S = 1.0
MOTOR_OUTER_POSITION = 1000
MOTOR_BASE_POSITION = 9960  #!TODO change for 3.4!!!!
MOTOR_POSITION_TOLERANCE = 0
MOTOR_DIRECTION_POSITIVE = 0
MOTOR_DIRECTION_NEGATIVE = 1
MOTOR_SPEED_MAX_DURATION_S = {0: 91, 15: 18}

# HK_MECH_CUR is a 12-bit ADC value stored in the upper 12 bits of the
# 16-bit housekeeping field. The mechanism-current calibration is:
# mA = ADC count * 0.12 / (0.2 * 10).
# The reported value is the net result of the active +12 V, +5 V, mechanism
# heater, and detector heater paths; heater offsets therefore depend on the
# active mechanism and detector heater combination rather than one fixed offset.
MECHANISM_CURRENT_MA_PER_ADU = 0.12 / (0.2 * 10)
MECHANISM_CURRENT_ZERO_MAX_ADU = 5
MECHANISM_CURRENT_IDLE_ADU = 135

# All PSU current-consumption checks use a flat +/-10 mA tolerance around the
# expected value, matching the EB-side consumption_check convention.
PSU_CURRENT_TOLERANCE_MA = 10.0

LIM_3V3_ADU = (1425, 1875)  # +2.85 - +3.75
LIM_1V5_ADU = (1350, 1650)  # +1.35 - +1.65
LIM_TPR_ADU_PCB = (1823, 2229)  # -50 - +50
LIM_TPR_ADU_MTR = (1823, 2245)  # -50 - +55

# OB-only PSU current contributions in mA. Profile totals are calculated by
# summing the components active in the measured hardware state.
OB_CURRENT_COMPONENTS_MA = {
    "OB5V": {"CH3": 60.0},
    "MechanismBoard": {"CH1": 3.0},
    "DetectorBoard": {"CH1": 14.4, "CH2": 5.7},
    "MechanismHeater": {"CH2": 83.0},
    "DetectorHeater": {"CH2": 41.0},
    "PoweredHeatedBoards": {"CH3": 10.0},
    "Moving": {"CH1": 85.0, "CH3": 7.0},
}
# Motor contribution to the mechanism PSU current for each qualification
# current setting. The mechanism-board baseline is added separately. Motion
# adds a small CH3 contribution in addition to the CH1 mechanism delta.
MOTOR_MOVING_CURRENT_MA = {20: 15.0, 40: 57.0, 64: 87.0}
MOTOR_MOVING_CURRENT_COMPONENTS_MA = {
    20: {"CH1": 15.0, "CH3": 7.0},
    40: {"CH1": 57.0, "CH3": 7.0},
    64: {"CH1": 85.0, "CH3": 7.0},
}

# Expected HK representation of each EB-style operating state on an OB-only
# interface. Heater tuples follow tc.heater_control argument order.
OB_STATE_EXPECTATIONS = {
    "State1": {"power": 0x00, "heater": (False, False, False, False, False), "moving": False},
    "State2": {"power": 0x00, "heater": (False, True, False, True, False), "moving": False},
    "State3": {"power": 0x03, "heater": (False, True, False, True, False), "moving": False},
    "State4": {"power": 0x03, "heater": (False, True, False, True, False), "moving": False},
    "State5": {"power": 0x03, "heater": (False, False, False, False, False), "moving": False},
    "State6": {"power": 0x03, "heater": (False, False, False, False, False), "moving": False},
    "State7": {"power": 0x03, "heater": (False, True, False, True, False), "moving": True},
    "Moving": {"power": 0x01, "heater": (False, False, False, False, False), "moving": True},
}

# Raw packet values. Adjust these limits after characterising the flight unit.
DARK_HK_TEMPERATURE_LIMITS = {
    "DETEC_TRP": (0, 0xFFFF),
    "MECH_TRP": (0, 0xFFFF),
    "MOTOR_TRP": (0, 0xFFFF),
}
DARK_SCIENCE_TEMPERATURE_LIMITS = {
    "SWIR_TEMP": (0, 0xFFFF),
    "HT_SINK_TEMP": (0, 0xFFFF),
}
DARK_POSITIONS = {"SWIR": 9600, "MWIR": 8000}
DARK_SCIENCE_LIMITS = {
    "SWIR_HIGH": (0, 0xFFFF),
    "SWIR_MED": (0, 0xFFFF),
    "SWIR_LOW": (0, 0xFFFF),
    "MWIR_HIGH": (0, 0xFFFF),
    "MWIR_MED": (0, 0xFFFF),
    "MWIR_LOW": (0, 0xFFFF),
}
