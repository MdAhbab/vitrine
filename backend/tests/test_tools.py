"""Tests for AI tool registry critical paths."""
from __future__ import annotations

import pytest

from backend.ai.tools import estimate_feature_cost


@pytest.mark.asyncio
async def test_estimate_feature_cost_returns_range():
    result = await estimate_feature_cost("listing-1", "Add OAuth with Google sign-in")
    assert "estimated_charge" in result
    assert "range_low" in result
    assert "range_high" in result
    assert result["range_low"] <= result["estimated_charge"] <= result["range_high"]

