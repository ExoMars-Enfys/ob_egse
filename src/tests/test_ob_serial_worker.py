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
