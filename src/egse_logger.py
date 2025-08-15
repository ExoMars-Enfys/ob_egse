import logging
from pathlib import Path

# TODO! : Need to have better control of logging levels and what is displayed. Perhaps in constants file.
# TODO! : Define the purpose and contents of each log file.

def get_loggers(basedir: Path, prefix: str, debug_level: str = logging.INFO) -> tuple[logging.Logger]:
    # ----Handlers---------------------------------------------------------------------------------------
    cl_formatter = logging.Formatter("{levelname} - {message}", style="{")  # Setting the logging format for console loggers
    fh_formatter = logging.Formatter("%(asctime)s - %(message)s")  # Setting the logging format for file loggers
    # -- Console Stream Handler --
    cl_hdlr = logging.StreamHandler()
    cl_hdlr.setFormatter(cl_formatter)
    cl_hdlr.setLevel(logging.WARNING)

    # -- Event Console Stream Handler --
    ecl_hdlr = logging.StreamHandler()
    ecl_hdlr.setFormatter(cl_formatter)
    ecl_hdlr.setLevel(logging.INFO)
    
    # -- File Stream Handlers --
    # -- Info Handler - Streams every single command being sent to the OB with its Response --
    info_fh = logging.FileHandler(basedir / (prefix + "_INFO.log"))
    info_fh.setFormatter(fh_formatter)
    
    # -- Error Handler - Streams every Error --
    error_fh = logging.FileHandler(basedir / (prefix + "_ERROR.log"))
    error_fh.setFormatter(fh_formatter)
    
    # -- PSU Handler - Streams only PSU logs --
    psu_fh = logging.FileHandler(basedir / (prefix + "_PSU.log"))
    psu_fh.setFormatter(fh_formatter)

    # ----Loggers---------------------------------------------------------------------------------------    
    # -- Initiate event_log streamer --
    event_log = logging.getLogger("event_log")
    event_log.setLevel(debug_level)
    event_log.addHandler(ecl_hdlr)
    event_log.addHandler(info_fh)
    error_fh_event = logging.FileHandler(basedir / (prefix + "_ERROR.log"))
    error_fh_event.setFormatter(fh_formatter)
    error_fh_event.setLevel(logging.ERROR)
    event_log.addHandler(error_fh_event)
    
    # -- Initiate info writer --
    info_log = logging.getLogger("info_log")
    info_log.setLevel(logging.INFO)
    info_log.addHandler(info_fh)
    info_log.addHandler(cl_hdlr)
    error_fh_info = logging.FileHandler(basedir / (prefix + "_ERROR.log"))
    error_fh_info.setFormatter(fh_formatter)
    error_fh_info.setLevel(logging.ERROR)
    info_log.addHandler(error_fh_info)

    # -- Initiate psu writer --
    psu_log = logging.getLogger("psu_log")
    psu_log.setLevel(logging.INFO)
    psu_log.addHandler(psu_fh)
    psu_log.addHandler(cl_hdlr)
    error_fh_psu = logging.FileHandler(basedir / (prefix + "_ERROR.log"))
    error_fh_psu.setFormatter(fh_formatter)
    error_fh_psu.setLevel(logging.ERROR)
    psu_log.addHandler(error_fh_psu)

    return (event_log, info_log, psu_log)
