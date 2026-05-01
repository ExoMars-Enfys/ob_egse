import logging
from queue import Queue

from datetime import datetime
from pathlib import Path

# ----Initialisation--------------------------------------------------------------------------------
DEBUG_LEVEL = logging.INFO
DEFAULT_PREFIX = datetime.now().strftime("%Y%m%dT%H%M%S")
DEFAULT_PATH = Path.cwd() / "logs" / DEFAULT_PREFIX

SCI_RESP_MARGIN = 0.020  # seconds
LOG_PREFIX = DEFAULT_PREFIX
LOG_PATH = DEFAULT_PATH

# ----Program Variables-----------------------------------------------------------------------------
# Set by EGSE.py do not write here.
ACK_LOG_FH = None
CMD_LOG_FH = None
HK_LOG_FH = None
SCI_LOG_FH = None

# HK queue
hk_queue = Queue(maxsize=100)
eb_post_queue = Queue(maxsize=100)
psu_queue = Queue(maxsize=100)
sci_queue = Queue(maxsize=30)

# ----Monitoring Limits-----------------------------------------------------------------------------
WLIM_3V3 = (3.0, 3.6)
WLIM_3V3_ADU = (1499, 1799)
ALIM_3V3 = (2.85, 3.75)
ALIM_3V3_ADU = (1424, 1874)

WLIM_1V5 = (1.425, 1.575)
WLIM_1V5_ADU = (1424, 1574)
ALIM_1V5 = (1.35, 1.65)
ALIM_1V5_ADU = (1349, 1649)

WLIM_TPR = (-45, +35)
WLIM_TPR_ADU = (1848, 2177)
ALIM_TPR = (-50, +50)
EB_ALIM_TPR = (-40, +75)
ALIM_TPR_ADU = (1823, 2211)

# ----Bus Voltage Settings-------------------------------------------------------------
# Bus voltage settings for different modes and channels (Min, Nominal, Max)
BUS_VOLTAGES = {
    "OB": {
        "CH1": {"MIN": 11.2, "NOM": 12.0, "MAX": 13.2},
        "CH2": {"MIN": 11.2, "NOM": 12.0, "MAX": 13.2},
        "CH3": {"MIN": 4.8, "NOM": 5.0, "MAX": 5.5},
    },
    "EB": {
        "CH3": {"MIN": 26.0, "NOM": 28.0, "MAX": 29.4},
        "CH4": {"MIN": 26.0, "NOM": 28.0, "MAX": 29.4},
    },
}

# ----Power State Limits based on Model-------------------------------------------------------------
# List of supported OB models
MODELS = ["DEM", "EM", "PFM", "FS"]

# Power consumption (mA) per state for each model
# State Map :
# State1 : Safe
# State2 : OB Heating
# State3 : OB Heating + Powered On
# State4 : OB Heating + Powered On + TEC at 1A
# State5 : Powered On + TEC at 1A
# State6 : ACQ
# State7 : All Active - OB Heating + Powered On + TEC at 1A + Moving

MODEL_CONSUMPTION = {
    "DEM": {
        "State1": 87,
        "State2": 160,
        "State3": 179,
        "State4": 327,
        "State5": 266,
        "State7": 380,
        "Standby": 101,
        "Mech": 4,
        "Det": 12,
        "DetHTR": 21,
        "MechHTR": 42,
        "Moving": 53,
        "TEC1A": 153,
        "TEC35": 100,
        "TEC65": 140,
    },
    "EM": {  # Consumption Dictionary for EMC
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
