from types import SimpleNamespace
from core_modules import config
from widget_modules import ui_runtime_controller as urc


class _DummyLogger:
    def __init__(self) -> None:
        self.warns = []
        self.errors = []

    def warning(self, msg, *args):
        self.warns.append(msg % args if args else msg)

    def error(self, msg, *args):
        self.errors.append(msg % args if args else msg)


def test_ob_alarm_details_filter_only_ob_related_flags() -> None:
    hk = SimpleNamespace(
        WARNING_FLAGS_BITS=SimpleNamespace(OB_UNRESPONSIVE=1, GENERAL_ERROR=1),
        FDIR_ALARM_FLAGS_BITS=SimpleNamespace(DIGITAL_BOARD_TRP=1, EB_PLUS_5V_SUPPLY=1),
        FDIR_WARNING_FLAGS_BITS=SimpleNamespace(MECH_BOARD_TRP=1, EB_TEC_SUPPLY=1),
        ERRORS=SimpleNamespace(IPI=1),
        MTR_ERRORS=SimpleNamespace(DSE=1),
    )

    details = urc.ob_alarm_details(hk)

    assert "OB Warning: OB_UNRESPONSIVE" in details
    assert "OB Warning: GENERAL_ERROR" not in details
    assert "OB FDIR Alarm: DIGITAL_BOARD_TRP" in details
    assert "OB FDIR Alarm: EB_PLUS_5V_SUPPLY" not in details
    assert "OB FDIR Warning: MECH_BOARD_TRP" in details
    assert "OB FDIR Warning: EB_TEC_SUPPLY" not in details
    assert "OB Error flags active" in details
    assert "OB Motor error flags active" in details


def test_eb_alarm_details_filter_only_eb_related_flags_and_tcs_rejected() -> None:
    hk = SimpleNamespace(
        TCS_REJECTED=2,
        WARNING_FLAGS_BITS=SimpleNamespace(GENERAL_ERROR=1, OB_UNRESPONSIVE=1),
        FDIR_ALARM_FLAGS_BITS=SimpleNamespace(EB_PLUS_5V_SUPPLY=1, MECH_BOARD_TRP=1),
        FDIR_WARNING_FLAGS_BITS=SimpleNamespace(PSU_BOARD_TEMPERATURE=1, MOTOR_TRP=1),
    )

    details = urc.eb_alarm_details(hk)

    assert "TCS Rejected: 2" in details
    assert "EB Warning: GENERAL_ERROR" in details
    assert "EB Warning: OB_UNRESPONSIVE" not in details
    assert "EB FDIR Alarm: EB_PLUS_5V_SUPPLY" in details
    assert "EB FDIR Alarm: MECH_BOARD_TRP" not in details
    assert "EB FDIR Warning: PSU_BOARD_TEMPERATURE" in details
    assert "EB FDIR Warning: MOTOR_TRP" not in details


def test_log_new_hk_alarm_details_logs_raise_once() -> None:
    state = {}
    logger = _DummyLogger()

    urc.log_new_hk_alarm_details(
        state,
        logger,
        channel="ob",
        details=["OB Warning: OB_UNRESPONSIVE", "OB FDIR Alarm: DIGITAL_BOARD_TRP"],
    )

    assert any("warning raised" in msg for msg in logger.warns)
    assert any("alarm raised" in msg for msg in logger.errors)

    # Re-logging same details should not produce duplicate raise messages.
    warn_count = len(logger.warns)
    error_count = len(logger.errors)
    urc.log_new_hk_alarm_details(
        state,
        logger,
        channel="ob",
        details=["OB Warning: OB_UNRESPONSIVE", "OB FDIR Alarm: DIGITAL_BOARD_TRP"],
    )
    assert len(logger.warns) == warn_count
    assert len(logger.errors) == error_count


def test_perform_hk_check_detects_non_zero_error_and_fdir_fields() -> None:
    hk = SimpleNamespace(
        EB_MEAS_MAIN_12V=30000,
        EB_MEAS_MAIN_NEG12V=30000,
        EB_MEAS_5V=30000,
        EB_MEAS_3V3=43000,
        EB_MEAS_TEC_RAIL=0,
        EB_0V_ADC_READING=0,
        EB_TEC_DRIVE_CURRENT=0,
        TCS_REJECTED=0,
        INSTRUMENT_STATUS_FLAGS=25604,
        ERROR_FLAGS=1,
        WARNING_FLAGS=0,
        FDIR_ALARM_FLAGS=2,
        FDIR_WARNING_FLAGS=4,
    )

    result = urc.perform_hk_check(hk=hk, hk_type="hk")

    assert result["passed"] is False
    assert any("ERROR_FLAGS mismatch. Got: 1, Expected: 0" in detail for detail in result["details"])
    assert any("FDIR_ALARM_FLAGS mismatch. Got: 2, Expected: 0" in detail for detail in result["details"])
    assert any("FDIR_WARNING_FLAGS mismatch. Got: 4, Expected: 0" in detail for detail in result["details"])


# ---------------------------------------------------------------------------
# Additional alarm lifecycle and HK/POST validation coverage
# ---------------------------------------------------------------------------


def _valid_hk() -> SimpleNamespace:
    return SimpleNamespace(
        EB_MEAS_MAIN_12V=round(12.0 / 0.000400543),
        EB_MEAS_MAIN_NEG12V=round(-12.0 / -0.00038147),
        EB_MEAS_5V=round(5.0 / 0.000152829),
        EB_MEAS_3V3=round(3.3 / 0.0000763),
        EB_MEAS_TEC_RAIL=0,
        EB_0V_ADC_READING=0,
        EB_TEC_DRIVE_CURRENT=0,
        TCS_REJECTED=0,
        INSTRUMENT_STATUS_FLAGS=25604,
        ERROR_FLAGS=0,
        WARNING_FLAGS=0,
        FDIR_ALARM_FLAGS=0,
        FDIR_WARNING_FLAGS=0,
    )


def _valid_post(**overrides) -> SimpleNamespace:
    values = {
        "POST_WARNING_FLAGS": 0,
        "POST_ERROR_FLAGS": 0,
        "NUM_BAD_FLASH_BLOCKS": 0,
        "NUM_BAD_SRAM_BLOCKS": 0,
        **config.POST_EXPECTED_CRC,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_alarm_detail_helpers_handle_missing_namespaces() -> None:
    hk = SimpleNamespace(
        TCS_REJECTED=0,
        WARNING_FLAGS_BITS=None,
        FDIR_ALARM_FLAGS_BITS=None,
        FDIR_WARNING_FLAGS_BITS=None,
        ERRORS=None,
        MTR_ERRORS=None,
    )

    assert urc.ob_alarm_details(hk) == []
    assert urc.eb_alarm_details(hk) == []


def test_alarm_detail_is_logged_again_after_clear_and_retrigger() -> None:
    state = {}
    logger = _DummyLogger()
    detail = "OB FDIR Alarm: DIGITAL_BOARD_TRP"

    urc.log_new_hk_alarm_details(state, logger, channel="ob", details=[detail])
    urc.log_new_hk_alarm_details(state, logger, channel="ob", details=[])
    urc.log_new_hk_alarm_details(state, logger, channel="ob", details=[detail])

    assert sum("alarm raised" in message for message in logger.errors) == 2


def test_perform_hk_check_reports_missing_hk() -> None:
    result = urc.perform_hk_check(hk=None, hk_type="hk")

    assert result == {"passed": False, "details": ["No HK data available."]}


def test_perform_hk_check_accepts_valid_hk() -> None:
    result = urc.perform_hk_check(hk=_valid_hk(), hk_type="hk")

    assert result == {"passed": True, "details": []}


def test_perform_hk_check_failure_reports_actual_and_expected_range() -> None:
    hk = _valid_hk()
    hk.EB_MEAS_MAIN_12V = round(14.0 / 0.000400543)

    result = urc.perform_hk_check(hk=hk, hk_type="hk")

    assert result["passed"] is False
    assert any(
        "EB 12V out of range. Got:" in detail and "Expected: 11.00 to 13.00 V" in detail
        for detail in result["details"]
    )


def test_perform_hk_check_reports_missing_required_field() -> None:
    hk = _valid_hk()
    del hk.EB_MEAS_MAIN_12V

    result = urc.perform_hk_check(hk=hk, hk_type="hk")

    assert result["passed"] is False
    assert any("Missing HK field" in detail for detail in result["details"])


def test_perform_hk_check_reports_none_value_without_conversion_error() -> None:
    hk = _valid_hk()
    hk.EB_MEAS_3V3 = None

    result = urc.perform_hk_check(hk=hk, hk_type="hk")

    assert result["passed"] is False
    assert "EB_MEAS_3V3. Got: None, Expected: numeric HK value" in result["details"]


def test_perform_post_check_reports_missing_post() -> None:
    result = urc.perform_hk_check(post=None, hk_type="post")

    assert result == {"passed": False, "details": ["No POST data available."]}


def test_perform_post_check_accepts_valid_crc_and_status_fields() -> None:
    result = urc.perform_hk_check(post=_valid_post(), hk_type="post")

    assert result == {"passed": True, "details": []}


def test_perform_post_check_reports_each_failed_status_or_crc() -> None:
    post = _valid_post(
        POST_WARNING_FLAGS=1,
        POST_ERROR_FLAGS=2,
        NUM_BAD_FLASH_BLOCKS=3,
        NUM_BAD_SRAM_BLOCKS=4,
        ASW_IMAGE_1_CRC=0,
        MEASUREMENT_TABLE_CRC=0,
    )

    result = urc.perform_hk_check(post=post, hk_type="post")

    assert result["passed"] is False
    assert any("POST_WARNING_FLAGS mismatch. Got: 1, Expected: 0" in detail for detail in result["details"])
    assert any("POST_ERROR_FLAGS mismatch. Got: 2, Expected: 0" in detail for detail in result["details"])
    assert any("NUM_BAD_FLASH_BLOCKS mismatch. Got: 3, Expected: 0" in detail for detail in result["details"])
    assert any("NUM_BAD_SRAM_BLOCKS mismatch. Got: 4, Expected: 0" in detail for detail in result["details"])
    assert any("ASW_IMAGE_1_CRC mismatch. Got: 0x0000, Expected:" in detail for detail in result["details"])
    assert any("MEASUREMENT_TABLE_CRC mismatch. Got: 0x0000, Expected:" in detail for detail in result["details"])


def test_perform_post_failure_diagnostics_are_separate_from_errors() -> None:
    post = _valid_post(MEASUREMENT_TABLE_CRC=0)

    result = urc.perform_hk_check(post=post, hk_type="post")

    assert result["passed"] is False
    assert len(result["details"]) == 1
    assert "MEASUREMENT_TABLE_CRC mismatch" in result["details"][0]
    diagnostics = result.get("diagnostics", [])
    assert any(
        "TM_12V: Got:" in detail
        and "Expected: 11.00 to 13.00 V" in detail
        and "[PASS]" in detail
        for detail in diagnostics
    )
    assert any(
        "TM_NEG12V: Got:" in detail
        and "Expected: -13.00 to -11.00 V" in detail
        and "[PASS]" in detail
        for detail in diagnostics
    )
    assert any(
        "TM_5V: Got:" in detail
        and "Expected: 4.50 to 5.50 V" in detail
        and "[PASS]" in detail
        for detail in diagnostics
    )
    assert any(
        "TM_3V3: Got:" in detail
        and "Expected: 3.00 to 3.45 V" in detail
        and "[PASS]" in detail
        for detail in diagnostics
    )
    assert any(
        "EB_PROCESSOR_TEMP: Got:" in detail
        and "Expected: -45.00 to 125.00 C" in detail
        and "[PASS]" in detail
        for detail in diagnostics
    )
    assert any(
        "TEC_DETECTOR_TEMP: Got:" in detail
        and "Expected: -45.00 to 35.00 C" in detail
        and "[PASS]" in detail
        for detail in diagnostics
    )


def test_perform_post_check_reports_conversion_error() -> None:
    post = _valid_post(TM_12V="not-numeric")

    result = urc.perform_hk_check(post=post, hk_type="post")

    assert result["passed"] is False
    assert any("POST conversion error" in detail for detail in result["details"])


def test_perform_hk_check_rejects_unknown_check_type() -> None:
    result = urc.perform_hk_check(hk_type="unknown")

    assert result == {"passed": False, "details": ["Unknown hk_type: unknown"]}
