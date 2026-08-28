"""
service/status_state.py

Thread-safe snapshot dict shared between the polling loop thread and the
status WebSocket server's asyncio thread. The loop thread only ever performs
a cheap dict.update() under a short-held lock; it never blocks on I/O here.
"""

import threading


class StatusState:
    """Holds the latest status snapshot for broadcast to UI clients."""

    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot: dict = {}

    def update(self, **fields):
        with self._lock:
            self._snapshot.update(fields)

    def get_snapshot(self) -> dict:
        with self._lock:
            return dict(self._snapshot)
