from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.database import get_db
from app.deps import CurrentUser, check_payment_rate_limit, get_current_user
from app.models import Subscription, User
from app import plans
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

PAYSTACK_BASE = "https://api.paystack.co"


class InitializeRequest(BaseModel):
    email: str
    plan: str = "semester"


class InitializeResponse(BaseModel):
    authorization_url: str
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


def _paystack_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.paystack_secret_key}",
        "Content-Type": "application/json",
    }


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

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            json={
                "email": body.email,
                "amount": plan_config.price_kobo,
                "reference": ref,
                "currency": "NGN",
                "callback_url": f"{settings.frontend_url}/pricing?trxref={ref}",
                "metadata": {
                    "user_id": user.user.id,
                    "plan": plan_config.key,
                },
            },
            headers=_paystack_headers(),
        )

    data = resp.json()
    if not data.get("status"):
        raise HTTPException(status_code=400, detail=data.get("message", "Paystack init failed"))

    return InitializeResponse(
        authorization_url=data["data"]["authorization_url"],
        reference=data["data"]["reference"],
    )


@router.post("/verify", response_model=VerifyResponse)
async def verify_payment(
    reference: str,
    user: CurrentUser = Depends(check_payment_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers=_paystack_headers(),
        )

    data = resp.json()
    if not data.get("status"):
        raise HTTPException(status_code=400, detail="Verification failed")

    txn = data["data"]
    if txn["status"] != "success":
        raise HTTPException(status_code=400, detail=f"Transaction not successful: {txn['status']}")

    if txn["metadata"]["user_id"] != user.user.id:
        raise HTTPException(status_code=403, detail="Reference belongs to another user")

    plan_key = txn["metadata"].get("plan", "semester")
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


def _is_valid_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """HMAC-SHA512 of the raw body signed with the Paystack secret key.

    Fails closed: if the secret is not configured or the header is missing,
    the webhook must be rejected — an unsigned endpoint would let anyone
    forge charge.success events and grant themselves paid plans.
    """
    if not settings.paystack_secret_key or not signature:
        return False
    expected = hmac.new(
        settings.paystack_secret_key.encode(), payload, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def paystack_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()

    if not _is_valid_webhook_signature(raw_body, request.headers.get("x-paystack-signature")):
        from app.services.alerting import alert_critical
        alert_critical(
            "Paystack webhook received with invalid/missing signature",
            source="paystack_webhook",
            extra={"ip": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()
    event = body.get("event")
    logger.info("paystack_webhook event=%s", event)

    if event != "charge.success":
        return {"status": "ignored"}

    data = body.get("data", {})
    reference = data.get("reference")
    metadata = data.get("metadata", {})
    user_id = metadata.get("user_id")
    plan_key = metadata.get("plan", "semester")

    if not reference or not user_id:
        logger.warning("paystack_webhook missing reference or user_id: ref=%s", reference)
        return {"status": "ignored"}

    try:
        sub = await _activate_subscription(db, user_id, reference, plan_key)
    except Exception as exc:
        from app.services.alerting import alert_critical
        alert_critical(
            f"Paystack webhook activation failed: {exc}",
            source="paystack_webhook",
            extra={"reference": reference, "user_id": user_id, "plan": plan_key},
        )
        raise

    if sub.plan != plan_key:
        return {"status": "duplicate"}

    logger.info("paystack_webhook activated plan=%s ref=%s user=%s", plan_key, reference, user_id)
    await db.commit()
    return {"status": "ok"}
