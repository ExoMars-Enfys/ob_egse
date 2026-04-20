![Enfys Logo](.\rsrc\Enfys_logo_-_FINAL_-_WHITE.png)

# Enfys EGSE V5 with GUI

## Description

This project is the EGSE software that runs the Enfys instrument in both the standalone OB and through the EB configurations

## Pre-requisites

- `VSCode`[download](https://code.visualstudio.com/)
- `Python 3.12<`[download](https://www.python.org/downloads/)
- `uv` [uv documentation](https://docs.astral.sh/uv/getting-started/)
- `UKRI RAL Space Enfys EGSE tools` available on [EB EGSE Github Repo](https://github.com/ExoMars-Enfys/EB_EGSE)

## Installation

### Virtual Environment Setup

The dependancy tool `uv` [uv documentation here](https://docs.astral.sh/uv/getting-started/)
is used to control the python virtual environment. This can be installed with

```
pip install uv
```

Once it has completed you can then run `uv sync --active` to install the appropriate dependencies.

### EB EGSE Tools Setup

1. The EGSE needs to be installed using gitbash by running the following command:

```gitbash =
cd c:/wdir/EB
git clone https://github.com/ExoMars-Enfys/EB_EGSE
git cd EB_EGSE
```

This installs the EB EGSE software repository alongside the Enfys Plot submodule and Enfys Scripts submodule.
Refer to each Test Procedure for the appropriate branch of each submodule to checkout to

2. Configure the EB EGSE by:
   1. Open the file <span style="color: #2ECC71;">.\RS422If.ini</span>  
       change the following line to the device COM-Ports needed for the EB.

      ```python =
      ComPort=14
      Parity=E
      BaudRate=112179
      ```

      <span style="color: #cc532e;">Note that when switching between Primary and Redundant RS422 connection the COM Port will need to be updated</span>

   2. Make sure you have the `enfys_map_file.json` in your Windows user directory as per:

      <span style="color: #2ECC71;">../../../Users/GK UserName/enfys_plot/enfys_map_file.json </span>

### EGSE Tools Setup

1. The EGSE needs to be installed using gitbash by running the following command:

```gitbash =
cd c:/wdir/OB_EGSE
git clone https://github.com/ExoMars-Enfys/ob_egse
git cd ob_egse
git checkout "insert final branch here"
```

2. Open the file <span style="color: #2ECC71;">.\src\core_modules\config.py</span>  
   change the following lines to the device COM-Ports needed and appropriate model ID

```python =
EXP_MODEL_ID = 0x07

DEFAULT_COM_PORT = 3
DEFAULT_CMD_SPEED = "Fast"  # "Steady" or "Fast"

# PSU Config
PSU_COM_PORT = 8
PSU_LOGGING_FREQ = 10  # in HZ
```

## Running the EGSE software tools

The EGSE software tools can now be ran by running through the following:

1. Run the EGSE software by executing the terminal command in a new terminal in VSCode

```python=
uv run main.py
```

<span style="color: #cc532e;">Decorator Options:</span>

**No Programmable PSU available to run `-np`**

```python=
uv run main.py -np
```

**Script mode `-s`**

```python=
uv run main.py -s
```

**Debugging mode that allows gui reload automatically at code save `-reload`**

```python=
uv run main.py -reload
```

![Alt IMG](Documentation\menu.png)

2. Select Start Tools
3. Select appropriate operating mode by toggling between the OB and EB switch

Extra steps for EB mode:

4. Select Log

   Navigate to the directory <span style="color: #2ECC71;">C:\wdir\EB\EB_EGSE\RS422</span> and locate the latest RS422.Log file

5. Select appropriate script and press play

## Shutting down the EGSE tools

The Tools are best shut using the appropriate procedure to ensure all logs are safely closed as well as all monitoring threads and PSU channels are turned off

The tools can be shut by pressing the stop button : ![stop button](Documentation\stop_button.png)
This ensures the following:

    1.  The log threads are safely terminated
    2. The PSU monitoring threads are safely terminated
    3. The PSU channels are turned off cutting the power to the instrument
    For EB only:
    4. Runs the Stop tools batch script that safely terminates the EB EGSE tools
