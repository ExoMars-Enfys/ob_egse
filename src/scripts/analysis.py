from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import matplotlib.pyplot as plt
import bitstruct
import sys
import logging
# Add parent directory to Python path to find tmstruct
sys.path.append(str(Path(__file__).parent.parent))
import tmstruct
info_log = logging.getLogger("info_log")

def calculate_cumulative_steps(abs_steps, rel_steps, cal_flag):
    if not rel_steps:
        return []
        
    cumulative = [0]
    # Handle initial uncalibrated state
    for i in range(1, len(abs_steps)):
        if cal_flag[i-1] == 0 and abs_steps[i-1]==0:
            step_diff = int(rel_steps[i]) - int(rel_steps[i-1])
            cumulative.append(cumulative[-1] + abs(step_diff))
        else:
            # System is calibrated, calculate based on absolute position difference
            if abs_steps[i] != 0:
                # Calculate difference between consecutive absolute positions
                step_diff = int(abs_steps[i]) - int(abs_steps[i-1])
                cumulative.append(cumulative[-1] + abs(step_diff))
    
    return cumulative

def decode_bytes(raw_bytes, struct = tmstruct.hk):
        param = bitstruct.unpack_dict(
            "".join(i[1] for i in struct),
            [i[0] for i in struct],
            raw_bytes,
        )
        return param


def parse_log_file(file_path):
    abs_steps = []
    rel_steps = []
    cal_flag = []
    
    with open(file_path, 'r') as f:
        for line in f:
            try: 
                # Get the hex string after timestamp
                raw_bytes = bytes.fromhex(line.split(' - ')[1].strip())
                parsed = decode_bytes(raw_bytes)                
                abs_steps.append(parsed['MTR_ABS_STEPS'])       
                rel_steps.append(parsed['MTR_REL_STEPS'])
                cal_flag.append((parsed['MTR_FLAGS_BYTE'] & 0x40) >> 6 )
                print(f"Abs: {parsed['MTR_ABS_STEPS']}, Rel: {parsed['MTR_REL_STEPS']}, CAL: {cal_flag[-1]}")
            except (IndexError, ValueError):
                continue
    
    return abs_steps, rel_steps, cal_flag

def export_results(abs_steps,cum_steps):
    
        if cum_steps:
            info_log.info(f"\n------------------------------------------------------------------")
            info_log.info(f"* Total cumulative steps moved: {cum_steps[-1]}")
            info_log.info(f"* Maximum absolute position: {max(abs_steps)}")
            info_log.info(f"* Minimum absolute position: {min(abs_steps)}")

def analysis(path,prefix):
    if path:
        file_path = path / (prefix + "_HK.LOG")
    else:
    # Open file dialog
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title="Select HK LOG file", 
                                            filetypes=[("Log files", "*HK*.LOG")])
    
    if not file_path:
        print("No file selected")
        return
    
    # Parse file and get absolute steps
    abs_steps, rel_steps, cal_flag = parse_log_file(file_path)
    cum_steps = calculate_cumulative_steps(abs_steps,rel_steps,cal_flag)
    
    # Print and export step counts
    print(f"Total samples: {len(abs_steps)}")
    if cum_steps:
        print(f"Total cumulative steps moved: {cum_steps[-1]}")
        print(f"Maximum absolute position: {max(abs_steps)}")
        print(f"Minimum absolute position: {min(abs_steps)}")
        
    # Export results
    export_results(abs_steps,cum_steps)

    # Create separate figure for Absolute Position
    fig1 = plt.figure(figsize=(10, 4))
    ax1 = fig1.add_subplot(1, 1, 1)
    ax1.plot(abs_steps, marker='.', linestyle='-', color='C0')
    ax1.set_title('Absolute Position')
    ax1.set_xlabel('Sample')
    ax1.set_ylabel('Steps')
    ax1.grid(True)
    plt.tight_layout()    
    plt.savefig(path / "-Abs_Steps.jpg", format="jpg")

    # Create separate figure for Cumulative Steps based only on relative steps
    fig2 = plt.figure(figsize=(10, 4))
    ax2 = fig2.add_subplot(1, 1, 1)
    ax2.plot(cum_steps, marker='.', linestyle='-', color='C1')
    ax2.set_title('Cumulative Steps')
    ax2.set_xlabel('Sample')
    ax2.set_ylabel('Cumulative Steps')
    ax2.grid(True)
    plt.tight_layout()
    plt.savefig(path / "-Cumulative_steps.jpg", format="jpg")

if __name__ == '__main__':
    analysis(path=None)