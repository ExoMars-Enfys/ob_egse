from saleae import automation
import os
import os.path
from datetime import datetime
import constants as const
import logging

info_log = logging.getLogger("info_log")

#Creation of HLA class to allow the inheritance of a manager accross threads
class HLA:
    def __init__(self) -> None:
         self.application_path="C:/Program Files/Logic/Logic.exe"
         self.manager = None
         self.capture = None

    def hla_init(self):
        # Launch of the Logic2 instance before starting the capture to give time to the software to connect to the analyser early.
        self.manager =  automation.Manager.launch(self.application_path)
        
        

    def hla_capture(self,path,hla_event):
        # Configuration of the HLA device capture parameters
        device_configuration = automation.LogicDeviceConfiguration(
            enabled_digital_channels=[0, 1, 2, 3,4,5,6,7],
            digital_sample_rate=10_000_000,
        )
        #for a time based capture, use the TimedCaptureMode instead of ManualCaptureMode
        capture_configuration = automation.CaptureConfiguration(
            capture_mode=automation.ManualCaptureMode()
        )
        while not hla_event.is_set():
            try:
                # Start the HLA capture
                self.capture = self.manager.start_capture(
                        device_id='C44025CE2965C155', # Replace with your Logic device ID - This Logic Device ID is for the Logic 16 MSSL ID0148
                        device_configuration=device_configuration,
                        capture_configuration=capture_configuration)
                info_log.info("HLA Capture Started")
                self.capture.wait()
            except Exception as e:
                info_log.error(f"HLA Capture Failed to Start: {e}")
            hla_event.wait()

    #Handle the stopping of HLA capture and exporting data
    def hla_stop(self,path):            
        self.capture.stop()
        # Export raw digital data to a CSV file
        csv_filepath = os.path.join(path,'hla_captures')
        print(f"Exporting raw data to {csv_filepath}...")
        self.capture.export_raw_data_csv(csv_filepath, digital_channels=[0, 1, 2, 3])
        # Save capture file as .SAL
        capture_filepath = os.path.join(csv_filepath, const.LOG_PREFIX +'_hla_capture.sal')
        self.capture.save_capture(filepath=capture_filepath)
        print(f"Capture saved to {capture_filepath}")
            # break



# The following is a function to add an analyzer to your capture. to add the analyzer, process the following statements before exporting to CSV or SAL
    # # Add SPI analyzer to the capture
    # spi_analyzer = capture.add_analyzer('SPI', label=f'Test Analyzer', settings={
    #             'MISO': 1,
    #             'Clock': 0,
    #             'Enable': 2,
    #             'Bits per Transfer': '8 Bits per Transfer (Standard)'
    #         })

    # # Export analyzer data to a CSV file
    # analyzer_export_filepath = os.path.join(path, 'spi_export.csv')
    # capture.export_data_table(
    #     filepath=analyzer_export_filepath,
    #     analyzers=[spi_analyzer]
    # )

    

    