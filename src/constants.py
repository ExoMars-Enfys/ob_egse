import logging
from collections import deque

from datetime import datetime
from pathlib import Path

CMD_SPEED_DICT = {
    "Steady": 0.25,
    "Fast": 0.05,
}

# ----Initialisation---------------------------------------------------------------------------------
EXP_MODEL_ID = 0x06

DEBUG_LEVEL = logging.INFO
DEFAULT_PREFIX = datetime.now().strftime("%Y%m%dT%H%M%S")
DEFAULT_PATH = Path.cwd() / "logs" / DEFAULT_PREFIX
DEFAULT_COM_PORT = 8
DEFAULT_CMD_SPEED = "Fast"  # "Steady" or "Fast"
SCI_RESP_MARGIN = 0.020  # seconds
LOG_PREFIX = DEFAULT_PREFIX
LOG_PATH = DEFAULT_PATH

# PSU Config
PSU_LOGGING_FREQ = 1  # in HZ
PSU_COM_PORT = 6
CH1_OVP = 12.5
CH1_I = 0.200

CH2_OVP = 12.5
CH2_I = 0.155

CH3_OVP = 5.5
CH3_I = 0.150

# Set by EGSE.py do not write here.
ACK_LOG_FH = None
CMD_LOG_FH = None
HK_LOG_FH = None
SCI_LOG_FH = None

# HK queue
hk_queue = deque(maxlen=100)

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
# LTM constants
LTM_HOMING_TIMEOUT = 30  # seconds
LTM_PARKING_TIMEOUT = 5  # seconds
LTM_BASE_NOMINAL_STEPS = 9480 
LTM_OUTER_NOMINAL_STEPS = 1000
LTM_TOL = 50  # steps
LTM_BASE_TOL = range(LTM_BASE_NOMINAL_STEPS - LTM_TOL, LTM_BASE_NOMINAL_STEPS + LTM_TOL)
LTM_OUTER_TOL = range(LTM_OUTER_NOMINAL_STEPS - LTM_TOL, LTM_OUTER_NOMINAL_STEPS + LTM_TOL)
LTM_PARKED = 9100
LTM_MWIR_DARK_POS = 8000
DARK_REGION_STEP_SIZE = 32  # steps
OPEN_APERTURE_STEP_SIZE = 48
# SCI queue
sci_queue = deque(maxlen=100)
