r"""Vitrine AI smoke test — verifies every provider, then every agent.

Run from the repo root with the project venv:
    .\.venv\Scripts\python.exe -m backend.scripts.check_ai

Exercises the real providers, so it costs a few fractions of a cent.
"""
from __future__ import annotations

import asyncio

from backend.shared.settings import settings

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[tuple[str, str, str]] = []


def line(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    mark = {"PASS": "[ok]  ", "FAIL": "[FAIL]", "WARN": "[warn]"}[status]
    print(f"{mark} {name:<34} {detail}")


def mask(key: str) -> str:
    return f"{key[:6]}...{key[-4:]} ({len(key)} chars)" if len(key) > 12 else "set (short!)"


async def main() -> int:
    from backend.ai.client import client, EMBED_DIM, _stub_embedding

    print("\n== 1. Configured providers ==")
    if settings.OPENAI_API_KEY:
        line(PASS, "OPENAI_API_KEY present", mask(settings.OPENAI_API_KEY))
    else:
        line(WARN, "OPENAI_API_KEY", "empty")
    if settings.GEMINI_API_KEY:
        line(PASS, "GEMINI_API_KEY present", mask(settings.GEMINI_API_KEY))
    else:
        line(WARN, "GEMINI_API_KEY", "empty")

    clients = await client._resolved_clients()
    if not clients:
        line(FAIL, "resolved provider clients", "none — every AI call will stub")
        return 1
    line(PASS, "resolved provider clients",
         " -> ".join(p for _, p in clients) + "  (tried in this order)")

    # 2. Each provider in isolation, so one working key can't mask a broken one.
    print("\n== 2. Each provider, isolated ==")
    for c, provider in clients:
        models = client._get_provider_models(provider, None)
        for m in models:
            try:
                resp = await asyncio.wait_for(
                    c.chat.completions.create(
                        model=m,
                        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
                    ),
                    timeout=30,
                )
                txt = (resp.choices[0].message.content or "").strip()[:30]
                line(PASS, f"{provider}: {m}", f'-> "{txt}"')
                break
            except Exception as e:
                err = str(e).split("\n")[0][:110]
                line(WARN, f"{provider}: {m}", f"{type(e).__name__}: {err}")
        else:
            line(FAIL, f"{provider}: all models failed",
                 "this provider contributes nothing to the chain")

    # 3. The chat path the agents actually use.
    print("\n== 3. Shared client paths ==")
    r = await client.chat([{"role": "user", "content": "Say: ready"}])
    line(FAIL if r.stub else PASS, "client.chat (plain)",
         f"stub={r.stub} model={r.model} tokens={r.tokens_in}/{r.tokens_out} ${r.cost_usd:.6f}")

    rj = await client.chat(
        [{"role": "user", "content": 'Return JSON {"ok":true}'}], json_mode=True
    )
    line(FAIL if rj.stub else PASS, "client.chat (json_mode)",
         f"stub={rj.stub} model={rj.model} -> {rj.text.strip()[:40]}")

    vec = await client.embed("vitrine smoke test")
    is_stub_vec = vec == _stub_embedding("vitrine smoke test")
    line(FAIL if is_stub_vec else PASS, "client.embed",
         f"dim={len(vec)} (want {EMBED_DIM}) "
         + ("STUB — semantic search is fake" if is_stub_vec else "real vector"))

    # 4. Vision — the one multimodal call, used by the Vitrine Score.
    print("\n== 4. Vision ==")
    from backend.ai.tools import vision_score_ui
    from backend.shared.db import SessionLocal
    from backend.shared.models import Listing
    from sqlalchemy import select

    async with SessionLocal() as db:
        listing = (
            await db.execute(select(Listing).where(Listing.status == "live").limit(1))
        ).scalars().first()
        lid, cover = (listing.id, listing.cover) if listing else (None, None)
        lname = listing.name if listing else "?"

    if cover:
        v = await vision_score_ui(cover)
        src = v.get("source")
        line(PASS if src == "vision" else WARN, "vision_score_ui",
             f"source={src} score={v.get('ui_score')} "
             + ("" if src == "vision" else "(fell back to heuristic)"))
    else:
        line(WARN, "vision_score_ui", "no live listing with a cover image")

    if not lid:
        print("\nNo live listing found — skipping agent runs.")
        return 0

    # 5. Every agent, against a real seeded listing.
    print(f"\n== 5. Agents (listing: {lname}) ==")
    from backend.ai.agents import pricing, verification, curation, feature_estimator, concierge

    p = await pricing.run(lid)
    line(FAIL if p.get("stub") else PASS, "Pricing & Pitch",
         f"tagline={str(p.get('tagline'))[:46]!r}")

    v = await verification.run(lid)
    line(PASS if v.get("verdict") else FAIL, "Verification",
         f"verdict={v.get('verdict')} confidence={v.get('confidence')}")

    c = await curation.run(lid)
    line(PASS if c.get("vitrine_score") is not None else FAIL, "Curation & Ranking",
         f"vitrine_score={c.get('vitrine_score')}")

    f = await feature_estimator.estimate(lid, "Add SSO with Google and Microsoft, plus an audit log.")
    line(FAIL if f.get("stub") else PASS, "Feature Cost Estimator",
         f"charge=${f.get('estimated_charge')} "
         f"range={f.get('range_low')}-{f.get('range_high')}")

    chunks = []
    async for ev in concierge.stream("React dashboard with Stripe under $40"):
        chunks.append(ev)
    # concierge yields {"type": "token", "text": ...}, then a final {"type": "done"}.
    text = "".join(e.get("text", "") for e in chunks if isinstance(e, dict))
    line(PASS if text.strip() else FAIL, "Buyer Concierge (SSE)",
         f"{len(chunks)} events, {len(text)} chars -> {text.strip()[:44]!r}")

    print("\n   Repo-Intake and Buyer Representative need a repo URL / live chat row;")
    print("   drive those from the UI (see the notes printed below).")

    print("\n== Summary ==")
    bad = [r for r in results if r[0] == FAIL]
    warn = [r for r in results if r[0] == WARN]
    print(f"   {len(results) - len(bad) - len(warn)} passed, {len(warn)} warnings, {len(bad)} failed")
    for _, n, d in bad:
        print(f"   FAILED: {n} — {d}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
