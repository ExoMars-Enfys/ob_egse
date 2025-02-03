import logging
from pathlib import Path

def get_loggers(basedir: Path, prefix:str, debug_level:str = logging.INFO):
    # ----Handlers---------------------------------------------------------------------------------------
    cl_formatter = logging.Formatter("{levelname} - {message}", style="{") # Setting the logging format for console loggers
    fh_formatter = logging.Formatter('%(asctime)s - %(message)s') # Setting the logging format for file loggers
    # -- Console Stream Handler --
    hdlr_1 = logging.StreamHandler()
    hdlr_1.setFormatter(cl_formatter)
    # -- File Stream Handlers --
    # -- Info Handler - Streams every single command being sent to the OB with its Response --
    info_fh = logging.FileHandler(basedir / (prefix + "_INFO_DUMP.log"))
    info_fh.setFormatter(fh_formatter)
    # -- Error Handler - Streams every Error --
    error_fh = logging.FileHandler(basedir / (prefix + '_ERROR.log'))
    error_fh.setFormatter(fh_formatter)
    # -- AbsSteps Handler - Streams only every movement and ABS Steps --
    abs_fh = logging.FileHandler(basedir / (prefix + '_ABS_STEPS.log'))
    abs_fh.setFormatter(fh_formatter)

    # ----Loggers---------------------------------------------------------------------------------------
    # -- Initiate tm_log streamer --
    tm_log = logging.getLogger("tm_log")
    tm_log.setLevel(debug_level)
    tm_log.addHandler(hdlr_1)
    # -- Initiate tc_log streamer --
    tc_log = logging.getLogger("tc_log")
    tc_log.setLevel(debug_level)
    tc_log.addHandler(hdlr_1)
    # -- Initiate event_log streamer --
    event_log = logging.getLogger("event_log")
    event_log.setLevel(debug_level)
    event_log.addHandler(hdlr_1)
    # -- Initiate info writer --
    info_log = logging.getLogger("info_log")
    info_log.setLevel(logging.INFO)
    info_log.addHandler(info_fh)
    # -- Initiate error writer --
    error_log = logging.getLogger("error_log")
    error_log.setLevel(logging.ERROR)
    error_log.addHandler(error_fh)
    # -- Initiate error writer --
    abs_log = logging.getLogger("abs_log")
    abs_log.setLevel(logging.INFO)
    abs_log.addHandler(abs_fh)

    return (tm_log, tc_log, event_log, info_log, error_log, abs_log)