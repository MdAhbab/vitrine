"""Stripe provider — drop-in for production. TODO(Phase 3): implement with the
stripe SDK + signed webhook verification (settings.STRIPE_WEBHOOK_SECRET)."""
from __future__ import annotations

from .base import CheckoutSession, PaymentEvent, PaymentProvider


class StripeProvider(PaymentProvider):
    async def create_checkout(self, *, order_id: str, amount_cents: int,
                              currency: str = "USD") -> CheckoutSession:
        raise NotImplementedError("StripeProvider.create_checkout — TODO Phase 3")

    async def verify_webhook(self, headers: dict, body: bytes) -> PaymentEvent:
        raise NotImplementedError("StripeProvider.verify_webhook — TODO Phase 3")
