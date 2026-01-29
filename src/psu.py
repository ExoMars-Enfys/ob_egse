# Std library
import logging
import sys
from collections import deque

# Added packages
import serial
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

# Local modules
import constants as const
import time

info_log = logging.getLogger("info_log")
event_log = logging.getLogger("event_log")
psu_log = logging.getLogger("psu_log")


def init_psu_comms(port) -> serial.Serial:
    psuport = serial.Serial(port=None, timeout=1.0)
    psuport.port = port  # Assign com_port afterwards to prevent opening immediately
    return psuport


def open_psu_comms(port, psu_not_required) -> serial.Serial | None:
    try:
        port.open()
    except serial.SerialException:
        if psu_not_required:
            return
        else:
            info_log.error(f"No PSU found on COM Port {port.port}, try another")
            sys.exit(1)

    # Clear buffers multiple times to ensure clean state
    for _ in range(3):
        port.flushOutput()
        port.flushInput()
    
    # Give PSU time to be ready after opening
    time.sleep(1.0)

    return port


def close_psu_comms(port: serial.Serial) -> None:
    if port:
        port.write("LOCAL\r\n".encode("utf-8"))
        time.sleep(0.5)
        port.close()
    return


def psuRead(
    port,
    channel,
    type,
    output=False,
):
    if not output:
        port.write(f"{type}{channel}?\r\n".encode("utf-8"))
        response = port.read(8).decode("utf-8")
    else:
        port.write(f"{type}{channel}O?\r\n".encode("utf-8"))
        response = port.read(8).decode("utf-8")
    port.flushOutput()
    port.flushInput()
    return response


def plot_psu_live_data(port, stop_event, freq):
   
    
    # Initialize data storage with max length of 100 readings
    max_readings = 100
    data_dict = {
        'ch1_voltages': deque(maxlen=max_readings),
        'ch1_currents': deque(maxlen=max_readings),
        'ch2_voltages': deque(maxlen=max_readings),
        'ch2_currents': deque(maxlen=max_readings),
        'ch3_voltages': deque(maxlen=max_readings),
        'ch3_currents': deque(maxlen=max_readings),
        'time_points': deque(maxlen=max_readings),
        'start_time': time.time(),
        'plot_counter': 0
    }
    
    # Create figure with 2 subplots (voltage and current)
    fig, (ax_voltage, ax_current) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle("PSU Live Monitoring", fontsize=16)
    
    # Configure voltage subplot
    ax_voltage.set_title("Voltage (V)")
    ax_voltage.set_xlabel("Time (s)")
    ax_voltage.set_ylabel("Voltage (V)")
    ax_voltage.grid(True, alpha=0.3)
    
    # Configure current subplot
    ax_current.set_title("Current (A)")
    ax_current.set_xlabel("Time (s)")
    ax_current.set_ylabel("Current (A)")
    ax_current.grid(True, alpha=0.3)
    
    # Line objects for direct plotting
    line_v_ch1, = ax_voltage.plot([], [], label='CH1', color='red', linewidth=2)
    line_v_ch2, = ax_voltage.plot([], [], label='CH2', color='blue', linewidth=2)
    line_v_ch3, = ax_voltage.plot([], [], label='CH3', color='green', linewidth=2)
    
    line_i_ch1, = ax_current.plot([], [], label='CH1', color='red', linewidth=2)
    line_i_ch2, = ax_current.plot([], [], label='CH2', color='blue', linewidth=2)
    line_i_ch3, = ax_current.plot([], [], label='CH3', color='green', linewidth=2)
    
    ax_voltage.legend(loc='upper left')
    ax_current.legend(loc='upper left')
    
    # Store axes and lines in data_dict for access in update function
    data_dict['axes'] = {'voltage': ax_voltage, 'current': ax_current}
    data_dict['lines'] = {
        'v_ch1': line_v_ch1, 'v_ch2': line_v_ch2, 'v_ch3': line_v_ch3,
        'i_ch1': line_i_ch1, 'i_ch2': line_i_ch2, 'i_ch3': line_i_ch3
    }
    data_dict['fig'] = fig
    
    psu_log.info("PSU Live Plot initialized (saving to file every 10 updates)")
    
    return fig, (ax_voltage, ax_current), data_dict


def update_psu_plot(data_dict, ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i):
    if data_dict is None:
        return
    
    try:
        # Strip units and convert to float
        ch1_v_float = float(ch1_v.rstrip().strip("V"))
        ch1_i_float = float(ch1_i.rstrip().strip("A"))
        ch2_v_float = float(ch2_v.rstrip().strip("V"))
        ch2_i_float = float(ch2_i.rstrip().strip("A"))
        ch3_v_float = float(ch3_v.rstrip().strip("V"))
        ch3_i_float = float(ch3_i.rstrip().strip("A"))
        
        # Store data
        data_dict['ch1_voltages'].append(ch1_v_float)
        data_dict['ch1_currents'].append(ch1_i_float)
        data_dict['ch2_voltages'].append(ch2_v_float)
        data_dict['ch2_currents'].append(ch2_i_float)
        data_dict['ch3_voltages'].append(ch3_v_float)
        data_dict['ch3_currents'].append(ch3_i_float)
        
        elapsed_time = time.time() - data_dict['start_time']
        data_dict['time_points'].append(elapsed_time)
        data_dict['plot_counter'] += 1
        
        # Update lines
        lines = data_dict['lines']
        axes = data_dict['axes']
        
        if len(data_dict['time_points']) > 0:
            lines['v_ch1'].set_data(list(data_dict['time_points']), list(data_dict['ch1_voltages']))
            lines['v_ch2'].set_data(list(data_dict['time_points']), list(data_dict['ch2_voltages']))
            lines['v_ch3'].set_data(list(data_dict['time_points']), list(data_dict['ch3_voltages']))
            
            lines['i_ch1'].set_data(list(data_dict['time_points']), list(data_dict['ch1_currents']))
            lines['i_ch2'].set_data(list(data_dict['time_points']), list(data_dict['ch2_currents']))
            lines['i_ch3'].set_data(list(data_dict['time_points']), list(data_dict['ch3_currents']))
            
            # Auto-scale axes
            if len(data_dict['time_points']) > 1:
                time_min = min(data_dict['time_points'])
                time_max = max(data_dict['time_points'])
                axes['voltage'].set_xlim(time_min, time_max)
                axes['current'].set_xlim(time_min, time_max)
                
                v_min = min(min(data_dict['ch1_voltages']) if data_dict['ch1_voltages'] else 0,
                           min(data_dict['ch2_voltages']) if data_dict['ch2_voltages'] else 0,
                           min(data_dict['ch3_voltages']) if data_dict['ch3_voltages'] else 0)
                v_max = max(max(data_dict['ch1_voltages']) if data_dict['ch1_voltages'] else 1,
                           max(data_dict['ch2_voltages']) if data_dict['ch2_voltages'] else 1,
                           max(data_dict['ch3_voltages']) if data_dict['ch3_voltages'] else 1)
                v_margin = (v_max - v_min) * 0.1 if (v_max - v_min) > 0 else 0.5
                axes['voltage'].set_ylim(v_min - v_margin, v_max + v_margin)
                
                i_min = min(min(data_dict['ch1_currents']) if data_dict['ch1_currents'] else 0,
                           min(data_dict['ch2_currents']) if data_dict['ch2_currents'] else 0,
                           min(data_dict['ch3_currents']) if data_dict['ch3_currents'] else 0)
                i_max = max(max(data_dict['ch1_currents']) if data_dict['ch1_currents'] else 1,
                           max(data_dict['ch2_currents']) if data_dict['ch2_currents'] else 1,
                           max(data_dict['ch3_currents']) if data_dict['ch3_currents'] else 1)
                i_margin = (i_max - i_min) * 0.1 if (i_max - i_min) > 0 else 0.5
                axes['current'].set_ylim(i_min - i_margin, i_max + i_margin)
                
                # Draw canvas and save plot to file every 10 updates
                if data_dict['plot_counter'] % 10 == 0:
                    try:
                        # Draw the figure canvas to refresh
                        if hasattr(data_dict['fig'].canvas, 'draw'):
                            data_dict['fig'].canvas.draw()
                        plot_path = const.LOG_PATH / "psu_live_plot.png"
                        data_dict['fig'].savefig(plot_path, dpi=100, bbox_inches='tight')
                    except Exception as e:
                        psu_log.warning(f"Error saving plot file: {e}")
    
    except Exception as e:
        psu_log.error(f"Error updating PSU plot: {e}")


def psu_monitor_thread(port, stop_event , freq, ebmode = False, psu_lock = None, channel_state=None):
    if port:
        
        if not ebmode:
            # Initialize plotting if not in GUI mode
            fig, axes, plot_data = plot_psu_live_data(port, stop_event, freq, )
            
            try:
                while not stop_event.is_set():
                    try:
                        # Read the voltage and current for each channel
                        ch1_v = psuRead(port, "1", "V", True).rstrip()
                        ch1_i = psuRead(port, "1", "I", True).rstrip()
                        ch2_v = psuRead(port, "2", "V", True).rstrip()
                        ch2_i = psuRead(port, "2", "I", True).rstrip()
                        ch3_v = psuRead(port, "3", "V", True).rstrip()
                        ch3_i = psuRead(port, "3", "I", True).rstrip()
                        ch4_v = "N/A"
                        ch4_i = "N/A"
                        
                        const.psu_queue.append([ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i, ch4_v, ch4_i])

                        # Log the readings
                        psu_log.info(f"{ch1_v}  \t{ch1_i}  \t{ch2_v}  \t{ch2_i}  \t{ch3_v}  \t{ch3_i}")
                        
                        # Update plot if not in GUI mode
                        if plot_data is not None:
                            update_psu_plot(plot_data, ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i)
                        
                        if (
                            not (11.2 < float(ch1_v.strip("V")) < 13.2)
                            or not (11.2 < float(ch2_v.strip("V")) < 13.2)
                            or not (4.8 < float(ch3_v.strip("V")) < 5.5)
                        ):
                            psu_log.error(f"Voltage out of bounds Ch1 :  {ch1_v}\t Ch2 : {ch2_v}\t Ch3 : {ch3_v} ")
                            emergencyShutDown(port)

                        if (
                            (float(ch1_i.strip("A")) >= 150)
                            or (float(ch2_i.strip("A")) >= 90)
                            or (float(ch3_i.strip("A")) >= 150)
                        ):
                            psu_log.error(f"Current out of bounds Ch1 :  {ch1_i}\t Ch2 : {ch2_i}\t Ch3 : {ch3_i} ")
                            emergencyShutDown(port)
            

                    except Exception as e:
                        psu_log.error(f"Error in PSU monitor thread: {e}")
                    waitTime = 1 / (freq)
                    stop_event.wait(waitTime)  # Sleep for 200 ms before the next reading
            finally:
                # Clean up matplotlib figures when thread stops
                if fig is not None:
                    try:
                        plt.close(fig)
                    except Exception as e:
                        psu_log.warning(f"Error closing plot figure: {e}")
        else:
            start_time = time.time()
            while not stop_event.is_set():
                try:
                    ch1_v = "N/A"
                    ch1_i = "N/A"
                    ch2_v = "N/A"
                    ch2_i = "N/A"
                    
                    # Acquire lock before reading from PSU
                    if psu_lock:
                        with psu_lock:
                            # Read the voltage and current for channel 3 (ROV heaters)
                            ch3_v = psuRead(port, "3", "V", True).rstrip()
                            ch3_i = psuRead(port, "3", "I", True).rstrip()
                            # Read the voltage and current for channel 4 (EB)
                            ch4_v = psuRead(port, "4", "V", True).rstrip()
                            ch4_i = psuRead(port, "4", "I", True).rstrip()
                    else:
                        # Read the voltage and current for channel 3 (ROV heaters)
                        ch3_v = psuRead(port, "3", "V", True).rstrip()
                        ch3_i = psuRead(port, "3", "I", True).rstrip()
                        # Read the voltage and current for channel 4 (EB)
                        ch4_v = psuRead(port, "4", "V", True).rstrip()
                        ch4_i = psuRead(port, "4", "I", True).rstrip()
                    
                    # Clean up readings by removing common artifacts
                    def clean_psu_reading(value):
                        if not value or value == "N/A":
                            return "N/A"
                        # Remove null bytes and common non-numeric chars, keep only digits, decimal, V, A
                        cleaned = ''.join(c for c in value if c.isdigit() or c in '.-VA')
                        # Extract just the numeric part
                        numeric_part = ''.join(c for c in cleaned if c.isdigit() or c == '.')
                        if numeric_part:
                            return numeric_part
                        return "N/A"
                    
                    ch3_v = clean_psu_reading(ch3_v)
                    ch3_i = clean_psu_reading(ch3_i)
                    ch4_v = clean_psu_reading(ch4_v)
                    ch4_i = clean_psu_reading(ch4_i)

                    # Log the readings
                    psu_log.info(f"CH3 Voltage: {ch3_v}  \tCH3 Current: {ch3_i}  \tCH4 Voltage: {ch4_v}  \tCH4 Current: {ch4_i}  ")
                    
                    # Append data to queue for GUI display
                    const.psu_queue.append([ch1_v, ch1_i, ch2_v, ch2_i, ch3_v, ch3_i, ch4_v, ch4_i])
                    
                    elapsed = time.time() - start_time
                    lower_bound = 0.0 if elapsed < 0.5 else 26.0

                    def safe_float(value):
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return None

                    ch3_v_val = safe_float(ch3_v)
                    ch4_v_val = safe_float(ch4_v)

                    ch3_on = True
                    ch4_on = True
                    if isinstance(channel_state, dict):
                        ch3_on = bool(channel_state.get("ch3", True))
                        ch4_on = bool(channel_state.get("ch4", True))

                    if ch3_on and ch3_v_val is not None and not (lower_bound <= ch3_v_val <= 29.5):
                        psu_log.error(f"Voltage out of bounds Ch3 :  {ch3_v} ")
                        emergencyShutDown(port)

                    if ch4_on and ch4_v_val is not None and not (lower_bound <= ch4_v_val <= 29.5):
                        psu_log.error(f"Voltage out of bounds Ch4 :  {ch4_v} ")
                        emergencyShutDown(port)

                    if ch4_on and (float(ch4_i.strip("A")) >= 500):
                        psu_log.error(f"Current out of bounds Ch4 :  {ch4_i} ")
                        emergencyShutDown(port)

                except Exception as e:
                    psu_log.error(f"Error in PSU monitor thread: {e}")
                waitTime = 1 / (freq)
                stop_event.wait(waitTime)  # Sleep before the next reading


def setChannels(port,rov_htrs = False,ebmode = False):
    if port:
        # Set the voltage and current limits for each channel
        if not ebmode:
            psu_log.info(f"Setting PSU Channels: CH1 V: {12}V OVP: {const.CH1_OVP}V, CH1 I: {const.CH1_I}A")
            port.write(f"V1 12\r\n".encode("utf-8"))
            port.write(f"I1 {const.CH1_I}\r\n".encode("utf-8"))
            port.write(f"OVP1 {const.CH1_OVP} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH2 V: {12}V OVP: {const.CH2_OVP}V, CH2 I: {const.CH2_I}A")
            port.write(f"V2 12\r\n".encode("utf-8"))
            port.write(f"I2 {const.CH2_I}\r\n".encode("utf-8"))
            port.write(f"OVP2 {const.CH2_OVP} 1\r\n".encode("utf-8"))

            psu_log.info(f"Setting PSU Channels: CH3 V: {5}V OVP: {const.CH3_OVP}V, CH3 I: {const.CH3_I}A")
            port.write(f"V3 5\r\n".encode("utf-8"))
            port.write(f"I3 {const.CH3_I}\r\n".encode("utf-8"))
            port.write(f"OVP3 {const.CH3_OVP} 1\r\n".encode("utf-8"))

            psu_log.info("PSU Channels set successfully")
            psu_log.info(f"  CH1_V +12 \t   CH1_I {const.CH1_I}\t  CH2_V -12 \t  CH2_I {const.CH2_I}\t  CH3_V +5 \t   CH3_I {const.CH3_I}")
            port.flushOutput()
            port.flushInput()
        else : 
            if rov_htrs:
                psu_log.info(f"Setting PSU Channels: CH3 V: {28}V OVP: {const.ROV_HTR_OVP}V, CH4 I: {const.ROV_HTR_I}A")
                port.write(f"V3 28\r\n".encode("utf-8"))
                port.write(f"I3 {const.ROV_HTR_I}\r\n".encode("utf-8"))
                port.write(f"OVP3 {const.ROV_HTR_OVP} 1\r\n".encode("utf-8"))
                psu_log.info("PSU Channels set successfully")
                psu_log.info(f"  ROV_HTR_V +28 \t   ROV_HTR_I {const.ROV_HTR_I}")
                port.flushOutput()
                port.flushInput()
            else : 
                psu_log.info(f"Setting PSU Channels: CH4 V: {28}V OVP: {const.EB_OVP}V, CH4 I: {const.EB_I}A")
                port.write(f"V4 28\r\n".encode("utf-8"))
                port.write(f"I4 {const.EB_I}\r\n".encode("utf-8"))
                port.write(f"OVP4 {const.EB_OVP} 1\r\n".encode("utf-8"))
                psu_log.info("PSU Channels set successfully")
                psu_log.info(f"  EB_V +28 \t   EB_I {const.EB_I}")
                port.flushOutput()
                port.flushInput()                
    return


def switchPSU(port, state,rov_htrs = False, ebmode = False):
    # psu_status = int(psuRead(psu_com, "1", "OP",False))
    # psu_status = not psu_status
    if port:
        if not ebmode:
            port.write(f"OPALL {int(state)}\r\n".encode("utf-8"))
        else : 
            if rov_htrs:
                port.write(f"OP3 {int(state)}\r\n".encode("utf-8"))
            else :
                port.write(f"OP4 {int(state)}\r\n".encode("utf-8"))
    return


def emergencyShutDown(port):
    if port:
        port.write(f"OPALL 0\r\n".encode("utf-8"))
        psu_log.info(f"Closing all channels")
        port.write(f"LOCAL\r\n".encode("utf-8"))
        psu_log.info(f"Setting to Local control")
        port.flushOutput()
        port.flushInput()
        port.close()
    return


## TODO: Create a log for this -
# #?Done
## TODO: Create a clear settings file, Voltages to be set, Current limits
# ?Done in the constants file
## TODO: Add monitoring, such that we have warning current limits and alarm limits
## TODO: If alarm limit, automatically shutdown
# ?Done using emergency shut down function - closes outputs and switches to local control before closing comms
## TODO: Close the comms
# ?See above
## TODO: Report the link status
## TODO: Loop through every 1s (async?)
# ?Done with threading
