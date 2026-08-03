"""Sale economics — the platform must never pay the buyer's markup to the seller."""
from __future__ import annotations

import pytest

from backend.shared.plans import COMMISSION_PCT, PROCESSING_PCT, split_sale


def test_buyer_pays_list_price_plus_processing():
    buyer, _take, _net = split_sale(10_000, "free", is_student=False)
    assert buyer == 10_200  # $100.00 + 2% processing


@pytest.mark.parametrize("plan", sorted(COMMISSION_PCT))
def test_seller_net_excludes_the_buyer_processing_markup(plan):
    """Regression: `amount_cents - commission_cents` is how every consumer
    (payouts, seller analytics) derives seller earnings. If the platform's
    recorded take omits the processing markup, that markup silently lands in
    the seller's balance and the platform never captures it."""
    base = 10_000
    buyer, take, net = split_sale(base, plan, is_student=False)

    assert net == buyer - take, "callers derive net as amount - commission"
    assert net == base - round(base * COMMISSION_PCT[plan] / 100)
    assert take == round(base * COMMISSION_PCT[plan] / 100) + round(base * PROCESSING_PCT / 100)


def test_free_plan_students_get_the_reduced_commission():
    _b, _t, student_net = split_sale(10_000, "free", is_student=True)
    _b, _t, standard_net = split_sale(10_000, "free", is_student=False)
    assert student_net > standard_net


def test_student_discount_does_not_apply_to_paid_plans():
    assert split_sale(10_000, "studio", is_student=True) == \
           split_sale(10_000, "studio", is_student=False)


def test_split_is_exact_no_cents_leak():
    """Every cent the buyer pays is accounted for as platform take or seller net."""
    for base in (2_900, 4_999, 10_000, 33_333, 1_500_000):
        for plan in COMMISSION_PCT:
            buyer, take, net = split_sale(base, plan, is_student=False)
            assert take + net == buyer
            assert take >= 0 and net >= 0
