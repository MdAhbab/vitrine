"""Listing quota accounting and repository-URL persistence.

Two behaviours the seller dashboard depends on:

  * A draft is unfinished work, not inventory. It must not consume one of the
    plan's active-listing slots — a free-plan seller who abandoned two drafts
    used to be locked out of creating anything at all, with the only escape
    being to publish or delete work they weren't ready to show.
  * `listings.repo_url` must survive an intake run. The Repo-Intake agent has
    always taken a repo URL as its primary input, but the column did not exist,
    so the URL lived only inside the event payload: the seller reopened the
    editor to an empty field and a re-run had nothing to work from.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.gateway.app import app
from backend.shared.db import get_session
from backend.shared.models import Listing, User
from backend.shared.plans import listing_limit
from backend.shared.security import make_access_token


async def _client(db_session):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_access_token(user_id=user.id, role=user.role)}"}


@pytest.mark.asyncio
async def test_drafts_do_not_consume_the_plan_quota(db_session):
    seller = User(email="quota@vitrine.io", password_hash="x", role="seller",
                  display_name="Quota Seller", plan="free")
    db_session.add(seller)
    await db_session.flush()

    # Free plan allows 2 active listings. Fill the quota entirely with drafts.
    assert listing_limit("free") == 2
    db_session.add_all([
        Listing(owner_id=seller.id, slug=f"draft-{i}", name=f"Draft {i}",
                category="Dashboards", price_cents=0, status="draft")
        for i in range(5)
    ])
    await db_session.commit()

    client = await _client(db_session)
    try:
        async with client as ac:
            res = await ac.post("/listings", headers=_auth(seller),
                                json={"name": "Real piece", "category": "Dashboards", "price": 49})
            assert res.status_code == 201, res.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quota_is_charged_on_submit_not_on_create(db_session):
    """A seller at quota can still draft; they just can't publish."""
    seller = User(email="full@vitrine.io", password_hash="x", role="seller",
                  display_name="Full Seller", plan="free")
    db_session.add(seller)
    await db_session.flush()

    db_session.add_all([
        Listing(owner_id=seller.id, slug="live-a", name="Live A",
                category="Dashboards", price_cents=100, status="live"),
        # `paused` counts too: the slot is still held by a published piece.
        Listing(owner_id=seller.id, slug="paused-b", name="Paused B",
                category="Dashboards", price_cents=100, status="paused"),
    ])
    await db_session.commit()

    client = await _client(db_session)
    try:
        async with client as ac:
            # Drafting is always allowed — that was the whole complaint.
            res = await ac.post("/listings", headers=_auth(seller),
                                json={"name": "One more idea", "category": "Dashboards", "price": 49})
            assert res.status_code == 201, res.text
            new_id = res.json()["id"]

            # Publishing it is what the plan actually limits.
            res = await ac.post(f"/listings/{new_id}/submit", headers=_auth(seller))
            assert res.status_code == 403
            assert "2 active listings" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_submit_succeeds_when_a_slot_is_free(db_session):
    seller = User(email="room@vitrine.io", password_hash="x", role="seller",
                  display_name="Room Seller", plan="free")
    db_session.add(seller)
    await db_session.flush()
    db_session.add_all([
        Listing(owner_id=seller.id, slug="only-live", name="Only Live",
                category="Dashboards", price_cents=100, status="live"),
        # Three drafts in the way must not block the one being submitted.
        *[Listing(owner_id=seller.id, slug=f"idle-{i}", name=f"Idle {i}",
                  category="Dashboards", price_cents=0, status="draft") for i in range(3)],
    ])
    listing = Listing(owner_id=seller.id, slug="ready", name="Ready",
                      category="Dashboards", price_cents=4900, status="draft")
    db_session.add(listing)
    await db_session.commit()

    client = await _client(db_session)
    try:
        async with client as ac:
            res = await ac.post(f"/listings/{listing.id}/submit", headers=_auth(seller))
            assert res.status_code == 200, res.text
            assert res.json()["status"] == "review"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_repo_url_round_trips_through_patch(db_session):
    seller = User(email="repo@vitrine.io", password_hash="x", role="seller",
                  display_name="Repo Seller", plan="studio")
    db_session.add(seller)
    await db_session.flush()
    listing = Listing(owner_id=seller.id, slug="repo-piece", name="Repo Piece",
                      category="Developer Tools", price_cents=4900, status="draft")
    db_session.add(listing)
    await db_session.commit()

    client = await _client(db_session)
    try:
        async with client as ac:
            res = await ac.patch(f"/listings/{listing.id}", headers=_auth(seller),
                                 json={"repo_url": "https://github.com/acme/widget"})
            assert res.status_code == 200, res.text
            assert res.json()["repoUrl"] == "https://github.com/acme/widget"

            # And it is readable back off the row, not just echoed.
            await db_session.refresh(listing)
            assert listing.repo_url == "https://github.com/acme/widget"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_intake_trigger_persists_the_repo_url(db_session):
    seller = User(email="intake@vitrine.io", password_hash="x", role="seller",
                  display_name="Intake Seller", plan="studio")
    db_session.add(seller)
    await db_session.flush()
    listing = Listing(owner_id=seller.id, slug="intake-piece", name="Intake Piece",
                      category="Developer Tools", price_cents=4900, status="draft")
    db_session.add(listing)
    await db_session.commit()

    client = await _client(db_session)
    try:
        async with client as ac:
            res = await ac.post(f"/listings/{listing.id}/intake", headers=_auth(seller),
                                json={"repo_url": "https://github.com/acme/tessera"})
            assert res.status_code == 200, res.text

            await db_session.refresh(listing)
            assert listing.repo_url == "https://github.com/acme/tessera"
    finally:
        app.dependency_overrides.clear()
