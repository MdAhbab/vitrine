"""
Shared agent plumbing: load the AGENTS.md section as the system prompt, run the
tool-calling loop, enforce budget, cache by input hash, and log the run.

Scaffold provides a minimal, working `run_agent()` (no multi-tool loop yet) so
agent stubs can call the LLM safely. Phase 2 adds the full tool loop + retries.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.shared.cache import cache, content_hash
from backend.shared.db import SessionLocal
from backend.shared.models import AgentRun

from ..budget import budget
from ..client import LLMResult, client

_AGENTS_MD = Path(__file__).resolve().parents[3] / "AGENTS.md"


def system_prompt_for(section_title: str, fallback: str = "") -> str:
    """Extract an agent's section from AGENTS.md to use as its system prompt.

    Lets the curator edit behaviour by editing AGENTS.md (and, at runtime, the
    admin_configs.system_prompts override — see AGENTS.md principle #8).
    """
    try:
        text = _AGENTS_MD.read_text()
    except OSError:
        return fallback
    m = re.search(rf"(?ms)^##\s.*{re.escape(section_title)}.*?(?=^##\s|\Z)", text)
    return (m.group(0).strip() if m else fallback) or fallback


async def run_agent(agent: str, system: str, user_msg: str, *,
                    listing_id: str | None = None, trigger: str = "api",
                    tools: list | None = None) -> LLMResult:
    key = f"agent:{agent}:{content_hash(system, user_msg)}"
    if cached := await cache.get(key):
        return LLMResult(**cached)

    budget.check()
    result = await client.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        tools=tools,
    )
    budget.record(result.cost_usd)

    async with SessionLocal() as db:
        db.add(AgentRun(agent=agent, listing_id=listing_id, trigger_event=trigger,
                        input_hash=key, model=result.model, tokens_in=result.tokens_in,
                        tokens_out=result.tokens_out, cost_usd=result.cost_usd,
                        status="degraded" if result.stub else "ok"))
        await db.commit()

    await cache.set(key, result.__dict__, ttl=86400)
    return result
