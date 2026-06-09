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
