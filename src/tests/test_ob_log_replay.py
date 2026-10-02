import io
import sys
from datetime import datetime

import bitstruct
import pytest

from core_modules import constants as const, tmstruct
from utility_modules import tc
from utility_modules.background_checks import check_science
from utility_modules.crc8_function import crc8Calculate
from utility_modules.ob_log_replay import OBLogReplay, ReplayError
from utility_modules.psu_log_utility import load_psu_channel_samples


def _packet(structure, **overrides):
    fields = {name: 0 for name, _ in structure}
    fields.update(overrides)
    raw = bitstruct.pack_dict("".join(fmt for _, fmt in structure), [name for name, _ in structure], fields)
    return crc8Calculate(raw[:-1].hex())


@pytest.fixture
def recording(tmp_path):
    def line(second, raw, name=""):
        return f"2026-10-02 11:00:{second:06.3f}{name} - {raw.hex(' ')}\n"

    power = crc8Calculate("04010000000000")
    offset = crc8Calculate("0e0fff0fff0000")
    science = crc8Calculate("0f041400000000")
    hk = _packet(tmstruct.hk, MOD_ID=5)
    hk_on = _packet(tmstruct.hk, MOD_ID=5, PWR_STAT=1)
    sci = _packet(
        tmstruct.sci, MOD_ID=5, CMD_ID=15, SWIR_OFFSET=4095, MWIR_OFFSET=4095,
        SWIR_TEMP=4856, HT_SINK_TEMP=4826, SCI_ADC_SAMPLES=4, SCI_ADC_SKIP=20,
    )
    (tmp_path / "run_CMD.LOG").write_text(
        line(0, bytes(8), "HK") + line(2, power, "PWR_CTRL") + line(3, bytes(8), "HK")
        + line(4, offset, "SCI_OFFSET") + line(5, science, "SCI_REQUEST"),
        encoding="utf-8",
    )
    (tmp_path / "run_HK.LOG").write_text(line(0.1, hk) + line(3.1, hk_on), encoding="utf-8")
    (tmp_path / "run_ACK.LOG").write_text(
        line(2.1, bytes.fromhex("a40001000000000000"))
        + line(4.1, bytes.fromhex("ae000fff0fff000000")),
        encoding="utf-8",
    )
    (tmp_path / "run_SCI.LOG").write_text(line(5.1, sci), encoding="utf-8")
    (tmp_path / "run_PSU.log").write_text(
        "2026-10-02 11:00:00,000 - 0.0 0.0 0.0 0.0 0.0 0.0\n"
        "2026-10-02 11:00:02,100 - 12.0 0.017 -12.0 0.0 5.0 0.06\n",
        encoding="utf-8",
    )
    return tmp_path, power, offset, science, hk, hk_on


def test_commands_are_strict_and_mismatch_does_not_advance(recording):
    path, power, *_ = recording
    replay = OBLogReplay(path, clock=lambda: 0)
    with pytest.raises(ReplayError, match="Command mismatch"):
        replay.ob_port.write(bytes.fromhex("0402000000000000"))
    assert replay.progress.startswith("0/3")
    replay.ob_port.write(power)
    assert replay.ob_port.read(4) + replay.ob_port.read(5) == bytes.fromhex("a40001000000000000")
    assert replay.progress.startswith("1/3")


def test_housekeeping_polling_uses_timeline_without_consuming_commands(recording):
    path, power, _, _, hk, hk_on = recording
    clock = [0.0]
    replay = OBLogReplay(path, clock=lambda: clock[0])
    assert replay.transact(bytes(8)) == hk
    assert replay.transact(bytes(8)) == hk
    replay.transact(power)
    clock[0] = 1.0
    assert replay.transact(bytes(8)) == hk_on
    assert replay.progress.startswith("1/3")


def test_real_science_parser_and_temperature_deferral_work_with_replay(recording, monkeypatch):
    path, power, offset, _, _, _ = recording
    replay = OBLogReplay(path, clock=lambda: 0)
    replay.transact(power)
    replay.transact(offset)
    monkeypatch.setattr(const, "CMD_LOG_FH", io.StringIO())
    monkeypatch.setattr(const, "SCI_LOG_FH", io.StringIO())
    monkeypatch.setattr(tc.time, "sleep", lambda _: None)
    response = tc.sci_request(replay.ob_port, 4, 20)
    assert check_science(response, check_temperatures=False) is response
    assert response.SWIR_OFFSET == response.MWIR_OFFSET == 4095
    with pytest.raises(AssertionError, match="SWIR_TEMP"):
        check_science(response)
    with pytest.raises(ReplayError, match="Recording ended"):
        replay.transact(offset)


def test_missing_response_is_explicit(recording):
    path, power, *_ = recording
    (path / "run_ACK.LOG").write_text("", encoding="utf-8")
    replay = OBLogReplay(path, clock=lambda: 0)
    with pytest.raises(ReplayError, match="No response recorded"):
        replay.transact(power)
    assert replay.progress.startswith("0/3")


def test_restart_resets_cursor_and_failed_load_preserves_recording(recording):
    path, power, *_ = recording
    replay = OBLogReplay(path, clock=lambda: 0)
    replay.transact(power)
    with pytest.raises(ReplayError, match="Select an OB run folder"):
        replay.load(path / "run_HK.LOG")
    assert replay.progress.startswith("1/3")
    replay.load(path)
    assert replay.progress.startswith("0/3")
    assert replay.last_error is None


def test_legacy_psu_samples_do_not_fabricate_channel_four(recording):
    path, power, *_ = recording
    samples = load_psu_channel_samples(path / "run_PSU.log")
    assert len(samples) == 2
    assert samples[1]["CHANNELS"]["CH1"] == {"V": 12.0, "I": 0.017}
    assert samples[1]["CHANNELS"]["CH4"] == {"V": None, "I": None}
    replay = OBLogReplay(path, clock=lambda: 0)
    replay.transact(power)
    replay.psu_port.write(b"OPALL 1\n")
    replay.psu_port.write(b"OP1?\n")
    assert replay.psu_port.readline() == b"1\n"
    replay.psu_port.write(b"I1O?\n")
    assert float(replay.psu_port.readline()) == 0.017
    with pytest.raises(ReplayError, match="No CH4"):
        replay.psu_port.write(b"I4O?\n")


def test_publish_psu_uses_normal_gui_queue_and_cache(recording, monkeypatch):
    from queue import Queue
    from utility_modules import eb_packet_utility

    path, power, *_ = recording
    replay = OBLogReplay(path, clock=lambda: 0)
    replay.transact(power)
    replay.psu_port.write(b"OPALL 1\n")
    queue = Queue()
    cache = []
    monkeypatch.setattr(const, "psu_queue", queue)
    monkeypatch.setattr(eb_packet_utility, "set_latest_psu", cache.append)
    replay.publish_psu()
    sample = queue.get_nowait()
    assert sample == cache[0]
    assert sample["CH1_I"] == 0.017
    assert sample["CH4_I"] is None
    assert sample["CH1_STATUS"] == 1
    assert isinstance(sample["TIME"], datetime)


def test_replay_startup_never_initializes_physical_ports(recording, monkeypatch):
    import main

    path, *_ = recording
    monkeypatch.setattr(sys, "argv", [
        "main.py", "--ob-replay", str(path),
    ])
    monkeypatch.setattr(main, "setup_logs", lambda: (main.logging.getLogger("test"),) * 3)
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    monkeypatch.setattr(main.atexit, "register", lambda *_args: None)
    monkeypatch.setattr(main.app, "on_shutdown", lambda *_args: None)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Physical serial initialization attempted during replay")

    monkeypatch.setattr(main.comms, "initialise_comms", forbidden)
    monkeypatch.setattr(main.psu, "init_psu_comms", forbidden)
    state = {}
    monkeypatch.setattr(main.parent_window_widget, "build_ui", lambda **kwargs: state.update(kwargs))

    def stop_gui(_reload):
        state["stop_event"].set()
        state["ob_worker"].close()

    main.main(gui_runner=stop_gui)
    assert state["default_mode"] == "OB"
    assert state["ob_port"].port == "OFFLINE-OB-REPLAY"
    assert state["psu_port"].port == "OFFLINE-PSU-REPLAY"
