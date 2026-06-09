from __future__ import annotations

from pydantic import BaseModel


class ConciergeIn(BaseModel):
    query: str
    history: list[dict] = []  # [{role, content}]


class NegotiateIn(BaseModel):
    chat_id: str  # the rep produces the next message for this negotiation


class EstimateFeatureIn(BaseModel):
    listing_id: str
    description: str


class EstimateFeatureOut(BaseModel):
    estimated_charge: float          # dollars (midpoint)
    range_low: float
    range_high: float
    rationale: str


class PricingIn(BaseModel):
    listing_id: str


class PricingOut(BaseModel):
    suggested_tiers: list[dict]      # [{name, price, features}]
    tagline: str
    short_description: str
    long_description: str
