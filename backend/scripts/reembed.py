r"""Re-embed the whole catalogue with the currently-configured provider.

    .\.venv\Scripts\python.exe -m backend.scripts.reembed

Why this is needed: a vector is only comparable to other vectors from the same
embedding model. Every stored vector was written by `_stub_embedding` while no
provider worked, so a real query vector scored against them is noise. Switching
embedding provider (stub -> Ollama, or Ollama -> OpenAI) means rewriting all of
them, not just the query side.

Uses the same text composition as the Repo-Intake agent, so the vectors this
writes are identical to what a normal intake run would produce.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from backend.ai.client import client, _stub_embedding
from backend.ai.vectorstore import vector_store
from backend.shared.db import SessionLocal
from backend.shared.models import Listing
from backend.shared.cache import content_hash


async def main() -> int:
    async with SessionLocal() as db:
        listings = (await db.execute(select(Listing))).scalars().all()
        print(f"{len(listings)} listings to embed\n")

        done = skipped = stubbed = 0
        for listing in listings:
            tags = " ".join(listing.tags or []) if listing.tags else ""
            text = " ".join(
                p for p in (listing.name, listing.tagline, listing.description, tags) if p
            ).strip()
            if not text:
                skipped += 1
                continue

            vec = await client.embed(text)
            # A stub vector must never be persisted: it would look like a real
            # row while poisoning every future comparison against it.
            if vec == _stub_embedding(text):
                stubbed += 1
                print(f"  STUB  {listing.name} — no embedding provider reachable")
                continue

            await vector_store.upsert(db, listing.id, vec, text_hash=content_hash(text))
            done += 1
            print(f"  ok    {listing.name}  (dim {len(vec)})")

        print(f"\n{done} embedded, {skipped} skipped (no text), {stubbed} stubbed")
        if stubbed:
            print("Stubbed rows were left untouched — fix the provider and re-run.")
        return 1 if stubbed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
