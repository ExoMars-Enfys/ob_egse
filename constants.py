import logging

from datetime import datetime
from pathlib import Path

# ----Initialisation---------------------------------------------------------------------------------
EXP_MODEL_ID = 0x07

DEBUG_LEVEL = logging.INFO
DEFAULT_PREFIX = datetime.now().strftime("%Y%m%dT%H%M%S")
DEFAULT_PATH = Path.cwd() / "logs" / DEFAULT_PREFIX
DEFAULT_COM_PORT = 14

# -- Functions to share between modules
def get_log_path() -> Path:
    return Path(logging.getLogger("info_log").handlers[0].baseFilename)

def get_log_dir() -> Path:
    return get_log_path().parent

def get_log_prefix() -> str:
    return get_log_path().stem.split('_')[0]
