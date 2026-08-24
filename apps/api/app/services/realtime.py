"""Redis pub/sub bridge for real-time events.

Chat and other live features publish events to Redis channels named after
WebSocket rooms (``conversation:{id}``, ``user:{id}``, ``department:{code}``).
Every API instance runs one subscriber task that forwards those events into
its local ConnectionManager, so fan-out works across replicas.

Delivery is fire-and-forget by design: Postgres remains the source of truth
and clients reconcile missed events from history on reconnect.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

EVENT_CHANNEL_PREFIX = "vylix:events:"

_client: Any | None = None


def event_channel(room: str) -> str:
    return f"{EVENT_CHANNEL_PREFIX}{room}"


def encode_event(event: str, data: dict[str, Any]) -> str:
    return json.dumps({"event": event, "data": data}, default=str)


def room_from_channel(channel: str | None) -> str | None:
    if not channel:
        return None
    room = channel.removeprefix(EVENT_CHANNEL_PREFIX)
    return room or None


def _get_client() -> Any:
    global _client
    if _client is None:
        import redis.asyncio as aioredis

        _client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


async def publish_event(room: str, event: str, data: dict[str, Any]) -> None:
    """Best-effort publish; a down Redis must never fail the request."""
    try:
        await _get_client().publish(event_channel(room), encode_event(event, data))
    except Exception:
        logger.warning("realtime publish failed for room %s (%s)", room, event, exc_info=True)


async def start_subscriber() -> None:
    """Forward every published event into this process's WebSocket rooms.

    Runs forever with reconnect/backoff so the API also works when Redis
    is briefly unavailable.
    """
    import redis.asyncio as aioredis

    from app.websocket import manager

    while True:
        pubsub = None
        try:
            client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.psubscribe(f"{EVENT_CHANNEL_PREFIX}*")
            logger.info("Realtime subscriber connected")
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                room = room_from_channel(message.get("channel"))
                if not room:
                    continue
                try:
                    payload = json.loads(message["data"])
                    await manager.send_to_room(
                        room, payload.get("event", ""), payload.get("data", {})
                    )
                except Exception:
                    logger.warning("Failed to dispatch realtime event", exc_info=True)
        except asyncio.CancelledError:
            if pubsub is not None:
                try:
                    await pubsub.aclose()
                except Exception:
                    pass
            raise
        except Exception:
            logger.warning("Realtime subscriber disconnected; retrying in 3s", exc_info=True)
            await asyncio.sleep(3)
