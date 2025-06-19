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

    tm_log, tc_log, event_log, info_log, error_log, abs_log, psu_log = egse_logger.get_loggers(
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

    return (tm_log, tc_log, event_log, info_log, error_log, abs_log,psu_log)


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


### --- Old Command Stuff ----------------------------------------------------------------------------------------------


def simple_commands(port) -> None:
    t1 = time.perf_counter(), time.process_time()

    # tc.heater_control(port, False, False, False, False, False)
    # tc.set_mech_sp(port, 2000, 1000)
    # tc.set_detec_sp(port, 2000, 1000)
    # tc.sci_offset(port, 2045, 973)
    # hk = tc.hk_request(port)  # cmd 00
    # sq.check_hk(port)
    # tc.clear_errors(port)                                                         #cmd 01
    # # TODO: Add set errors      (02)
    # tc.power_control(port, 0x03)  # cmd 04
    # tc.heater_control(port, False, True, False, False, True, verify=True)         #cmd 05
    # tc.set_mech_sp(port, 0x0ABC, 0x0123)                                          #cmd 06
    # tc.set_detec_sp(port, 0x0DEF, 0x0456)                                         #cmd 07
    # tc.set_mtr_param(port, 0x4000, 0x0001, 0x09, 0xFF)  # cmd 0A
    # tc.set_mtr_guard(port, 0x03, 0x0020, 0x0F, 0x0002)  # cmd 0B
    # tc.set_mtr_mon(port, 0x3200, 0x3200, 0x01E0)  # cmd 0C
    # TODO: Add Set Mtr Errors  (0D)
    # tc.mtr_mov_pos(port, 0x2190)                                                  #cmd 10
    # tc.mtr_mov_neg(port, 0x02190)                                                  #cmd 11
    # tc.mtr_mov_abs(port, 0x1FA4)                                                  #cmd 12
    # tc.mtr_homing(port, False, False, True)  # cmd 13
    #sq.power_up_tests(port)
    #sq.homing_test(port)
    # sq.motor_fw_test(port)
    # TODO: Add Motor Halt      (15)
    # TODO: Add SWIR            (18)
    # TODO: Add MWIR            (19)
    # TODO: Add HK Samples      (1B)
    # sci = tc.sci_request(port, 3, 1)
    # sq.check_sci(port)
    #event_log.info(f"HK SWIR offset: {hk.SWIR_OFFSET}; SCI SWIR offset: {sci.SWIR_OFFSET}")
    #event_log.info(f"HK MWIR offset: {hk.MWIR_OFFSET}; SCI MWIR offset: {sci.MWIR_OFFSET}")

    # cmd_mtr_mov_pos(port, 0x1000, True)

    # for i in range(0, 100):
    #     hk = tc.hk_request(port)

    # hk = tc.hk_request(port)
    # set_params(HEATERS=False)
    # tc.mtr_mov_abs(port, 0x1FA4)
    # sq.verify_sequence(port)
    # continuous_runs()
    # sq.script_repeat_hk(port)
    # start_stops()
    # script_stops()

    t2 = time.perf_counter(), time.process_time()

    # print(f" Real time: {t2[0] - t1[0]:.4f} seconds")
    # print(f" CPU time: {t2[1] - t1[1]:.4f} seconds")


def main() -> None:
    parser = init_arparse()
    args = parser.parse_args()

    # Setup loggers
    const.LOG_PREFIX = str(args.prefix).strip("'")
    const.LOG_PATH = args.basedir
    (tm_log, tc_log, event_log, info_log, error_log, abs_log,psu_log) = setup_logs()

    com_port = "COM" + str(args.com)

    if args.script:
        info_log.info("Running Script")
        port = comms.initialise_comms(com_port)
        port = comms.open_comms(port)

        # Initialise PSU
        # psu_port = psu.initialise_psu_mx100qp_comms(const.PSU_COMM_PORT)
        # psu.setChannels(psu_port, True, True, True)

        # User add commands or sequences here
        sq.abu_hk(port, False)
        sq.abu_cal_motor(port)
        sq.abu_dac_mwir_offset(port, 2048)
        # sq.abu_set_offset(port, 2170, 2048) # DAC Offsets Determined
        # sq.abu_set_offset(port, 2750, 3200)
        # sq.abu_rtn_to_base(port)
        sq.abu_measure(port, 0)
        for i in range(0, 500, 100):
            sq.abu_measure(port, 100)

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
