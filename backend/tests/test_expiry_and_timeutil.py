"""Regressions for listing expiry and naive/aware datetime handling.

Covers three bugs found in end-to-end testing:
  * `is_past`/`is_future` used to be raw `<`/`>` comparisons, which raised
    "can't compare offset-naive and offset-aware datetimes" for any datetime
    read back from SQLite. That turned a reposted listing's product page into a
    500 for every visitor, and a banned user's login into a 500 instead of 403.
  * `search_listings` filtered on `status == 'live'` only, so expired listings
    leaked into search results and into grounded Concierge answers.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.ai.searching import search_listings
from backend.shared.models import Listing, User
from backend.shared.timeutil import as_utc, is_future, is_past


def test_as_utc_treats_naive_as_utc():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    assert as_utc(naive) == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert as_utc(None) is None


def test_is_past_and_is_future_accept_naive_datetimes():
    """The SQLite-shaped case: naive values must not raise."""
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    naive_past = now_naive - timedelta(days=1)
    naive_future = now_naive + timedelta(days=1)

    assert is_past(naive_past) is True
    assert is_past(naive_future) is False
    assert is_future(naive_future) is True
    assert is_future(naive_past) is False


def test_is_past_and_is_future_accept_aware_datetimes():
    aware_past = datetime.now(timezone.utc) - timedelta(days=1)
    aware_future = datetime.now(timezone.utc) + timedelta(days=1)

    assert is_past(aware_past) is True
    assert is_future(aware_future) is True


def test_none_expiry_never_counts_as_expired():
    """A NULL expires_at means 'evergreen', not 'expired'."""
    assert is_past(None) is False
    assert is_future(None) is False


@pytest.mark.asyncio
async def test_search_excludes_expired_listings(db_session):
    seller = User(email="seller@example.com", password_hash="x", role="seller",
                  display_name="Seller")
    db_session.add(seller)
    await db_session.flush()

    common = dict(category="Dashboards", framework="React", price_cents=9900,
                  status="live", demo_url="https://example.com/demo", vitrine_score=90)
    db_session.add_all([
        Listing(owner_id=seller.id, slug="evergreen-dash", name="Evergreen Dash",
                tagline="A dashboard that is still for sale", tags=["dashboard"],
                expires_at=None, **common),
        Listing(owner_id=seller.id, slug="expired-dash", name="Expired Dash",
                tagline="A dashboard that has lapsed", tags=["dashboard"],
                expires_at=datetime.now(timezone.utc) - timedelta(days=5), **common),
    ])
    await db_session.commit()

    names = {r.name for r in await search_listings(db_session, "dashboard", use_ai=False)}
    assert "Evergreen Dash" in names
    assert "Expired Dash" not in names, "expired listings must not be recommended"
