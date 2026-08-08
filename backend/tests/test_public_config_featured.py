"""The curator's featured picks have to reach the people they were picked for.

`featured_ids` used to be readable only through `GET /admin/config`, which is
role-gated to admins. The storefront therefore saw an empty list for every
signed-out visitor and every buyer, fell back to "top 3 by Vitrine Score", and
the curator's selection changed nothing about the site — while looking correct
in the console that set it.

What the storefront depends on:

  * the picks are served WITHOUT authentication;
  * curator order is preserved, because it is an editorial ordering;
  * only `live` listings go out — a draft or archived pick must not be
    advertised, and the storefront cannot render one;
  * the public payload never carries the admin-only material that sits in the
    same `admin_configs` table.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.gateway.app import app
from backend.shared.db import get_session
from backend.shared.models import AdminConfig, Listing, User


async def _client(db_session):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _catalogue(db_session) -> dict[str, str]:
    """One seller, three listings: two live, one still a draft."""
    seller = User(email="curator-picks@vitrine.io", password_hash="x",
                  role="seller", display_name="Picks Seller", plan="studio")
    db_session.add(seller)
    await db_session.flush()

    ids: dict[str, str] = {}
    for slug, status in (("alpha", "live"), ("beta", "live"), ("gamma", "draft")):
        row = Listing(owner_id=seller.id, slug=slug, name=slug.title(),
                      category="Dashboards", price_cents=4900, status=status)
        db_session.add(row)
        await db_session.flush()
        ids[slug] = row.id
    await db_session.commit()
    return ids


async def _set_featured(db_session, values: list) -> None:
    db_session.add(AdminConfig(key="featured_ids", value=values))
    await db_session.commit()


@pytest.mark.asyncio
async def test_featured_ids_served_without_authentication(db_session):
    ids = await _catalogue(db_session)
    await _set_featured(db_session, [ids["beta"], ids["alpha"]])

    async with await _client(db_session) as ac:
        # Deliberately no Authorization header: this is the anonymous visitor
        # whose storefront was silently falling back before.
        res = await ac.get("/public-config")

    assert res.status_code == 200
    assert res.json()["featuredIds"] == [ids["beta"], ids["alpha"]]


@pytest.mark.asyncio
async def test_reordering_the_picks_reorders_the_response(db_session):
    """Order is carried through, not incidental to how the rows were queried.

    Serving these via a plain `IN (...)` lookup would return them in whatever
    order the database chose, so the curator could rearrange the showcase and
    see nothing change. Reversing the stored list must reverse the response.
    """
    ids = await _catalogue(db_session)
    await _set_featured(db_session, [ids["beta"], ids["alpha"]])

    async with await _client(db_session) as ac:
        first = (await ac.get("/public-config")).json()["featuredIds"]

        row = await db_session.get(AdminConfig, "featured_ids")
        row.value = [ids["alpha"], ids["beta"]]
        db_session.add(row)
        await db_session.commit()

        second = (await ac.get("/public-config")).json()["featuredIds"]

    assert first == [ids["beta"], ids["alpha"]]
    assert second == [ids["alpha"], ids["beta"]]


@pytest.mark.asyncio
async def test_non_live_picks_are_withheld(db_session):
    ids = await _catalogue(db_session)
    await _set_featured(db_session, [ids["alpha"], ids["gamma"]])

    async with await _client(db_session) as ac:
        featured = (await ac.get("/public-config")).json()["featuredIds"]

    assert featured == [ids["alpha"]], "a draft pick must not be advertised"


@pytest.mark.asyncio
async def test_stale_and_malformed_ids_are_dropped(db_session):
    ids = await _catalogue(db_session)
    await _set_featured(db_session, [ids["alpha"], "no-such-listing-id", None, 42])

    async with await _client(db_session) as ac:
        res = await ac.get("/public-config")

    assert res.status_code == 200, "junk in the config must not 500 the storefront"
    assert res.json()["featuredIds"] == [ids["alpha"]]


@pytest.mark.asyncio
async def test_no_featured_selection_yields_an_empty_list(db_session):
    await _catalogue(db_session)

    async with await _client(db_session) as ac:
        res = await ac.get("/public-config")

    # Empty, never absent: the gallery reads the key directly to decide whether
    # to render the Hero Showcase at all.
    assert res.json()["featuredIds"] == []


@pytest.mark.asyncio
async def test_public_payload_withholds_admin_material(db_session):
    await _catalogue(db_session)
    db_session.add(AdminConfig(key="api_keys", value=[
        {"id": "k1", "provider": "openai", "label": "primary",
         "key": "sk-should-never-be-public", "enabled": True},
    ]))
    db_session.add(AdminConfig(key="system_prompts", value={"concierge": "secret prompt"}))
    await db_session.commit()

    async with await _client(db_session) as ac:
        body = (await ac.get("/public-config")).json()

    assert set(body) == {"categories", "frameworks", "sections", "forms", "featuredIds"}
    assert "sk-should-never-be-public" not in str(body)
    assert "secret prompt" not in str(body)
