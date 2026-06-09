"""
AI stream workers — subscribe to events and drive the publishing pipeline:

    listing.created  -> Repo-Intake -> Verification -> Curation (Vitrine Score)

In monolith dev (EVENT_BUS=memory) call `register_handlers()` once at startup
(ai/app.py does this). As separate processes (EVENT_BUS=redis) run this module:

    python -m backend.ai.workers
"""
from __future__ import annotations

import asyncio

from backend.shared.events import bus

from .agents import curation, repo_intake, verification


async def _on_listing_created(event: dict) -> None:
    p = event["payload"]
    lid = p["listing_id"]
    await repo_intake.run(lid, p.get("repo_url"), p.get("readme_text"))
    await verification.run(lid)
    await curation.run(lid)
    # Each step should emit its own event in Phase 2; scaffold chains directly.


async def _on_review_or_update(event: dict) -> None:
    lid = event["payload"].get("listing_id")
    if lid:
        await curation.run(lid)


_REGISTERED = False


def register_handlers() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    bus.subscribe("listing.created", _on_listing_created)
    bus.subscribe("review.created", _on_review_or_update)
    bus.subscribe("listing.updated", _on_review_or_update)
    _REGISTERED = True


async def _main() -> None:
    register_handlers()
    print("[ai.workers] running (redis stream consumer mode). Ctrl-C to stop.")
    while True:  # TODO Phase 2: real XREADGROUP loop when EVENT_BUS=redis
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(_main())
