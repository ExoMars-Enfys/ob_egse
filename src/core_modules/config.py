CMD_SPEED_DICT = {
    "Steady": 0.25,
    "Fast": 0.05,
}

# Model bitmap mapping for the OB/EB instrument. DEM is the BB2 device variant,
# which uses the 3-bit value 010.
MODEL_OPTIONS = [
    "DEV",
    "IFM",
    "DEM",
    "Firmware TB",
    "EM",
    "FM",
    "FS",
    "CMOD EGSE",
]
MODEL_BITMAPS = {
    "DEV": "000",
    "IFM": "001",
    "DEM": "010",
    "BB2": "010",
    "Firmware TB": "011",
    "EM": "100",
    "FM": "101",
    "FS": "110",
    "CMOD EGSE": "111",
}
DEFAULT_COM_PORT = 9
DEFAULT_CMD_SPEED = "Fast"  # "Steady" or "Fast"

# PSU Config
PSU_COM_PORT = 8
PSU_LOGGING_FREQ = 10  # in HZ

# Scope Config (Tektronix MSO44B, direct-cabled LAN link — see tek_scope_api)
SCOPE_VISA_RESOURCE = "TCPIP0::169.254.9.67::INSTR"

CH1_OVP = 12.5
CH1_I = 0.150

CH2_OVP = 12.5
CH2_I = 0.150

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
