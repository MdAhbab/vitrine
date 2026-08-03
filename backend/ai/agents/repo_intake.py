"""Repo-Intake Agent — repo/README -> filled form sheet. See AGENTS.md §1."""
from __future__ import annotations

import logging

from backend.shared.cache import content_hash
from backend.shared.form_schema import ai_fillable_keys

from .base import run_agent, system_prompt_for

_log = logging.getLogger("vitrine.agents.repo_intake")

SYSTEM = system_prompt_for("Repo-Intake Agent",
                           "Fill the listing technical form from the repo/README.")


async def run(listing_id: str, repo_url: str | None = None,
              readme_text: str | None = None) -> dict:
    user_msg = f"Listing ID: {listing_id}\n"
    if repo_url:
        user_msg += f"Repository URL: {repo_url}\n"
    if readme_text:
        user_msg += f"Readme Text:\n{readme_text}\n"

    # Without an explicit mandate the model sometimes writes a prose summary
    # claiming the form was filled while never calling the persist tool, so the
    # listing stays empty. Name the tool and the keys it must use.
    user_msg += (
        "\nYou MUST call `write_listing_fields` with this listing's id before you "
        "finish — a prose summary alone does not save anything. Use these field "
        "keys: " + ", ".join(sorted({k.split(".", 1)[-1] for k in ai_fillable_keys()})) +
        ". Also include `description`, `tagline` and `tags` so the storefront "
        "listing renders. Omit any field the repository does not evidence; never "
        "invent one. Only after the tool returns success, summarise what you filled."
    )

    result = await run_agent(
        "repo_intake", SYSTEM, user_msg,
        listing_id=listing_id, trigger="listing.created",
        tools=["fetch_repo_tree", "fetch_file", "read_readme", "detect_stack", "write_listing_fields"]
    )
    
    from backend.shared.db import SessionLocal
    from backend.shared.models import Listing
    from backend.ai.vectorstore import vector_store
    
    from sqlalchemy import select
    from backend.shared.models import ListingField

    fields_written = 0
    async with SessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        fields_written = len((await db.execute(
            select(ListingField).where(ListingField.listing_id == listing_id)
        )).scalars().all())
        if listing:
            # AGENTS.md §1.4 embeds name + tagline + description + TAGS; tags
            # were being dropped, which cost tag-based semantic recall.
            tags = " ".join(listing.tags or []) if isinstance(listing.tags, list) else ""
            text_to_embed = " ".join(
                p for p in (listing.name, listing.tagline, listing.description, tags) if p
            ).strip()
            # Skip the call entirely when the text is unchanged. Intake re-runs on
            # listing.created / .updated / manual retries, and each one used to
            # re-purchase an identical embedding — the `text_hash` column existed
            # for exactly this and was never populated.
            new_hash = content_hash(text_to_embed)
            if text_to_embed and new_hash != await vector_store.current_hash(db, listing_id):
                from backend.ai.tools import embed_text
                try:
                    emb_res = await embed_text(text_to_embed)
                    if "embedding" in emb_res:
                        await vector_store.upsert(db, listing_id, emb_res["embedding"],
                                                  text_hash=new_hash)
                except Exception:
                    _log.exception("embedding failed for listing %s", listing_id)

    return {
        "listing_id": listing_id,
        "fillable_fields": ai_fillable_keys(),
        "draft_summary": result.text,
        # Lets the seller UI tell "enriched" apart from "the agent talked but
        # saved nothing" instead of both looking like success.
        "fields_written": fields_written,
        "enriched": fields_written > 0,
        "needs_seller_confirmation": ["price", "license"],
        "stub": result.stub,
    }
