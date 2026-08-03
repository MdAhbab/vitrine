"""Legacy-order backfill for the `commission_cents` meaning change."""
from __future__ import annotations

import pytest

from backend.shared.models import Order, User
from backend.shared.plans import PROCESSING_PCT, commission_cents, split_sale


def _legacy_order(seller_id: str, base_cents: int, plan: str) -> Order:
    """An order as checkout used to write it: amount includes the buyer markup,
    but commission records only the plan cut."""
    return Order(
        buyer_id="buyer", seller_id=seller_id, listing_id="listing",
        amount_cents=round(base_cents * (1 + PROCESSING_PCT / 100)),
        commission_cents=commission_cents(base_cents, plan, False),
        status="delivered",
    )


@pytest.mark.asyncio
async def test_backfill_repairs_legacy_orders_and_is_idempotent(db_session, monkeypatch):
    import backend.shared.db as dbmod

    seller = User(email="s@vitrine.io", password_hash="x", role="seller", plan="free")
    db_session.add(seller)
    await db_session.flush()

    base = 10_000
    order = _legacy_order(seller.id, base, "free")
    db_session.add(order)
    await db_session.commit()

    # Precondition: the legacy row pays the seller the buyer's 2% markup on top
    # of the intended net (10200 - 1200 = 9000, where the correct net is 8800).
    legacy_net = order.amount_cents - order.commission_cents
    _b, _t, correct_net = split_sale(base, "free", False)
    assert legacy_net == correct_net + (order.amount_cents - base), \
        "precondition: the old formula overpaid by exactly the markup"

    class _Session:
        async def __aenter__(self): return db_session
        async def __aexit__(self, *a): return False
        def __call__(self): return self

    monkeypatch.setattr(dbmod, "SessionLocal", _Session())

    await dbmod._backfill_platform_take()
    await db_session.refresh(order)

    expected_buyer, expected_take, expected_net = split_sale(base, "free", False)
    assert order.commission_cents == expected_take
    assert order.amount_cents - order.commission_cents == expected_net == base - 1200

    # Running again must not double-apply the markup.
    await dbmod._backfill_platform_take()
    await db_session.refresh(order)
    assert order.commission_cents == expected_take


@pytest.mark.asyncio
async def test_backfill_leaves_already_correct_orders_alone(db_session, monkeypatch):
    import backend.shared.db as dbmod

    seller = User(email="s2@vitrine.io", password_hash="x", role="seller", plan="studio")
    db_session.add(seller)
    await db_session.flush()

    buyer_cents, take, _net = split_sale(25_000, "studio", False)
    order = Order(buyer_id="b", seller_id=seller.id, listing_id="l",
                  amount_cents=buyer_cents, commission_cents=take, status="paid")
    db_session.add(order)
    await db_session.commit()

    class _Session:
        async def __aenter__(self): return db_session
        async def __aexit__(self, *a): return False
        def __call__(self): return self

    monkeypatch.setattr(dbmod, "SessionLocal", _Session())
    await dbmod._backfill_platform_take()
    await db_session.refresh(order)
    assert order.commission_cents == take
