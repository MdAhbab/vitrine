"""Mock payment provider — instant 'paid', no real money. Demo default."""
from __future__ import annotations

import uuid

from .base import CheckoutSession, PaymentEvent, PaymentProvider


class MockProvider(PaymentProvider):
    async def create_checkout(self, *, order_id: str, amount_cents: int,
                              currency: str = "USD") -> CheckoutSession:
        return CheckoutSession(provider_ref=f"mock_{uuid.uuid4().hex[:12]}",
                               redirect_url=None, status="paid")

    async def verify_webhook(self, headers: dict, body: bytes) -> PaymentEvent:
        # In mock mode checkout is already 'paid'; webhook is a no-op echo.
        return PaymentEvent(provider_ref="mock", status="paid")
