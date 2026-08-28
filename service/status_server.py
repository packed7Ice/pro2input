"""
service/status_server.py

WebSocket status broadcaster. Runs its own asyncio event loop inside a
dedicated daemon thread, fully decoupled from the polling loop thread — it
only ever reads a StatusState snapshot on its own timer. A slow/absent client
or a network hiccup here can never block the polling loop.
"""

import asyncio
import json
import os
import threading
import time

import websockets

DEFAULT_PORT = 8765
BROADCAST_INTERVAL_SEC = 0.05


class StatusServer:
    """Broadcasts StatusState snapshots to all connected WebSocket clients."""

    def __init__(self, status_state, port: int | None = None):
        self.status_state = status_state
        self.port = port or int(os.environ.get("PRO2INPUT_STATUS_PORT", DEFAULT_PORT))
        self._clients: set = set()

    def start(self):
        thread = threading.Thread(target=self._run, daemon=True, name="StatusServer")
        thread.start()

    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        async with websockets.serve(self._handle_client, "127.0.0.1", self.port):
            await self._broadcast_loop()

    async def _handle_client(self, websocket, *_args):
        # *_args absorbs the legacy `path` positional arg on older websockets versions.
        self._clients.add(websocket)
        try:
            async for _ in websocket:
                pass  # no inbound commands in this slice; ignore anything received
        finally:
            self._clients.discard(websocket)

    async def _broadcast_loop(self):
        while True:
            await asyncio.sleep(BROADCAST_INTERVAL_SEC)
            if not self._clients:
                continue
            snapshot = self.status_state.get_snapshot()
            snapshot["type"] = "status"
            snapshot["ts"] = time.time()
            websockets.broadcast(self._clients, json.dumps(snapshot))
