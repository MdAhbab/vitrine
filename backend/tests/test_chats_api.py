"""Chats API validation tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from backend.gateway.app import app
from backend.shared.db import get_session
from backend.shared.models import User, Listing
from backend.shared.security import make_access_token

@pytest.mark.asyncio
async def test_start_negotiation_validates_budget(db_session):
    # Setup database dependencies
    buyer = User(email="testbuyer@vitrine.io", password_hash="hash", role="buyer", display_name="Test Buyer")
    seller = User(email="testseller@vitrine.io", password_hash="hash", role="seller", display_name="Test Seller")
    db_session.add_all([buyer, seller])
    await db_session.flush()

    listing = Listing(
        owner_id=seller.id, slug="test-item", name="Test Item",
        category="Dashboards", price_cents=10000, status="live"
    )
    db_session.add(listing)
    await db_session.commit()

    # Override session dependency
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session

    # Generate auth token
    token = make_access_token(user_id=buyer.id, role="buyer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # 1. Budget of zero should fail with 400
        res = await ac.post(
            "/chats/negotiate/start",
            headers=headers,
            json={"listing_id": listing.id, "budget": 0, "readme_context": "SSO required"}
        )
        assert res.status_code == 400
        assert "Budget must be greater than zero" in res.json()["detail"]

        # 2. Negative budget should fail with 400
        res2 = await ac.post(
            "/chats/negotiate/start",
            headers=headers,
            json={"listing_id": listing.id, "budget": -10.5, "readme_context": "SSO required"}
        )
        assert res2.status_code == 400
        assert "Budget must be greater than zero" in res2.json()["detail"]

        # 3. Positive budget should succeed (returns 200 or 201)
        res3 = await ac.post(
            "/chats/negotiate/start",
            headers=headers,
            json={"listing_id": listing.id, "budget": 80.0, "readme_context": "SSO required"}
        )
        assert res3.status_code in (200, 201)
        data = res3.json()
        assert data["isAgent"] is True
        assert data["agentBudget"] == 80.0


@pytest.mark.asyncio
async def test_deactivate_negotiation_rep(db_session):
    # Setup database dependencies
    buyer = User(email="testbuyer2@vitrine.io", password_hash="hash", role="buyer", display_name="Test Buyer")
    seller = User(email="testseller2@vitrine.io", password_hash="hash", role="seller", display_name="Test Seller")
    db_session.add_all([buyer, seller])
    await db_session.flush()

    listing = Listing(
        owner_id=seller.id, slug="test-item-2", name="Test Item 2",
        category="Dashboards", price_cents=10000, status="live"
    )
    db_session.add(listing)
    await db_session.commit()

    # Override session dependency
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session

    # Generate auth token
    token = make_access_token(user_id=buyer.id, role="buyer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # Start negotiation
        start_res = await ac.post(
            "/chats/negotiate/start",
            headers=headers,
            json={"listing_id": listing.id, "budget": 80.0, "readme_context": "SSO required"}
        )
        assert start_res.status_code in (200, 201)
        chat_id = start_res.json()["id"]

        # Deactivate representative
        deact_res = await ac.post(
            f"/chats/{chat_id}/deactivate-rep",
            headers=headers
        )
        assert deact_res.status_code == 200
        assert deact_res.json()["isAgent"] is False

        # Attempt to deactivate someone else's rep (should return 403 or 404 depending on access)
        other_token = make_access_token(user_id=seller.id, role="seller")
        other_headers = {"Authorization": f"Bearer {other_token}"}
        
        fail_res = await ac.post(
            f"/chats/{chat_id}/deactivate-rep",
            headers=other_headers
        )
        assert fail_res.status_code in (403, 404)
