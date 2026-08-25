from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis_modules import rs422_excel_extractor as extractor


def test_convert_hk_includes_tec_current_and_peltier_temperature() -> None:
    hk = SimpleNamespace(
        EB_TEC_DRIVE_CURRENT=62000,
        EB_PELTIER_TEMP=20000,
    )

    result = extractor.convert_hk(hk, SimpleNamespace())

    assert "TEC Current (A)" in extractor.HEADERS
    assert result["TEC Current (A)"] == pytest.approx(1.0044, rel=1e-6)
    assert result["Peltier Temp(°C)"] == pytest.approx(14.67017922, rel=1e-6)


def test_summary_headers_include_tec_current_and_peltier_temperature() -> None:
    assert "TEC Current (A)" in extractor.HEADERS
    assert "Peltier Temp(°C)" in extractor.HEADERS


def test_group_rows_by_test_matrix_keeps_non_matrix_sft_runs() -> None:
    rows = []
    for sft_number, temp_c in ((1, -40), (30, 0), (32, 10)):
        rows.append(
            (
                Path(f"/tmp/SFT{sft_number}.log"),
                extractor.Summary(
                    values={"Temp (°C)": temp_c, "run": f"SFT{sft_number}", "SFT Date/Time": datetime(2024, 1, 1, 12, 0, 0)},
                    hk_count=1,
                    science_packets=0,
                    first_time=datetime(2024, 1, 1, 12, 0, 0),
                    last_time=datetime(2024, 1, 1, 12, 0, 0),
                    ob_switch_time=None,
                    warnings=[],
                    state_condition_times={},
                ),
                {"run": f"SFT{sft_number}", "SFT Date/Time": datetime(2024, 1, 1, 12, 0, 0)},
            )
        )

    grouped = extractor.group_rows_by_test_matrix(rows)

    assert {extractor._sft_number(row) for row in grouped} == {1, 30, 32}


def test_tec_at_setpoint_row_uses_science_acquisition_assertion() -> None:
    hk_packets = [
        extractor.Packet(
            datetime(2024, 1, 1, 12, 0, 0),
            SimpleNamespace(
                CURRENT_OPERATING_STATE=0x08,
                INSTR_STATUS_FLAGS=SimpleNamespace(TEC_AT_SETPOINT=0),
                EB_TEC_DRIVE_CURRENT=1000,
                EB_PELTIER_TEMP=1000,
            ),
        ),
        extractor.Packet(
            datetime(2024, 1, 1, 12, 0, 1),
            SimpleNamespace(
                CURRENT_OPERATING_STATE=0x08,
                INSTR_STATUS_FLAGS=SimpleNamespace(TEC_AT_SETPOINT=1),
                EB_TEC_DRIVE_CURRENT=62000,
                EB_PELTIER_TEMP=20000,
            ),
        ),
        extractor.Packet(
            datetime(2024, 1, 1, 12, 0, 2),
            SimpleNamespace(
                CURRENT_OPERATING_STATE=0x08,
                INSTR_STATUS_FLAGS=SimpleNamespace(TEC_AT_SETPOINT=1),
                EB_TEC_DRIVE_CURRENT=70000,
                EB_PELTIER_TEMP=25000,
            ),
        ),
    ]
    rows = [extractor.convert_hk(packet.hk, SimpleNamespace()) for packet in hk_packets]

    selected = extractor._tec_at_setpoint_row(hk_packets, rows)

    assert selected is rows[1]
    assert selected["TEC Current (A)"] == pytest.approx(1.0044, rel=1e-6)
    assert selected["Peltier Temp(°C)"] == pytest.approx(14.67017922, rel=1e-6)
