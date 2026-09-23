import pytest

from utility_modules.port_selection import validate_com_port_selection


def test_validate_com_port_selection_rejects_duplicate_ports() -> None:
    with pytest.raises(SystemExit, match="OB and PSU COM ports must be different"):
        validate_com_port_selection("COM12", "COM12")


def test_validate_com_port_selection_allows_duplicate_when_psu_disabled() -> None:
    validate_com_port_selection("COM12", "COM12", nopsu=True)


def test_validate_com_port_selection_normalizes_whitespace_and_case() -> None:
    with pytest.raises(SystemExit):
        validate_com_port_selection(" com12 ", "COM12")