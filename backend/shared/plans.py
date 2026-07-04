"""
Seller plan economics — the single source of truth for commission rates and
listing caps. Previously these constants were duplicated across the orders and
catalog services (and re-implemented a third time in seed.py), which let the
tiered-commission business model drift out of sync with what checkout actually
charged. Keep all plan math here.

Rates match README §2 and the frontend PLAN_DETAILS. Runtime overrides can live
in admin_configs.fees, but these are the safe defaults.
"""
from __future__ import annotations

# Platform commission % taken from the sale, by seller plan.
COMMISSION_PCT = {"free": 12, "studio": 8, "atelier": 5, "maison": 3}
# Non-subscribed (free-plan) students get a reduced commission.
STUDENT_FREE_PCT = 7.5

# Max simultaneously-active listings by plan (maison = effectively unlimited).
LISTING_LIMITS = {"free": 2, "studio": 10, "atelier": 40, "maison": 1_000_000}

# Buyer-side processing markup applied on top of the sale price.
PROCESSING_PCT = 2.0


def commission_cents(amount_cents: int, plan: str, is_student: bool) -> int:
    """Platform cut for a sale, honouring plan tier + student discount."""
    pct = COMMISSION_PCT.get(plan, COMMISSION_PCT["free"])
    if plan == "free" and is_student:
        pct = STUDENT_FREE_PCT
    return round(amount_cents * pct / 100)


def buyer_cents(base_cents: int) -> int:
    """What the buyer pays including the processing markup."""
    return round(base_cents * (1 + PROCESSING_PCT / 100))


def listing_limit(plan: str) -> int:
    return LISTING_LIMITS.get(plan, LISTING_LIMITS["free"])
