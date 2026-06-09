"""
Budget guard — protects the $10 OpenAI allowance.

Enforces a per-run token cap and a global daily USD cap (OPENAI_DAILY_LIMIT_USD).
Scaffold uses an in-process daily counter; Phase 2 persists spend via agent_runs
aggregates / Redis so the cap survives restarts and spans workers.
"""
from __future__ import annotations

from datetime import date

from backend.shared.settings import settings


class BudgetExceeded(Exception):
    pass


class _DailyBudget:
    def __init__(self) -> None:
        self._day = date.today()
        self._spent_usd = 0.0

    def _roll(self) -> None:
        today = date.today()
        if today != self._day:
            self._day, self._spent_usd = today, 0.0

    def check(self) -> None:
        self._roll()
        if self._spent_usd >= settings.OPENAI_DAILY_LIMIT_USD:
            raise BudgetExceeded(
                f"Daily OpenAI cap ${settings.OPENAI_DAILY_LIMIT_USD} reached"
            )

    def record(self, cost_usd: float) -> None:
        self._roll()
        self._spent_usd += cost_usd

    @property
    def spent_today(self) -> float:
        self._roll()
        return self._spent_usd


budget = _DailyBudget()
