"""Seller payout balance — the check-then-insert must not be racy.

A payout request reads the seller's available balance, compares it to the
requested amount, then inserts a Payout row. Without serialisation two
concurrent requests both read the pre-insert balance, both pass the check, and
the seller withdraws the same money twice.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.services.orders.app import _available_payout_cents, _payout_lock
from backend.shared.models import Order, Payout, User
from backend.shared.plans import split_sale


async def _seller_with_sale(db, email: str, base_cents: int = 10_000) -> User:
    seller = User(email=email, password_hash="x", role="seller", plan="free")
    db.add(seller)
    await db.flush()
    buyer_cents, take, _net = split_sale(base_cents, "free", False)
    db.add(Order(buyer_id="b", seller_id=seller.id, listing_id="l",
                 amount_cents=buyer_cents, commission_cents=take, status="delivered"))
    await db.commit()
    return seller


@pytest.mark.asyncio
async def test_available_balance_is_net_of_commission(db_session):
    seller = await _seller_with_sale(db_session, "payout1@vitrine.io")
    _b, _t, net = split_sale(10_000, "free", False)
    assert await _available_payout_cents(db_session, seller.id) == net


@pytest.mark.asyncio
async def test_pending_and_processed_payouts_reduce_the_balance(db_session):
    seller = await _seller_with_sale(db_session, "payout2@vitrine.io")
    _b, _t, net = split_sale(10_000, "free", False)

    db_session.add(Payout(seller_id=seller.id, amount_cents=1_000, status="pending"))
    db_session.add(Payout(seller_id=seller.id, amount_cents=2_000, status="processed"))
    # A rejected claim must NOT hold the money hostage.
    db_session.add(Payout(seller_id=seller.id, amount_cents=5_000, status="rejected"))
    await db_session.commit()

    assert await _available_payout_cents(db_session, seller.id) == net - 3_000


@pytest.mark.asyncio
async def test_undelivered_orders_do_not_count_toward_the_balance(db_session):
    seller = await _seller_with_sale(db_session, "payout3@vitrine.io")
    _b, _t, net = split_sale(10_000, "free", False)
    db_session.add(Order(buyer_id="b", seller_id=seller.id, listing_id="l2",
                         amount_cents=50_000, commission_cents=6_000, status="pending"))
    await db_session.commit()
    assert await _available_payout_cents(db_session, seller.id) == net


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_double_spend_the_balance(db_session):
    """Regression: without _payout_lock both coroutines read the same balance
    before either inserts, so both pass the check and the seller is paid twice."""
    seller = await _seller_with_sale(db_session, "payout4@vitrine.io")
    _b, _t, net = split_sale(10_000, "free", False)

    async def claim(amount: int) -> bool:
        # Mirrors the route body: lock, re-read, check, insert, commit.
        async with _payout_lock:
            available = await _available_payout_cents(db_session, seller.id)
            if amount > available:
                return False
            db_session.add(Payout(seller_id=seller.id, amount_cents=amount, status="pending"))
            await db_session.commit()
            return True

    results = await asyncio.gather(claim(net), claim(net))
    assert sorted(results) == [False, True], "exactly one full-balance claim may win"
    assert await _available_payout_cents(db_session, seller.id) == 0
