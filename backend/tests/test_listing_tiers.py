"""Pricing-tier persistence.

`listing_tiers` is a separate table, so it needs its own branch in
`PATCH /listings/{id}` — without one the endpoint happily accepted a `tiers`
array, saved the base `price_cents`, and dropped the ladder on the floor. A
seller who ran the Pricing & Pitch agent (or typed their own packages) then
reopened a listing that answered `"tiers": []` forever.

What the seller's editor depends on:

  * a ladder sent in a PATCH is written and comes back on GET /listings/{slug};
  * a PATCH *without* a `tiers` key never touches the existing ladder, so
    saving copy — or submitting for review — can't silently erase pricing;
  * sending `tiers` is a full replacement, and `[]` genuinely clears it;
  * a malformed tier is refused rather than half-written.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.gateway.app import app
from backend.shared.db import get_session
from backend.shared.models import Listing, ListingTier, User
from backend.shared.security import make_access_token


async def _client(db_session):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_access_token(user_id=user.id, role=user.role)}"}


async def _seller_with_listing(db_session, email: str, slug: str) -> tuple[User, Listing]:
    seller = User(email=email, password_hash="x", role="seller",
                  display_name="Tier Seller", plan="studio")
    db_session.add(seller)
    await db_session.flush()
    listing = Listing(owner_id=seller.id, slug=slug, name=slug.replace("-", " ").title(),
                      category="Dashboards", price_cents=8900, status="draft")
    db_session.add(listing)
    await db_session.commit()
    return seller, listing


LADDER = [
    {"name": "Source", "price": 119, "features": ["Full source code", "MIT license"], "recommended": False},
    {"name": "Source + Setup", "price": 189, "features": ["Onboarding call"], "recommended": True},
    {"name": "Bespoke", "price": 329, "features": ["Brand reskin"], "recommended": False},
]


@pytest.mark.asyncio
async def test_tiers_round_trip_through_patch_and_get(db_session):
    seller, listing = await _seller_with_listing(db_session, "tiers@vitrine.io", "tiered-piece")

    client = await _client(db_session)
    try:
        async with client as ac:
            res = await ac.patch(f"/listings/{listing.id}", headers=_auth(seller),
                                 json={"tiers": LADDER})
            assert res.status_code == 200, res.text
            assert [t["name"] for t in res.json()["tiers"]] == ["Source", "Source + Setup", "Bespoke"]

            # Written to the table, not just echoed back.
            rows = (await db_session.execute(
                select(ListingTier).where(ListingTier.listing_id == listing.id))).scalars().all()
            assert sorted(r.price_cents for r in rows) == [11900, 18900, 32900]

            # And served on the seller-facing read the editor reopens against.
            res = await ac.get(f"/listings/{listing.slug}", headers=_auth(seller))
            assert res.status_code == 200, res.text
            tiers = res.json()["tiers"]
            assert [t["price"] for t in tiers] == [119.0, 189.0, 329.0]
            assert tiers[1]["recommended"] is True
            assert tiers[0]["features"] == ["Full source code", "MIT license"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_a_patch_without_tiers_leaves_the_ladder_alone(db_session):
    """Saving copy, or submitting for review, must not erase pricing."""
    seller, listing = await _seller_with_listing(db_session, "keep@vitrine.io", "keeps-tiers")

    client = await _client(db_session)
    try:
        async with client as ac:
            await ac.patch(f"/listings/{listing.id}", headers=_auth(seller), json={"tiers": LADDER})

            res = await ac.patch(f"/listings/{listing.id}", headers=_auth(seller),
                                 json={"tagline": "Now with a tagline"})
            assert res.status_code == 200, res.text
            assert len(res.json()["tiers"]) == 3

            res = await ac.post(f"/listings/{listing.id}/submit", headers=_auth(seller))
            assert res.status_code == 200, res.text

            res = await ac.get(f"/listings/{listing.slug}", headers=_auth(seller))
            assert len(res.json()["tiers"]) == 3
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sending_tiers_replaces_the_whole_ladder(db_session):
    seller, listing = await _seller_with_listing(db_session, "replace@vitrine.io", "replaces-tiers")

    client = await _client(db_session)
    try:
        async with client as ac:
            await ac.patch(f"/listings/{listing.id}", headers=_auth(seller), json={"tiers": LADDER})

            # A shorter ladder replaces, it does not merge.
            res = await ac.patch(f"/listings/{listing.id}", headers=_auth(seller),
                                 json={"tiers": [{"name": "One price", "price": 249, "features": []}]})
            assert res.status_code == 200, res.text
            assert [t["name"] for t in res.json()["tiers"]] == ["One price"]

            # And an explicit empty list means "no tiers", not "ignore me".
            res = await ac.patch(f"/listings/{listing.id}", headers=_auth(seller), json={"tiers": []})
            assert res.status_code == 200, res.text
            assert res.json()["tiers"] == []
            rows = (await db_session.execute(
                select(ListingTier).where(ListingTier.listing_id == listing.id))).scalars().all()
            assert rows == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    {"tiers": "Source"},
    {"tiers": [{"price": 49}]},                       # no name
    {"tiers": [{"name": "Source", "price": -1}]},     # negative
    {"tiers": [{"name": "Source", "price": "free"}]},  # not a number
    {"tiers": [{"name": "Source", "price": 10, "features": "code"}]},
])
async def test_malformed_tiers_are_refused(db_session, bad):
    seller, listing = await _seller_with_listing(db_session, "bad@vitrine.io", "bad-tiers")

    client = await _client(db_session)
    try:
        async with client as ac:
            res = await ac.patch(f"/listings/{listing.id}", headers=_auth(seller), json=bad)
            assert res.status_code == 422, res.text

            rows = (await db_session.execute(
                select(ListingTier).where(ListingTier.listing_id == listing.id))).scalars().all()
            assert rows == [], "a rejected patch must not half-write the ladder"
    finally:
        app.dependency_overrides.clear()
