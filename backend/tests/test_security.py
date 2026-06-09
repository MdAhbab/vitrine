"""Auth and rate-limit tests."""
from __future__ import annotations

import pytest

from backend.shared.security import hash_password, verify_password, make_access_token, decode_token
from backend.shared.ratelimit import _MemoryLimiter


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    token = make_access_token("user-abc", "buyer")
    claims = decode_token(token)
    assert claims["sub"] == "user-abc"
    assert claims["role"] == "buyer"
    assert claims["kind"] == "access"


@pytest.mark.asyncio
async def test_memory_rate_limiter_blocks():
    limiter = _MemoryLimiter()
    for _ in range(5):
        await limiter.check("test:key", limit=5, window=60)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await limiter.check("test:key", limit=5, window=60)


@pytest.mark.asyncio
async def test_ai_rate_limit_enforced():
    from backend.shared.security import ai_rate_limit
    from fastapi import Request, HTTPException
    from unittest.mock import Mock

    mock_request = Mock(spec=Request)
    mock_request.headers = {}
    mock_request.client = Mock()
    mock_request.client.host = "9.9.9.9"

    for _ in range(10):
        await ai_rate_limit(mock_request)

    with pytest.raises(HTTPException) as excinfo:
        await ai_rate_limit(mock_request)
    assert excinfo.value.status_code == 429

