"""AI API integration tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_concierge_stream_allows_anonymous(monkeypatch, db_session):
    from backend.gateway.app import app
    from backend.ai.client import client
    from backend.shared.db import get_session
    import backend.ai.agents.concierge as concierge_module
    import backend.ai.agents.base as base_module

    async def _empty_clients():
        return []

    async def _get_test_session():
        yield db_session

    class MockSessionLocal:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def __call__(self):
            return self

    monkeypatch.setattr(client, "_get_configured_clients", _empty_clients)
    monkeypatch.setattr("backend.shared.settings.settings.OPENAI_API_KEY", "")
    monkeypatch.setattr(concierge_module, "SessionLocal", MockSessionLocal())
    monkeypatch.setattr(base_module, "SessionLocal", MockSessionLocal())
    
    app.dependency_overrides[get_session] = _get_test_session

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
