"""
Vector store abstraction — semantic search backend.

  * SqliteBruteForce (now): embeddings live as JSON float-arrays in
    listing_embeddings; similarity is cosine computed in Python. Fine for a
    demo catalog (tens–hundreds of listings).
  * PgVector (later): embeddings as pgvector vector(1536) with an HNSW/IVFFlat
    index; similarity via the `<=>` operator in SQL. TODO Phase 2.

Chosen automatically by the DB dialect (settings.is_sqlite).
"""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.models import ListingEmbedding
from backend.shared.settings import settings


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class SqliteBruteForce:
    async def upsert(self, db: AsyncSession, listing_id: str,
                     embedding: list[float], text_hash: str = "") -> None:
        row = await db.get(ListingEmbedding, listing_id)
        if row:
            row.embedding, row.text_hash = embedding, text_hash
        else:
            db.add(ListingEmbedding(listing_id=listing_id, embedding=embedding,
                                    text_hash=text_hash))
        await db.commit()

    async def search(self, db: AsyncSession, query_vec: list[float],
                     k: int = 20) -> list[tuple[str, float]]:
        rows = (await db.execute(select(ListingEmbedding))).scalars().all()
        scored = [(r.listing_id, cosine(query_vec, r.embedding or [])) for r in rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


class PgVector:
    async def upsert(self, db: AsyncSession, listing_id: str,
                     embedding: list[float], text_hash: str = "") -> None:
        row = await db.get(ListingEmbedding, listing_id)
        if row:
            row.embedding, row.text_hash = embedding, text_hash
        else:
            db.add(ListingEmbedding(listing_id=listing_id, embedding=embedding,
                                    text_hash=text_hash))
        await db.commit()

    async def search(self, db: AsyncSession, query_vec: list[float],
                     k: int = 20) -> list[tuple[str, float]]:
        rows = (await db.execute(select(ListingEmbedding))).scalars().all()
        scored = [(r.listing_id, cosine(query_vec, r.embedding or [])) for r in rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


def get_vector_store():
    return SqliteBruteForce() if settings.is_sqlite else PgVector()


vector_store = get_vector_store()
