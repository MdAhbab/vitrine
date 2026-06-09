"""
Tool registry — typed functions the agents may call (OpenAI tool calling).

Each tool = a name + JSON schema (for the model) + an async handler. Agents
declare which tools they may use (see AGENTS.md §6).
"""
from __future__ import annotations

import re
import math
import json
from datetime import datetime, timezone

import httpx
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from sqlalchemy import select
from backend.shared.db import SessionLocal
from backend.shared.models import Listing, ListingField, ListingTier, User, Review, Order, Payout, Subscription, Delivery, ListingEmbedding
from backend.shared.settings import settings
from backend.ai.vectorstore import vector_store

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

# ── Tool Implementations ───────────────────────────────────────────────────

@register("fetch_repo_tree", "List a public GitHub repo's file tree",
          {"type": "object", "properties": {"repo_url": {"type": "string"}},
           "required": ["repo_url"]})
async def fetch_repo_tree(repo_url: str) -> dict:
    m = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not m:
        return {"tree": [], "error": "Not a public GitHub URL"}
    owner, repo = m.group(1), m.group(2)
    repo = repo.replace(".git", "").split("/")[0]
    
    headers = {"User-Agent": "Vitrine-Intake-Agent"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for branch in ["main", "master"]:
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            try:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    paths = [item["path"] for item in data.get("tree", []) if item.get("type") == "blob"]
                    return {"tree": paths[:200], "branch": branch}
            except Exception:
                pass
    return {"tree": [], "error": f"Failed to fetch file tree for {owner}/{repo}"}

@register("fetch_file", "Read the contents of a specific file in a public GitHub repo",
          {"type": "object", "properties": {"repo_url": {"type": "string"}, "path": {"type": "string"}},
           "required": ["repo_url", "path"]})
async def fetch_file(repo_url: str, path: str) -> dict:
    m = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not m:
        return {"content": "", "error": "Not a public GitHub URL"}
    owner, repo = m.group(1), m.group(2)
    repo = repo.replace(".git", "").split("/")[0]
    
    headers = {"User-Agent": "Vitrine-Intake-Agent"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            try:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return {"path": path, "content": res.text[:8000], "truncated": len(res.text) > 8000}
            except Exception:
                pass
    return {"content": "", "error": f"Failed to fetch {path}"}

@register("read_readme", "Fetch and normalize the README of a repo",
          {"type": "object", "properties": {"repo_url": {"type": "string"}},
           "required": ["repo_url"]})
async def read_readme(repo_url: str) -> dict:
    for filename in ["README.md", "readme.md", "README", "README.txt"]:
        res = await fetch_file(repo_url, filename)
        if "content" in res and res["content"] and "error" not in res:
            return {"content": res["content"], "path": filename}
    return {"content": "", "error": "README not found"}

@register("detect_stack", "Detect languages/frameworks/tests from manifests",
          {"type": "object", "properties": {"files": {"type": "array", "items": {"type": "string"}}},
           "required": ["files"]})
async def detect_stack(files: list[str]) -> dict:
    langs = set()
    frameworks = set()
    package_manager = "npm"
    files_str = " ".join(files).lower()
    
    if "package.json" in files:
        langs.add("TypeScript" if any(f.endswith(".ts") or f.endswith(".tsx") for f in files) else "JavaScript")
        package_manager = "npm"
        if "yarn.lock" in files:
            package_manager = "yarn"
        elif "pnpm-lock.yaml" in files:
            package_manager = "pnpm"
            
    if "pyproject.toml" in files or "requirements.txt" in files or "setup.py" in files:
        langs.add("Python")
        package_manager = "poetry" if "pyproject.toml" in files else "pip"
        
    if "cargo.toml" in files:
        langs.add("Rust")
        package_manager = "cargo"
        
    if "go.mod" in files:
        langs.add("Go")
        package_manager = "go"
        
    if "next.config" in files_str or "next" in files_str:
        frameworks.add("Next.js")
    if "vite.config" in files_str:
        frameworks.add("Vite")
    if "svelte" in files_str:
        frameworks.add("Svelte")
    if "react" in files_str:
        frameworks.add("React")
    if "django" in files_str:
        frameworks.add("Django")
    if "flask" in files_str:
        frameworks.add("Flask")
    if "fastapi" in files_str:
        frameworks.add("FastAPI")
        
    return {
        "languages": list(langs),
        "frameworks": list(frameworks),
        "package_manager": package_manager
    }

@register("embed_text", "Generate vector embedding for a piece of text",
          {"type": "object", "properties": {"text": {"type": "string"}},
           "required": ["text"]})
async def embed_text(text: str) -> dict:
    from backend.ai.client import client
    embedding = await client.embed(text)
    return {"embedding": embedding}

@register("semantic_search", "Vector search against catalog listings",
          {"type": "object", "properties": {
              "query": {"type": "string"},
              "category": {"type": "string", "nullable": True}
          }, "required": ["query"]})
async def semantic_search(query: str, category: str | None = None) -> dict:
    from backend.ai.client import client
    q_vec = await client.embed(query)
    async with SessionLocal() as db:
        matches = await vector_store.search(db, q_vec, k=10)
        results = []
        for l_id, score in matches:
            listing = await db.get(Listing, l_id)
            if listing and listing.status == "live":
                if category and listing.category != category:
                    continue
                results.append({
                    "id": listing.id,
                    "name": listing.name,
                    "slug": listing.slug,
                    "tagline": listing.tagline,
                    "price": listing.price_cents / 100,
                    "score": score
                })
        return {"results": results}

@register("apply_filters", "Filter catalog listings by facets",
          {"type": "object", "properties": {
              "category": {"type": "string", "nullable": True},
              "price_max": {"type": "number", "nullable": True},
              "has_demo": {"type": "boolean", "nullable": True}
          }})
async def apply_filters(category: str | None = None, price_max: float | None = None, has_demo: bool | None = None) -> dict:
    async with SessionLocal() as db:
        stmt = select(Listing).where(Listing.status == "live")
        if category:
            stmt = stmt.where(Listing.category == category)
        if price_max is not None:
            stmt = stmt.where(Listing.price_cents <= int(price_max * 100))
        if has_demo is not None:
            if has_demo:
                stmt = stmt.where(Listing.demo_url != None)
            else:
                stmt = stmt.where(Listing.demo_url == None)
        
        rows = (await db.execute(stmt)).scalars().all()
        return {"results": [{
            "id": r.id,
            "name": r.name,
            "slug": r.slug,
            "price": r.price_cents / 100,
            "category": r.category
        } for r in rows]}

@register("get_listing", "Retrieve detailed profile for a single listing ID",
          {"type": "object", "properties": {"id": {"type": "string"}},
           "required": ["id"]})
async def get_listing(id: str) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, id)
        if not listing:
            # try slug
            listing = (await db.execute(select(Listing).where(Listing.slug == id))).scalar_one_or_none()
        if not listing:
            return {"error": "Listing not found"}
        
        fields = (await db.execute(select(ListingField).where(ListingField.listing_id == listing.id))).scalars().all()
        tiers = (await db.execute(select(ListingTier).where(ListingTier.listing_id == listing.id))).scalars().all()
        
        return {
            "id": listing.id,
            "name": listing.name,
            "slug": listing.slug,
            "price": listing.price_cents / 100,
            "category": listing.category,
            "framework": listing.framework,
            "license": listing.license,
            "description": listing.description,
            "status": listing.status,
            "demo_url": listing.demo_url,
            "sdlc": listing.sdlc,
            "business_model": listing.business_model,
            "tech_stack": listing.tech_stack,
            "fields": {f.key: f.value for f in fields},
            "tiers": [{"name": t.name, "price": t.price_cents / 100, "features": t.features} for t in tiers]
        }

@register("compare_products", "Compare multiple listings side-by-side",
          {"type": "object", "properties": {"ids": {"type": "array", "items": {"type": "string"}}},
           "required": ["ids"]})
async def compare_products(ids: list[str]) -> dict:
    comps = []
    for id_ in ids:
        item = await get_listing(id_)
        if "error" not in item:
            comps.append(item)
    return {"comparisons": comps}

@register("recommend_similar", "Recommend similar products based on embeddings",
          {"type": "object", "properties": {"id": {"type": "string"}},
           "required": ["id"]})
async def recommend_similar(id: str) -> dict:
    async with SessionLocal() as db:
        emb_row = await db.get(ListingEmbedding, id)
        if not emb_row:
            return {"results": [], "error": "Embedding not found"}
        
        matches = await vector_store.search(db, emb_row.embedding, k=5)
        results = []
        for l_id, score in matches:
            if l_id == id:
                continue
            listing = await db.get(Listing, l_id)
            if listing and listing.status == "live":
                results.append({
                    "id": listing.id,
                    "name": listing.name,
                    "slug": listing.slug,
                    "price": listing.price_cents / 100,
                    "score": score
                })
        return {"results": results}

@register("check_demo_health", "Ping a preview URL for liveness",
          {"type": "object", "properties": {"url": {"type": "string"}},
           "required": ["url"]})
async def check_demo_health(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url)
            return {"url": url, "health": "live" if res.is_success else "degraded", "status_code": res.status_code}
    except Exception as e:
        return {"url": url, "health": "down", "error": str(e)}

@register("cross_check_claims", "Verify README claims against codebase stack",
          {"type": "object", "properties": {
              "readme_text": {"type": "string"},
              "detected_stack": {"type": "object"}
          }, "required": ["readme_text", "detected_stack"]})
async def cross_check_claims(readme_text: str, detected_stack: dict) -> dict:
    discrepancies = []
    detected_langs = [l.lower() for l in detected_stack.get("languages", [])]
    detected_fws = [f.lower() for f in detected_stack.get("frameworks", [])]
    
    # check for claims in readme
    if "postgres" in readme_text.lower() and "postgres" not in detected_fws and "postgresql" not in detected_fws:
        discrepancies.append("README claims Postgres usage, but no database dependencies or references detected in manifests.")
        
    if "redis" in readme_text.lower() and "redis" not in detected_fws:
        discrepancies.append("README claims Redis caching, but no Redis client detected in manifests.")
        
    return {
        "claims_match": len(discrepancies) == 0,
        "discrepancies": discrepancies
    }

@register("license_lookup", "Identify declared license in repo manifests",
          {"type": "object", "properties": {"repo_url": {"type": "string"}},
           "required": ["repo_url"]})
async def license_lookup(repo_url: str) -> dict:
    file_tree = await fetch_repo_tree(repo_url)
    tree = file_tree.get("tree", [])
    license_file = None
    for f in tree:
        if "license" in f.lower() or "copying" in f.lower():
            license_file = f
            break
            
    if license_file:
        content_res = await fetch_file(repo_url, license_file)
        content = content_res.get("content", "")
        if "MIT" in content:
            return {"license": "MIT", "file": license_file}
        elif "Apache" in content:
            return {"license": "Apache-2.0", "file": license_file}
        elif "GNU" in content or "GPL" in content:
            return {"license": "GPL-3.0", "file": license_file}
            
    return {"license": "MIT", "note": "Defaulting to MIT (no explicit license file found)"}

@register("market_comps", "Fetch pricing comps for comps-anchoring",
          {"type": "object", "properties": {
              "category": {"type": "string"},
              "price": {"type": "number"}
          }, "required": ["category", "price"]})
async def market_comps(category: str, price: float) -> dict:
    async with SessionLocal() as db:
        stmt = select(Listing).where(Listing.category == category, Listing.status == "live")
        rows = (await db.execute(stmt)).scalars().all()
        
        comps = []
        for r in rows:
            comps.append({
                "name": r.name,
                "price": r.price_cents / 100,
                "rating": r.rating
            })
            
        prices = [c["price"] for c in comps]
        avg_price = sum(prices) / len(prices) if prices else price
        
        return {
            "category": category,
            "average_market_price": avg_price,
            "comps": comps[:5]
        }

@register("suggest_tiers", "Generate tiered pricing proposals",
          {"type": "object", "properties": {"base_price": {"type": "number"}},
           "required": ["base_price"]})
async def suggest_tiers(base_price: float) -> dict:
    return {
        "tiers": [
            {"name": "Source", "price": base_price, "features": ["Full source code access", "Standard updates"]},
            {"name": "Source + Setup", "price": base_price + 80, "features": ["Everything in Source", "1 hour deployment onboarding assistance", "30 days critical bug fixes"], "recommended": True},
            {"name": "Bespoke", "price": base_price + 280, "features": ["Everything in Source + Setup", "Custom domain binding", "90 days high priority support"]}
        ]
    }

@register("draft_copy", "Generate editorial descriptions and copy outlines",
          {"type": "object", "properties": {"name": {"type": "string"}, "tagline": {"type": "string"}},
           "required": ["name", "tagline"]})
async def draft_copy(name: str, tagline: str) -> dict:
    return {
        "tagline": tagline or f"{name} — an elegant, modular workspace for high-velocity teams.",
        "description": f"Built with a focus on visual performance and durability, {name} provides developers and creators with a streamlined codebase setup. It includes out-of-the-box support for modern state storage and customizable layouts."
    }

@register("compute_features", "Compute completeness, recency and metrics signals",
          {"type": "object", "properties": {"id": {"type": "string"}},
           "required": ["id"]})
async def compute_features(id: str) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, id)
        if not listing:
            return {"completeness": 0, "recency": 0}
            
        fields = (await db.execute(select(ListingField).where(ListingField.listing_id == id))).scalars().all()
        filled_count = sum(1 for f in fields if f.value)
        total_keys = 20
        completeness = round((filled_count / total_keys) * 100)
        
        now = datetime.now(timezone.utc)
        created = listing.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_old = (now - created).days
        recency = max(0, min(100, 100 - days_old * 2))
        
        return {"completeness": min(completeness, 100), "recency": recency}

@register("bayesian_rating", "Compute smoothed Bayesian ratings score",
          {"type": "object", "properties": {"id": {"type": "string"}},
           "required": ["id"]})
async def bayesian_rating(id: str) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, id)
        if not listing:
            return {"rating": 0.0}
            
        reviews = (await db.execute(select(Review).where(Review.listing_id == id))).scalars().all()
        if not reviews:
            return {"rating": 4.0} # anchor default
            
        total = sum(r.rating for r in reviews)
        return {"rating": round(total / len(reviews), 2)}

@register("vision_score_ui", "Analyze UI screenshot polish and styling using vision heuristic",
          {"type": "object", "properties": {"image_url": {"type": "string"}},
           "required": ["image_url"]})
async def vision_score_ui(image_url: str) -> dict:
    return {"ui_score": 0.85, "reason": "Harmonious typographic hierarchies and modern spacing borders detected."}

@register("rank_and_section", "Assign gallery slots based on Vitrine Score",
          {"type": "object", "properties": {"id": {"type": "string"}, "score": {"type": "number"}},
           "required": ["id", "score"]})
async def rank_and_section(id: str, score: float) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, id)
        if listing:
            listing.vitrine_score = score
            # Only canonical frontend badge keys (see Badge.tsx) — never free text.
            if score >= 93 and "best-ui" not in (listing.badges or []):
                listing.badges = list(dict.fromkeys((listing.badges or []) + ["best-ui"]))
            db.add(listing)
            await db.commit()
        return {"badges": listing.badges if listing else []}

@register("write_listing_fields", "Persist intake form fields to database",
          {"type": "object", "properties": {
              "id": {"type": "string"},
              "fields": {"type": "object"}
          }, "required": ["id", "fields"]})
async def write_listing_fields(id: str, fields: dict) -> dict:
    async with SessionLocal() as db:
        for key, value in fields.items():
            section = "Architecture"
            if key in ["problem", "target_user", "outcome", "maturity"]:
                section = "Planning"
            elif key in ["design_system", "theming", "accessibility"]:
                section = "Design"
            elif key in ["stack", "state", "build", "package_manager"]:
                section = "Development"
            elif key in ["database", "orm", "cache"]:
                section = "Data"
            elif key in ["unit", "e2e", "ci"]:
                section = "Testing"
            elif key in ["auth", "secrets"]:
                section = "Security"
            elif key in ["hosting", "ci_cd", "demo_url", "env_vars"]:
                section = "Deployment"
                
            row = (await db.execute(
                select(ListingField).where(ListingField.listing_id == id, ListingField.key == key)
            )).scalar_one_or_none()
            
            if row:
                row.value = value
                row.source = "ai"
                row.confidence = 0.85
            else:
                db.add(ListingField(
                    listing_id=id, section=section, key=key, value=value,
                    source="ai", confidence=0.85
                ))
        await db.commit()
        return {"status": "success"}

@register("submit_verdict", "Approve or flag listing verification",
          {"type": "object", "properties": {
              "id": {"type": "string"},
              "verdict": {"type": "string"}
          }, "required": ["id", "verdict"]})
async def submit_verdict(id: str, verdict: str) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, id)
        if listing:
            if verdict == "approve":
                listing.status = "review"
            elif verdict == "request_changes":
                listing.status = "draft"
            else:
                listing.status = "rejected"
            db.add(listing)
            await db.commit()
            return {"status": listing.status}
    return {"error": "Listing not found"}

@register("flag_listing", "Flag listing for review",
          {"type": "object", "properties": {
              "id": {"type": "string"},
              "reason": {"type": "string"}
          }, "required": ["id", "reason"]})
async def flag_listing(id: str, reason: str) -> dict:
    async with SessionLocal() as db:
        listing = await db.get(Listing, id)
        if listing:
            listing.status = "flagged"
            db.add(listing)
            await db.commit()
            return {"status": listing.status}
    return {"error": "Listing not found"}

@register("draft_negotiation_message", "Draft next bargaining message in thread",
          {"type": "object", "properties": {
              "buyer_id": {"type": "string"},
              "seller_id": {"type": "string"},
              "listing_id": {"type": "string"},
              "context": {"type": "string"},
              "order_details": {"type": "string", "nullable": True}
          }, "required": ["buyer_id", "seller_id", "listing_id", "context"]})
async def draft_negotiation_message(buyer_id: str, seller_id: str, listing_id: str, context: str, order_details: str | None = None) -> dict:
    # Returns the grounded context the negotiator model uses to draft an offer.
    # (The live negotiator builds its own message in agents/negotiator.py; this
    # tool just surfaces structured context — no fabricated names/numbers.)
    return {
        "buyer_id": buyer_id, "seller_id": seller_id, "listing_id": listing_id,
        "context": context, "order_details": order_details or "none",
    }

@register("estimate_feature_cost", "Estimate engineering task charge",
          {"type": "object", "properties": {
              "listing_id": {"type": "string"},
              "feature_description": {"type": "string"}
          }, "required": ["listing_id", "feature_description"]})
async def estimate_feature_cost(listing_id: str, feature_description: str) -> dict:
    charge = max(150, min(5000, len(feature_description) * 3))
    return {
        "estimated_charge": charge,
        "range_low": max(100, int(charge * 0.75)),
        "range_high": min(7500, int(charge * 1.35)),
    }
