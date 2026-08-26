from __future__ import annotations

import time
from concurrent.futures import Future

from utility_modules.cyclic_hk import CyclicHKController


def _wait_until(predicate, timeout=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


def test_cyclic_hk_does_not_queue_a_backlog():
    submitted = []

    def submit():
        future = Future()
        submitted.append(future)
        return future

    controller = CyclicHKController(submit, interval_s=0.1)
    try:
        controller.set_enabled(True)
        assert _wait_until(lambda: len(submitted) == 1)
        time.sleep(0.22)
        assert len(submitted) == 1

        submitted[0].set_result(None)
        assert _wait_until(lambda: len(submitted) == 2)
    finally:
        controller.close()


def test_disabling_cancels_a_queued_request():
    future = Future()
    controller = CyclicHKController(lambda: future, interval_s=0.1)
    try:
        controller.set_enabled(True)
        assert _wait_until(lambda: controller._pending is future)
        controller.set_enabled(False)
        assert future.cancelled()
    finally:
        controller.close()


def test_interval_validation():
    try:
        CyclicHKController(lambda: Future(), interval_s=0.01)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected an interval validation error")
