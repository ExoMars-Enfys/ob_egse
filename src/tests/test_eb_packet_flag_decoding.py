import bitstruct
import pytest

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


# ---------------------------------------------------------------------------
# Additional packet parser edge and helper coverage
# ---------------------------------------------------------------------------

def test_parse_eb_hk_all_zero_bitmaps_decode_to_zero() -> None:
    hk = eb_packet_utility.parse_eb_hk(_make_hk_packet())

    assert all(value == 0 for value in vars(hk.WARNING_FLAGS_BITS).values())
    assert all(value == 0 for value in vars(hk.ERROR_FLAGS_BITS).values())
    assert all(value == 0 for value in vars(hk.FDIR_WARNING_FLAGS_BITS).values())
    assert all(value == 0 for value in vars(hk.FDIR_ALARM_FLAGS_BITS).values())
    assert hk.ONGOING_PROCESS_FLAGS_BITS.ANY == 0


@pytest.mark.parametrize("flag_struct_name", ["eb_warning_flags", "eb_fdir_flags"])
def test_parse_eb_hk_decodes_first_and_last_named_bitmap_bits(flag_struct_name: str) -> None:
    flag_struct = getattr(tmstruct, flag_struct_name)
    first_name = flag_struct[0][0]
    last_name = flag_struct[-1][0]
    packed = _pack_flags(flag_struct, {first_name, last_name})

    if flag_struct_name == "eb_warning_flags":
        hk = eb_packet_utility.parse_eb_hk(_make_hk_packet(WARNING_FLAGS=packed))
        decoded = hk.WARNING_FLAGS_BITS
    else:
        hk = eb_packet_utility.parse_eb_hk(_make_hk_packet(FDIR_ALARM_FLAGS=packed))
        decoded = hk.FDIR_ALARM_FLAGS_BITS

    assert getattr(decoded, first_name) == 1
    assert getattr(decoded, last_name) == 1


def test_parse_eb_hk_decodes_ob_and_motor_error_bytes() -> None:
    error_name = next(name for name, _ in tmstruct.error_struct if not name.startswith("UNUSED"))
    motor_name = next(name for name, _ in tmstruct.mtr_error_struct if name != "UNUSED")
    error_raw = _pack_flags(tmstruct.error_struct, {error_name})
    motor_raw = _pack_flags(tmstruct.mtr_error_struct, {motor_name})

    hk = eb_packet_utility.parse_eb_hk(
        _make_hk_packet(OB_LAST_ERROR=error_raw, OB_MOTOR_ERROR=motor_raw)
    )

    assert getattr(hk.ERRORS, error_name) == 1
    assert getattr(hk.MTR_ERRORS, motor_name) == 1


def test_parse_eb_hk_rejects_truncated_packet() -> None:
    packet = _make_hk_packet()

    with pytest.raises(Exception):
        eb_packet_utility.parse_eb_hk(packet[:-1])


def test_read_block_length_handles_short_and_complete_headers() -> None:
    assert eb_packet_utility.read_block_length(b"\x00" * 13) is None

    packet = bytearray(14)
    packet[12:14] = (25).to_bytes(2, "big")
    assert eb_packet_utility.read_block_length(bytes(packet)) == 25


def test_trim_sci_packet_uses_declared_block_length() -> None:
    packet = bytearray(30)
    packet[12:14] = (4).to_bytes(2, "big")

    trimmed = eb_packet_utility.trim_sci_packet_by_block_length(bytes(packet))

    assert len(trimmed) == 18
    assert trimmed == bytes(packet[:18])


def test_trim_sci_packet_preserves_packet_shorter_than_declared_length() -> None:
    packet = bytearray(18)
    packet[12:14] = (20).to_bytes(2, "big")

    assert eb_packet_utility.trim_sci_packet_by_block_length(bytes(packet)) == bytes(packet)
