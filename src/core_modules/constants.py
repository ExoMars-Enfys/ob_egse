import logging
from datetime import datetime
from pathlib import Path
from queue import Queue

from core_modules import config

# ----Initialisation--------------------------------------------------------------------------------
DEBUG_LEVEL = logging.INFO
DEFAULT_PREFIX = datetime.now().strftime("%Y%m%dT%H%M%S")
DEFAULT_PATH = Path.cwd() / "logs" / DEFAULT_PREFIX
DEFAULT_STARTUP_MODE = "OB"

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
# hk_explorer_queue = Queue(maxsize=100)  # Separate queue for HK parameter explorer
eb_post_queue = Queue(maxsize=100)
psu_queue = Queue(maxsize=100)
sci_queue = Queue(maxsize=100)

# ----Monitoring Limits-----------------------------------------------------------------------------
# Real-space limits (engineering units) from TM reference table
WLIM_EB_12V = (11.0, 13.0)
ALIM_EB_12V = (10.5, 13.5)

WLIM_EB_NEG12V = (-13.0, -11.0)
ALIM_EB_NEG12V = (-13.5, -10.5)

WLIM_EB_5V = (4.5, 5.5)
ALIM_EB_5V = (4.0, 6.0)

WLIM_EB_3V3 = (3.0, 3.45)
ALIM_EB_3V3 = (3.0, 3.6)

# EB TEC rail is upper-bound monitored only per table (low side not monitored)
WLIM_EB_TEC_RAIL = (None, 3.25)
ALIM_EB_TEC_RAIL = (None, 3.5)

WLIM_EB_MCU_INTERNAL_TEMP = (-45, 125)
ALIM_EB_MCU_INTERNAL_TEMP = (-50, 135)

WLIM_EB_INTERNAL_TRP_TEMP = (-42, 70)
ALIM_EB_INTERNAL_TRP_TEMP = (-45, 90)

WLIM_EB_PSU_BOARD_TEMP = (-45, 110)
ALIM_EB_PSU_BOARD_TEMP = (-50, 120)

WLIM_3V3 = (3.0, 3.6)
ALIM_3V3 = (2.85, 3.75)

WLIM_1V5 = (1.425, 1.575)
ALIM_1V5 = (1.35, 1.65)

WLIM_TPR = (-45, +35)
ALIM_TPR = (-50, +45)

# ADU-space limits derived from conversion formulas in utility_modules/hk_conversions.py
# and utility_modules/eb_packet_utility.py
WLIM_EB_12V_ADU = (27463, 32456)
ALIM_EB_12V_ADU = (26214, 33704)

WLIM_EB_NEG12V_ADU = (28836, 34079)
ALIM_EB_NEG12V_ADU = (27525, 35389)

WLIM_EB_5V_ADU = (29445, 35988)
ALIM_EB_5V_ADU = (26173, 39260)

WLIM_EB_3V3_ADU = (39318, 45216)
ALIM_EB_3V3_ADU = (39318, 47182)

WLIM_EB_MCU_INTERNAL_TEMP_ADU = (13926, 24310)
ALIM_EB_MCU_INTERNAL_TEMP_ADU = (13621, 24921)

# EB thermistor ADU limits (decode_eb_trps conversion; temperature decreases with ADU)
WLIM_EB_INTERNAL_TRP_TEMP_ADU = (30992, 65238)
ALIM_EB_INTERNAL_TRP_TEMP_ADU = (21269, 65297)

WLIM_EB_PSU_BOARD_TEMP_ADU = (14121, 65297)
ALIM_EB_PSU_BOARD_TEMP_ADU = (11469, 65373)

WLIM_3V3_ADU = (1500, 1800)
ALIM_3V3_ADU = (1425, 1875)

WLIM_1V5_ADU = (1425, 1575)
ALIM_1V5_ADU = (1350, 1650)

# OB thermistor ADU limits (adu_to_temp conversion)
WLIM_TPR_ADU = (1849, 2178)
ALIM_TPR_ADU = (1825, 2212)

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
# Keep the selectable model list in config so the UI and protocol config stay aligned.
MODELS = list(config.MODEL_OPTIONS)

# States whose MODEL_CONSUMPTION values already include heater (OB Heating) power.
# When one of these states is used in consumption_check, heater sub-states (MechHTR/DetHTR)
# must NOT be added again from verify_heater_states — they are already baked in.
# State2 = OB Heating
# State3 = OB Heating + Powered On
# State4 = OB Heating + Powered On + TEC at 1A
# State7 = All Active (OB Heating + Powered On + TEC at 1A + Moving)
HEATER_INCLUSIVE_STATES: frozenset[str] = frozenset({"State2", "State3", "State4", "State7"})

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
        "State6": 207,
        "State7": 380,
        "Standby": 101,
        "Mech": 4,
        "Det": 12,
        "DetHTR": 21,
        "MechHTR": 42,
        "Moving": 53,
        "TEC_0_9A": 145,
        "TEC35": 100,
        "TEC65": 140,
    },
    "EM": {  # Consumption Dictionary for EMC
        "State1": 90,
        "State2": 170,
        "State3": 190,
        "State4": 340,
        "State5": 277,
        "State6": 200,
        "State7": 394,
        "Standby": 110,
        "Mech": 4,
        "Det": 10,
        "DetHTR": 19,
        "MechHTR": 38,
        "Moving": 50,
        "TEC_0_9A": 150,
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

# ----MMS Configuration-----------------------------------------------------------------------------
# When True, OB_GENERAL_ERROR in the EB ERROR_FLAGS is excluded from MMS trigger conditions.
# OB_GENERAL_ERROR is a sticky bit that may linger after the OB error has already cleared.
# Set to False to allow OB_GENERAL_ERROR to trigger MMS actions.
MMS_MASK_OB_GENERAL_ERROR: bool = False
