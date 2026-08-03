"""
Vector store — semantic search backend.

Embeddings live as JSON float-arrays in `listing_embeddings`; similarity is
cosine computed in Python. That is fine for a boutique catalog (tens–hundreds of
listings) and is portable across SQLite and Postgres.

`text_hash` is the content hash of the embedded text. Callers compare it before
embedding so unchanged content never re-purchases an embedding call.

TODO Phase 2 (Postgres): swap `embedding` to `vector(1536)`, add an HNSW index,
and push similarity into SQL via the `<=>` operator. Until that exists there is
deliberately ONE implementation here — the previous `PgVector` class was a
byte-identical copy of the brute-force one, which made it look as though the
pgvector path were already live.
"""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.models import ListingEmbedding


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class BruteForceVectorStore:
    async def upsert(self, db: AsyncSession, listing_id: str,
                     embedding: list[float], text_hash: str = "") -> None:
        row = await db.get(ListingEmbedding, listing_id)
        if row:
            row.embedding, row.text_hash = embedding, text_hash
        else:
            db.add(ListingEmbedding(listing_id=listing_id, embedding=embedding,
                                    text_hash=text_hash))
        await db.commit()

    async def current_hash(self, db: AsyncSession, listing_id: str) -> str:
        """Hash of the text this listing's stored vector was built from."""
        row = await db.get(ListingEmbedding, listing_id)
        return (row.text_hash or "") if row else ""

    async def search(self, db: AsyncSession, query_vec: list[float],
                     k: int = 20) -> list[tuple[str, float]]:
        rows = (await db.execute(select(ListingEmbedding))).scalars().all()
        scored = [(r.listing_id, cosine(query_vec, r.embedding or [])) for r in rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


def get_vector_store() -> BruteForceVectorStore:
    return BruteForceVectorStore()


vector_store = get_vector_store()
