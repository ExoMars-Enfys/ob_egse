import threading

from utility_modules import ebtcs


def test_gate_send_sleeps_while_paused(monkeypatch) -> None:
    pause_states = iter([True, False])
    sleep_calls: list[float] = []

    monkeypatch.setattr(ebtcs.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    ebtcs.configure_send_flow_control(should_pause=lambda: next(pause_states, False), poll_s=0.05)

    try:
        assert ebtcs._gate_send() is None
    finally:
        ebtcs.clear_send_flow_control()

    assert sleep_calls == [0.05]


def test_paused_script_does_not_block_manual_safe_or_psu_ret(monkeypatch) -> None:
    paused = threading.Event()
    resume = threading.Event()
    finished = threading.Event()
    commands: list[str] = []

    class Interface:
        def send_command_to_cmdtool(self, command, **_kwargs):
            commands.append(command)
            return True

    interface = Interface()
    monkeypatch.setattr(ebtcs, "_read_latest_hk_and_index", lambda: (None, None))

    def should_pause() -> bool:
        paused.set()
        return not resume.is_set()

    def script() -> None:
        ebtcs.configure_send_flow_control(
            should_pause=should_pause,
            # Bound a wrongly gated manual send instead of hanging this test.
            should_abort=lambda: threading.current_thread() is not thread,
            poll_s=0.01,
        )
        try:
            ebtcs.hk_request(interface, 0)
        finally:
            ebtcs.clear_send_flow_control()
            finished.set()

    thread = threading.Thread(target=script, daemon=True)
    thread.start()
    try:
        assert paused.wait(2.0)
        ebtcs.safe(interface, 0)
        ebtcs.ret(interface, 0, 0, 0, 0, 0, 0)
        assert commands == ["ENFYS_SAFE 0", "ENFYS_RET 0 0 0 0 0 0", "ENFYS_RET 0 0 0 0 0 0"]
        assert not finished.is_set()
    finally:
        resume.set()
        thread.join(timeout=2.0)

    assert finished.is_set()
    assert commands[-1] == "ENFYS_REQUEST_HK 0"


def test_aborted_script_does_not_abort_manual_commands(monkeypatch) -> None:
    commands: list[str] = []

    class Interface:
        def send_command_to_cmdtool(self, command, **_kwargs):
            commands.append(command)
            return True

    interface = Interface()
    monkeypatch.setattr(ebtcs, "_read_latest_hk_and_index", lambda: (None, None))
    ebtcs.configure_send_flow_control(should_abort=lambda: True)
    try:
        assert ebtcs.hk_request(interface, 0) == "ERROR"
        thread = threading.Thread(target=lambda: ebtcs.safe(interface, 0))
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert commands == ["ENFYS_SAFE 0", "ENFYS_RET 0 0 0 0 0 0"]
        assert ebtcs._gate_send() == "ERROR"
    finally:
        ebtcs.clear_send_flow_control()
    assert ebtcs._gate_send() is None


def test_safe_reports_send_failure_and_does_not_send_ret(monkeypatch) -> None:
    commands: list[str] = []

    class Interface:
        def send_command_to_cmdtool(self, command, **_kwargs):
            commands.append(command)
            return False

    monkeypatch.setattr(ebtcs, "_read_latest_hk_and_index", lambda: (None, None))
    assert ebtcs.safe(Interface(), 0) == "ERROR"
    assert commands == ["ENFYS_SAFE 0"]


def test_safe_reports_ret_failure(monkeypatch) -> None:
    class Interface:
        def send_command_to_cmdtool(self, command, **_kwargs):
            return command == "ENFYS_SAFE 0"

    monkeypatch.setattr(ebtcs, "_read_latest_hk_and_index", lambda: (None, None))
    assert ebtcs.safe(Interface(), 0) == "ERROR"
