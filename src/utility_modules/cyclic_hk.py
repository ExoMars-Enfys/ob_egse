"""Independent, non-overlapping scheduler for cyclic OB housekeeping requests."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future
from typing import Callable


class CyclicHKController:
    """Schedule HK transactions without ever writing to the OB port directly.

    ``submit_hk`` must enqueue a complete HK command/response transaction on
    the shared OB serial worker.  Only one cyclic transaction may be queued or
    running at a time, preventing a slow link from creating an HK backlog.
    """

    def __init__(
        self,
        submit_hk: Callable[[], Future],
        *,
        interval_s: float = 1.0,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._submit_hk = submit_hk
        self._interval_s = self._validate_interval(interval_s)
        self._logger = logger or logging.getLogger("info_log")
        self._clock = clock
        self._condition = threading.Condition()
        self._enabled = False
        self._closed = False
        self._next_due: float | None = None
        self._pending: Future | None = None
        self._thread = threading.Thread(target=self._run, name="cyclic-ob-hk", daemon=True)
        self._thread.start()

    @staticmethod
    def _validate_interval(value: float) -> float:
        interval = float(value)
        if interval < 0.1:
            raise ValueError("Cyclic HK interval must be at least 0.1 seconds")
        return interval

    @property
    def enabled(self) -> bool:
        with self._condition:
            return self._enabled

    @property
    def interval_s(self) -> float:
        with self._condition:
            return self._interval_s

    def set_enabled(self, enabled: bool) -> None:
        with self._condition:
            self._enabled = bool(enabled)
            self._next_due = self._clock() if self._enabled else None
            if not self._enabled and self._pending is not None:
                self._pending.cancel()
            self._condition.notify_all()

    def set_interval(self, interval_s: float) -> None:
        interval = self._validate_interval(interval_s)
        with self._condition:
            self._interval_s = interval
            if self._enabled:
                self._next_due = self._clock() + interval
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._enabled = False
            if self._pending is not None:
                self._pending.cancel()
            self._condition.notify_all()
        self._thread.join(timeout=2.0)

    def _clear_pending(self, future: Future) -> None:
        try:
            exception = future.exception()
        except BaseException:
            exception = None
        if exception is not None:
            self._logger.error("Cyclic HK request failed: %s", exception)
        with self._condition:
            if self._pending is future:
                self._pending = None
            self._condition.notify_all()

    def _run(self) -> None:
        while True:
            with self._condition:
                if self._closed:
                    return
                if not self._enabled:
                    self._condition.wait()
                    continue

                now = self._clock()
                due = self._next_due if self._next_due is not None else now
                if now < due:
                    self._condition.wait(timeout=due - now)
                    continue

                # Advance from the scheduled deadline, not completion time, so
                # normal execution overhead never accumulates cadence drift.
                missed = int(max(0.0, now - due) // self._interval_s)
                self._next_due = due + (missed + 1) * self._interval_s

                if self._pending is not None and not self._pending.done():
                    continue

                try:
                    future = self._submit_hk()
                except BaseException as exc:
                    self._logger.error("Unable to queue cyclic HK request: %s", exc)
                    continue
                self._pending = future
                future.add_done_callback(self._clear_pending)
