from __future__ import annotations

import threading

from utility_modules.ob_serial_worker import OBSerialWorker


def test_worker_uses_shared_port_lock_for_complete_transaction():
    lock = threading.Lock()
    worker = OBSerialWorker(object(), port_lock=lock)
    observed = []

    def transaction(_port):
        acquired = lock.acquire(blocking=False)
        observed.append(acquired)
        if acquired:
            lock.release()

    try:
        worker.call(transaction)
        assert observed == [False]
    finally:
        worker.close()


def test_running_transaction_cannot_be_cancelled_and_worker_survives():
    started = threading.Event()
    release = threading.Event()
    worker = OBSerialWorker(object())

    def transaction(_port):
        started.set()
        release.wait(timeout=1.0)
        return "done"

    try:
        future = worker.submit(transaction)
        assert started.wait(timeout=0.5)
        assert future.cancel() is False
        release.set()
        assert future.result(timeout=0.5) == "done"
        assert worker.call(lambda _port: "still running") == "still running"
    finally:
        release.set()
        worker.close()
