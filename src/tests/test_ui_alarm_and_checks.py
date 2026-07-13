from types import SimpleNamespace

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
    assert any("ERROR_FLAGS not 0" in detail for detail in result["details"])
    assert any("FDIR_ALARM_FLAGS not 0" in detail for detail in result["details"])
    assert any("FDIR_WARNING_FLAGS not 0" in detail for detail in result["details"])
