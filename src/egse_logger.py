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
    info_fh = logging.FileHandler(basedir / (prefix + "_INFO_DUMP.log"))
    info_fh.setFormatter(fh_formatter)
    
    # -- Error Handler - Streams every Error --
    error_fh = logging.FileHandler(basedir / (prefix + "_ERROR.log"))
    error_fh.setFormatter(fh_formatter)
    
    # -- PSU Handler - Streams only PSU logs --
    psu_fh = logging.FileHandler(basedir / (prefix + "_PSU.log"))
    psu_fh.setFormatter(fh_formatter)

    # ----Loggers---------------------------------------------------------------------------------------
    # -- Initiate tm_log streamer --
    tm_log = logging.getLogger("tm_log")
    tm_log.setLevel(debug_level)
    tm_log.addHandler(cl_hdlr)
    
    # -- Initiate tc_log streamer --
    tc_log = logging.getLogger("tc_log")
    tc_log.setLevel(debug_level)
    if not tc_log.handlers:
        tc_log.addHandler(cl_hdlr)
    
    # -- Initiate event_log streamer --
    event_log = logging.getLogger("event_log")
    event_log.setLevel(debug_level)
    event_log.addHandler(ecl_hdlr)
    
    # -- Initiate info writer --
    info_log = logging.getLogger("info_log")
    info_log.setLevel(logging.INFO)
    info_log.addHandler(info_fh)
    
    # -- Initiate error writer --
    error_log = logging.getLogger("error_log")
    error_log.setLevel(logging.ERROR)
    error_log.addHandler(error_fh)

    # -- Initiate psu writer --
    psu_log = logging.getLogger("psu_log")
    psu_log.setLevel(logging.INFO)
    psu_log.addHandler(psu_fh)

    return (tm_log, tc_log, event_log, info_log, error_log, psu_log)
