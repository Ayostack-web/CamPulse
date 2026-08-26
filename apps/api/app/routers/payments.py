from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.database import get_db
from app.deps import CurrentUser, check_payment_rate_limit, get_current_user
from app.models import Subscription, User
from app import plans
from app.services.paywall_log import record_paywall_event
from app.services.monnify import (
    initialize_transaction,
    verify_transaction,
    verify_webhook_signature,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


class InitializeRequest(BaseModel):
    email: str
    plan: str = "semester"


class InitializeResponse(BaseModel):
    checkout_url: str
    reference: str


class VerifyResponse(BaseModel):
    status: str
    plan: str
    expires_at: str | None
    quota_remaining: int | None


def _validate_plan(plan: str) -> plans.Plan:
    try:
        p = plans.get_plan(plan)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}")
    if p.price_kobo <= 0:
        raise HTTPException(status_code=400, detail=f"Plan is not purchasable: {plan}")
    return p


async def _activate_subscription(
    db: AsyncSession,
    user_id: str,
    reference: str,
    plan: str,
) -> Subscription:
    """Create (or return existing) an active entitlement row for a payment.

    Idempotent by reference so the webhook and the verify redirect can both
    race to activate the same payment without creating duplicates.
    """
    result = await db.execute(
        select(Subscription).where(Subscription.reference == reference)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    plan_config = plans.get_plan(plan) if plan in plans.PLANS else plans.get_plan("semester")
    expires_at = datetime.now(timezone.utc) + timedelta(days=plan_config.duration_days or 0)

    sub = Subscription(
        user_id=user_id,
        reference=reference,
        plan=plan,
        status="active",
        expires_at=expires_at,
        quota_total=plan_config.query_quota,
        quota_used=0,
        storage_bytes_total=plan_config.storage_bytes,
        storage_bytes_used=0,
    )
    db.add(sub)
    await db.flush()
    return sub


@router.post("/initialize", response_model=InitializeResponse)
async def initialize_payment(
    body: InitializeRequest,
    user: CurrentUser = Depends(get_current_user),
):
    plan_config = _validate_plan(body.plan)
    ref = f"VYLIX-{plan_config.key.upper()}-{user.user.id}-{int(datetime.now(timezone.utc).timestamp())}"

    result = await initialize_transaction(
        amount=plan_config.price_kobo / 100,
        email=body.email,
        name=user.user.name or user.user.email,
        payment_reference=ref,
        description=f"Vylix {plan_config.name}",
        redirect_url=f"{settings.frontend_url}/pricing?trxref={ref}",
    )

    if not result.get("checkout_url"):
        raise HTTPException(status_code=400, detail="Monnify init failed")

    return InitializeResponse(
        checkout_url=result["checkout_url"],
        reference=ref,
    )


@router.post("/verify", response_model=VerifyResponse)
async def verify_payment(
    reference: str,
    user: CurrentUser = Depends(check_payment_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    txn = await verify_transaction(reference)
    status = txn.get("payment_status", "").upper()

    if status != "PAID":
        raise HTTPException(status_code=400, detail=f"Transaction not successful: {status}")

    # Monnify doesn't return metadata on verify — we need to look up the plan
    # from the subscription we created at init time (or from the reference itself).
    ref_parts = reference.split("-")
    plan_key = ref_parts[1].lower() if len(ref_parts) >= 2 else "semester"

    sub = await _activate_subscription(db, user.user.id, reference, plan_key)
    await db.commit()

    plan_config = plans.get_plan(sub.plan)
    remaining = None
    if sub.quota_total is not None:
        remaining = max(0, sub.quota_total - sub.quota_used)

    return VerifyResponse(
        status=sub.status,
        plan=sub.plan,
        expires_at=str(sub.expires_at) if sub.expires_at else None,
        quota_remaining=remaining,
    )


@router.post("/webhook")
async def monnify_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("monnify-signature")

    if not verify_webhook_signature(raw_body, signature):
        from app.services.alerting import alert_critical
        alert_critical(
            "Monnify webhook received with invalid/missing signature",
            source="monnify_webhook",
            extra={"ip": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()
    event = body.get("eventType")
    logger.info("monnify_webhook event=%s", event)

    if event != "SUCCESSFUL_TRANSACTION":
        return {"status": "ignored"}

    data = body.get("eventData", {})
    reference = data.get("paymentReference")
    transaction_reference = data.get("transactionReference")
    payment_status = data.get("paymentStatus", "").upper()

    if not reference:
        logger.warning("monnify_webhook missing paymentReference")
        return {"status": "ignored"}

    if payment_status != "PAID":
        logger.info("monnify_webhook ignoring non-PAID status=%s", payment_status)
        return {"status": "ignored"}

    # Look up existing subscription to get plan + user_id.
    result = await db.execute(
        select(Subscription).where(Subscription.reference == reference)
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.info("monnify_webhook already activated ref=%s", reference)
        return {"status": "duplicate"}

    # No subscription found — this could be a late webhook.
    # Parse the reference to recover plan + user_id.
    ref_parts = reference.split("-")
    if len(ref_parts) < 3:
        logger.warning("monnify_webhook unparseable reference: %s", reference)
        return {"status": "ignored"}

    plan_key = ref_parts[1].lower()
    user_id = ref_parts[2]

    try:
        sub = await _activate_subscription(db, user_id, reference, plan_key)
    except Exception as exc:
        from app.services.alerting import alert_critical
        alert_critical(
            f"Monnify webhook activation failed: {exc}",
            source="monnify_webhook",
            extra={
                "reference": reference,
                "transaction_reference": transaction_reference,
                "user_id": user_id,
                "plan": plan_key,
            },
        )
        raise

    logger.info("monnify_webhook activated plan=%s ref=%s user=%s", plan_key, reference, user_id)
    await db.commit()
    return {"status": "ok"}


# ── Paywall funnel events ──────────────────────────────────────────


class PaywallEventRequest(BaseModel):
    event_type: str
    plan_key: str | None = None
    metadata: dict | None = None


@router.post("/paywall/events")
async def paywall_event(
    body: PaywallEventRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Best-effort paywall funnel tracking. Never fails the client."""
    record_paywall_event(
        user_id=user.user.id,
        event_type=body.event_type,
        plan_key=body.plan_key,
        metadata=body.metadata,
    )
    return {"ok": True}
