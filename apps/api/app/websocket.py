from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room: str, user_id: str | None = None):
        # A socket may join many rooms over its lifetime; only the first
        # connect performs the accept handshake.
        if websocket.application_state != WebSocketState.CONNECTED:
            await websocket.accept()
        if room not in self.active_connections:
            self.active_connections[room] = []
        self.active_connections[room].append(websocket)

        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room: str, user_id: str | None = None):
        if room in self.active_connections:
            self.active_connections[room] = [
                c for c in self.active_connections[room] if c != websocket
            ]
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id] = [
                c for c in self.user_connections[user_id] if c != websocket
            ]

    async def send_to_room(self, room: str, event: str, data: dict[str, Any]):
        if room in self.active_connections:
            message = json.dumps({"event": event, **data})
            dead = []
            for conn in self.active_connections[room]:
                try:
                    await conn.send_text(message)
                except Exception:
                    dead.append(conn)
            for d in dead:
                self.active_connections[room].remove(d)

    async def send_to_user(self, user_id: str, event: str, data: dict[str, Any]):
        if user_id in self.user_connections:
            message = json.dumps({"event": event, **data})
            dead = []
            for conn in self.user_connections[user_id]:
                try:
                    await conn.send_text(message)
                except Exception:
                    dead.append(conn)
            for d in dead:
                self.user_connections[user_id].remove(d)

    async def broadcast(self, event: str, data: dict[str, Any]):
        message = json.dumps({"event": event, **data})
        for room_conns in self.active_connections.values():
            for conn in room_conns:
                try:
                    await conn.send_text(message)
                except Exception:
                    pass


manager = ConnectionManager()
