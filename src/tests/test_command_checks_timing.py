from __future__ import annotations

from types import SimpleNamespace

from utility_modules.background_checks import CommandChecks, _power_transition_transaction


def test_power_waits_for_requested_hk_state_instead_of_failing_first_sample():
    response = SimpleNamespace(PWR_STAT=3)
    submitted = []
    checks = CommandChecks(
        port=object(),
        transaction_runner=lambda function, *args: submitted.append((function, args)) or response,
    )
    checks._validate_hk = lambda value, **_kwargs: value

    result = checks.power(3, label="both boards power on")

    assert result.PWR_STAT == 3
    assert submitted == [(_power_transition_transaction, (3,))]
