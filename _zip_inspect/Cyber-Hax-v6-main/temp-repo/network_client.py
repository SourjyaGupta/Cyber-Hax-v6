import asyncio
import json
import threading

import websockets


class NetworkClient:
    def __init__(self, term, session_id, player_name, server_base, state_callback=None, autostart=True):
        self.term = term
        self.session_id = session_id
        self.player_name = player_name
        self.server_base = server_base.rstrip("/")
        self.state_callback = state_callback
        self.url = f"{self.server_base}/ws/{self.session_id}"
        self.ws = None
        self.connected = False
        self._closed = False
        self.loop = None
        self.thread = None
        self.status = "idle"
        self.last_error = ""
        if autostart:
            self.start()

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return
        self._closed = False
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._start_loop, daemon=True)
        self.thread.start()
        asyncio.run_coroutine_threadsafe(self.listen_forever(), self.loop)

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def listen_forever(self):
        while not self._closed:
            try:
                self.status = "connecting"
                async with websockets.connect(self.url) as ws:
                    self.ws = ws
                    self.connected = True
                    self.status = "connected"
                    self.last_error = ""
                    await ws.send(
                        json.dumps({"type": "join", "player_name": self.player_name})
                    )
                    async for raw_message in ws:
                        data = json.loads(raw_message)
                        message_type = data.get("type")
                        if message_type == "welcome":
                            self.player_name = data.get("player_name", self.player_name)
                        elif message_type == "log":
                            for line in data.get("lines", []):
                                self.term.add(line)
                        elif message_type == "state":
                            if self.state_callback is not None:
                                self.state_callback(
                                    data.get("state", {}),
                                    data.get("player_name", self.player_name),
                                )
                        elif message_type == "error":
                            self.term.add(f"[Network] {data.get('message', 'Unknown error')}")
            except Exception as exc:
                self.last_error = str(exc)
                self.status = "disconnected"
                if not self._closed:
                    self.term.add(f"[Network] Disconnected: {exc}")
            finally:
                self.connected = False
                self.ws = None

            if not self._closed:
                self.status = "reconnecting"
                await asyncio.sleep(3)
        self.status = "closed"

    def send_command(self, line):
        if not self.connected or self.ws is None:
            self.term.add("[Network] Not connected.")
            return
        asyncio.run_coroutine_threadsafe(
            self.ws.send(json.dumps({"type": "command", "command": line})),
            self.loop,
        )

    def close(self):
        self._closed = True
        self.connected = False
        self.status = "closed"
        if self.loop is None:
            return
        if self.ws is not None:
            try:
                asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
            except RuntimeError:
                pass
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
