"""
AI Orchestrator service — interactive agent endpoints + AI-owned admin.

Endpoints (see backend.md §11):
  POST /ai/intake            run Repo-Intake synchronously
  POST /ai/concierge  (SSE)  Buyer Concierge streamed discovery
  POST /ai/pricing           Pricing & Pitch suggestions
  POST /ai/negotiate         Buyer Rep next message
  POST /ai/estimate-feature  Feature cost estimate
  GET/PATCH /admin/config    runtime config (prompts, keys, fees, flags)
  GET  /admin/agent-runs     cost meter / observability
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.shared.db import get_session
from backend.shared.models import AdminConfig, AgentRun, Listing, Chat, User
from backend.shared.schemas.ai import (
    ConciergeIn,
    EstimateFeatureIn,
    NegotiateIn,
    PricingIn,
)
from backend.shared.schemas.listing import IntakeIn
from backend.shared.crypto import encrypt_value
from backend.shared.security import Principal, ai_rate_limit, current_user, optional_user, require_role

from .agents import concierge, feature_estimator, negotiator, pricing, repo_intake
from .budget import budget
from .workers import register_handlers

router = APIRouter(tags=["ai"])


@router.post("/ai/intake", dependencies=[Depends(ai_rate_limit)])
async def intake(body: IntakeIn, listing_id: str,
                 user: Principal = Depends(require_role("seller", "admin")),
                 db: AsyncSession = Depends(get_session)) -> dict:
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return await repo_intake.run(listing_id, body.repo_url, body.readme_text)


@router.post("/ai/concierge", dependencies=[Depends(ai_rate_limit)])
async def concierge_stream(body: ConciergeIn, user: Principal | None = Depends(optional_user)):
    async def gen():
        async for chunk in concierge.stream(body.query, body.history):
            yield {"data": json.dumps(chunk)}
    return EventSourceResponse(gen())


@router.post("/ai/pricing", dependencies=[Depends(ai_rate_limit)])
async def pricing_suggest(body: PricingIn,
                          user: Principal = Depends(require_role("seller", "admin"))) -> dict:
    return await pricing.run(body.listing_id)


@router.post("/ai/negotiate", dependencies=[Depends(ai_rate_limit)])
async def negotiate(body: NegotiateIn, user: Principal = Depends(current_user),
                    db: AsyncSession = Depends(get_session)) -> dict:
    chat = await db.get(Chat, body.chat_id)
    if not chat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    if not chat.is_agent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not an agent negotiation chat")
    if chat.buyer_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the buyer can dispatch the AI rep")
    return await negotiator.next_message(body.chat_id)


@router.post("/ai/estimate-feature", dependencies=[Depends(ai_rate_limit)])
async def estimate_feature(body: EstimateFeatureIn,
                           user: Principal = Depends(current_user)) -> dict:
    return await feature_estimator.estimate(body.listing_id, body.description)


# ── admin (AI-owned) ────────────────────────────────────────────────────
def _mask(key: str) -> str:
    return key if len(key) < 8 else key[:6] + "••••" + key[-3:]


@router.get("/admin/config")
async def get_config(user: Principal = Depends(require_role("admin")),
                     db: AsyncSession = Depends(get_session)) -> dict:
    rows = {r.key: r.value for r in (await db.execute(select(AdminConfig))).scalars()}
    api_keys = [{**k, "key": "••••••••" if k.get("key") else ""} for k in rows.get("api_keys", [])]
    # Shape mirrors frontend AdminConfig; missing keys fall back to {} / [].
    return {
        "systemPrompts": rows.get("system_prompts", {}),
        "apiKeys": api_keys,
        "flags": rows.get("flags", {}),
        "fees": rows.get("fees", {}),
        "escrow": rows.get("escrow", {}),
        "branding": rows.get("branding", {}),
        "notes": rows.get("notes", ""),
    }


@router.patch("/admin/config")
async def patch_config(patch: dict, user: Principal = Depends(require_role("admin")),
                       db: AsyncSession = Depends(get_session)) -> dict:
    # map camelCase frontend keys -> admin_configs row keys
    keymap = {"systemPrompts": "system_prompts", "apiKeys": "api_keys",
              "flags": "flags", "fees": "fees", "escrow": "escrow",
              "branding": "branding", "notes": "notes"}
    for fe_key, value in patch.items():
        row_key = keymap.get(fe_key, fe_key)
        stored = value
        is_encrypted = False
        if row_key == "api_keys" and isinstance(value, list):
            is_encrypted = True
            stored = []
            existing = (await db.get(AdminConfig, "api_keys"))
            old_by_id = {}
            if existing and isinstance(existing.value, list):
                for k in existing.value:
                    if isinstance(k, dict) and k.get("id"):
                        old_by_id[k["id"]] = k.get("key", "")
            for k in value:
                if not isinstance(k, dict):
                    continue
                entry = dict(k)
                raw = entry.get("key", "")
                if raw and "••••" not in raw:
                    entry["key"] = encrypt_value(raw)
                elif entry.get("id") in old_by_id:
                    entry["key"] = old_by_id[entry["id"]]
                stored.append(entry)
        row = await db.get(AdminConfig, row_key)
        if row:
            row.value = stored
            row.is_encrypted = is_encrypted or row.is_encrypted
        else:
            db.add(AdminConfig(key=row_key, value=stored, is_encrypted=is_encrypted))
    await db.commit()
    return {"ok": True}


@router.get("/admin/agent-runs")
async def agent_runs(user: Principal = Depends(require_role("admin")),
                     db: AsyncSession = Depends(get_session)) -> dict:
    rows = (await db.execute(
        select(AgentRun).order_by(AgentRun.created_at.desc()).limit(100))).scalars().all()
    return {
        "spent_today_usd": round(budget.spent_today, 4),
        "runs": [{"agent": r.agent, "model": r.model, "cost_usd": r.cost_usd,
                  "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                  "status": r.status, "ts": int(r.created_at.timestamp() * 1000)}
                 for r in rows],
    }


@router.get("/admin/verification-queue", response_model=list[dict])
async def verification_queue(user: Principal = Depends(require_role("admin")),
                             db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(Listing).where(Listing.status.in_(["review", "flagged", "enriching", "draft"]))
    rows = (await db.execute(stmt)).scalars().all()
    res = []
    for r in rows:
        seller = await db.get(User, r.owner_id)
        res.append({
            "id": r.id,
            "name": r.name,
            "cover": r.cover or "",
            "category": r.category,
            "price": r.price_cents / 100,
            "framework": r.framework or "",
            "status": r.status,
            "seller": {"name": seller.display_name if seller else "Unknown"}
        })
    return res


@router.post("/admin/listings/{listing_id}/decision")
async def admin_decision(listing_id: str, body: dict,
                         user: Principal = Depends(require_role("admin")),
                         db: AsyncSession = Depends(get_session)) -> dict:
    verdict = body.get("verdict")
    from fastapi import HTTPException
    if verdict not in ["approve", "reject"]:
        raise HTTPException(400, "Verdict must be approve or reject")
        
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
        
    listing.status = "live" if verdict == "approve" else "rejected"
    db.add(listing)
    await db.commit()
    return {"id": listing.id, "status": listing.status}


@router.get("/admin/chats", response_model=list[dict])
async def admin_chats(user: Principal = Depends(require_role("admin")),
                      db: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(Chat).order_by(Chat.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    res = []
    for c in rows:
        listing = await db.get(Listing, c.listing_id)
        buyer = await db.get(User, c.buyer_id)
        seller = await db.get(User, c.seller_id)
        res.append({
            "id": c.id,
            "productId": c.listing_id,
            "productName": listing.name if listing else "",
            "productCover": (listing.cover or "") if listing else "",
            "buyerId": c.buyer_id,
            "buyerName": buyer.display_name if buyer else "",
            "sellerId": c.seller_id,
            "sellerName": seller.display_name if seller else "",
            "isAgent": c.is_agent,
            "agentBudget": (c.agent_budget_cents / 100) if c.agent_budget_cents else None,
            "status": c.status,
            "unreadFor": c.unread_for or [],
            "createdAt": int(c.created_at.timestamp() * 1000),
        })
    return res


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_handlers()  # wire event-driven pipeline in monolith mode
    yield


app = FastAPI(title="Vitrine ai-orchestrator", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "ai-orchestrator"}
