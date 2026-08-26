"""Monnify payment gateway client.

Handles authentication (Basic Auth → Bearer token), transaction
initialization, verification, and webhook signature validation.

Docs: https://developers.monnify.com/docs
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# In-process cache for Bearer tokens (valid 1 hour from Monnify).
_token_cache: tuple[float, str] | None = None
_TOKEN_TTL_SECONDS = 3000  # refresh at 50 min, safe margin


def _base_url() -> str:
    settings = get_settings()
    return settings.monnify_base_url


def _auth_headers() -> dict[str, str]:
    """Basic Auth header for token generation."""
    settings = get_settings()
    import base64
    creds = base64.b64encode(f"{settings.monnify_api_key}:{settings.monnify_secret_key}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def _get_access_token() -> str:
    """Get or refresh a Bearer token. Cached in-process."""
    global _token_cache
    now = time.monotonic()
    if _token_cache and now - _token_cache[0] < _TOKEN_TTL_SECONDS:
        return _token_cache[1]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/api/v1/auth/login",
            headers=_auth_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    token = data["responseBody"]["accessToken"]
    _token_cache = (now, token)
    return token


async def initialize_transaction(
    *,
    amount: float,
    email: str,
    name: str,
    payment_reference: str,
    description: str,
    redirect_url: str,
) -> dict:
    """Initialize a Monnify transaction. Returns {checkout_url, transaction_reference}."""
    settings = get_settings()
    token = await _get_access_token()

    payload = {
        "amount": amount,
        "customerEmail": email,
        "customerName": name,
        "paymentReference": payment_reference,
        "paymentDescription": description,
        "currencyCode": "NGN",
        "contractCode": settings.monnify_contract_code,
        "redirectUrl": redirect_url,
        "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/api/v1/merchant/transactions/init-transaction",
            json=payload,
            headers=_bearer_headers(token),
        )
        resp.raise_for_status()
        data = resp.json()

    body = data["responseBody"]
    return {
        "checkout_url": body.get("checkoutUrl", ""),
        "transaction_reference": body.get("transactionReference", ""),
    }


async def verify_transaction(payment_reference: str) -> dict:
    """Verify a Monnify transaction by payment reference.

    Returns dict with at least: payment_status, amount_paid, transaction_reference.
    """
    settings = get_settings()
    token = await _get_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_base_url()}/api/v1/merchant/transactions/verify/{payment_reference}",
            headers=_bearer_headers(token),
        )
        resp.raise_for_status()
        data = resp.json()

    body = data.get("responseBody", {})
    return {
        "payment_status": body.get("paymentStatus", ""),
        "amount_paid": body.get("amountPaid", 0),
        "transaction_reference": body.get("transactionReference", ""),
        "payment_reference": body.get("paymentReference", payment_reference),
    }


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """Validate Monnify webhook signature using HMAC-SHA512.

    Formula: SHA-512(client_secret + request_body_string)
    """
    if not signature:
        return False
    settings = get_settings()
    secret = settings.monnify_secret_key
    if not secret:
        return False

    computed = hashlib.sha512((secret + payload.decode()).encode()).hexdigest()
    return hmac.compare_digest(computed, signature)
