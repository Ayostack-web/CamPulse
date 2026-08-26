"""Paywall funnel event recording.

Tracks the full conversion funnel: paywall shown -> plan clicked ->
checkout started -> completed/failed. Best-effort by design: a failed
insert must never fail the request it is measuring.

Event types:
    paywall_shown      – modal opened
    paywall_dismissed  – "Maybe Later" clicked
    plan_clicked       – "Get Plan" button clicked
    checkout_started   – payment init succeeded, redirecting to provider
    checkout_completed – payment verified successfully
    checkout_failed    – payment verification failed
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def record_paywall_event(
    *,
    user_id: str | None = None,
    event_type: str,
    plan_key: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert one paywall_events row. Never raises."""
    try:
        from app.core.postgres import get_connection

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO paywall_events (
                        id, user_id, event_type, plan_key, metadata, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        event_type,
                        plan_key,
                        json.dumps(metadata) if metadata else None,
                        datetime.now(timezone.utc),
                    ),
                )
            conn.commit()
    except Exception:
        logger.warning("paywall_events insert failed", exc_info=True)
