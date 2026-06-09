"""Repo-Intake Agent — repo/README -> filled form sheet. See AGENTS.md §1."""
from __future__ import annotations

from backend.shared.form_schema import ai_fillable_keys

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Repo-Intake Agent",
                           "Fill the listing technical form from the repo/README.")


async def run(listing_id: str, repo_url: str | None = None,
              readme_text: str | None = None) -> dict:
    user_msg = f"Listing ID: {listing_id}\n"
    if repo_url:
        user_msg += f"Repository URL: {repo_url}\n"
    if readme_text:
        user_msg += f"Readme Text:\n{readme_text}\n"
        
    result = await run_agent(
        "repo_intake", SYSTEM, user_msg,
        listing_id=listing_id, trigger="listing.created",
        tools=["fetch_repo_tree", "fetch_file", "read_readme", "detect_stack", "write_listing_fields"]
    )
    
    from backend.shared.db import SessionLocal
    from backend.shared.models import Listing
    from backend.ai.vectorstore import vector_store
    
    async with SessionLocal() as db:
        listing = await db.get(Listing, listing_id)
        if listing:
            text_to_embed = f"{listing.name} {listing.tagline} {listing.description}"
            from backend.ai.tools import embed_text
            try:
                emb_res = await embed_text(text_to_embed)
                if "embedding" in emb_res:
                    await vector_store.upsert(db, listing_id, emb_res["embedding"])
            except Exception:
                pass
                
    return {
        "listing_id": listing_id,
        "fillable_fields": ai_fillable_keys(),
        "draft_summary": result.text,
        "needs_seller_confirmation": ["price", "license"],
        "stub": result.stub,
    }
