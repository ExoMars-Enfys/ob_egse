"""Single-owner transaction queue for the OB RS-485 port."""

from __future__ import annotations

import threading
from concurrent.futures import Future
from contextlib import nullcontext
from queue import PriorityQueue
from typing import Any, Callable


class OBSerialWorker:
    """Own one OB port and execute complete command/response transactions."""

    def __init__(self, port: Any, port_lock: Any = None) -> None:
        self.port = port
        self.port_lock = port_lock
        self._queue: PriorityQueue[tuple[int, int, Future, Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = (
            PriorityQueue()
        )
        self._sequence = 0
        self._sequence_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ob-serial-worker", daemon=True)
        self._thread.start()

    def submit(self, function: Callable[..., Any], *args: Any, priority: int = 10, **kwargs: Any) -> Future:
        """Queue a transaction and return immediately."""
        future: Future = Future()
        with self._sequence_lock:
            sequence = self._sequence
            self._sequence += 1
        self._queue.put((priority, sequence, future, function, args, kwargs))
        return future

    def call(self, function: Callable[..., Any], *args: Any, priority: int = 10, **kwargs: Any) -> Any:
        """Queue a transaction and wait from a non-GUI caller."""
        return self.submit(function, *args, priority=priority, **kwargs).result()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                _, _, future, function, args, kwargs = self._queue.get(timeout=0.1)
            except Exception:
                continue
            if future.cancelled():
                self._queue.task_done()
                continue
            try:
                lock_ctx = self.port_lock if self.port_lock is not None else nullcontext()
                with lock_ctx:
                    future.set_result(function(self.port, *args, **kwargs))
            except BaseException as exc:
                future.set_exception(exc)
            finally:
                self._queue.task_done()
