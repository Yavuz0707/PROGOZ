import json
from collections import defaultdict
from typing import DefaultDict, Set

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._channels: DefaultDict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._channels[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        self._channels[channel].discard(websocket)

    async def broadcast(self, channel: str, message: dict) -> None:
        dead: list[WebSocket] = []
        payload = json.dumps(message, default=str)
        for ws in list(self._channels[channel]):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)


manager = WebSocketManager()

