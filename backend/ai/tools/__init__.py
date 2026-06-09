"""
Tool registry — typed functions the agents may call (OpenAI tool calling).

Each tool = a name + JSON schema (for the model) + an async handler. Agents
declare which tools they may use (see AGENTS.md §6). Scaffold registers the
deterministic tools as stubs; flesh out handlers in Phase 2.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON schema
    handler: Callable[..., Awaitable]

    def openai_schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.parameters}}


REGISTRY: dict[str, Tool] = {}


def register(name: str, description: str, parameters: dict):
    def deco(fn: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        REGISTRY[name] = Tool(name, description, parameters, fn)
        return fn
    return deco


async def invoke(name: str, args: dict):
    tool = REGISTRY.get(name)
    if not tool:
        raise KeyError(f"Unknown tool: {name}")
    return await tool.handler(**args)


# ── stub tools (Phase 2: implement real handlers) ───────────────────────
@register("fetch_repo_tree", "List a public GitHub repo's file tree",
          {"type": "object", "properties": {"repo_url": {"type": "string"}},
           "required": ["repo_url"]})
async def fetch_repo_tree(repo_url: str) -> dict:
    return {"repo_url": repo_url, "tree": [], "todo": "implement via GitHub API/httpx"}


@register("detect_stack", "Detect languages/frameworks/tests from manifests",
          {"type": "object", "properties": {"files": {"type": "array"}},
           "required": ["files"]})
async def detect_stack(files: list) -> dict:
    return {"languages": [], "frameworks": [], "todo": "parse package.json/pyproject/etc."}


@register("check_demo_health", "Ping a preview URL for liveness",
          {"type": "object", "properties": {"url": {"type": "string"}},
           "required": ["url"]})
async def check_demo_health(url: str) -> dict:
    return {"url": url, "health": "live", "todo": "real HTTP check (hosting service)"}


# TODO Phase 2: read_readme, fetch_file, embed_text, semantic_search,
# apply_filters, get_listing, compare_products, recommend_similar,
# cross_check_claims, license_lookup, market_comps, suggest_tiers, draft_copy,
# compute_features, bayesian_rating, vision_score_ui, rank_and_section,
# write_listing_fields, submit_verdict, flag_listing.  (See AGENTS.md §6.)
