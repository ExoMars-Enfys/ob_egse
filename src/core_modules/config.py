CMD_SPEED_DICT = {
    "Steady": 0.25,
    "Fast": 0.05,
}

EXP_MODEL_ID = 0x07

DEFAULT_COM_PORT = 3
DEFAULT_CMD_SPEED = "Fast"  # "Steady" or "Fast"

# PSU Config
PSU_COM_PORT = 8
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

# List of supported OB models
MODELS = ["DEM", "EM", "PFM", "FS"]

# Power consumption (mA) per state for each model
MODEL_CONSUMPTION = {
    "DEM": {
        "State1": 100,
        "State2": 120,
        "State3": 140,
        "State4": 160,
        "State5": 180,
        "State6": 200,
        "State7": 220,
        "Standby": 110,
    },
    "EM": {
        "State1": 90,
        "State2": 170,
        "State3": 190,
        "State4": 340,
        "State5": 277,
        "State7": 394,
        "Standby": 110,
        "Mech": 4,
        "Det": 10,
        "DetHTR": 19,
        "MechHTR": 38,
        "Moving": 50,
        "TEC1A": 150,
        "TEC35": 100,
        "TEC65": 140,
    },
    "PFM": {
        "State1": 90,
        "State2": 110,
        "State3": 130,
        "State4": 150,
        "State5": 170,
        "State6": 190,
        "State7": 210,
        "Standby": 100,
    },
    "FS": {
        "State1": 85,
        "State2": 105,
        "State3": 125,
        "State4": 145,
        "State5": 165,
        "State6": 185,
        "State7": 205,
        "Standby": 95,
    },
}
