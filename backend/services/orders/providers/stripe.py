"""Stripe provider — checkout sessions + signed webhook verification."""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from .base import CheckoutSession, PaymentEvent, PaymentProvider
from backend.shared.settings import settings


class StripeProvider(PaymentProvider):
    def _stripe(self):
        try:
            import stripe
        except ImportError as exc:
            raise HTTPException(500, "stripe package not installed") from exc
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(500, "STRIPE_SECRET_KEY not configured")
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe

    async def create_checkout(self, *, order_id: str, amount_cents: int,
                              currency: str = "USD") -> CheckoutSession:
        if not settings.STRIPE_SECRET_KEY:
            return CheckoutSession(
                provider_ref=f"stripe_stub_{uuid.uuid4().hex[:12]}",
                redirect_url=None,
                status="paid",
            )
        stripe = self._stripe()
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": amount_cents,
                    "product_data": {"name": f"Vitrine order {order_id}"},
                },
                "quantity": 1,
            }],
            metadata={"order_id": order_id},
            success_url=f"{settings.FRONTEND_ORIGIN}/#/dashboard",
            cancel_url=f"{settings.FRONTEND_ORIGIN}/#/browse",
        )
        return CheckoutSession(
            provider_ref=session.id,
            redirect_url=session.url,
            status="pending",
        )

    async def verify_webhook(self, headers: dict, body: bytes) -> PaymentEvent:
        if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
            raise HTTPException(400, "Stripe webhook not configured")
        stripe = self._stripe()
        sig = headers.get("stripe-signature") or headers.get("Stripe-Signature")
        if not sig:
            raise HTTPException(400, "Missing stripe-signature header")
        try:
            event = stripe.Webhook.construct_event(
                body, sig, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:
            raise HTTPException(400, f"Webhook verification failed: {exc}") from exc

        if event.type == "checkout.session.completed":
            obj = event.data.object
            return PaymentEvent(provider_ref=obj.id, status="paid")
        if event.type in ("checkout.session.expired", "payment_intent.payment_failed"):
            obj = event.data.object
            ref = getattr(obj, "id", "unknown")
            return PaymentEvent(provider_ref=ref, status="failed")
        return PaymentEvent(provider_ref="ignored", status="ignored")
