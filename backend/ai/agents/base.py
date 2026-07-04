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

from ..budget import BudgetExceeded, budget
from ..client import LLMResult, client

_AGENTS_MD = Path(__file__).resolve().parents[3] / "AGENTS.md"


_PROMPT_KEY_MAP = {
    "Repo-Intake Agent": "repoIntake",
    "Listing Verification Agent": "verification",
    "Buyer Concierge Agent": "concierge",
    "Pricing & Pitch Agent": "pricingAgent",
    "Buyer Representative Agent": "buyerRep",
    "Feature Cost Estimator Agent": "featureEstimator",
    "Curation & Ranking Agent": "curation",
}

_AGENT_SECTION = {
    "repo_intake": "Repo-Intake Agent",
    "verification": "Listing Verification Agent",
    "concierge": "Buyer Concierge Agent",
    "pricing": "Pricing & Pitch Agent",
    "negotiator": "Buyer Representative Agent",
    "feature_estimator": "Feature Cost Estimator Agent",
    "curation": "Curation & Ranking Agent",
}


def system_prompt_for(section_title: str, fallback: str = "") -> str:
    """Extract an agent's section from AGENTS.md (file fallback at import time)."""
    try:
        text = _AGENTS_MD.read_text()
    except OSError:
        return fallback
    m = re.search(rf"(?ms)^##\s.*{re.escape(section_title)}.*?(?=^##\s|\Z)", text)
    return (m.group(0).strip() if m else fallback) or fallback


async def resolve_system_prompt(agent: str, system: str) -> str:
    """Apply admin_configs.system_prompts override at runtime (AGENTS.md §8)."""
    title = _AGENT_SECTION.get(agent)
    if not title:
        return system
    key = _PROMPT_KEY_MAP.get(title)
    if not key:
        return system
    try:
        from backend.shared.models import AdminConfig
        async with SessionLocal() as db:
            row = await db.get(AdminConfig, "system_prompts")
            if row and isinstance(row.value, dict):
                val = row.value.get(key, "")
                if val and str(val).strip():
                    return str(val).strip()
    except Exception:
        pass
    return system


async def run_agent(agent: str, system: str, user_msg: str, *,
                     listing_id: str | None = None, trigger: str = "api",
                     tools: list | None = None) -> LLMResult:
    system = await resolve_system_prompt(agent, system)
    key = f"agent:{agent}:{content_hash(system, user_msg)}"
    if cached := await cache.get(key):
        return LLMResult(**cached)

    try:
        budget.check()
    except BudgetExceeded:
        degraded = LLMResult(
            text="[Budget exceeded — heuristic-only mode. Needs human review.]",
            stub=True,
            model="budget-cap",
        )
        async with SessionLocal() as db:
            db.add(AgentRun(agent=agent, listing_id=listing_id, trigger_event=trigger,
                            input_hash=key, model="budget-cap", tokens_in=0,
                            tokens_out=0, cost_usd=0.0, status="degraded"))
            await db.commit()
        return degraded

    openai_tools = None
    if tools:
        from ..tools import REGISTRY
        openai_tools = []
        for tname in tools:
            if isinstance(tname, str):
                if tname in REGISTRY:
                    openai_tools.append(REGISTRY[tname].openai_schema())
            elif hasattr(tname, "openai_schema"):
                openai_tools.append(tname.openai_schema())
            else:
                openai_tools.append(tname)
                
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]
    
    total_in = 0
    total_out = 0
    total_cost = 0.0
    final_text = ""
    is_stub = False
    model_used = ""
    
    for i in range(5):
        result = await client.chat(messages, tools=openai_tools)
        total_in += result.tokens_in
        total_out += result.tokens_out
        total_cost += result.cost_usd
        is_stub = is_stub or result.stub
        model_used = result.model
        
        if result.stub or not result.tool_calls:
            final_text = result.text
            break
            
        messages.append({
            "role": "assistant",
            "content": result.text or None,
            "tool_calls": result.tool_calls
        })
        
        from ..tools import invoke
        import json
        for tc in result.tool_calls:
            tc_id = tc["id"]
            tc_name = tc["function"]["name"]
            tc_args = json.loads(tc["function"]["arguments"])
            
            try:
                output = await invoke(tc_name, tc_args)
            except Exception as e:
                output = {"error": str(e)}
                
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "name": tc_name,
                "content": json.dumps(output)
            })
    else:
        # Loop exhausted while still calling tools -> force one final text answer
        # (no tools) so callers never get an empty draft/summary.
        if not is_stub:
            final = await client.chat(messages, tools=None)
            total_in += final.tokens_in
            total_out += final.tokens_out
            total_cost += final.cost_usd
            final_text = final.text
            model_used = final.model

    budget.record(total_cost)
    
    final_result = LLMResult(
        text=final_text,
        tool_calls=[],
        tokens_in=total_in,
        tokens_out=total_out,
        model=model_used,
        stub=is_stub
    )
    
    async with SessionLocal() as db:
        db.add(AgentRun(agent=agent, listing_id=listing_id, trigger_event=trigger,
                        input_hash=key, model=model_used, tokens_in=total_in,
                        tokens_out=total_out, cost_usd=total_cost,
                        status="degraded" if is_stub else "ok"))
        await db.commit()

    await cache.set(key, final_result.__dict__, ttl=86400)
    return final_result


def parse_json(text: str) -> dict | None:
    """Best-effort parse of a model's JSON reply (tolerates ```json fences)."""
    import json as _json
    import re

    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t[3:]
        if t[:4].lower() == "json":
            t = t[4:]
        if "```" in t:
            t = t[: t.rindex("```")]
        t = t.strip()
    try:
        return _json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return _json.loads(m.group(0))
            except Exception:
                return None
    return None


async def run_json(agent: str, system: str, user_msg: str, *,
                   listing_id: str | None = None, trigger: str = "api") -> tuple[dict | None, bool]:
    """One structured (JSON-mode) model call with budget + run logging.

    Returns (parsed_dict_or_None, is_stub). Used by agents that need coherent
    structured output (Pricing, Feature estimator) instead of a tool loop.
    """
    from backend.shared.settings import settings

    system = await resolve_system_prompt(agent, system)
    try:
        budget.check()
    except BudgetExceeded:
        return None, True

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]
    parsed: dict | None = None
    result = None
    # Schema-reject -> retry, per AGENTS.md §0.1 (max AGENT_MAX_RETRIES).
    for attempt in range(1 + max(0, settings.AGENT_MAX_RETRIES)):
        result = await client.chat(messages, json_mode=True)
        budget.record(result.cost_usd)
        async with SessionLocal() as db:
            db.add(AgentRun(agent=agent, listing_id=listing_id, trigger_event=trigger,
                            input_hash="", model=result.model, tokens_in=result.tokens_in,
                            tokens_out=result.tokens_out, cost_usd=result.cost_usd,
                            status="degraded" if result.stub else "ok"))
            await db.commit()
        if result.stub:
            return None, True
        parsed = parse_json(result.text)
        if parsed is not None:
            return parsed, False
        # Nudge the model once with its own invalid output before retrying.
        messages.append({"role": "assistant", "content": result.text})
        messages.append({"role": "user",
                         "content": "That was not valid JSON. Reply with ONLY the JSON object."})
    return None, False
