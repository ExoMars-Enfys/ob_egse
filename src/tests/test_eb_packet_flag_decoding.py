from types import SimpleNamespace

import bitstruct

from core_modules import tmstruct
from utility_modules import eb_packet_utility


def _pack_flags(flag_struct: list[tuple[str, str]], active_names: set[str]) -> int:
    names = [name for name, _ in flag_struct]
    fmt = "".join(spec for _, spec in flag_struct)
    raw = bitstruct.pack_dict(fmt, names, {name: 1 if name in active_names else 0 for name in names})
    return int.from_bytes(raw, "big")


def _make_hk_packet(**overrides) -> bytes:
    names = [name for name, _ in tmstruct.eb_hk]
    fmt = "".join(spec for _, spec in tmstruct.eb_hk)
    values = {name: 0 for name in names}
    values.update(overrides)
    return bitstruct.pack_dict(fmt, names, values)


def test_parse_eb_hk_decodes_warning_error_and_fdir_bitmaps() -> None:
    warning_bits = {"GENERAL_ERROR", "OB_GENERAL_ERROR", "RS422_TRANSMIT_ERROR"}
    error_bits = {"GENERAL_ERROR", "EB_FDIR_ALARM"}
    fdir_alarm_bits = {"EB_PLUS_12V_SUPPLY", "DIGITAL_BOARD_TRP"}
    fdir_warning_bits = {"EB_TEC_SUPPLY", "FPGA_CORE_POWER_SUPPLY"}

    packet = _make_hk_packet(
        WARNING_FLAGS=_pack_flags(tmstruct.eb_warning_flags, warning_bits),
        ERROR_FLAGS=_pack_flags(tmstruct.eb_warning_flags, error_bits),
        FDIR_ALARM_FLAGS=_pack_flags(tmstruct.eb_fdir_flags, fdir_alarm_bits),
        FDIR_WARNING_FLAGS=_pack_flags(tmstruct.eb_fdir_flags, fdir_warning_bits),
    )

    hk = eb_packet_utility.parse_eb_hk(packet)

    assert hk.WARNING_FLAGS_BITS.GENERAL_ERROR == 1
    assert hk.WARNING_FLAGS_BITS.OB_GENERAL_ERROR == 1
    assert hk.WARNING_FLAGS_BITS.RS422_TRANSMIT_ERROR == 1
    assert hk.WARNING_FLAGS_BITS.RESERVED == 0

    assert hk.ERROR_FLAGS_BITS.GENERAL_ERROR == 1
    assert hk.ERROR_FLAGS_BITS.EB_FDIR_ALARM == 1
    assert hk.ERROR_FLAGS_BITS.OB_UNRESPONSIVE == 0

    assert hk.FDIR_ALARM_FLAGS_BITS.EB_PLUS_12V_SUPPLY == 1
    assert hk.FDIR_ALARM_FLAGS_BITS.DIGITAL_BOARD_TRP == 1
    assert hk.FDIR_ALARM_FLAGS_BITS.EB_PLUS_5V_SUPPLY == 0

    assert hk.FDIR_WARNING_FLAGS_BITS.EB_TEC_SUPPLY == 1
    assert hk.FDIR_WARNING_FLAGS_BITS.FPGA_CORE_POWER_SUPPLY == 1
    assert hk.FDIR_WARNING_FLAGS_BITS.MECH_BOARD_TRP == 0


def test_parse_eb_hk_decodes_ongoing_process_flags_with_any_bit() -> None:
    packet = _make_hk_packet(ONGOING_PROCESS_FLAGS=0b1001)

    hk = eb_packet_utility.parse_eb_hk(packet)

    assert hk.ONGOING_PROCESS_FLAGS_BITS.BIT_0 == 1
    assert hk.ONGOING_PROCESS_FLAGS_BITS.BIT_3 == 1
    assert hk.ONGOING_PROCESS_FLAGS_BITS.BIT_1 == 0
    assert hk.ONGOING_PROCESS_FLAGS_BITS.ANY == 1


def test_parse_eb_hk_ongoing_process_any_clears_when_zero() -> None:
    packet = _make_hk_packet(ONGOING_PROCESS_FLAGS=0)

    hk = eb_packet_utility.parse_eb_hk(packet)

    assert hk.ONGOING_PROCESS_FLAGS_BITS.ANY == 0
