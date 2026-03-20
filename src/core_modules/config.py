CMD_SPEED_DICT = {
    "Steady": 0.25,
    "Fast": 0.05,
}

EXP_MODEL_ID = 0x04

DEFAULT_COM_PORT = 16
DEFAULT_CMD_SPEED = "Fast"  # "Steady" or "Fast"

# PSU Config
PSU_COM_PORT = 4
PSU_LOGGING_FREQ = 10  # in HZ

CH1_OVP = 12.5
CH1_I = 0.100

CH2_OVP = 12.5
CH2_I = 0.135

CH3_OVP = 5.5
CH3_I = 0.150

ROV_HTR_OVP = 30
ROV_HTR_I = 0.05

EB_OVP = 30
EB_I = 0.5

# DAC Offset
SWIR_DAC_MIN_TH = 100
SWIR_DAC_MAX_TH = 300
MWIR_DAC_MIN_TH = 3300
MWIR_DAC_MAX_TH = 3500

MEASUREMENT_TABLES = [
    # The full range of values
    list(range(0, 8600)),
    # Guess at edges of the window.
    list(range(1300, 7600)),
    # Uneven steps for testing
    list(range(0, 1300, 10)) + list(range(1300, 7600)) + list(range(7600, 8601, 10)),
]
