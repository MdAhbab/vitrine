"""Repo-Intake Agent — repo/README -> filled form sheet. See AGENTS.md §1."""
from __future__ import annotations

from backend.shared.form_schema import ai_fillable_keys

from .base import run_agent, system_prompt_for

SYSTEM = system_prompt_for("Repo-Intake Agent",
                           "Fill the listing technical form from the repo/README.")


async def run(listing_id: str, repo_url: str | None = None,
              readme_text: str | None = None) -> dict:
    # TODO Phase 2: heuristic manifest parsing first, then ONE LLM call to fill
    # judgment fields via the write_listing_fields tool; embed for search; emit
    # listing.enriched. Scaffold returns the target field set + a draft note.
    src = repo_url or "(uploaded README)"
    result = await run_agent("repo_intake", SYSTEM,
                             f"Summarize and draft listing fields for: {src}\n\n{readme_text or ''}",
                             listing_id=listing_id, trigger="listing.created")
    return {
        "listing_id": listing_id,
        "fillable_fields": ai_fillable_keys(),
        "draft_summary": result.text,
        "needs_seller_confirmation": ["price", "license"],
        "stub": result.stub,
    }
