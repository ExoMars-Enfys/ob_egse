# ----Module Imports--------------------------------------------------------------------------------
# Std library
import logging
import time
import sys
import atexit
import argparse
from pathlib import Path
from datetime import datetime
import threading

# Local modules
import comms
import constants as const
import egse_logger
import gui
import psu
import scripts.sequences as sq
import scripts.error_checks as ec
import scripts.abu_sequences as abu
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
    parser.add_argument("-psuport", type = int, default = const.PSU_COM_PORT)
    parser.add_argument("-basedir", type=Path, default=const.DEFAULT_PATH)
    parser.add_argument("-np","--nopsu", action="store_true")
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
# def clean_exit(psuport):
#     # Adding parsing to be able to shut down psu 
#     # !TODO: Make sure this is the correct way?


#     const.ACK_LOG_FH.close()
#     const.CMD_LOG_FH.close()
#     const.HK_LOG_FH.close()
#     const.SCI_LOG_FH.close()
#     psu.emergencyShutDown(psuport)
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
    psu_com = "COM" + str(args.psuport)

    if args.script:
        info_log.info("Running Script")
        info_log.info("Initialising RS-485 Comms")
        port = comms.initialise_comms(com_port)
        port = comms.open_comms(port)

        # info_log.info("Initialising PSU Comms")
        # psuport = psu.init_psu_comms(psu_com)       
        # psuport = psu.open_psu_comms(psuport,args.nopsu)
        # psu.setChannels(psuport, const.CH1_OVP, const.CH1_I, const.CH2_OVP, const.CH2_I, const.CH3_OVP, const.CH3_I)
        # psu.switchPSU(psuport, 1)  # Switch on PSU
        # time.sleep(1) #Adding a 1 second delay before starting monitoring thread for compensation of OVP
        # stop_event = threading.Event()
        # psu_thread = threading.Thread(target=psu.psu_monitor_thread, args=(psuport, stop_event,const.PSU_LOGGING_FREQ), daemon=True)
        # psu_thread.start()

        # TODO: Ensure sequence runs are recorded in info log as well.
        # ------------------------------------------------------------------------------------------
        # User add commands or sequences from here:
        # ------------------------------------------------------------------------------------------
        # sq.abu_hk(port, False)
        tc.clear_errors(port)
        tc.power_control(port,0x03)
        sq.check_hk(port)
        #abu.abu_hk(port,False)
        #sq.motor_fw_test(port)
        # Cal to Base
        #abu.abu_cal_motor(port)

        # # Home to Outer
        #abu.abu_outer_home(port)
        #abu.abu_pos_steps(port, 1900)

        # # Dark Offsets
        #
        # # find swir_offset whilst mwir_offset set to 500
        #swir_offset = abu.abu_dac_swir_offset(port, 500)
        # # move to abs_steps=2000
        #abu.abu_neg_steps(port,6960)
        #mwir_offset = abu.abu_dac_mwir_offset(port, swir_offset)

        # # Set offsets to (port,SWIR,MWIR)
        #abu.abu_set_offset(port, 100, 100)

        #abu.abu_cal_motor(port)
        #abu.abu_outer_home(port)

        #sq.abu_outer_home(port)
        #sq.abu_measure(port, 0 )
        #step=10
        #for i in range(1, 4095, 100):
        #    abu.abu_set_offset(port,i, 300,sci_adc_samp=1,sci_adc_skip=20)

        #for i in range(1, 4095):
        #    abu.abu_set_offset(port,300, i,sci_adc_samp=0,sci_adc_skip=20)

        # # Drive to Laser Peak
        # abu.abu_pos_steps(port, 2800)



        #abu.abu_measurement_scan(port, step_spacing = 10)
        #abu.abu_cal_motor(port)
        #abu.abu_outer_home(port)
        #abu.abu_pos_steps(port, 4000)
        #abu.abu_set_offset(port, 1984, 3584)
        #abu.abu_dac_swir_offset(port, 1984)
        #sq.abu_dac_mwir_offset(port, 1984)
        #event_log.info("Set both ADCs mid range")
        #while(True):
        #    sq.abu_hk(port, display_contents=True)
        #    sq.check_sci(port, 4, 20)
        #for i in range(1000,2100,1):
            #    time.sleep(1)
        #    abu.abu_set_offset(port,i, 300,sci_adc_samp=0,sci_adc_skip=20)

        #abu.abu_outer_home(port)
        #abu.abu_pos_steps(port, 1900)

        #for i in range(1800,4000,1):
            #    time.sleep(1)
        #    abu.abu_set_offset(port,1782, i)

        
        # # TODO! Add ability to give back local control of PSU
        # psuport.write(f"LOCAL\r\n".encode('utf-8'))
        # psu.close_psu_comms(psuport)
        
        comms.close_comms(port)
    else:
        info_log.info("Running GUI")
        gui.streamlit_gui(com_port,psu_com)


if __name__ == "__main__":
    main()

# TODO
# - Add a way to stop the script
# - Implement some sort of thread queue with the GUI running seperately
# - Move streamlit stuff to a different module
# - See if there is a better way to launch streamlit
# - See if the python run button can have arguments in vscode
