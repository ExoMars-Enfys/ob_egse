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
