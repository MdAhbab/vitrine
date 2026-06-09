"""AI API integration tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_concierge_stream_allows_anonymous(monkeypatch):
    from backend.gateway.app import app
    from backend.ai.client import client

    async def _false() -> bool:
        return False

    monkeypatch.setattr(client, "_ensure_client", _false)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        res = await ac.post(
            "/ai/concierge",
            json={"query": "React dashboard", "history": []},
        )

    assert res.status_code == 200
    body = res.text
    assert '"type": "results"' in body or '"type":"results"' in body
    assert '"type": "done"' in body or '"type":"done"' in body
