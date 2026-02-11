import logging
import math
from pathlib import Path
import sys

# Add src to path to import constants
sys.path.insert(0, str(Path(__file__).parent.parent))
import constants as const

# Create SFT check logger using project's log structure
sft_log_file = const.DEFAULT_PATH / "SFT_CHECK_LOG.log"
sft_log_file.parent.mkdir(parents=True, exist_ok=True)

sft_logger = logging.getLogger("sft_check")
sft_logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler(sft_log_file)
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)

sft_logger.addHandler(file_handler)


def _convert_thermistor_b_parameter(adu):
    T0 = 298.0  # K
    R0 = 5000.0  # Ω
    B = 3891.0
    
    # Calculate resistance from ADU
    if adu >= 65536 or adu < 0:
        return float('nan')  # Invalid ADU
    
    denominator = (65536.0 - adu)
    if denominator <= 0:
        return float('nan')  # Invalid ADU
    
    R = 1000.0 * ((65536.0 / denominator) - 1.0)
    
    # Validate resistance is positive
    if R <= 0:
        return float('nan')  # Invalid resistance
    
    try:
        # Calculate temperature using B-parameter equation
        inv_T = (1.0 / T0) + (1.0 / B) * math.log(R / R0)
        T_kelvin = 1.0 / inv_T
        T_celsius = T_kelvin - 273.15
        return T_celsius
    except (ValueError, ZeroDivisionError):
        return float('nan')  # Invalid calculation


def check_sft(
    last_hk,
    post_hk=None,
    mode=None,
    expected_model_id=None,
):
    try:
        # Get operating state
        op_state_map = {0x00: "INITIALISING", 0x02: "SAFE", 0x04: "STANDBY", 0x08: "ACQUISITION"}
        operating_state = last_hk.CURRENT_OPERATING_STATE
        op_state_name = op_state_map.get(operating_state, f"UNKNOWN(0x{operating_state:02X})")
        
        sft_logger.info(
            f"SFT Check started - Operating State: {op_state_name} (0x{operating_state:02X}), Selected Mode: {mode}"
        )
        
        all_passed = True
        error_messages = []
        
        # Mode override from GUI
        if mode == "Safe Mode Checks":
            sft_logger.info("Selected SAFE mode checks - Checking HK and POST parameters")

            # Check regular HK packet
            hk_pass, hk_errors = _check_hk_parameters(
                last_hk,
                mode=mode,
                expected_model_id=expected_model_id,
            )
            if not hk_pass:
                all_passed = False
                error_messages.extend(hk_errors)
                for error in hk_errors:
                    sft_logger.error(f"HK Check Failed: {error}")
            else:
                sft_logger.info("HK parameters check PASSED")

            # Check POST packet (if provided)
            if post_hk is not None:
                post_pass, post_errors = _check_post_parameters(post_hk)
                if not post_pass:
                    all_passed = False
                    error_messages.extend(post_errors)
                    for error in post_errors:
                        sft_logger.error(f"POST Check Failed: {error}")
                else:
                    sft_logger.info("POST parameters check PASSED")
            else:
                sft_logger.warning("POST packet not provided for SAFE mode check")

        elif mode == "Standby Mode Checks":
            sft_logger.info("Selected STANDBY mode checks - Checking HK parameters only")

            # Check regular HK packet
            hk_pass, hk_errors = _check_hk_parameters(
                last_hk,
                mode=mode,
                expected_model_id=expected_model_id,
            )
            if not hk_pass:
                all_passed = False
                error_messages.extend(hk_errors)
                for error in hk_errors:
                    sft_logger.error(f"HK Check Failed: {error}")
            else:
                sft_logger.info("HK parameters check PASSED")

        # SAFE mode checks (both HK and POST)
        elif operating_state == 0x02:
            sft_logger.info("Operating in SAFE mode - Checking HK and POST parameters")
            
            # Check regular HK packet
            hk_pass, hk_errors = _check_hk_parameters(
                last_hk,
                mode=mode,
                expected_model_id=expected_model_id,
            )
            if not hk_pass:
                all_passed = False
                error_messages.extend(hk_errors)
                for error in hk_errors:
                    sft_logger.error(f"HK Check Failed: {error}")
            else:
                sft_logger.info("HK parameters check PASSED")
            
            # Check POST packet (if provided)
            if post_hk is not None:
                post_pass, post_errors = _check_post_parameters(post_hk)
                if not post_pass:
                    all_passed = False
                    error_messages.extend(post_errors)
                    for error in post_errors:
                        sft_logger.error(f"POST Check Failed: {error}")
                else:
                    sft_logger.info("POST parameters check PASSED")
            else:
                sft_logger.warning("POST packet not provided for SAFE mode check")
        
        # STANDBY mode checks (HK only)
        elif operating_state == 0x04:
            sft_logger.info("Operating in STANDBY mode - Checking HK parameters only")
            
            # Check regular HK packet
            hk_pass, hk_errors = _check_hk_parameters(
                last_hk,
                mode=mode,
                expected_model_id=expected_model_id,
            )
            if not hk_pass:
                all_passed = False
                error_messages.extend(hk_errors)
                for error in hk_errors:
                    sft_logger.error(f"HK Check Failed: {error}")
            else:
                sft_logger.info("HK parameters check PASSED")
        
        # Other modes
        else:
            sft_logger.warning(f"Operating state {op_state_name} not configured for SFT checks")
        
        # Log final result
        if all_passed:
            sft_logger.info("SFT Check PASSED - All parameters within limits")
            return True, "SFT Check PASSED"
        else:
            error_summary = "; ".join(error_messages)
            sft_logger.error(f"SFT Check FAILED - {error_summary}")
            return False, f"SFT Check FAILED: {error_summary}"
    
    except Exception as e:
        sft_logger.error(f"Exception during SFT check: {str(e)}", exc_info=True)
        return False, f"SFT Check ERROR: {str(e)}"


def _check_hk_parameters(
    last_hk,
    mode=None,
    expected_model_id=None,
):
    all_passed = True
    errors = []
    
    # Get operating state to determine which checks to run
    operating_state = last_hk.CURRENT_OPERATING_STATE

    if mode == "Safe Mode Checks":
        effective_mode = "SAFE"
    elif mode == "Standby Mode Checks":
        effective_mode = "STANDBY"
    elif operating_state == 0x02:
        effective_mode = "SAFE"
    elif operating_state == 0x04:
        effective_mode = "STANDBY"
    else:
        effective_mode = None
    
    # ============ CHECKS FOR BOTH SAFE AND STANDBY MODES ============
    
    sft_logger.info("--- Checking HK Parameters (Common to SAFE and STANDBY) ---")
    
    # TC's Rejected (should be 0 in both modes)
    sft_logger.info(f"TCS_REJECTED: {last_hk.TCS_REJECTED} (expected 0)")
    if last_hk.TCS_REJECTED != 0:
        all_passed = False
        errors.append(f"TCS_REJECTED unexpected: {last_hk.TCS_REJECTED} (expected 0)")
    
    # Error Flags (should be 0 in both modes)
    sft_logger.info(f"ERROR_FLAGS: {last_hk.ERROR_FLAGS} (expected 0)")
    if last_hk.ERROR_FLAGS != 0:
        all_passed = False
        errors.append(f"ERROR_FLAGS unexpected: {last_hk.ERROR_FLAGS} (expected 0)")
    
    # Warning Flags (should be 0 in both modes)
    sft_logger.info(f"WARNING_FLAGS: {last_hk.WARNING_FLAGS} (expected 0)")
    if last_hk.WARNING_FLAGS != 0:
        all_passed = False
        errors.append(f"WARNING_FLAGS unexpected: {last_hk.WARNING_FLAGS} (expected 0)")
    
    # EB +5V (5V +/- 0.5V, range 4.5V to 5.5V in both modes) - apply conversion factor
    eb_5v_converted = last_hk.EB_MEAS_5V * 0.000153
    sft_logger.info(f"EB_MEAS_5V: raw={last_hk.EB_MEAS_5V}, converted={eb_5v_converted:.4f}V (expected 4.5-5.5V)")
    if not (4.5 <= eb_5v_converted <= 5.5):
        all_passed = False
        errors.append(f"EB_MEAS_5V out of range: {eb_5v_converted:.2f}V (expected 4.5-5.5V)")
    
    # EB +3V3 (3.3V +/- 0.5V, range 2.8V to 3.8V in both modes) - apply conversion factor
    eb_3v3_converted = last_hk.EB_MEAS_3V3 * 0.0000763
    sft_logger.info(f"EB_MEAS_3V3: raw={last_hk.EB_MEAS_3V3}, converted={eb_3v3_converted:.4f}V (expected 2.8-3.8V)")
    if not (2.8 <= eb_3v3_converted <= 3.8):
        all_passed = False
        errors.append(f"EB_MEAS_3V3 out of range: {eb_3v3_converted:.2f}V (expected 2.8-3.8V)")
    
    # EB TEC_V (0V +/- 0.5V, range -0.5V to 0.5V in both modes) - apply conversion factor
    eb_tec_v_converted = last_hk.EB_MEAS_TEC_RAIL * 0.0000763
    sft_logger.info(f"EB_MEAS_TEC_RAIL: raw={last_hk.EB_MEAS_TEC_RAIL}, converted={eb_tec_v_converted:.4f}V (expected -0.5 to 0.5V)")
    if not (-0.5 <= eb_tec_v_converted <= 0.5):
        all_passed = False
        errors.append(f"EB_MEAS_TEC_RAIL out of range: {eb_tec_v_converted:.2f}V (expected -0.5 to 0.5V)")
    
    # EB 0V (0V +/- 0.5V, range -0.5V to 0.5V in both modes) - apply conversion factor
    eb_0v_converted = last_hk.EB_0V_ADC_READING * 0.0000763
    sft_logger.info(f"EB_0V_ADC_READING: raw={last_hk.EB_0V_ADC_READING}, converted={eb_0v_converted:.4f}V (expected -0.5 to 0.5V)")
    if not (-0.5 <= eb_0v_converted <= 0.5):
        all_passed = False
        errors.append(f"EB_0V_ADC_READING out of range: {eb_0v_converted:.2f}V (expected -0.5 to 0.5V)")
    
    # EB MCU Internal Temperature (~23C +20C/-5C, range 18C to 43C in both modes) - apply conversion factor
    eb_mcu_temp_converted = last_hk.EB_MCU_INTERNAL_TEMP * 0.01637198 - 273
    sft_logger.info(f"EB_MCU_INTERNAL_TEMP: raw={last_hk.EB_MCU_INTERNAL_TEMP}, converted={eb_mcu_temp_converted:.2f}°C (expected 18.0-43.0°C)")
    if not (18.0 <= eb_mcu_temp_converted <= 43.0):
        all_passed = False
        errors.append(f"EB_MCU_INTERNAL_TEMP out of range: {eb_mcu_temp_converted:.2f}C (expected 18.0-43.0C)")
    
    # EB Peltier Temperature (~23C +20C/-5C, range 18C to 43C in both modes)
    eb_peltier_temp_converted = last_hk.EB_PELTIER_TEMP * (-0.001830011) + 51.27039922
    sft_logger.info(f"EB_PELTIER_TEMP: raw={last_hk.EB_PELTIER_TEMP}, converted={eb_peltier_temp_converted:.2f}°C (expected 18.0-43.0°C)")
    if not (18.0 <= eb_peltier_temp_converted <= 43.0):
        all_passed = False
        errors.append(f"EB_PELTIER_TEMP out of range: {eb_peltier_temp_converted:.2f}C (expected 18.0-43.0C)")
    
    # EB Internal TRP Thermistor Temperature (~23C +20C/-5C, range 18C to 43C in both modes) - use B-parameter equation
    eb_internal_trp_converted = _convert_thermistor_b_parameter(last_hk.EB_INTERNAL_TRP_TEMP)
    sft_logger.info(f"EB_INTERNAL_TRP_TEMP: raw={last_hk.EB_INTERNAL_TRP_TEMP}, converted={eb_internal_trp_converted:.2f}°C (expected 18.0-43.0°C)")
    if not (18.0 <= eb_internal_trp_converted <= 43.0):
        all_passed = False
        errors.append(f"EB_INTERNAL_TRP_TEMP out of range: {eb_internal_trp_converted:.2f}C (expected 18.0-43.0C)")
    
    # EB PSU Board Thermistor Temperature (~23C +20C/-5C, range 18C to 43C in both modes) - use B-parameter equation
    eb_psu_temp_converted = _convert_thermistor_b_parameter(last_hk.EB_PSU_BOARD_TEMP)
    sft_logger.info(f"EB_PSU_BOARD_TEMP: raw={last_hk.EB_PSU_BOARD_TEMP}, converted={eb_psu_temp_converted:.2f}°C (expected 18.0-43.0°C)")
    if not (18.0 <= eb_psu_temp_converted <= 43.0):
        all_passed = False
        errors.append(f"EB_PSU_BOARD_TEMP out of range: {eb_psu_temp_converted:.2f}C (expected 18.0-43.0C)")
    
    # EB InAs Detector TEC Drive Current (0A +/- 0.1A in both modes) - apply conversion factor
    eb_tec_current_converted = last_hk.EB_TEC_DRIVE_CURRENT * 0.0000162
    sft_logger.info(f"EB_TEC_DRIVE_CURRENT: raw={last_hk.EB_TEC_DRIVE_CURRENT}, converted={eb_tec_current_converted:.4f}A (expected -0.1 to 0.1A)")
    if not (-0.1 <= eb_tec_current_converted <= 0.1):
        all_passed = False
        errors.append(f"EB_TEC_DRIVE_CURRENT out of range: {eb_tec_current_converted:.3f}A (expected -0.1 to 0.1A)")
    
    # ============ MODE-SPECIFIC CHECKS ============
    
    if effective_mode == "SAFE":  # SAFE MODE
        
        sft_logger.info("--- Checking SAFE Mode Specific Parameters ---")
        
        # TC's Accepted (should be 1 in SAFE mode)
        sft_logger.info(f"TCS_ACCEPTED: {last_hk.TCS_ACCEPTED} (expected 1)")
        if last_hk.TCS_ACCEPTED != 1:
            all_passed = False
            errors.append(f"TCS_ACCEPTED unexpected in SAFE: {last_hk.TCS_ACCEPTED} (expected 1)")
        
        # Instrument Status Flags (should be 6 in SAFE mode)
        sft_logger.info(f"INSTRUMENT_STATUS_FLAGS: {last_hk.INSTRUMENT_STATUS_FLAGS} (expected 6)")
        if last_hk.INSTRUMENT_STATUS_FLAGS != 6:
            all_passed = False
            errors.append(f"INSTRUMENT_STATUS_FLAGS unexpected in SAFE: {last_hk.INSTRUMENT_STATUS_FLAGS} (expected 6)")
        
        # Current Operating State (should be Safe, 0x02)
        sft_logger.info(f"CURRENT_OPERATING_STATE: 0x{last_hk.CURRENT_OPERATING_STATE:02X} (expected 0x02 SAFE)")
        if last_hk.CURRENT_OPERATING_STATE != 0x02:
            all_passed = False
            errors.append(f"CURRENT_OPERATING_STATE unexpected: 0x{last_hk.CURRENT_OPERATING_STATE:02X} (expected 0x02 SAFE)")
        
        # EB +12V in SAFE (12V +/- 1V, range 11V to 13V) - apply conversion factor
        eb_12v_converted = last_hk.EB_MEAS_MAIN_12V * 0.0004005
        sft_logger.info(f"EB_MEAS_MAIN_12V: raw={last_hk.EB_MEAS_MAIN_12V}, converted={eb_12v_converted:.4f}V (expected 11.0-13.0V)")
        if not (11.0 <= eb_12v_converted <= 13.0):
            all_passed = False
            errors.append(f"EB_MEAS_MAIN_12V out of range: {eb_12v_converted:.2f}V (expected 11.0-13.0V)")
        
        # EB -12V in SAFE (-12V +/- 1V, range -13V to -11V) - apply conversion factor and negate
        eb_neg12v_converted = -(last_hk.EB_MEAS_MAIN_NEG12V * 0.00038147)
        sft_logger.info(f"EB_MEAS_MAIN_NEG12V: raw={last_hk.EB_MEAS_MAIN_NEG12V}, converted={eb_neg12v_converted:.4f}V (expected -13.0 to -11.0V)")
        if not (-13.0 <= eb_neg12v_converted <= -11.0):
            all_passed = False
            errors.append(f"EB_MEAS_MAIN_NEG12V out of range: {eb_neg12v_converted:.2f}V (expected -13.0 to -11.0V)")
        
        # Software Major Version (should be 2 in SAFE)
        sft_logger.info(f"SOFTWARE_MAJOR_VERSION: {last_hk.SOFTWARE_MAJOR_VERSION} (expected 2)")
        if last_hk.SOFTWARE_MAJOR_VERSION != 2:
            all_passed = False
            errors.append(f"SOFTWARE_MAJOR_VERSION unexpected in SAFE: {last_hk.SOFTWARE_MAJOR_VERSION} (expected 2)")
        
        # Software Minor Version (should be 0 in SAFE)
        sft_logger.info(f"SOFTWARE_MINOR_VERSION: {last_hk.SOFTWARE_MINOR_VERSION} (expected 0)")
        if last_hk.SOFTWARE_MINOR_VERSION != 0:
            all_passed = False
            errors.append(f"SOFTWARE_MINOR_VERSION unexpected in SAFE: {last_hk.SOFTWARE_MINOR_VERSION} (expected 0)")
        
        # Software Patch Version (should be 4 in SAFE)
        sft_logger.info(f"SOFTWARE_PATCH_VERSION: {last_hk.SOFTWARE_PATCH_VERSION} (expected 4)")
        if last_hk.SOFTWARE_PATCH_VERSION != 4:
            all_passed = False
            errors.append(f"SOFTWARE_PATCH_VERSION unexpected in SAFE: {last_hk.SOFTWARE_PATCH_VERSION} (expected 4)")
    
    elif effective_mode == "STANDBY":  # STANDBY MODE
        
        sft_logger.info("--- Checking STANDBY Mode Specific Parameters ---")
        
        # TC's Accepted (should be 2 in STANDBY mode)
        sft_logger.info(f"TCS_ACCEPTED: {last_hk.TCS_ACCEPTED} (expected 2)")
        if last_hk.TCS_ACCEPTED != 2:
            all_passed = False
            errors.append(f"TCS_ACCEPTED unexpected in STANDBY: {last_hk.TCS_ACCEPTED} (expected 2)")
        
        # Instrument Status Flags (should be 25604 in STANDBY mode)
        sft_logger.info(f"INSTRUMENT_STATUS_FLAGS: {last_hk.INSTRUMENT_STATUS_FLAGS} (expected 25604)")
        if last_hk.INSTRUMENT_STATUS_FLAGS != 25604:
            all_passed = False
            errors.append(f"INSTRUMENT_STATUS_FLAGS unexpected in STANDBY: {last_hk.INSTRUMENT_STATUS_FLAGS} (expected 25604)")
        
        # Current Operating State (should be Standby, 0x04)
        sft_logger.info(f"CURRENT_OPERATING_STATE: 0x{last_hk.CURRENT_OPERATING_STATE:02X} (expected 0x04 STANDBY)")
        if last_hk.CURRENT_OPERATING_STATE != 0x04:
            all_passed = False
            errors.append(f"CURRENT_OPERATING_STATE unexpected: 0x{last_hk.CURRENT_OPERATING_STATE:02X} (expected 0x04 STANDBY)")
        
        # EB +12V in STANDBY (12V +/- 1V, range 11V to 13V) - apply conversion factor
        eb_12v_converted = last_hk.EB_MEAS_MAIN_12V * 0.0004005
        sft_logger.info(f"EB_MEAS_MAIN_12V: raw={last_hk.EB_MEAS_MAIN_12V}, converted={eb_12v_converted:.4f}V (expected 11.0-13.0V)")
        if not (11.0 <= eb_12v_converted <= 13.0):
            all_passed = False
            errors.append(f"EB_MEAS_MAIN_12V out of range: {eb_12v_converted:.2f}V (expected 11.0-13.0V)")
        
        # EB -12V in STANDBY (-12V +/- 1V, range -13V to -11V) - apply conversion factor and negate
        eb_neg12v_converted = -(last_hk.EB_MEAS_MAIN_NEG12V * 0.00038147)
        sft_logger.info(f"EB_MEAS_MAIN_NEG12V: raw={last_hk.EB_MEAS_MAIN_NEG12V}, converted={eb_neg12v_converted:.4f}V (expected -13.0 to -11.0V)")
        if not (-13.0 <= eb_neg12v_converted <= -11.0):
            all_passed = False
            errors.append(f"EB_MEAS_MAIN_NEG12V out of range: {eb_neg12v_converted:.2f}V (expected -13.0 to -11.0V)")

        # OB HK ID (full byte) must match selected model id shifted left by 5
        ob_hk_id = getattr(last_hk, "OB_HK_ID", None)
        if ob_hk_id is None:
            sft_logger.info("OB_HK_ID: missing")
            all_passed = False
            errors.append("OB_HK_ID missing in STANDBY")
        elif expected_model_id is not None:
            expected_ob_hk_id = expected_model_id << 5
            sft_logger.info(f"OB_HK_ID: {ob_hk_id} (expected {expected_ob_hk_id})")
            if ob_hk_id != expected_ob_hk_id:
                all_passed = False
                errors.append(
                    f"OB_HK_ID unexpected in STANDBY: {ob_hk_id} (expected {expected_ob_hk_id})"
                )

        # OB Command Count (expected 8 in STANDBY)
        sft_logger.info(f"OB_COMMAND_COUNT: {last_hk.OB_COMMAND_COUNT} (expected 8)")
        if last_hk.OB_COMMAND_COUNT != 8:
            all_passed = False
            errors.append(f"OB_COMMAND_COUNT unexpected in STANDBY: {last_hk.OB_COMMAND_COUNT} (expected 8)")

        # Software version (expected 3.2.8 in STANDBY)
        sft_logger.info(f"SOFTWARE_MAJOR_VERSION: {last_hk.SOFTWARE_MAJOR_VERSION} (expected 3)")
        if last_hk.SOFTWARE_MAJOR_VERSION != 3:
            all_passed = False
            errors.append(
                f"SOFTWARE_MAJOR_VERSION unexpected in STANDBY: {last_hk.SOFTWARE_MAJOR_VERSION} (expected 3)"
            )
        sft_logger.info(f"SOFTWARE_MINOR_VERSION: {last_hk.SOFTWARE_MINOR_VERSION} (expected 2)")
        if last_hk.SOFTWARE_MINOR_VERSION != 2:
            all_passed = False
            errors.append(
                f"SOFTWARE_MINOR_VERSION unexpected in STANDBY: {last_hk.SOFTWARE_MINOR_VERSION} (expected 2)"
            )
        sft_logger.info(f"SOFTWARE_PATCH_VERSION: {last_hk.SOFTWARE_PATCH_VERSION} (expected 8)")
        if last_hk.SOFTWARE_PATCH_VERSION != 8:
            all_passed = False
            errors.append(
                f"SOFTWARE_PATCH_VERSION unexpected in STANDBY: {last_hk.SOFTWARE_PATCH_VERSION} (expected 8)"
            )

        # OB Model ID from OB_HK_ID byte (if present)
        ob_hk_id = getattr(last_hk, "OB_HK_ID", None)
        if ob_hk_id is not None:
            actual_model_id = (ob_hk_id >> 5) & 0x7
        else:
            actual_model_id = None

        if expected_model_id is not None:
            if actual_model_id is None:
                sft_logger.warning("OB_HK_ID not present in HK packet; skipping model ID check")
            else:
                sft_logger.info(f"OB_MODEL_ID: {actual_model_id} (expected {expected_model_id})")
                if actual_model_id != expected_model_id:
                    all_passed = False
                    errors.append(
                        f"OB_MODEL_ID unexpected in STANDBY: {actual_model_id} (expected {expected_model_id})"
                    )
    
    return all_passed, errors


def _check_post_parameters(post_hk):
    all_passed = True
    errors = []
    
    sft_logger.info("--- Checking POST Packet Parameters ---")
    
    # POST Warning Flags (should be 0)
    sft_logger.info(f"POST_WARNING_FLAGS: {post_hk.POST_WARNING_FLAGS} (expected 0)")
    if post_hk.POST_WARNING_FLAGS != 0:
        all_passed = False
        errors.append(f"POST_WARNING_FLAGS unexpected: {post_hk.POST_WARNING_FLAGS} (expected 0)")
    
    # POST Error Flags (should be 0)
    sft_logger.info(f"POST_ERROR_FLAGS: {post_hk.POST_ERROR_FLAGS} (expected 0)")
    if post_hk.POST_ERROR_FLAGS != 0:
        all_passed = False
        errors.append(f"POST_ERROR_FLAGS unexpected: {post_hk.POST_ERROR_FLAGS} (expected 0)")
    
    # Num Bad Flash Blocks (should be 0)
    sft_logger.info(f"NUM_BAD_FLASH_BLOCKS: {post_hk.NUM_BAD_FLASH_BLOCKS} (expected 0)")
    if post_hk.NUM_BAD_FLASH_BLOCKS != 0:
        all_passed = False
        errors.append(f"NUM_BAD_FLASH_BLOCKS unexpected: {post_hk.NUM_BAD_FLASH_BLOCKS} (expected 0)")
    
    # Num Bad SRAM Blocks (should be 0)
    sft_logger.info(f"NUM_BAD_SRAM_BLOCKS: {post_hk.NUM_BAD_SRAM_BLOCKS} (expected 0)")
    if post_hk.NUM_BAD_SRAM_BLOCKS != 0:
        all_passed = False
        errors.append(f"NUM_BAD_SRAM_BLOCKS unexpected: {post_hk.NUM_BAD_SRAM_BLOCKS} (expected 0)")
    
    # ASW Image#1 CRC (should be 0xBAF7)
    sft_logger.info(f"ASW_IMAGE_1_CRC: 0x{post_hk.ASW_IMAGE_1_CRC:04X} (expected 0xBAF7)")
    if post_hk.ASW_IMAGE_1_CRC != 0xBAF7:
        all_passed = False
        errors.append(f"ASW_IMAGE_1_CRC mismatch: got 0x{post_hk.ASW_IMAGE_1_CRC:04X}, expected 0xBAF7")
    
    # ASW Image#2 CRC (should be 0x5C55)
    sft_logger.info(f"ASW_IMAGE_2_CRC: 0x{post_hk.ASW_IMAGE_2_CRC:04X} (expected 0x5C55)")
    if post_hk.ASW_IMAGE_2_CRC != 0x5C55:
        all_passed = False
        errors.append(f"ASW_IMAGE_2_CRC mismatch: got 0x{post_hk.ASW_IMAGE_2_CRC:04X}, expected 0x5C55")
    
    # ASW Image#3 CRC (should be 0x01CB)
    sft_logger.info(f"ASW_IMAGE_3_CRC: 0x{post_hk.ASW_IMAGE_3_CRC:04X} (expected 0x01CB)")
    if post_hk.ASW_IMAGE_3_CRC != 0x01CB:
        all_passed = False
        errors.append(f"ASW_IMAGE_3_CRC mismatch: got 0x{post_hk.ASW_IMAGE_3_CRC:04X}, expected 0x01CB")
    
    # ASW Image#4 CRC (should be 0x5318)
    sft_logger.info(f"ASW_IMAGE_4_CRC: 0x{post_hk.ASW_IMAGE_4_CRC:04X} (expected 0x5318)")
    if post_hk.ASW_IMAGE_4_CRC != 0x5318:
        all_passed = False
        errors.append(f"ASW_IMAGE_4_CRC mismatch: got 0x{post_hk.ASW_IMAGE_4_CRC:04X}, expected 0x5318")
    
    # ASW Image#5 CRC (should be 0xDCAE)
    sft_logger.info(f"ASW_IMAGE_5_CRC: 0x{post_hk.ASW_IMAGE_5_CRC:04X} (expected 0xDCAE)")
    if post_hk.ASW_IMAGE_5_CRC != 0xDCAE:
        all_passed = False
        errors.append(f"ASW_IMAGE_5_CRC mismatch: got 0x{post_hk.ASW_IMAGE_5_CRC:04X}, expected 0xDCAE")
    
    # BSW Image CRC (should be 0xD2D7)
    sft_logger.info(f"BSW_IMAGE_CRC: 0x{post_hk.BSW_IMAGE_CRC:04X} (expected 0xD2D7)")
    if post_hk.BSW_IMAGE_CRC != 0xD2D7:
        all_passed = False
        errors.append(f"BSW_IMAGE_CRC mismatch: got 0x{post_hk.BSW_IMAGE_CRC:04X}, expected 0xD2D7")
    
    # Measurement Table CRC (should be 0x9D9B)
    sft_logger.info(f"MEASUREMENT_TABLE_CRC: 0x{post_hk.MEASUREMENT_TABLE_CRC:04X} (expected 0x9D9B)")
    if post_hk.MEASUREMENT_TABLE_CRC != 0x9D9B:
        all_passed = False
        errors.append(f"MEASUREMENT_TABLE_CRC mismatch: got 0x{post_hk.MEASUREMENT_TABLE_CRC:04X}, expected 0x9D9B")
    
    return all_passed, errors
