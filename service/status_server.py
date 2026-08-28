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
    """
    Broadcasts StatusState snapshots to all connected WebSocket clients, and
    optionally dispatches inbound client commands (settings get/set/reset)
    to a command_handler.

    command_handler, if given, must expose:
      on_connect() -> dict | None      called once when a client connects;
                                        the returned message (if any) is sent
                                        to that client only.
      handle(msg: dict) -> dict | None called for each inbound JSON frame;
                                        the returned message (if any) is
                                        broadcast to ALL connected clients.
    """

    def __init__(self, status_state, port: int | None = None, command_handler=None):
        self.status_state = status_state
        self.port = port or int(os.environ.get("PRO2INPUT_STATUS_PORT", DEFAULT_PORT))
        self.command_handler = command_handler
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
            if self.command_handler is not None:
                greeting = self.command_handler.on_connect()
                if greeting is not None:
                    await websocket.send(json.dumps(greeting))
            async for raw in websocket:
                if self.command_handler is None:
                    continue
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                try:
                    response = self.command_handler.handle(msg)
                except Exception as exc:
                    print(f"[StatusServer] command handler error: {exc}")
                    continue
                if response is not None and self._clients:
                    websockets.broadcast(self._clients, json.dumps(response))
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
