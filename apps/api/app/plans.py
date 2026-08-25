"""Vylix pricing tiers — single source of truth.

Every tier (including the AI Top-Up) is defined here so the quota resolver,
storage enforcement, payment activation and the public /plans endpoint all
agree on the same numbers.

Prices are in kobo (Paystack works in the minor unit of NGN).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

MB = 1024 * 1024

# Free tier daily AI query allowance.
FREE_DAILY_LIMIT = 5
# Generous first-day allowance so new users see value before the wall tightens.
FIRST_DAY_BOOST_LIMIT = 10
FIRST_DAY_BOOST_DURATION = timedelta(hours=24)

# Free storage vault allowance (applies to every user, paid or not).
FREE_STORAGE_BYTES = 25 * MB


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_kobo: int
    duration_days: int | None
    query_quota: int | None  # None = no AI query entitlement (free tier uses the daily counter)
    storage_bytes: int  # additional vault allowance granted on top of the free base
    tagline: str
    featured: bool = False

    @property
    def price_ngn(self) -> int:
        return self.price_kobo // 100


PLANS: dict[str, Plan] = {
    "free": Plan(
        key="free",
        name="Campus Psychology Free",
        price_kobo=0,
        duration_days=None,
        query_quota=None,
        storage_bytes=0,
        tagline="Gets you hooked on the AI Study Agent.",
    ),
    "night": Plan(
        key="night",
        name="Night Class Pass",
        price_kobo=30000,  # ₦300
        duration_days=3,
        query_quota=150,
        storage_bytes=50 * MB,
        tagline="The impulse buy — cheaper than a bottle of Coke.",
    ),
    "weekly": Plan(
        key="weekly",
        name="Weekly Boost",
        price_kobo=80000,  # ₦800
        duration_days=7,
        query_quota=500,
        storage_bytes=100 * MB,
        tagline="Perfect for assignment weeks and test prep.",
    ),
    "semester": Plan(
        key="semester",
        name="Semester Pro",
        price_kobo=300000,  # ₦3,000
        duration_days=120,
        query_quota=2500,
        storage_bytes=250 * MB,
        tagline="Anchored to the price of a standard departmental handout.",
        featured=True,
    ),
    "session": Plan(
        key="session",
        name="Session VIP",
        price_kobo=550000,  # ₦5,500
        duration_days=270,
        query_quota=5000,
        storage_bytes=500 * MB,
        tagline="Best per-query value — built for the long haul.",
    ),
    "topup": Plan(
        key="topup",
        name="AI Top-Up",
        price_kobo=100000,  # ₦1,000
        duration_days=365,
        query_quota=600,
        storage_bytes=0,
        tagline="More AI questions when you run out. Stacks on any pass.",
    ),
}

# Paid tiers shown in the paywall (night / weekly / semester / session).
PAYWALL_ORDER = ["night", "weekly", "semester", "session"]
# Tiers shown on the public /pricing page.
PUBLIC_ORDER = ["free", "night", "weekly", "semester", "session", "topup"]

PAID_PLAN_KEYS = {key for key, plan in PLANS.items() if plan.price_kobo > 0}


def get_plan(key: str) -> Plan:
    plan = PLANS.get(key)
    if plan is None:
        raise KeyError(f"Unknown plan: {key}")
    return plan


def paid_plans() -> list[Plan]:
    return [PLANS[key] for key in PAYWALL_ORDER if key in PLANS]


def public_plans() -> list[Plan]:
    return [PLANS[key] for key in PUBLIC_ORDER if key in PLANS]
