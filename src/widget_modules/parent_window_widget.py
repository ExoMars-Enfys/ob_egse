from __future__ import annotations

from typing import Any


def stop_and_shutdown(stop_event: Any, app: Any) -> None:
    if stop_event is not None:
        stop_event.set()
    app.shutdown()
