from datetime import datetime, timedelta

from analysis_modules.plot_all import (
    build_hk_motor_anchors,
    interpolate_mode0_sci_times,
)


def test_mode0_times_interpolate_from_hk_motor_positions():
    start = datetime(2026, 9, 24, 10, 0, 0)
    hk_packets = [
        type("HK", (), {"TIME": start, "OB_MOTOR_ABS_STEPS": 1000})(),
        type("HK", (), {"TIME": start + timedelta(seconds=10), "OB_MOTOR_ABS_STEPS": 1100})(),
    ]
    anchors = build_hk_motor_anchors(hk_packets, "rs422")

    result = interpolate_mode0_sci_times(
        [start + timedelta(seconds=5)],
        [1050],
        [0x00],
        ["rs422"],
        {"rs422": anchors},
    )

    assert result == [start + timedelta(seconds=5)]


def test_mode0_interpolation_handles_reverse_motor_motion():
    start = datetime(2026, 9, 24, 10, 0, 0)
    anchors = [
        (start, 1100.0),
        (start + timedelta(seconds=10), 1000.0),
    ]

    result = interpolate_mode0_sci_times(
        [start + timedelta(seconds=5)],
        [1050],
        [0x00],
        ["rs422"],
        {"rs422": anchors},
    )

    assert result == [start + timedelta(seconds=5)]


def test_mode1_time_is_not_replaced_by_hk_interpolation():
    start = datetime(2026, 9, 24, 10, 0, 0)
    original = start + timedelta(seconds=2)
    anchors = [
        (start, 1000.0),
        (start + timedelta(seconds=10), 1100.0),
    ]

    result = interpolate_mode0_sci_times([original], [1020], [0x01], ["rs422"], {"rs422": anchors})

    assert result == [original]


def test_mode0_packet_ends_at_its_sat_timestamp():
    start = datetime(2026, 9, 24, 10, 0, 0)
    anchors = [
        (start, 1000.0),
        (start + timedelta(seconds=10), 1100.0),
    ]

    result = interpolate_mode0_sci_times(
        [start, start, start],
        [1000, 1050, 1100],
        [0x00, 0x00, 0x00],
        ["rs422", "rs422", "rs422"],
        {"rs422": anchors},
        [(0, 2, 1, start + timedelta(seconds=10), 0x00, "rs422")],
    )

    assert result == [start, start + timedelta(seconds=5), start + timedelta(seconds=10)]
