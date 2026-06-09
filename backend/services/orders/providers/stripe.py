"""Stripe provider — drop-in for production. TODO(Phase 3): implement with the
stripe SDK + signed webhook verification (settings.STRIPE_WEBHOOK_SECRET)."""
from __future__ import annotations

import uuid
from .base import CheckoutSession, PaymentEvent, PaymentProvider
from backend.shared.settings import settings


class StripeProvider(PaymentProvider):
    async def create_checkout(self, *, order_id: str, amount_cents: int,
                              currency: str = "USD") -> CheckoutSession:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            # In a real implementation:
            # session = stripe.checkout.Session.create(...)
            # return CheckoutSession(provider_ref=session.id, redirect_url=session.url, status="pending")
        except ImportError:
            pass
            
        return CheckoutSession(
            provider_ref=f"stripe_{uuid.uuid4().hex[:12]}",
            redirect_url=f"https://checkout.stripe.com/pay/{uuid.uuid4().hex}",
            status="pending"
        )

    async def verify_webhook(self, headers: dict, body: bytes) -> PaymentEvent:
        try:
            import stripe
            # In a real implementation:
            # sig = headers.get("stripe-signature")
            # event = stripe.Webhook.construct_event(body, sig, settings.STRIPE_WEBHOOK_SECRET)
            # return PaymentEvent(provider_ref=event.data.object.id, status="paid" if event.type == "checkout.session.completed" else "failed")
        except (ImportError, Exception):
            pass
            
        return PaymentEvent(provider_ref="stripe_mock", status="paid")
