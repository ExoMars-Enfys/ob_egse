const MODULE_METADATA = {
  "root": "main.py",
  "generated_from": "src/**/*.py",
  "module_count": 42,
  "modules": [
    {
      "path": "src/analysis_modules/analysis.py",
      "package": "analysis_modules",
      "module": "analysis",
      "description": "Provides `analysis` module logic.",
      "functions": [
        {
          "name": "analysis",
          "line": 43,
          "description": "Analyze RS422 log file and create plots for EB and OB data.",
          "kind": "function"
        },
        {
          "name": "_read_all_packets",
          "line": 229,
          "description": "Read all packets from RS422 log file.",
          "kind": "function"
        },
        {
          "name": "_read_hk_line_log_packets",
          "line": 289,
          "description": "Read packets from line-based HK log format: '<timestamp> - <hex words>'.",
          "kind": "function"
        },
        {
          "name": "_parse_timestamp_text",
          "line": 345,
          "description": "Parse a timestamp string using known datetime formats.",
          "kind": "function"
        },
        {
          "name": "_apply_time_cutoff",
          "line": 355,
          "description": "Trim EB/OB/PSU data after a given time-of-day cutoff (HH:MM[:SS]).",
          "kind": "function"
        },
        {
          "name": "_build_error128_zoom_data",
          "line": 399,
          "description": "Build zoomed data from 5 samples before first Error 128 to the end.",
          "kind": "function"
        },
        {
          "name": "_extract_packet_timestamp",
          "line": 445,
          "description": "Extract packet timestamp from telemetry line context.",
          "kind": "function"
        },
        {
          "name": "_read_psu_log",
          "line": 479,
          "description": "Read PSU log file and extract CH3/CH4 voltage and current time series.",
          "kind": "function"
        },
        {
          "name": "_build_timeseries",
          "line": 560,
          "description": "Build time series data from packets.",
          "kind": "function"
        },
        {
          "name": "_get_state_name",
          "line": 663,
          "description": "Convert state code to human readable name.",
          "kind": "function"
        },
        {
          "name": "_get_state_color",
          "line": 674,
          "description": "Convert state code to color for plotting.",
          "kind": "function"
        },
        {
          "name": "_error_bits_to_value",
          "line": 685,
          "description": "Convert ERROR_FLAGS_BITS object to an integer for comparison.",
          "kind": "function"
        },
        {
          "name": "_decode_error_flags",
          "line": 704,
          "description": "Extract active EB error flags from decoded ERROR_FLAGS_BITS object.",
          "kind": "function"
        },
        {
          "name": "_format_error_description",
          "line": 722,
          "description": "Format EB error description for display.",
          "kind": "function"
        },
        {
          "name": "_show_error_popup",
          "line": 750,
          "description": "Display EB error information in a popup window.",
          "kind": "function"
        },
        {
          "name": "_format_hk_data",
          "line": 770,
          "description": "Format HK packet data for display.",
          "kind": "function"
        },
        {
          "name": "_get_hk_packet_from_pick",
          "line": 845,
          "description": "Resolve clicked sample to nearest HK packet in time.",
          "kind": "function"
        },
        {
          "name": "_show_hk_popup",
          "line": 881,
          "description": "Display HK data in a popup window.",
          "kind": "function"
        },
        {
          "name": "_create_eb_plot",
          "line": 899,
          "description": "Create EB window with voltage and temperature plots.",
          "kind": "function"
        },
        {
          "name": "_create_ob_plot",
          "line": 1044,
          "description": "Create OB window with voltage and temperature plots.",
          "kind": "function"
        },
        {
          "name": "_create_psu_plot",
          "line": 1182,
          "description": "Create PSU window with CH3/CH4 current plots.",
          "kind": "function"
        },
        {
          "name": "_create_ob_abs_steps_plot",
          "line": 1300,
          "description": "Create OB absolute motor steps plot over time.",
          "kind": "function"
        },
        {
          "name": "_build_arg_parser",
          "line": 1361,
          "description": "Implements `_build_arg_parser`.",
          "kind": "function"
        },
        {
          "name": "_save_open_figures",
          "line": 1394,
          "description": "Save all currently open matplotlib figures (as displayed in the plotting window).",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/analysis_modules/fill_chamber_temps_and_dwell.py",
      "package": "analysis_modules",
      "module": "fill_chamber_temps_and_dwell",
      "description": "Provides `fill_chamber_temps_and_dwell` module logic.",
      "functions": [
        {
          "name": "_parse_time",
          "line": 41,
          "description": "Implements `_parse_time`.",
          "kind": "function"
        },
        {
          "name": "_safe_float",
          "line": 53,
          "description": "Implements `_safe_float`.",
          "kind": "function"
        },
        {
          "name": "_extract_sft_key",
          "line": 66,
          "description": "Implements `_extract_sft_key`.",
          "kind": "function"
        },
        {
          "name": "_parse_setpoint",
          "line": 73,
          "description": "Implements `_parse_setpoint`.",
          "kind": "function"
        },
        {
          "name": "_read_eb_series",
          "line": 80,
          "description": "Implements `_read_eb_series`.",
          "kind": "function"
        },
        {
          "name": "_read_ob_series",
          "line": 107,
          "description": "Implements `_read_ob_series`.",
          "kind": "function"
        },
        {
          "name": "_pt1000_resistance_from_temp",
          "line": 122,
          "description": "Implements `_pt1000_resistance_from_temp`.",
          "kind": "function"
        },
        {
          "name": "_build_pt1000_lookup",
          "line": 132,
          "description": "Implements `_build_pt1000_lookup`.",
          "kind": "function"
        },
        {
          "name": "_pt1000_lookup_temp_from_ohms",
          "line": 141,
          "description": "Implements `_pt1000_lookup_temp_from_ohms`.",
          "kind": "function"
        },
        {
          "name": "_read_rov_series",
          "line": 166,
          "description": "Implements `_read_rov_series`.",
          "kind": "function"
        },
        {
          "name": "_nearest_value",
          "line": 202,
          "description": "Implements `_nearest_value`.",
          "kind": "function"
        },
        {
          "name": "_stable_dwell_seconds",
          "line": 211,
          "description": "Implements `_stable_dwell_seconds`.",
          "kind": "function"
        },
        {
          "name": "_run_switch_times",
          "line": 248,
          "description": "Implements `_run_switch_times`.",
          "kind": "function"
        },
        {
          "name": "_ensure_column",
          "line": 267,
          "description": "Implements `_ensure_column`.",
          "kind": "function"
        },
        {
          "name": "_fmt",
          "line": 288,
          "description": "Implements `_fmt`.",
          "kind": "function"
        },
        {
          "name": "fill_workbook",
          "line": 294,
          "description": "Implements `fill_workbook`.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "SeriesPoint",
          "line": 36,
          "description": "Implements `SeriesPoint`.",
          "bases": [],
          "methods": []
        }
      ]
    },
    {
      "path": "src/analysis_modules/sci_plot.py",
      "package": "analysis_modules",
      "module": "sci_plot",
      "description": "Provides `sci_plot` module logic.",
      "functions": [
        {
          "name": "_parse_sci_log_line",
          "line": 31,
          "description": "Implements `_parse_sci_log_line`.",
          "kind": "function"
        },
        {
          "name": "_remove_offset_calibration",
          "line": 49,
          "description": "Implements `_remove_offset_calibration`.",
          "kind": "function"
        },
        {
          "name": "_parse_rs422_science",
          "line": 66,
          "description": "Implements `_parse_rs422_science`.",
          "kind": "function"
        },
        {
          "name": "plot_sci_log_file",
          "line": 133,
          "description": "Implements `plot_sci_log_file`.",
          "kind": "function"
        },
        {
          "name": "plot_sci_from_rs422",
          "line": 219,
          "description": "Implements `plot_sci_from_rs422`.",
          "kind": "function"
        },
        {
          "name": "plot_sci_packets",
          "line": 281,
          "description": "Implements `plot_sci_packets`.",
          "kind": "function"
        },
        {
          "name": "render_sci_packets_data_urls",
          "line": 351,
          "description": "Implements `render_sci_packets_data_urls`.",
          "kind": "function"
        },
        {
          "name": "plot_sci_logs",
          "line": 466,
          "description": "Implements `plot_sci_logs`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/analysis_modules/thermal_summary.py",
      "package": "analysis_modules",
      "module": "thermal_summary",
      "description": "Provides `thermal_summary` module logic.",
      "functions": [
        {
          "name": "_extract_temperature_label",
          "line": 29,
          "description": "Implements `_extract_temperature_label`.",
          "kind": "function"
        },
        {
          "name": "_convert_eb_rails",
          "line": 37,
          "description": "Implements `_convert_eb_rails`.",
          "kind": "function"
        },
        {
          "name": "_convert_eb_temps",
          "line": 47,
          "description": "Implements `_convert_eb_temps`.",
          "kind": "function"
        },
        {
          "name": "_convert_ob_temps",
          "line": 56,
          "description": "Implements `_convert_ob_temps`.",
          "kind": "function"
        },
        {
          "name": "_convert_ob_rails",
          "line": 65,
          "description": "Implements `_convert_ob_rails`.",
          "kind": "function"
        },
        {
          "name": "_find_ob_switch_on_index",
          "line": 72,
          "description": "Implements `_find_ob_switch_on_index`.",
          "kind": "function"
        },
        {
          "name": "_is_valid_switch_sample",
          "line": 96,
          "description": "Implements `_is_valid_switch_sample`.",
          "kind": "function"
        },
        {
          "name": "_first_valid_sample_after_index",
          "line": 103,
          "description": "Implements `_first_valid_sample_after_index`.",
          "kind": "function"
        },
        {
          "name": "_first_valid_sample_before_index",
          "line": 110,
          "description": "Implements `_first_valid_sample_before_index`.",
          "kind": "function"
        },
        {
          "name": "_nearest_non_nan",
          "line": 117,
          "description": "Implements `_nearest_non_nan`.",
          "kind": "function"
        },
        {
          "name": "_read_science_packets",
          "line": 130,
          "description": "Implements `_read_science_packets`.",
          "kind": "function"
        },
        {
          "name": "_find_preferred_rs422_logs",
          "line": 172,
          "description": "Implements `_find_preferred_rs422_logs`.",
          "kind": "function"
        },
        {
          "name": "_rs422_rank",
          "line": 192,
          "description": "Implements `_rs422_rank`.",
          "kind": "function"
        },
        {
          "name": "_extract_run_key",
          "line": 201,
          "description": "Implements `_extract_run_key`.",
          "kind": "function"
        },
        {
          "name": "_iter_psu_candidates",
          "line": 208,
          "description": "Implements `_iter_psu_candidates`.",
          "kind": "function"
        },
        {
          "name": "_rank_psu_candidate",
          "line": 223,
          "description": "Implements `_rank_psu_candidate`.",
          "kind": "function"
        },
        {
          "name": "_find_psu_logs_for_rs422",
          "line": 239,
          "description": "Implements `_find_psu_logs_for_rs422`.",
          "kind": "function"
        },
        {
          "name": "_fmt",
          "line": 269,
          "description": "Implements `_fmt`.",
          "kind": "function"
        },
        {
          "name": "_summarize_log",
          "line": 279,
          "description": "Implements `_summarize_log`.",
          "kind": "function"
        },
        {
          "name": "build_table",
          "line": 372,
          "description": "Implements `build_table`.",
          "kind": "function"
        },
        {
          "name": "_build_arg_parser",
          "line": 393,
          "description": "Implements `_build_arg_parser`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/core_modules/cmd_ids.py",
      "package": "core_modules",
      "module": "cmd_ids",
      "description": "Provides `cmd_ids` module logic.",
      "functions": [],
      "classes": []
    },
    {
      "path": "src/core_modules/config.py",
      "package": "core_modules",
      "module": "config",
      "description": "Provides `config` module logic.",
      "functions": [],
      "classes": []
    },
    {
      "path": "src/core_modules/constants.py",
      "package": "core_modules",
      "module": "constants",
      "description": "Provides `constants` module logic.",
      "functions": [],
      "classes": []
    },
    {
      "path": "src/core_modules/tmstruct.py",
      "package": "core_modules",
      "module": "tmstruct",
      "description": "Provides `tmstruct` module logic.",
      "functions": [],
      "classes": []
    },
    {
      "path": "src/main.py",
      "package": "root",
      "module": "main",
      "description": "Provides `main` module logic.",
      "functions": [
        {
          "name": "init_arparse",
          "line": 30,
          "description": "Implements `init_arparse`.",
          "kind": "function"
        },
        {
          "name": "setup_logs",
          "line": 46,
          "description": "Implements `setup_logs`.",
          "kind": "function"
        },
        {
          "name": "clean_exit",
          "line": 71,
          "description": "Implements `clean_exit`.",
          "kind": "function"
        },
        {
          "name": "main",
          "line": 86,
          "description": "Implements `main`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/scripts_modules/abu_sequences.py",
      "package": "scripts_modules",
      "module": "abu_sequences",
      "description": "Provides `abu_sequences` module logic.",
      "functions": [
        {
          "name": "read_hk",
          "line": 14,
          "description": "This function requests a HK and generates a decoded log of all the HK parameters.",
          "kind": "function"
        },
        {
          "name": "cal_motor_to_base",
          "line": 86,
          "description": "This function powers the Mechanism board (if it isn't already).",
          "kind": "function"
        },
        {
          "name": "home_to_outer",
          "line": 162,
          "description": "This function powers the Mechanism board (if it isn't already).",
          "kind": "function"
        },
        {
          "name": "home_to_base",
          "line": 218,
          "description": "Then commands the motor to HOME to BASE.",
          "kind": "function"
        },
        {
          "name": "mv_pos_steps",
          "line": 281,
          "description": "Script that moves the mechanism a certain number of steps positive (towards the base).",
          "kind": "function"
        },
        {
          "name": "mv_neg_steps",
          "line": 325,
          "description": "Script that moves the mechanism a certain number of steps negative (towards the outer).",
          "kind": "function"
        },
        {
          "name": "set_offset_and_check_sci",
          "line": 358,
          "description": "Function that will power the detector board if it isn't already.",
          "kind": "function"
        },
        {
          "name": "mwir_binary_chop",
          "line": 392,
          "description": "This fixes the SWIR DAC offset as per the functional call.",
          "kind": "function"
        },
        {
          "name": "swir_binary_chop",
          "line": 439,
          "description": "This sets the MWIR DAC offset as per the functional call.",
          "kind": "function"
        },
        {
          "name": "move_and_measure",
          "line": 486,
          "description": "Moves the specified number of steps forward and then takes a measurement. 0 steps can be entered",
          "kind": "function"
        },
        {
          "name": "abu_measurement_scan",
          "line": 523,
          "description": "Performs the basic Enfys science measurement",
          "kind": "function"
        },
        {
          "name": "sweep_offset_mwir",
          "line": 550,
          "description": "This function sweeps through the mwir DAC from 0 to 4095 using the increment specified.",
          "kind": "function"
        },
        {
          "name": "sweep_offset_swir",
          "line": 560,
          "description": "This function sweeps through the swir DAC from 0 to 4095 using the increment specified.",
          "kind": "function"
        },
        {
          "name": "first_power_on",
          "line": 570,
          "description": "Very simple sequence that powers on both sub-systems.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/scripts_modules/error_checks.py",
      "package": "scripts_modules",
      "module": "error_checks",
      "description": "Provides `error_checks` module logic.",
      "functions": [
        {
          "name": "check_set_ob_errors",
          "line": 15,
          "description": "Implements `check_set_ob_errors`.",
          "kind": "function"
        },
        {
          "name": "check_set_mtr_errors",
          "line": 51,
          "description": "Implements `check_set_mtr_errors`.",
          "kind": "function"
        },
        {
          "name": "check_mask_mtr_errors",
          "line": 89,
          "description": "Implements `check_mask_mtr_errors`.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "SetError",
          "line": 10,
          "description": "Implements `SetError`.",
          "bases": [
            "Exception"
          ],
          "methods": []
        },
        {
          "name": "ClearError",
          "line": 12,
          "description": "Implements `ClearError`.",
          "bases": [
            "Exception"
          ],
          "methods": []
        }
      ]
    },
    {
      "path": "src/scripts_modules/fft.py",
      "package": "scripts_modules",
      "module": "fft",
      "description": "Provides `fft` module logic.",
      "functions": [
        {
          "name": "run_fft",
          "line": 7,
          "description": "Implements `run_fft`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/scripts_modules/heaters.py",
      "package": "scripts_modules",
      "module": "heaters",
      "description": "Provides `heaters` module logic.",
      "functions": [
        {
          "name": "mech_auto_heater_test",
          "line": 12,
          "description": "Implements `mech_auto_heater_test`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/scripts_modules/LTM.py",
      "package": "scripts_modules",
      "module": "LTM",
      "description": "Provides `LTM` module logic.",
      "functions": [
        {
          "name": "LTM_Measurement",
          "line": 15,
          "description": "Implements `LTM_Measurement`.",
          "kind": "function"
        },
        {
          "name": "outer_cal",
          "line": 63,
          "description": "Implements `outer_cal`.",
          "kind": "function"
        },
        {
          "name": "outer_home",
          "line": 113,
          "description": "Implements `outer_home`.",
          "kind": "function"
        },
        {
          "name": "base_home",
          "line": 165,
          "description": "Implements `base_home`.",
          "kind": "function"
        },
        {
          "name": "mwir_dark_region_start",
          "line": 216,
          "description": "Implements `mwir_dark_region_start`.",
          "kind": "function"
        },
        {
          "name": "stepping",
          "line": 237,
          "description": "Implements `stepping`.",
          "kind": "function"
        },
        {
          "name": "acquisition",
          "line": 250,
          "description": "Implements `acquisition`.",
          "kind": "function"
        },
        {
          "name": "park",
          "line": 285,
          "description": "Implements `park`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/scripts_modules/OB_FFT.py",
      "package": "scripts_modules",
      "module": "OB_FFT",
      "description": "Provides `OB_FFT` module logic.",
      "functions": [
        {
          "name": "fft",
          "line": 21,
          "description": "Implements `fft`.",
          "kind": "function"
        },
        {
          "name": "hk_check",
          "line": 100,
          "description": "Implements `hk_check`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/scripts_modules/sequences.py",
      "package": "scripts_modules",
      "module": "sequences",
      "description": "Provides `sequences` module logic.",
      "functions": [
        {
          "name": "power_up",
          "line": 15,
          "description": "Implements `power_up`.",
          "kind": "function"
        },
        {
          "name": "mech_heater_test",
          "line": 44,
          "description": "Implements `mech_heater_test`.",
          "kind": "function"
        },
        {
          "name": "parse_hk",
          "line": 65,
          "description": "Implements `parse_hk`.",
          "kind": "function"
        },
        {
          "name": "check_sci",
          "line": 135,
          "description": "Implements `check_sci`.",
          "kind": "function"
        },
        {
          "name": "check_sci_vs_hk",
          "line": 157,
          "description": "Implements `check_sci_vs_hk`.",
          "kind": "function"
        },
        {
          "name": "hk_approx_cal",
          "line": 186,
          "description": "Request a HK packet and provide an approximate calibration of all analogue parameters.",
          "kind": "function"
        },
        {
          "name": "increasing_torque_test",
          "line": 211,
          "description": "Perform a motor torque test by incrementally increasing the motor current until the motor moves.",
          "kind": "function"
        },
        {
          "name": "torque_test",
          "line": 235,
          "description": "Perform a motor torque test by incrementally increasing the motor current until the motor moves.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/app_theme.py",
      "package": "utility_modules",
      "module": "app_theme",
      "description": "Provides `app_theme` module logic.",
      "functions": [
        {
          "name": "_extract_block_vars",
          "line": 13,
          "description": "Return the CSS custom properties declared inside *selector* { \u2026 }.",
          "kind": "function"
        },
        {
          "name": "_resolve_vars",
          "line": 25,
          "description": "Resolve var(--x) references until all values are concrete colours.",
          "kind": "function"
        },
        {
          "name": "load_css_vars",
          "line": 42,
          "description": "Parse *css_path* and return a flat dict of resolved CSS variable values",
          "kind": "function"
        },
        {
          "name": "get_theme_palette",
          "line": 56,
          "description": "Get a color palette based on the current theme and GUI variables.",
          "kind": "function"
        },
        {
          "name": "apply_plot_theme",
          "line": 89,
          "description": "Apply the given color palette to a matplotlib Axes object.",
          "kind": "function"
        },
        {
          "name": "apply_theme_to_plots",
          "line": 114,
          "description": "Implements `apply_theme_to_plots`.",
          "kind": "function"
        },
        {
          "name": "set_logo_sources",
          "line": 131,
          "description": "Implements `set_logo_sources`.",
          "kind": "function"
        },
        {
          "name": "apply_theme",
          "line": 139,
          "description": "Implements `apply_theme`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/comms.py",
      "package": "utility_modules",
      "module": "comms",
      "description": "Provides `comms` module logic.",
      "functions": [
        {
          "name": "initialise_comms",
          "line": 12,
          "description": "Initialise an unopened RS485 port with project communication settings.",
          "kind": "function"
        },
        {
          "name": "open_comms",
          "line": 34,
          "description": "Open an initialised RS485 port and clear stale input/output buffers.",
          "kind": "function"
        },
        {
          "name": "close_comms",
          "line": 47,
          "description": "Clear buffers and close an open RS485 port.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/crc8_function.py",
      "package": "utility_modules",
      "module": "crc8_function",
      "description": "Provides `crc8_function` module logic.",
      "functions": [
        {
          "name": "crc8Calculate",
          "line": 5,
          "description": "Append CRC8 to a hex command string and return bytes ready to send.",
          "kind": "function"
        },
        {
          "name": "crc8InjectErr",
          "line": 15,
          "description": "Append an invalid trailing byte to inject a deliberate CRC mismatch.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/eb_interface.py",
      "package": "utility_modules",
      "module": "eb_interface",
      "description": "Provides `eb_interface` module logic.",
      "functions": [
        {
          "name": "rs422_log_changed",
          "line": 218,
          "description": "Return True if the RS422 log path or mtime changed since last check.",
          "kind": "function"
        },
        {
          "name": "get_egse_log_snapshot",
          "line": 238,
          "description": "Return latest EB EGSE log snapshot if changed.",
          "kind": "function"
        },
        {
          "name": "get_egse_interface",
          "line": 277,
          "description": "Get the EGSE interface instance, initializing it if it doesn't exist.",
          "kind": "function"
        },
        {
          "name": "update_egse_interface_path",
          "line": 285,
          "description": "Update the EGSE interface path and reinitialize the interface if it already exists.",
          "kind": "function"
        },
        {
          "name": "select_cmd_script",
          "line": 295,
          "description": "Open a file picker instance to select an EGSE script file and send it to CmdTool using Typecast.",
          "kind": "function"
        },
        {
          "name": "select_egse_folder",
          "line": 329,
          "description": "Open folder picker to set the EGSE tools directory.",
          "kind": "function"
        },
        {
          "name": "select_rs422_log",
          "line": 352,
          "description": "Open file picker to select an RS422if log file.",
          "kind": "function"
        },
        {
          "name": "locate_latest_egse_log",
          "line": 378,
          "description": "Locate the newest EB EGSE log file.",
          "kind": "function"
        },
        {
          "name": "start_egse_tools",
          "line": 388,
          "description": "Method that runs the batch file to start the EGSE tools.",
          "kind": "function"
        },
        {
          "name": "stop_egse_tools",
          "line": 409,
          "description": "Stop the EGSE tools.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "EGSEInterface",
          "line": 28,
          "description": "Implements `EGSEInterface`.",
          "bases": [],
          "methods": [
            {
              "name": "__init__",
              "line": 29,
              "description": "Interface class to manage interactions with the EB EGSE tools, including starting/stopping the tools and sending commands via typecasting.",
              "kind": "method"
            },
            {
              "name": "start_egse",
              "line": 34,
              "description": "Start the EGSE tools by running the Start_tools.bat script. Optionally, a script argument can be passed to be executed after the tools start.",
              "kind": "method"
            },
            {
              "name": "stop_egse",
              "line": 63,
              "description": "Stop the EGSE tools by running the Stop_tools.bat script.",
              "kind": "method"
            },
            {
              "name": "typecast",
              "line": 83,
              "description": "Typecasting function that sends the commands from a script file to the CMDTool window.",
              "kind": "method"
            },
            {
              "name": "send_command_to_cmdtool",
              "line": 122,
              "description": "Send a single command string to the CmdTool input window.",
              "kind": "method"
            },
            {
              "name": "send_makesafe",
              "line": 166,
              "description": "Send MakeSafe sequence into CmdTool and verify SAFE operating state.",
              "kind": "method"
            },
            {
              "name": "wait_for_safe_state",
              "line": 185,
              "description": "Poll latest HK from RS422 log until CURRENT_OPERATING_STATE becomes SAFE (0x02).",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/utility_modules/eb_packet_utility.py",
      "package": "utility_modules",
      "module": "eb_packet_utility",
      "description": "Provides `eb_packet_utility` module logic.",
      "functions": [
        {
          "name": "read_pkt",
          "line": 26,
          "description": "Reads packet from EB RS422_if.log files.",
          "kind": "function"
        },
        {
          "name": "read_block_length",
          "line": 130,
          "description": "Read the block length from bytes 12-13 of the packet data. Returns None if packet is too short.",
          "kind": "function"
        },
        {
          "name": "trim_sci_packet_by_block_length",
          "line": 137,
          "description": "Trims Science packet to header + block length if block length is present and packet is long enough. Otherwise returns original packet data.",
          "kind": "function"
        },
        {
          "name": "parse_eb_hk",
          "line": 155,
          "description": "Parse EB Housekeeping packet data and decode all relevant fields, using the defined dictionaries from TMStruct",
          "kind": "function"
        },
        {
          "name": "decode_post_hk",
          "line": 317,
          "description": "Implements `decode_post_hk`.",
          "kind": "function"
        },
        {
          "name": "decode_dump_data",
          "line": 332,
          "description": "Decodes Dump Data SCI packet using the defined dictionary from TMStruct for dump_data",
          "kind": "function"
        },
        {
          "name": "decode_cscience_data",
          "line": 348,
          "description": "Decodes Critical Science Data SCI packet using the defined dictionary from TMStruct for eb_sci_header, and trims packet to header + block length if block length is present.",
          "kind": "function"
        },
        {
          "name": "decode_ncscience_data",
          "line": 367,
          "description": "Decodes Non-Critical Science Data SCI packet using the defined dictionary from TMStruct for eb_sci_header, and trims packet to header + block length if block length is present.",
          "kind": "function"
        },
        {
          "name": "decode_sci_data_points",
          "line": 387,
          "description": "Decodes SCI data points from a decoded SCI packet, returning a list of SimpleNamespace objects.",
          "kind": "function"
        },
        {
          "name": "merge_sci_data_packet",
          "line": 445,
          "description": "Decodes SCI data points from a decoded SCI packet, and merges decoded SCI data point fields with base packet fields.",
          "kind": "function"
        },
        {
          "name": "decode_ob_trps",
          "line": 481,
          "description": "Convert a thermistor ADU value to temperature in Celsius using the linear conversion defined by the HKREF voltage divider circuitry and an estimation formula using a PT1000 table.",
          "kind": "function"
        },
        {
          "name": "decode_eb_trps",
          "line": 489,
          "description": "Convert a thermistor ADU value to temperature in Celsius using the B-parameter equation.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/ebtcs.py",
      "package": "utility_modules",
      "module": "ebtcs",
      "description": "Provides `ebtcs` module logic.",
      "functions": [
        {
          "name": "_resolve_tc_name",
          "line": 37,
          "description": "Implements `_resolve_tc_name`.",
          "kind": "function"
        },
        {
          "name": "_build_ebtc_line",
          "line": 44,
          "description": "Implements `_build_ebtc_line`.",
          "kind": "function"
        },
        {
          "name": "send_tc",
          "line": 57,
          "description": "Method to send an EB TC command to CmdTool and write command log.",
          "kind": "function"
        },
        {
          "name": "configure_send_flow_control",
          "line": 82,
          "description": "Configure optional external flow-control hooks for script execution.",
          "kind": "function"
        },
        {
          "name": "clear_send_flow_control",
          "line": 90,
          "description": "Disable external flow-control hooks.",
          "kind": "function"
        },
        {
          "name": "_gate_send",
          "line": 95,
          "description": "Block or reject sends based on configured pause/abort hooks.",
          "kind": "function"
        },
        {
          "name": "pause",
          "line": 109,
          "description": "Send CmdTool pause command.",
          "kind": "function"
        },
        {
          "name": "wait",
          "line": 114,
          "description": "Send CmdTool wait command in milliseconds.",
          "kind": "function"
        },
        {
          "name": "verify_ack_hdr",
          "line": 125,
          "description": "Verify basic TC acknowledgement fields from HK snapshots.",
          "kind": "function"
        },
        {
          "name": "verify_blank_ack_params",
          "line": 153,
          "description": "Verify optional fields are zero, mirroring tc.py blank ACK checks.",
          "kind": "function"
        },
        {
          "name": "_read_latest_hk_and_index",
          "line": 167,
          "description": "Read latest HK and its line index from currently selected RS422 log.",
          "kind": "function"
        },
        {
          "name": "_wait_for_response_hk",
          "line": 183,
          "description": "Wait for a newer HK packet after command send; fall back to latest HK if index is unchanged.",
          "kind": "function"
        },
        {
          "name": "_verify_tc",
          "line": 199,
          "description": "Implements `_verify_tc`.",
          "kind": "function"
        },
        {
          "name": "_send_named_tc",
          "line": 213,
          "description": "Implements `_send_named_tc`.",
          "kind": "function"
        },
        {
          "name": "ret",
          "line": 226,
          "description": "Implements `ret`.",
          "kind": "function"
        },
        {
          "name": "hk_request",
          "line": 230,
          "description": "Implements `hk_request`.",
          "kind": "function"
        },
        {
          "name": "patch",
          "line": 234,
          "description": "Implements `patch`.",
          "kind": "function"
        },
        {
          "name": "dump",
          "line": 238,
          "description": "Implements `dump`.",
          "kind": "function"
        },
        {
          "name": "set_hk_rate",
          "line": 242,
          "description": "Implements `set_hk_rate`.",
          "kind": "function"
        },
        {
          "name": "monitor_addr",
          "line": 246,
          "description": "Implements `monitor_addr`.",
          "kind": "function"
        },
        {
          "name": "abort",
          "line": 250,
          "description": "Implements `abort`.",
          "kind": "function"
        },
        {
          "name": "generic_tc",
          "line": 254,
          "description": "Implements `generic_tc`.",
          "kind": "function"
        },
        {
          "name": "safe",
          "line": 258,
          "description": "Implements `safe`.",
          "kind": "function"
        },
        {
          "name": "standby",
          "line": 262,
          "description": "Implements `standby`.",
          "kind": "function"
        },
        {
          "name": "acquisition",
          "line": 266,
          "description": "Implements `acquisition`.",
          "kind": "function"
        },
        {
          "name": "set_motor_configs",
          "line": 270,
          "description": "Implements `set_motor_configs`.",
          "kind": "function"
        },
        {
          "name": "set_heater_configs",
          "line": 274,
          "description": "Implements `set_heater_configs`.",
          "kind": "function"
        },
        {
          "name": "set_acq_configs",
          "line": 278,
          "description": "Implements `set_acq_configs`.",
          "kind": "function"
        },
        {
          "name": "set_tec_setpoint",
          "line": 282,
          "description": "Implements `set_tec_setpoint`.",
          "kind": "function"
        },
        {
          "name": "set_fdir_limits",
          "line": 286,
          "description": "Implements `set_fdir_limits`.",
          "kind": "function"
        },
        {
          "name": "en_mech_board",
          "line": 290,
          "description": "Implements `en_mech_board`.",
          "kind": "function"
        },
        {
          "name": "en_det_board",
          "line": 294,
          "description": "Implements `en_det_board`.",
          "kind": "function"
        },
        {
          "name": "en_mech_heater",
          "line": 298,
          "description": "Implements `en_mech_heater`.",
          "kind": "function"
        },
        {
          "name": "en_det_heater",
          "line": 302,
          "description": "Implements `en_det_heater`.",
          "kind": "function"
        },
        {
          "name": "en_ob5v",
          "line": 306,
          "description": "Implements `en_ob5v`.",
          "kind": "function"
        },
        {
          "name": "ob_park",
          "line": 310,
          "description": "Implements `ob_park`.",
          "kind": "function"
        },
        {
          "name": "ob_homing",
          "line": 314,
          "description": "Implements `ob_homing`.",
          "kind": "function"
        },
        {
          "name": "ob_hk",
          "line": 318,
          "description": "Implements `ob_hk`.",
          "kind": "function"
        },
        {
          "name": "check_memory",
          "line": 322,
          "description": "Implements `check_memory`.",
          "kind": "function"
        },
        {
          "name": "goto",
          "line": 326,
          "description": "Implements `goto`.",
          "kind": "function"
        },
        {
          "name": "copy_memory",
          "line": 330,
          "description": "Implements `copy_memory`.",
          "kind": "function"
        },
        {
          "name": "switch_rs422",
          "line": 334,
          "description": "Implements `switch_rs422`.",
          "kind": "function"
        },
        {
          "name": "set_tec_current",
          "line": 338,
          "description": "Implements `set_tec_current`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/egse_logger.py",
      "package": "utility_modules",
      "module": "egse_logger",
      "description": "Provides `egse_logger` module logic.",
      "functions": [
        {
          "name": "get_loggers",
          "line": 8,
          "description": "Initializes and returns the event_log, info_log, and psu_log loggers.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/hk_conversions.py",
      "package": "utility_modules",
      "module": "hk_conversions",
      "description": "Universal ADU-to-physical conversion table for EB/OB HK telemetry fields.",
      "functions": [
        {
          "name": "decode_field",
          "line": 57,
          "description": "Convert one raw HK field to its physical value.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "FieldConversion",
          "line": 26,
          "description": "Conversion definition for a single HK telemetry field.",
          "bases": [],
          "methods": []
        }
      ]
    },
    {
      "path": "src/utility_modules/psu.py",
      "package": "utility_modules",
      "module": "psu",
      "description": "Provides `psu` module logic.",
      "functions": [
        {
          "name": "init_psu_comms",
          "line": 16,
          "description": "Initialise an unopened PSU serial port handle.",
          "kind": "function"
        },
        {
          "name": "open_psu_comms",
          "line": 23,
          "description": "Open PSU serial comms and verify the expected IDN response.",
          "kind": "function"
        },
        {
          "name": "close_psu_comms",
          "line": 48,
          "description": "Return PSU to local mode, clear buffers, and close the serial port.",
          "kind": "function"
        },
        {
          "name": "psuRead",
          "line": 58,
          "description": "Read a PSU value for a channel and command type.",
          "kind": "function"
        },
        {
          "name": "parse_psu_reading",
          "line": 71,
          "description": "Parse raw PSU text readings into float values with safe fallback to 0.0.",
          "kind": "function"
        },
        {
          "name": "psu_monitor_thread",
          "line": 83,
          "description": "Monitor PSU channels, log telemetry, and shut down on limit violations.",
          "kind": "function"
        },
        {
          "name": "setChannels",
          "line": 240,
          "description": "Configure PSU channel voltage/current/OVP limits for OB or EB mode.",
          "kind": "function"
        },
        {
          "name": "switch_psu_channel",
          "line": 294,
          "description": "Switch a PSU channel on or off.",
          "kind": "function"
        },
        {
          "name": "emergencyShutDown",
          "line": 300,
          "description": "Perform emergency PSU shutdown and hand control back to local front panel.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/psu_log_utility.py",
      "package": "utility_modules",
      "module": "psu_log_utility",
      "description": "Provides `psu_log_utility` module logic.",
      "functions": [
        {
          "name": "load_psu_channel_samples",
          "line": 10,
          "description": "Parse PSU log file and return generic per-channel samples.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/send_cmd.py",
      "package": "utility_modules",
      "module": "send_cmd",
      "description": "Provides `send_cmd` module logic.",
      "functions": [
        {
          "name": "cmd_repeat",
          "line": 14,
          "description": "Retry a TC once after clearing errors when the first attempt fails.",
          "kind": "function"
        },
        {
          "name": "poll_hk",
          "line": 35,
          "description": "Implements `poll_hk`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/tc.py",
      "package": "utility_modules",
      "module": "tc",
      "description": "Provides `tc` module logic.",
      "functions": [
        {
          "name": "send_tc",
          "line": 30,
          "description": "Method to send a TC command to the EGSE. This method also logs the command to a file with a timestamp.",
          "kind": "function"
        },
        {
          "name": "verify_ack_hdr",
          "line": 39,
          "description": "This function verifies the header parameters in the ACK response. If any of the parameters do not match the expected values, then a error condition is raised.",
          "kind": "function"
        },
        {
          "name": "verify_blank_ack_params",
          "line": 54,
          "description": "This function verifies that all unused parameters in the ACK response are set to 0. Saves",
          "kind": "function"
        },
        {
          "name": "hk_request",
          "line": 79,
          "description": "Method to request HK - No parameters",
          "kind": "function"
        },
        {
          "name": "clear_errors",
          "line": 105,
          "description": "Method to Clear Errors - No parameters",
          "kind": "function"
        },
        {
          "name": "set_errors",
          "line": 139,
          "description": "Method to Set Errors - Setting : TMO|IPA|CD|AB|ABS|DSE Ignoring :IG_B|IG_O  Masking : M_CD|M_AB|M_ABS|M_DSE",
          "kind": "function"
        },
        {
          "name": "power_control",
          "line": 178,
          "description": "Method to send Power Control command. 0 - All OFF|1 - Mech ON|2 - Detec ON|3 - Both ON",
          "kind": "function"
        },
        {
          "name": "heater_control",
          "line": 217,
          "description": "Method to send Heater Control command. 16 : HTR_SCI_TOG | 8 : HTR_DETEC_MAN | 4 : HTR_DETEC_AUTO | 2 : HTR_MECH_MAN | 1 : HTR_MECH_AUTO",
          "kind": "function"
        },
        {
          "name": "set_mech_sp",
          "line": 263,
          "description": "Method to set Mechanism Thermal SetPoints. OFF_SP [0:FFF] | ON_SP [0:FFF]",
          "kind": "function"
        },
        {
          "name": "set_detec_sp",
          "line": 318,
          "description": "Method to set Detector Thermal SetPoints. OFF_SP [0:FFF] | ON_SP [0:FFF]",
          "kind": "function"
        },
        {
          "name": "set_mtr_param",
          "line": 373,
          "description": "Method to set Motor Parameters. PEAK_CURRENT [0:7F] Nom:40(85mA) | GUARD [0:FF] Nom: | RECVAL [0:FF] | SPEED [0:0F]",
          "kind": "function"
        },
        {
          "name": "mtr_mov_pos",
          "line": 437,
          "description": "Method to send Move Pos Steps command. POS_STEPS [0:10000]",
          "kind": "function"
        },
        {
          "name": "mtr_mov_neg",
          "line": 477,
          "description": "Method to send Move Neg Steps command. NEG_STEPS [0:10000]",
          "kind": "function"
        },
        {
          "name": "mtr_homing",
          "line": 517,
          "description": "\"Method to send Motor Homing command. 2 - CAL | 1 - DRIVE TO OUTER",
          "kind": "function"
        },
        {
          "name": "mtr_halt",
          "line": 555,
          "description": "Method to send Motor Halt command.No Parameters",
          "kind": "function"
        },
        {
          "name": "set_hk_samples",
          "line": 588,
          "description": "Method to send Set HK Samples command. SAMPLES [0:6]",
          "kind": "function"
        },
        {
          "name": "sci_offset",
          "line": 625,
          "description": "Method to send Set Sci Offset command. SWIR_OFFSET [0:FFF] | MWIR_OFFSET [0:FFF]",
          "kind": "function"
        },
        {
          "name": "sci_request",
          "line": 674,
          "description": "Method to send SCI Request command. SCI_ADC_SAMP [0:10] | SCI_ADC_SKIP [0:255]",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/utility_modules/tm.py",
      "package": "utility_modules",
      "module": "tm",
      "description": "Provides `tm` module logic.",
      "functions": [
        {
          "name": "get_response",
          "line": 270,
          "description": "Read the raw bytes from the serial port and return them",
          "kind": "function"
        },
        {
          "name": "parse_tm",
          "line": 276,
          "description": "Parse the raw bytes from the TM response and return the appropriate object based on the CMD ID",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "Response",
          "line": 28,
          "description": "Class Definition for the raw response received from the serial port.",
          "bases": [],
          "methods": [
            {
              "name": "__init__",
              "line": 30,
              "description": "Implements `__init__`.",
              "kind": "method"
            },
            {
              "name": "get_cmd_mod_id",
              "line": 37,
              "description": "Extract the command and module IDs from the raw bytes.",
              "kind": "method"
            },
            {
              "name": "verify_cmd_id",
              "line": 42,
              "description": "Verify that the command ID matches one of the expected values and set the command type accordingly.",
              "kind": "method"
            },
            {
              "name": "verify_model_id",
              "line": 50,
              "description": "Verify that the model ID matches the expected value.",
              "kind": "method"
            },
            {
              "name": "verify_crc",
              "line": 55,
              "description": "Calculate the CRC8 of the raw bytes and compare it to the expected value. The CRC8 should be 0x00 if the data is correct.",
              "kind": "method"
            }
          ]
        },
        {
          "name": "TM",
          "line": 63,
          "description": "Parent Class Definition for all TM responses. Reads the raw bytes from the response and parses them based on the dictionary defined in tmstruct.py",
          "bases": [],
          "methods": [
            {
              "name": "__init__",
              "line": 66,
              "description": "Implements `__init__`.",
              "kind": "method"
            },
            {
              "name": "check_len",
              "line": 71,
              "description": "Implements `check_len`.",
              "kind": "method"
            },
            {
              "name": "decode_bytes",
              "line": 74,
              "description": "Read the raw bytes and decode them into the appropriate variables using the dictionary defined in tmstruct.py",
              "kind": "method"
            },
            {
              "name": "decode_error_byte",
              "line": 84,
              "description": "Read the error byte and decode it into the appropriate flags using the dictionary defined in tmstruct.py",
              "kind": "method"
            },
            {
              "name": "decode_mtr_error_byte",
              "line": 97,
              "description": "Read the motor error byte and decode it into the appropriate flags using the dictionary defined in tmstruct.py",
              "kind": "method"
            },
            {
              "name": "decode_thrm_status_byte",
              "line": 110,
              "description": "Read the thermal status byte and decode it into the appropriate flags using the dictionary defined in tmstruct.py",
              "kind": "method"
            },
            {
              "name": "check_errors",
              "line": 123,
              "description": "Check the error byte and log any errors that are asserted",
              "kind": "method"
            }
          ]
        },
        {
          "name": "HK",
          "line": 144,
          "description": "HK Class Definition. Reads the HK response and parses it based on the dictionary defined in tmstruct.py",
          "bases": [
            "TM"
          ],
          "methods": [
            {
              "name": "__init__",
              "line": 146,
              "description": "Implements `__init__`.",
              "kind": "method"
            },
            {
              "name": "check_len",
              "line": 194,
              "description": "Check the length of the HK message",
              "kind": "method"
            },
            {
              "name": "check_unused",
              "line": 200,
              "description": "Check the unused bytes in the HK message. These should always be 0.",
              "kind": "method"
            }
          ]
        },
        {
          "name": "ACK",
          "line": 205,
          "description": "ACK Class Definition. Reads the ACK response and parses it based on the dictionary defined in tmstruct.py",
          "bases": [
            "TM"
          ],
          "methods": [
            {
              "name": "__init__",
              "line": 207,
              "description": "Implements `__init__`.",
              "kind": "method"
            },
            {
              "name": "check_len",
              "line": 221,
              "description": "Check the length of the ACK message",
              "kind": "method"
            }
          ]
        },
        {
          "name": "SCI",
          "line": 228,
          "description": "SCI Class Definition. Reads the SCI response and parses it based on the dictionary defined in tmstruct.py",
          "bases": [
            "TM"
          ],
          "methods": [
            {
              "name": "__init__",
              "line": 230,
              "description": "Implements `__init__`.",
              "kind": "method"
            },
            {
              "name": "check_len",
              "line": 245,
              "description": "Check the length of the SCI message",
              "kind": "method"
            }
          ]
        },
        {
          "name": "NACK",
          "line": 250,
          "description": "NACK Class Definition. Reads the NACK response and parses it based on the dictionary defined in tmstruct.py",
          "bases": [
            "TM"
          ],
          "methods": [
            {
              "name": "__init__",
              "line": 252,
              "description": "Implements `__init__`.",
              "kind": "method"
            },
            {
              "name": "check_len",
              "line": 264,
              "description": "Check the length of the NACK message",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/widget_modules/detector_tab.py",
      "package": "widget_modules",
      "module": "detector_tab",
      "description": "Provides `detector_tab` module logic.",
      "functions": [
        {
          "name": "create_detector_tab",
          "line": 11,
          "description": "Build detector controls (legacy detector panel) for OB mode.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/widget_modules/file_dialog_window_widget.py",
      "package": "widget_modules",
      "module": "file_dialog_window_widget",
      "description": "Provides `file_dialog_window_widget` module logic.",
      "functions": [
        {
          "name": "create_dialog_root",
          "line": 12,
          "description": "Creates a hidden root window for the file dialog to ensure it appears on top of other windows.",
          "kind": "function"
        },
        {
          "name": "select_folder_dialog",
          "line": 27,
          "description": "Opens a folder selection dialog and returns the selected path.",
          "kind": "function"
        },
        {
          "name": "select_file_dialog",
          "line": 42,
          "description": "Opens a file selection dialog and returns the selected file path.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/widget_modules/log_terminal_widget.py",
      "package": "widget_modules",
      "module": "log_terminal_widget",
      "description": "Provides `log_terminal_widget` module logic.",
      "functions": [
        {
          "name": "create_log_terminal",
          "line": 71,
          "description": "Creates a log terminal using ui.log and a custom logging.Handler to display logs in the UI.",
          "kind": "function"
        },
        {
          "name": "set_log_display",
          "line": 110,
          "description": "Set the log display mode and logging level based on user selection.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "LogTerminalController",
          "line": 13,
          "description": "Implements `LogTerminalController`.",
          "bases": [],
          "methods": [
            {
              "name": "set_level",
              "line": 17,
              "description": "Implements `set_level`.",
              "kind": "method"
            }
          ]
        },
        {
          "name": "LogElementHandler",
          "line": 21,
          "description": "Implements `LogElementHandler`.",
          "bases": [
            "logging.Handler"
          ],
          "methods": [
            {
              "name": "__init__",
              "line": 37,
              "description": "Implements `__init__`.",
              "kind": "method"
            },
            {
              "name": "emit",
              "line": 42,
              "description": "Emit a log record to the ui.log element.",
              "kind": "method"
            },
            {
              "name": "bind_level_radio",
              "line": 58,
              "description": "Bind the log level radio button to this handler for dynamic level changes.",
              "kind": "method"
            },
            {
              "name": "on_level_change",
              "line": 62,
              "description": "Update logger level and selected radio color based on level selection.",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/widget_modules/mechanism_tab.py",
      "package": "widget_modules",
      "module": "mechanism_tab",
      "description": "Provides `mechanism_tab` module logic.",
      "functions": [
        {
          "name": "create_mechanism_tab",
          "line": 11,
          "description": "Build mechanism controls (legacy motor panel) for OB mode.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/widget_modules/menu_widget.py",
      "package": "widget_modules",
      "module": "menu_widget",
      "description": "Provides `menu_widget` module logic.",
      "functions": [
        {
          "name": "create_menu",
          "line": 47,
          "description": "Creates the menu for the application. The menu contains buttons to start/stop EB EGSE tools, select a log file, and take a log snapshot.",
          "kind": "function"
        },
        {
          "name": "_call_set_mode",
          "line": 146,
          "description": "Implements `_call_set_mode`.",
          "kind": "function"
        },
        {
          "name": "_log_psu_snapshot",
          "line": 152,
          "description": "Logs the current PSU readings to the info log.",
          "kind": "function"
        },
        {
          "name": "_log_snapshot",
          "line": 170,
          "description": "Takes a snapshot of the current logs and PSU readings, and logs them to the info log.",
          "kind": "function"
        },
        {
          "name": "_select_psu_log",
          "line": 176,
          "description": "Open a PSU log picker and register selected replay file in app state.",
          "kind": "function"
        },
        {
          "name": "_run_selected_script",
          "line": 228,
          "description": "Run the selected EB script from the menu.",
          "kind": "function"
        },
        {
          "name": "_start_egse_tools",
          "line": 285,
          "description": "Start EB EGSE tools and expose script controls only on successful startup.",
          "kind": "function"
        },
        {
          "name": "_stop_egse_tools",
          "line": 295,
          "description": "Stop EB EGSE tools and hide script controls.",
          "kind": "function"
        },
        {
          "name": "_pause_selected_script",
          "line": 304,
          "description": "Toggle pause/resume for a running script.",
          "kind": "function"
        },
        {
          "name": "_abort_selected_script",
          "line": 332,
          "description": "Abort a running script.",
          "kind": "function"
        },
        {
          "name": "stop_and_shutdown",
          "line": 356,
          "description": "Stops any running processes and shuts down the application.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "MenuController",
          "line": 18,
          "description": "Implements `MenuController`.",
          "bases": [],
          "methods": [
            {
              "name": "open",
              "line": 23,
              "description": "Opens the menu by setting the state and applying styles to show the card.",
              "kind": "method"
            },
            {
              "name": "close",
              "line": 31,
              "description": "Closes the menu by setting the state and applying styles to hide the card.",
              "kind": "method"
            },
            {
              "name": "toggle",
              "line": 39,
              "description": "Toggles the menu open or closed based on the current state.",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/widget_modules/metrics_card_widget.py",
      "package": "widget_modules",
      "module": "metrics_card_widget",
      "description": "Provides `metrics_card_widget` module logic.",
      "functions": [
        {
          "name": "_safe_get_value",
          "line": 188,
          "description": "Implements `_safe_get_value`.",
          "kind": "function"
        },
        {
          "name": "_coerce_float",
          "line": 195,
          "description": "Implements `_coerce_float`.",
          "kind": "function"
        },
        {
          "name": "_coerce_bool",
          "line": 203,
          "description": "Implements `_coerce_bool`.",
          "kind": "function"
        },
        {
          "name": "_format_value",
          "line": 209,
          "description": "Implements `_format_value`.",
          "kind": "function"
        },
        {
          "name": "_flag_true",
          "line": 222,
          "description": "Implements `_flag_true`.",
          "kind": "function"
        },
        {
          "name": "_has_any_asserted",
          "line": 232,
          "description": "Implements `_has_any_asserted`.",
          "kind": "function"
        },
        {
          "name": "_decoded",
          "line": 239,
          "description": "Implements `_decoded`.",
          "kind": "function"
        },
        {
          "name": "_tec_temp",
          "line": 243,
          "description": "Implements `_tec_temp`.",
          "kind": "function"
        },
        {
          "name": "_state_name",
          "line": 250,
          "description": "Implements `_state_name`.",
          "kind": "function"
        },
        {
          "name": "_ob_warm",
          "line": 257,
          "description": "Implements `_ob_warm`.",
          "kind": "function"
        },
        {
          "name": "_parked",
          "line": 265,
          "description": "Implements `_parked`.",
          "kind": "function"
        },
        {
          "name": "_direction",
          "line": 272,
          "description": "Implements `_direction`.",
          "kind": "function"
        },
        {
          "name": "_stop",
          "line": 282,
          "description": "Implements `_stop`.",
          "kind": "function"
        },
        {
          "name": "_ns_bool",
          "line": 293,
          "description": "Implements `_ns_bool`.",
          "kind": "function"
        },
        {
          "name": "_eb_hk_specs",
          "line": 300,
          "description": "Implements `_eb_hk_specs`.",
          "kind": "function"
        },
        {
          "name": "_ob_hk_specs",
          "line": 425,
          "description": "Implements `_ob_hk_specs`.",
          "kind": "function"
        },
        {
          "name": "_render_metric_grid",
          "line": 619,
          "description": "Implements `_render_metric_grid`.",
          "kind": "function"
        },
        {
          "name": "_bind_metric_popups",
          "line": 632,
          "description": "Implements `_bind_metric_popups`.",
          "kind": "function"
        },
        {
          "name": "create_metrics_card",
          "line": 651,
          "description": "Implements `create_metrics_card`.",
          "kind": "function"
        },
        {
          "name": "create_default_eb_metrics_card",
          "line": 663,
          "description": "Implements `create_default_eb_metrics_card`.",
          "kind": "function"
        },
        {
          "name": "create_default_ob_metrics_card",
          "line": 703,
          "description": "Implements `create_default_ob_metrics_card`.",
          "kind": "function"
        },
        {
          "name": "create_packet_metrics_card",
          "line": 763,
          "description": "Implements `create_packet_metrics_card`.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "MetricSpec",
          "line": 28,
          "description": "Implements `MetricSpec`.",
          "bases": [],
          "methods": []
        },
        {
          "name": "MetricPill",
          "line": 48,
          "description": "Implements `MetricPill`.",
          "bases": [],
          "methods": []
        },
        {
          "name": "MetricsCardController",
          "line": 54,
          "description": "Implements `MetricsCardController`.",
          "bases": [],
          "methods": [
            {
              "name": "set_visible",
              "line": 60,
              "description": "Implements `set_visible`.",
              "kind": "method"
            },
            {
              "name": "set_no_data",
              "line": 66,
              "description": "Implements `set_no_data`.",
              "kind": "method"
            },
            {
              "name": "update_from_packet",
              "line": 71,
              "description": "Implements `update_from_packet`.",
              "kind": "method"
            }
          ]
        },
        {
          "name": "PacketMetricsCardController",
          "line": 140,
          "description": "Implements `PacketMetricsCardController`.",
          "bases": [],
          "methods": [
            {
              "name": "set_no_data",
              "line": 145,
              "description": "Implements `set_no_data`.",
              "kind": "method"
            },
            {
              "name": "set_mode",
              "line": 150,
              "description": "Implements `set_mode`.",
              "kind": "method"
            },
            {
              "name": "refresh",
              "line": 161,
              "description": "Implements `refresh`.",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/widget_modules/packet_viewer_widget.py",
      "package": "widget_modules",
      "module": "packet_viewer_widget",
      "description": "Provides `packet_viewer_widget` module logic.",
      "functions": [
        {
          "name": "create_packet_viewer",
          "line": 141,
          "description": "Creates a packet viewer UI component and returns its controller for updates.",
          "kind": "function"
        },
        {
          "name": "create_telemetry_list",
          "line": 179,
          "description": "Implements `create_telemetry_list`.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "PacketViewerController",
          "line": 33,
          "description": "Implements `PacketViewerController`.",
          "bases": [],
          "methods": [
            {
              "name": "refresh",
              "line": 40,
              "description": "Refresh values currently available in state.",
              "kind": "method"
            },
            {
              "name": "increment",
              "line": 47,
              "description": "Backward-compatible counter update used by existing callers.",
              "kind": "method"
            },
            {
              "name": "set_packet_type",
              "line": 51,
              "description": "Set the current packet type and refresh displayed values accordingly.",
              "kind": "method"
            },
            {
              "name": "update_from_packet",
              "line": 61,
              "description": "Store and render one decoded TM packet.",
              "kind": "method"
            },
            {
              "name": "_render_values",
              "line": 99,
              "description": "Render the given packet values in the UI, matching field names to labels.",
              "kind": "method"
            },
            {
              "name": "_format_value",
              "line": 117,
              "description": "Format a telemetry field value for display, with special handling for certain types.",
              "kind": "method"
            },
            {
              "name": "_coerce_packet_dict",
              "line": 130,
              "description": "Coerce a raw packet into a dictionary for easier processing.",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/widget_modules/parent_window_widget.py",
      "package": "widget_modules",
      "module": "parent_window_widget",
      "description": "Provides `parent_window_widget` module logic.",
      "functions": [
        {
          "name": "build_ui",
          "line": 42,
          "description": "Implements `build_ui`.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/widget_modules/plot_widget.py",
      "package": "widget_modules",
      "module": "plot_widget",
      "description": "Provides `plot_widget` module logic.",
      "functions": [
        {
          "name": "create_plot_card",
          "line": 28,
          "description": "Create a generic plot card.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "SeriesConfig",
          "line": 12,
          "description": "Configuration for a single plotted series.",
          "bases": [],
          "methods": []
        },
        {
          "name": "PlotCardController",
          "line": 21,
          "description": "Implements `PlotCardController`.",
          "bases": [],
          "methods": []
        }
      ]
    },
    {
      "path": "src/widget_modules/popup_widget.py",
      "package": "widget_modules",
      "module": "popup_widget",
      "description": "Provides `popup_widget` module logic.",
      "functions": [
        {
          "name": "show_message",
          "line": 10,
          "description": "Implements `show_message`.",
          "kind": "function"
        },
        {
          "name": "show_flag_popup",
          "line": 18,
          "description": "Show a popup with decoded flag bits for the selected metric.",
          "kind": "function"
        }
      ],
      "classes": []
    },
    {
      "path": "src/widget_modules/psu_widget.py",
      "package": "widget_modules",
      "module": "psu_widget",
      "description": "Provides `psu_widget` module logic.",
      "functions": [
        {
          "name": "create_psu_channel_card",
          "line": 54,
          "description": "Create a PSU channel card with a plot and enable switch.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "PsuChannelController",
          "line": 16,
          "description": "Implements `PsuChannelController`.",
          "bases": [],
          "methods": [
            {
              "name": "set_visible",
              "line": 23,
              "description": "Implements `set_visible`.",
              "kind": "method"
            },
            {
              "name": "apply_profile",
              "line": 29,
              "description": "Implements `apply_profile`.",
              "kind": "method"
            },
            {
              "name": "push_sample",
              "line": 45,
              "description": "Push a new sample to the channel's plot and update the value label.",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/widget_modules/traffic_light_widget.py",
      "package": "widget_modules",
      "module": "traffic_light_widget",
      "description": "Provides `traffic_light_widget` module logic.",
      "functions": [
        {
          "name": "create_traffic_lights",
          "line": 182,
          "description": "Implements `create_traffic_lights`.",
          "kind": "function"
        }
      ],
      "classes": [
        {
          "name": "AlarmLight",
          "line": 11,
          "description": "Implements `AlarmLight`.",
          "bases": [],
          "methods": [
            {
              "name": "__init__",
              "line": 12,
              "description": "Creates an alarm light with a label. The light can be set to OK or Fault state, and clicking on it will show a dialog with details.",
              "kind": "method"
            },
            {
              "name": "_create_fault_widget",
              "line": 28,
              "description": "Creates the UI elements for the fault light and its dialog.",
              "kind": "method"
            },
            {
              "name": "_refresh_from_sources",
              "line": 50,
              "description": "Implements `_refresh_from_sources`.",
              "kind": "method"
            },
            {
              "name": "_refresh_light",
              "line": 81,
              "description": "Refreshes the fault light's appearance based on its current state.",
              "kind": "method"
            },
            {
              "name": "set_fault_state",
              "line": 86,
              "description": "Sets the fault state to OK or Fault, and updates the details if provided.",
              "kind": "method"
            },
            {
              "name": "update_from_faults",
              "line": 99,
              "description": "Updates the fault state based on source-specific fault names and active status.",
              "kind": "method"
            },
            {
              "name": "clear_selected_faults",
              "line": 104,
              "description": "Acknowledge selected details while leaving other active alarms untouched.",
              "kind": "method"
            },
            {
              "name": "clear_fault",
              "line": 115,
              "description": "Clears the fault state and details.",
              "kind": "method"
            },
            {
              "name": "show_fault_dialog",
              "line": 127,
              "description": "Shows a dialog with the current fault details.",
              "kind": "method"
            },
            {
              "name": "set_visible",
              "line": 175,
              "description": "Implements `set_visible`.",
              "kind": "method"
            }
          ]
        }
      ]
    },
    {
      "path": "src/widget_modules/ui_runtime_controller.py",
      "package": "widget_modules",
      "module": "ui_runtime_controller",
      "description": "Provides `ui_runtime_controller` module logic.",
      "functions": [
        {
          "name": "create_set_mode",
          "line": 25,
          "description": "Create a mode setter callback bound to current state and app.",
          "kind": "function"
        },
        {
          "name": "dispatch_ob_tc",
          "line": 46,
          "description": "Send an OB TC using the shared OB port lock when available.",
          "kind": "function"
        },
        {
          "name": "_apply_theme_to_ui",
          "line": 62,
          "description": "Implements `_apply_theme_to_ui`.",
          "kind": "function"
        },
        {
          "name": "create_set_theme",
          "line": 89,
          "description": "Create a theme setter callback bound to current UI controllers.",
          "kind": "function"
        },
        {
          "name": "_reset_psu_replay",
          "line": 137,
          "description": "Implements `_reset_psu_replay`.",
          "kind": "function"
        },
        {
          "name": "_card_channel_preferences",
          "line": 147,
          "description": "Implements `_card_channel_preferences`.",
          "kind": "function"
        },
        {
          "name": "_update_psu_readings",
          "line": 158,
          "description": "Implements `_update_psu_readings`.",
          "kind": "function"
        },
        {
          "name": "_update_psu_cards",
          "line": 165,
          "description": "Implements `_update_psu_cards`.",
          "kind": "function"
        },
        {
          "name": "_update_psu_alarm_lights",
          "line": 172,
          "description": "Implements `_update_psu_alarm_lights`.",
          "kind": "function"
        },
        {
          "name": "_apply_psu_sample",
          "line": 185,
          "description": "Implements `_apply_psu_sample`.",
          "kind": "function"
        },
        {
          "name": "_build_replay_psu_sample",
          "line": 191,
          "description": "Implements `_build_replay_psu_sample`.",
          "kind": "function"
        },
        {
          "name": "create_set_psu_log_path",
          "line": 221,
          "description": "Create PSU replay-log setter callback bound to current state.",
          "kind": "function"
        },
        {
          "name": "create_set_psu_card_profiles",
          "line": 250,
          "description": "Create mode-dependent PSU card profile callback bound to PSU card controllers.",
          "kind": "function"
        },
        {
          "name": "create_poll_psu",
          "line": 287,
          "description": "Create PSU polling callback bound to the current UI state and cards.",
          "kind": "function"
        },
        {
          "name": "_decode_tuple",
          "line": 362,
          "description": "Implements `_decode_tuple`.",
          "kind": "function"
        },
        {
          "name": "_decoded",
          "line": 372,
          "description": "Implements `_decoded`.",
          "kind": "function"
        },
        {
          "name": "_active_flag_names",
          "line": 382,
          "description": "Implements `_active_flag_names`.",
          "kind": "function"
        },
        {
          "name": "_any_flag",
          "line": 392,
          "description": "Implements `_any_flag`.",
          "kind": "function"
        },
        {
          "name": "_ob_alarm_details",
          "line": 396,
          "description": "Implements `_ob_alarm_details`.",
          "kind": "function"
        },
        {
          "name": "_eb_alarm_details",
          "line": 411,
          "description": "Implements `_eb_alarm_details`.",
          "kind": "function"
        },
        {
          "name": "_update_hk_alarm_lights",
          "line": 426,
          "description": "Implements `_update_hk_alarm_lights`.",
          "kind": "function"
        },
        {
          "name": "_update_plot_cards",
          "line": 436,
          "description": "Implements `_update_plot_cards`.",
          "kind": "function"
        },
        {
          "name": "_update_packet_viewer",
          "line": 455,
          "description": "Implements `_update_packet_viewer`.",
          "kind": "function"
        },
        {
          "name": "_drain_packet_queue",
          "line": 459,
          "description": "Implements `_drain_packet_queue`.",
          "kind": "function"
        },
        {
          "name": "_violates_limits",
          "line": 485,
          "description": "Implements `_violates_limits`.",
          "kind": "function"
        },
        {
          "name": "_append_violation",
          "line": 492,
          "description": "Implements `_append_violation`.",
          "kind": "function"
        },
        {
          "name": "_limit_tuple",
          "line": 502,
          "description": "Implements `_limit_tuple`.",
          "kind": "function"
        },
        {
          "name": "_mms_reasons",
          "line": 508,
          "description": "Implements `_mms_reasons`.",
          "kind": "function"
        },
        {
          "name": "_disable_ob5v",
          "line": 526,
          "description": "Implements `_disable_ob5v`.",
          "kind": "function"
        },
        {
          "name": "_run_mms_actions",
          "line": 538,
          "description": "Implements `_run_mms_actions`.",
          "kind": "function"
        },
        {
          "name": "create_poll_tm",
          "line": 606,
          "description": "Create TM polling callback bound to current controllers and state.",
          "kind": "function"
        }
      ],
      "classes": []
    }
  ]
};
