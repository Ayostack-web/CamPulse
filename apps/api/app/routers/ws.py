import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.websocket import manager
from app.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

AUTH_FAILED_CODE = 4001
HEARTBEAT_TIMEOUT_CODE = 4002

# Server pings clients so half-open TCP sockets (dropped connections that
# never sent a close frame) are detected and reaped instead of accumulating.
HEARTBEAT_INTERVAL_SECONDS = 25.0
HEARTBEAT_TIMEOUT_SECONDS = 60.0


async def _verify_ws_token(token: str | None) -> str | None:
    """Verify JWT and return user_id, or None if invalid."""
    if not token:
        return None
    try:
        payload = await decode_access_token(token)
        return payload.get("sub")
    except Exception:
        return None


async def _heartbeat_loop(websocket: WebSocket) -> None:
    """Ping the client periodically; close if it goes quiet."""
    last_seen = time.monotonic()
    websocket.state.last_seen = last_seen

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        now = time.monotonic()
        if now - getattr(websocket.state, "last_seen", now) > HEARTBEAT_TIMEOUT_SECONDS:
            logger.info("WebSocket heartbeat timeout, closing")
            try:
                await websocket.close(code=HEARTBEAT_TIMEOUT_CODE, reason="Heartbeat timeout")
            except Exception:
                pass
            return
        try:
            await websocket.send_json({"event": "pulse:ping", "ts": now})
        except Exception:
            return


@router.websocket("/pulse")
async def pulse_websocket(
    websocket: WebSocket,
    department_code: str | None = Query(default=None),
    department_id: str | None = Query(default=None),
    token: str | None = Query(default=None),
):
    verified_user_id = await _verify_ws_token(token)
    if not verified_user_id:
        logger.warning("WebSocket auth failed: invalid or missing token")
        await websocket.close(code=AUTH_FAILED_CODE, reason="Authentication required")
        return

    rooms = set()

    def _join(room: str):
        rooms.add(room)

    if department_code:
        _join(f"department:{department_code}")
    elif department_id:
        _join(f"department:{department_id}")

    user_room = f"user:{verified_user_id}"
    _join(user_room)

    for room in rooms:
        await manager.connect(websocket, room, verified_user_id)

    # Runs alongside receive(); sending from a second task is safe because
    # Starlette/uvicorn keep send and receive queues independent.
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))

    try:
        while True:
            data = await websocket.receive_json()
            websocket.state.last_seen = time.monotonic()
            event = data.get("event", "")

            if event == "pulse:ping":
                # Client-initiated liveness check.
                try:
                    await websocket.send_json({"event": "pulse:pong"})
                except Exception:
                    break

            elif event in ("pulse:join", "pulse:join-room"):
                room_type = data.get("roomType", "department")
                room_key = data.get("roomKey", "")
                room = f"{room_type}:{room_key}"
                await manager.connect(websocket, room, verified_user_id)
                _join(room)

            elif event == "pulse:leave-room":
                room_type = data.get("roomType", "department")
                room_key = data.get("roomKey", "")
                room = f"{room_type}:{room_key}"
                manager.disconnect(websocket, room, verified_user_id)
                rooms.discard(room)

    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass
        for room in rooms:
            manager.disconnect(websocket, room, verified_user_id)
