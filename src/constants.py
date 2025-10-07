import logging
from collections import deque

from datetime import datetime
from pathlib import Path

CMD_SPEED_DICT = {
    "Steady": 0.15,
    "Fast": 0,
}

# ----Initialisation---------------------------------------------------------------------------------
EXP_MODEL_ID = 0x06

DEBUG_LEVEL = logging.INFO
DEFAULT_PREFIX = datetime.now().strftime("%Y%m%dT%H%M%S")
DEFAULT_PATH = Path.cwd() / "logs" / DEFAULT_PREFIX
DEFAULT_COM_PORT = 18
DEFAULT_CMD_SPEED = "Steady"  # "Steady" or "Fast"
SCI_RESP_MARGIN = 0.020 # seconds
LOG_PREFIX = DEFAULT_PREFIX
LOG_PATH = DEFAULT_PATH

#PSU Config
PSU_LOGGING_FREQ = 1 #in HZ
PSU_COM_PORT = 3
CH1_OVP = 12.5
CH1_I = 0.150

CH2_OVP = 12.5
CH2_I = 0.05

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

#SCI queue
sci_queue = deque(maxlen=100)
