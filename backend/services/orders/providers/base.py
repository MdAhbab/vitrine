from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CheckoutSession:
    provider_ref: str
    redirect_url: str | None  # None for instant/mock
    status: str               # 'paid' | 'pending'


@dataclass
class PaymentEvent:
    provider_ref: str
    status: str               # 'paid' | 'refunded' | 'failed'
    order_id: str | None = None


class PaymentProvider(Protocol):
    async def create_checkout(self, *, order_id: str, amount_cents: int,
                              currency: str = "USD") -> CheckoutSession: ...

    async def verify_webhook(self, headers: dict, body: bytes) -> PaymentEvent: ...
