"""Tests for grounded catalog search constraints."""
from __future__ import annotations

import pytest

from backend.ai.searching import search_listings
from backend.shared.models import Listing, User


@pytest.mark.asyncio
async def test_search_listings_honors_price_and_demo_constraints(db_session):
    seller = User(email="seller@example.com", password_hash="x", role="seller", display_name="Seller")
    db_session.add(seller)
    await db_session.flush()

    rows = [
        Listing(
            owner_id=seller.id,
            slug="cheap-react-dashboard",
            name="Cheap React Dashboard",
            tagline="React dashboard with live preview",
            category="Dashboards",
            tags=["dashboard", "react"],
            framework="React",
            price_cents=9900,
            status="live",
            demo_url="https://example.com/demo",
            vitrine_score=90,
        ),
        Listing(
            owner_id=seller.id,
            slug="expensive-stripe-dashboard",
            name="Expensive Stripe Dashboard",
            tagline="Stripe dashboard",
            category="Dashboards",
            tags=["dashboard", "stripe"],
            framework="React",
            price_cents=16900,
            status="live",
            demo_url="https://example.com/demo",
            vitrine_score=99,
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    found = await search_listings(db_session, "React dashboard with Stripe under $100 live demo", k=10)

    assert [r.slug for r in found] == ["cheap-react-dashboard"]
