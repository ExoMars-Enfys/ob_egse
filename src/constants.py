import logging
from collections import deque

from datetime import datetime
from pathlib import Path

CMD_SPEED_DICT = {
    "Steady": 1.0,
    "Fast": 0,
}

# ----Initialisation---------------------------------------------------------------------------------
EXP_MODEL_ID = 0x07

DEBUG_LEVEL = logging.INFO
DEFAULT_PREFIX = "PSU_LOG_test"  # datetime.now().strftime("%Y%m%dT%H%M%S")
DEFAULT_PATH = Path.cwd() / "logs" / DEFAULT_PREFIX
DEFAULT_COM_PORT = 12
DEFAULT_CMD_SPEED = "Steady"  # "Steady" or "Fast"
SCI_RESP_MARGIN = 0.020 # seconds

LOG_PREFIX = DEFAULT_PREFIX
LOG_PATH = DEFAULT_PATH

#PSU Config
PSU_COMM_PORT = 7

# Set by EGSE.py do not write here.
ACK_LOG_FH = None
CMD_LOG_FH = None
HK_LOG_FH = None

# HK queue
hk_queue = deque(maxlen=100)
