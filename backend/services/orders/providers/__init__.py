"""Payment providers. Select via settings.PAYMENT_PROVIDER (mock | stripe)."""
from __future__ import annotations

from backend.shared.settings import settings

from .base import PaymentProvider
from .mock import MockProvider
from .stripe import StripeProvider


def get_provider() -> PaymentProvider:
    return StripeProvider() if settings.PAYMENT_PROVIDER == "stripe" else MockProvider()
