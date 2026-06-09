"""Analytics API validation tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from backend.gateway.app import app
from backend.shared.db import get_session
from backend.shared.models import User, Listing, AnalyticEvent, Order
from backend.shared.security import make_access_token



@pytest.mark.asyncio
async def test_analytics_endpoints(db_session):
    # Setup test database users
    buyer = User(email="testbuyer@vitrine.io", password_hash="hash", role="buyer", display_name="Test Buyer")
    seller = User(email="testseller@vitrine.io", password_hash="hash", role="seller", display_name="Test Seller", plan="studio")
    admin = User(email="testadmin@vitrine.io", password_hash="hash", role="admin", display_name="Test Admin")
    db_session.add_all([buyer, seller, admin])
    await db_session.flush()

    listing = Listing(
        owner_id=seller.id, slug="test-item-analytics", name="Test Item Analytics",
        category="Dashboards", price_cents=10000, status="live"
    )
    db_session.add(listing)
    await db_session.commit()

    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # 1. Test record view automatically via GET /listings/{slug}
        headers_buyer = {"Authorization": f"Bearer {make_access_token(user_id=buyer.id, role='buyer')}"}
        res = await ac.get("/listings/test-item-analytics", headers=headers_buyer)
        assert res.status_code == 200

        # Verify event was recorded in DB
        events = (await db_session.execute(
            select(AnalyticEvent).where(AnalyticEvent.listing_id == listing.id)
        )).scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "view"

        # 2. Test record view/launch via POST /analytics/event
        res = await ac.post(
            "/analytics/event",
            json={"event_type": "launch", "listing_id": listing.id}
        )
        assert res.status_code == 201

        # Verify second event (launch) was recorded
        events2 = (await db_session.execute(
            select(AnalyticEvent).where(AnalyticEvent.listing_id == listing.id).where(AnalyticEvent.event_type == "launch")
        )).scalars().all()
        assert len(events2) == 1

        # Add an order to generate earnings
        order = Order(
            buyer_id=buyer.id, listing_id=listing.id, seller_id=seller.id,
            amount_cents=10000, commission_cents=800, status="paid"
        )
        db_session.add(order)
        await db_session.commit()

        # 3. Test GET /seller/analytics
        headers_seller = {"Authorization": f"Bearer {make_access_token(user_id=seller.id, role='seller')}"}
        res = await ac.get("/seller/analytics", headers=headers_seller)
        assert res.status_code == 200
        data = res.json()
        assert data["views_14d"] >= 1
        assert data["launches_14d"] >= 1
        assert data["earnings_all_time"] == 92.0 # 10000 - 800 cents = 92.00 dollars
        assert len(data["history"]) == 14

        # 4. Test GET /admin/analytics
        headers_admin = {"Authorization": f"Bearer {make_access_token(user_id=admin.id, role='admin')}"}
        res = await ac.get("/admin/analytics", headers=headers_admin)
        assert res.status_code == 200
        admin_data = res.json()
        assert admin_data["views_14d"] >= 1
        assert len(admin_data["history"]) == 14
