from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import matplotlib.pyplot as plt
import bitstruct
import sys
# Add parent directory to Python path to find tmstruct
sys.path.append(str(Path(__file__).parent.parent))
import tmstruct

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

def export_results(file_path, abs_steps, rel_steps, cum_steps,cal_flag):
    output_path = Path(file_path).parent / "step_analysis.md"
    print(output_path)
    
    with open(output_path, "w") as f:
        f.write("# Step Analysis Results\n\n")
        f.write(f"## Analysis of: {Path(file_path).name}\n\n")
        f.write(f"* Total samples: {len(abs_steps)}\n")
        if cum_steps:
            f.write(f"* Total cumulative steps moved: {cum_steps[-1]}\n")
            f.write(f"* Maximum absolute position: {max(abs_steps)}\n")
            f.write(f"* Minimum absolute position: {min(abs_steps)}\n\n")
            
            f.write("## Sample Data\n\n")
            f.write("| Sample | Absolute Position | Relative Steps | Cumulative Steps |\n")
            f.write("|--------|------------------:|---------------:|------------------:|\n")
            
            for i in range(len(abs_steps)):
                abs_pos = abs_steps[i]
                cum_pos = cum_steps[i] if i < len(cum_steps) else ""
                rel = ""
                if rel_steps is not None and i < len(rel_steps):
                    rel = rel_steps[i]
                f.write(f"| {i} | \t{ abs_pos} | \t{rel} | \t{cum_pos} |\t{cal_flag[i]}\n")

def main(path):
    if path:
        file_path = path / (path.name + "_HK.LOG")
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
    export_results(file_path, abs_steps, rel_steps, cum_steps,cal_flag)

    # Create separate figure for Absolute Position
    fig1 = plt.figure(figsize=(10, 4))
    ax1 = fig1.add_subplot(1, 1, 1)
    ax1.plot(abs_steps, marker='.', linestyle='-', color='C0')
    ax1.set_title('Absolute Position')
    ax1.set_xlabel('Sample')
    ax1.set_ylabel('Steps')
    ax1.grid(True)
    plt.tight_layout()

    # Create separate figure for Cumulative Steps based only on relative steps
    fig2 = plt.figure(figsize=(10, 4))
    ax2 = fig2.add_subplot(1, 1, 1)
    ax2.plot(cum_steps, marker='.', linestyle='-', color='C1')
    ax2.set_title('Cumulative Steps (relative-only)')
    ax2.set_xlabel('Sample')
    ax2.set_ylabel('Cumulative Steps')
    ax2.grid(True)
    plt.tight_layout()

    plt.show()

if __name__ == '__main__':
    main()