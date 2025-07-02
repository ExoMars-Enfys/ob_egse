# ----Module Imports--------------------------------------------------------------------------------
# Std library
import logging
import time
import sys
import atexit
import argparse
from pathlib import Path
from datetime import datetime
import psu

# Local modules
import comms
import constants as const
import egse_logger
import gui
import sequences as sq
import tc


## -- Setup session ----------------------------------------------------------------------------------------------------
def init_arparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] ",
        prog="ob_egse",
        description="Executes the OB EGSE either in script mode or with the streamlit GUI.",
    )
    parser.add_argument("-prefix", type=ascii, default=const.DEFAULT_PREFIX)
    parser.add_argument("-com", type=int, default=const.DEFAULT_COM_PORT)
    parser.add_argument("-basedir", type=Path, default=const.DEFAULT_PATH)
    parser.add_argument("-s", "--script", action="store_true")
    return parser


def setup_logs() -> tuple[logging.Logger]:
    if const.LOG_PATH == const.DEFAULT_PATH:
        const.LOG_PATH.mkdir(parents=True, exist_ok=True)

    event_log, info_log, psu_log = egse_logger.get_loggers(
        const.LOG_PATH, const.LOG_PREFIX, const.DEBUG_LEVEL
    )

    # Create ACK Byte Log
    ack_log_name = const.DEFAULT_PREFIX + "_ACK.LOG"
    const.ACK_LOG_FH = open(const.LOG_PATH / ack_log_name, "a+", encoding="utf-8")

    # Create CMD Byte Log
    cmd_log_name = const.DEFAULT_PREFIX + "_CMD.LOG"
    const.CMD_LOG_FH = open(const.LOG_PATH / cmd_log_name, "a+", encoding="utf-8")

    # Create HK Byte Log
    hk_log_name = const.DEFAULT_PREFIX + "_HK.LOG"
    const.HK_LOG_FH = open(const.LOG_PATH / hk_log_name, "a+", encoding="utf-8")

    # Create SCI Byte Log
    sci_log_name = const.DEFAULT_PREFIX + "_SCI.LOG"
    const.SCI_LOG_FH = open(const.LOG_PATH / sci_log_name, "a+", encoding="utf-8")

    return (event_log, info_log, psu_log)


# ----FPGA Boot and Connect-------------------------------------------------------------------------


# @atexit.register
# def clean_exit():
#     const.ACK_LOG_FH.close()
#     const.CMD_LOG_FH.close()
#     const.HK_LOG_FH.close()
#     const.SCI_LOG_FH.close()
#     sys.exit(1001)
#     #! TODO Add code here, possibly try and power insturment off
#     #! TODO power off power supply
#     #! TODO ensure all logs are written

def main() -> None:
    parser = init_arparse()
    args = parser.parse_args()

    # Setup loggers
    const.LOG_PREFIX = str(args.prefix).strip("'")
    const.LOG_PATH = args.basedir
    (event_log, info_log, psu_log) = setup_logs()

    com_port = "COM" + str(args.com)

    if args.script:
        info_log.info("Running Script")
        port = comms.initialise_comms(com_port)
        port = comms.open_comms(port)
        # TODO: Ensure sequence runs are recorded in info log as well.

        # Initialise PSU
        # psu_port = psu.initialise_psu_mx100qp_comms(const.PSU_COMM_PORT)
        # psu.setChannels(psu_port, True, True, True)

        # ------------------------------------------------------------------------------------------
        # User add commands or sequences from here:
        # ------------------------------------------------------------------------------------------
        sq.abu_hk(port, False)
        sq.vsense_check(port)
        # # Cal to Base
        # sq.abu_cal_motor(port)

        # # Home to Outer
        # sq.abu_outer_home(port)
        
        # # Dark Offsets
        # mwir_offset = sq.abu_dac_mwir_offset(port, 2048)
        # swir_offset = sq.abu_dac_swir_offset(port, mwir_offset)

        # # Drive to Laser Peak
        # sq.abu_pos_steps(port, 2800)
    
        # Take an averaging measurement there with detec heaters on 20 times.
        loop_len = 90
        event_log.info(f"Running rover heater test for-loop every 2 seconds: {loop_len} times")
        for i in range(0, loop_len):
            sq.abu_measure(port, 0)
            hk = tc.hk_request(port)
            event_log.info(f"Digital board temperature: {hk.DIGITAL_TRP}")
            time.sleep(2)
        
        event_log.info(f"Rover Heater Test Finished")

    else:
        info_log.info("Running GUI")
        gui.streamlit_gui(com_port)


if __name__ == "__main__":
    main()

# TODO
# - Add a way to stop the script
# - Implement some sort of thread queue with the GUI running seperately
# - Move streamlit stuff to a different module
# - See if there is a better way to launch streamlit
# - See if the python run button can have arguments in vscode
