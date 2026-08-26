"""Critical failure alerting — thin wrapper around Sentry + structured logging.

Use ``alert_critical()`` for events that need immediate human attention:
webhook signature failures, Celery task deaths, payment activation errors,
database connection losses, etc.

When Sentry is configured, critical alerts are captured as Sentry events
with ``level=error`` and tagged ``alert=critical``.  The structured log
line is always emitted regardless of Sentry state.

Optional: add a Slack/Discord webhook URL to ``settings.alert_webhook_url``
to get push notifications for critical events.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.request import Request, urlopen

import sentry_sdk

from app.core.config import get_settings

logger = logging.getLogger("vylix.alert")


def alert_critical(
    message: str,
    *,
    source: str = "unknown",
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a critical alert to Sentry + logs + optional webhook.

    ``source`` labels where the alert originated (e.g. "monnify_webhook",
    "celery_worker", "db_connection").

    ``extra`` is attached as structured context to both Sentry and the log
    line.
    """
    # Structured log line (always emitted)
    log_payload = {"alert": "critical", "source": source, "message": message}
    if extra:
        log_payload.update(extra)
    logger.error(json.dumps(log_payload))

    # Sentry event
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("alert", "critical")
        scope.set_tag("source", source)
        if extra:
            for k, v in extra.items():
                scope.set_extra(k, v)
        sentry_sdk.capture_message(message, level="error")

    # Optional webhook (Slack, Discord, etc.)
    settings = get_settings()
    webhook_url = getattr(settings, "alert_webhook_url", None)
    if webhook_url:
        _send_webhook(webhook_url, message, source, extra)


def _send_webhook(
    url: str, message: str, source: str, extra: dict[str, Any] | None
) -> None:
    """Best-effort POST to a webhook URL. Never raises."""
    try:
        payload = json.dumps({
            "text": f"*[{source}]* {message}",
            "source": source,
            "extra": extra or {},
        }).encode()
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=5) as resp:
            resp.read()
    except Exception as exc:
        logger.warning("Alert webhook failed: %s", exc)
