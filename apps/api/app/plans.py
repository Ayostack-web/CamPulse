"""Vylix pricing tiers — single source of truth.

Every tier (including the AI Top-Ups) is defined here so the quota resolver,
storage enforcement, payment activation and the public /plans endpoint all
agree on the same numbers.

Prices are in kobo (Monnify works in the minor unit of NGN).

Per-query pricing ladder (longer commitment = real discount):
  Night   → ₦2.00/query  (₦300  / 150 queries)
  Weekly  → ₦1.60/query  (₦800  / 500 queries)
  Semester→ ₦1.20/query  (₦3,000/ 2,500 queries)
  Session → ₦1.18/query  (₦6,500/ 5,500 queries)
  Top-Up  → ₦1.67/query  (₦1,000/ 600 queries)  — stacks on any pass
  Mini    → ₦2.00/query  (₦500  / 250 queries)  — lighter top-up
  Micro   → ₦10.00/query (₦100  / 10 queries)   — impulse single-use
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

MB = 1024 * 1024

# Free tier daily AI query allowance.
FREE_DAILY_LIMIT = 3
# Generous first-day allowance so new users see value before the wall tightens.
FIRST_DAY_BOOST_LIMIT = 10
FIRST_DAY_BOOST_DURATION = timedelta(hours=24)

# Free storage vault allowance (applies to every user, paid or not).
FREE_STORAGE_BYTES = 25 * MB

# Soft daily cap for long-duration plans to spread usage across the subscription.
# Prevents power users from exhausting a 120/270-day pass in a few weeks.
PAID_DAILY_SOFT_CAP = 50


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
    daily_query_cap: int | None = None  # soft per-day limit; None = uncapped within quota

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
        price_kobo=30000,  # ₦300  →  ₦2.00/query
        duration_days=3,
        query_quota=150,
        storage_bytes=50 * MB,
        tagline="The impulse buy — cheaper than a bottle of Coke.",
    ),
    "weekly": Plan(
        key="weekly",
        name="Weekly Boost",
        price_kobo=80000,  # ₦800  →  ₦1.60/query
        duration_days=7,
        query_quota=500,
        storage_bytes=100 * MB,
        tagline="Perfect for assignment weeks and test prep.",
    ),
    "semester": Plan(
        key="semester",
        name="Semester Pro",
        price_kobo=300000,  # ₦3,000  →  ₦1.20/query
        duration_days=120,
        query_quota=2500,
        storage_bytes=250 * MB,
        tagline="Anchored to the price of a standard departmental handout.",
        featured=True,
        daily_query_cap=PAID_DAILY_SOFT_CAP,
    ),
    "session": Plan(
        key="session",
        name="Session VIP",
        price_kobo=650000,  # ₦6,500  →  ₦1.18/query
        duration_days=270,
        query_quota=5500,
        storage_bytes=500 * MB,
        tagline="Best per-query value — built for the long haul.",
        daily_query_cap=PAID_DAILY_SOFT_CAP,
    ),
    "topup": Plan(
        key="topup",
        name="AI Top-Up",
        price_kobo=100000,  # ₦1,000  →  ₦1.67/query
        duration_days=365,
        query_quota=600,
        storage_bytes=0,
        tagline="More AI questions when you run out. Stacks on any pass.",
    ),
    "topup_mini": Plan(
        key="topup_mini",
        name="Mini Top-Up",
        price_kobo=50000,  # ₦500  →  ₦2.00/query
        duration_days=365,
        query_quota=250,
        storage_bytes=0,
        tagline="A lighter top-up when 600 is too much.",
    ),
    "micro": Plan(
        key="micro",
        name="Quick Ask",
        price_kobo=10000,  # ₦100  →  ₦10.00/query
        duration_days=30,
        query_quota=10,
        storage_bytes=0,
        tagline="Just one question? We got you.",
    ),
}

# Paid tiers shown in the paywall (night / weekly / semester / session).
PAYWALL_ORDER = ["night", "weekly", "semester", "session"]
# Tiers shown on the public /pricing page.
PUBLIC_ORDER = ["free", "night", "weekly", "semester", "session", "topup", "topup_mini", "micro"]

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
