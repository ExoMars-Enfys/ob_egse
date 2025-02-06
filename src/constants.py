import logging

from datetime import datetime
from pathlib import Path

CMD_SPEED_DICT = {
    "Steady": 1.0,
    "Fast": 0,
}

# ----Initialisation---------------------------------------------------------------------------------
EXP_MODEL_ID = 0x07

DEBUG_LEVEL = logging.INFO
DEFAULT_PREFIX = datetime.now().strftime("%Y%m%dT%H%M%S")
DEFAULT_PATH = Path.cwd() / "logs" / DEFAULT_PREFIX
DEFAULT_COM_PORT = 10
DEFAULT_CMD_SPEED = "Steady"

LOG_PREFIX = DEFAULT_PREFIX
LOG_PATH = DEFAULT_PATH

# Set by EGSE.py do not write here.
ACK_LOG_FH = None
CMD_LOG_FH = None
HK_LOG_FH = None
