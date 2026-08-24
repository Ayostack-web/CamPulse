"""Redis pub/sub realtime bridge: pure helpers + failure isolation."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.services import realtime


def test_event_channel_naming():
    assert realtime.event_channel("conversation:abc") == "vylix:events:conversation:abc"
    assert realtime.room_from_channel("vylix:events:user:123") == "user:123"
    assert realtime.room_from_channel("unrelated") is None or realtime.room_from_channel(
        "unrelated"
    ) == "unrelated"
    assert realtime.room_from_channel(None) is None
    assert realtime.room_from_channel("vylix:events:") is None


def test_encode_event_serializes_datetimes():
    ts = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    raw = realtime.encode_event("message:new", {"created_at": ts, "id": "m1"})
    payload = json.loads(raw)
    assert payload["event"] == "message:new"
    assert payload["data"]["id"] == "m1"
    assert "2026-08-22" in payload["data"]["created_at"]


@pytest.mark.asyncio
async def test_publish_swallows_redis_failure(monkeypatch):
    class ExplodingClient:
        async def publish(self, channel, message):
            raise ConnectionError("redis down")

    monkeypatch.setattr(realtime, "_client", ExplodingClient())
    await realtime.publish_event("conversation:x", "typing", {"user_id": "u"})
