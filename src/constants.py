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
ALIM_TPR = (-50, +40)
ALIM_TPR_ADU = (1823, 2211)
