from __future__ import annotations

from pydantic import BaseModel


class CheckoutIn(BaseModel):
    listing_id: str
    tier_index: int = 0
    kind: str = "purchase"  # purchase | advance


class OrderOut(BaseModel):
    """Mirrors frontend `Order`/`Transaction` (store.ts)."""

    id: str
    productId: str
    productName: str
    buyerId: str
    buyerName: str
    sellerId: str
    sellerName: str
    tier: str
    amount: float        # gross dollars
    commission: float
    status: str          # pending | paid | refunded
    ts: int              # epoch ms
    delivered: bool | None = None
    licenseKey: str | None = None


class DeliverIn(BaseModel):
    artifact_url: str | None = None


class FeatureRequestIn(BaseModel):
    listing_id: str
    description: str


class FeatureQuoteIn(BaseModel):
    developer_charge: float  # dollars


class PayoutRequestIn(BaseModel):
    amount: float
    payout_method: str = "bank"  # bank | mobile_wallet
    details: dict = {}


class SubscribeIn(BaseModel):
    tier: str  # free | studio | atelier | maison
