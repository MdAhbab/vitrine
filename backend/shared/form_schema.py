"""
FORM_SCHEMA — single source of truth for the Listing Intake Form Sheet.

Read by:
  * the Repo-Intake Agent (to know which fields to fill, with what policy), and
  * the frontend Sell wizard / SpecSheet (to render & group fields).

Section titles mirror the frontend `SpecSection` grouping (Planning, Design,
Development, Architecture, Data, Testing, Security, Deployment) so the composed
`spec` on a listing serializes straight into the Product type. Extend per
README §7 (the full 11-section sheet) as the build progresses.

Field policy:
  ai_fill: "ai"  -> agent fills outright
           "ai*" -> agent suggests, seller confirms
           ""    -> seller-only
"""
from __future__ import annotations

from typing import Any

FORM_SCHEMA: list[dict[str, Any]] = [
    {
        "section": "Planning",
        "fields": [
            {"key": "problem", "label": "Problem", "type": "md", "required": True, "ai_fill": "ai"},
            {"key": "target_user", "label": "Target user", "type": "text", "ai_fill": "ai*"},
            {"key": "outcome", "label": "Outcome", "type": "text", "ai_fill": "ai*"},
            {"key": "maturity", "label": "Maturity", "type": "enum", "ai_fill": "ai*",
             "options": ["Prototype", "MVP", "Beta", "Production", "Mature"]},
        ],
    },
    {
        "section": "Design",
        "fields": [
            {"key": "design_system", "label": "Design system", "type": "text", "ai_fill": "ai"},
            {"key": "theming", "label": "Theming", "type": "enum", "ai_fill": "ai",
             "options": ["Dark", "Light", "Both", "N/A"]},
            {"key": "accessibility", "label": "Accessibility", "type": "text", "ai_fill": "ai*"},
        ],
    },
    {
        "section": "Development",
        "fields": [
            {"key": "stack", "label": "Stack", "type": "multi", "required": True, "ai_fill": "ai"},
            {"key": "state", "label": "State", "type": "text", "ai_fill": "ai*"},
            {"key": "build", "label": "Build", "type": "text", "ai_fill": "ai"},
            {"key": "package_manager", "label": "Package manager", "type": "enum", "ai_fill": "ai",
             "options": ["npm", "pnpm", "yarn", "pip", "poetry", "cargo", "go"]},
        ],
    },
    {
        "section": "Architecture",
        "fields": [
            {"key": "pattern", "label": "Pattern", "type": "enum", "ai_fill": "ai*",
             "options": ["Monolith", "Modular monolith", "Microservices", "Serverless",
                         "Static", "Client-only"]},
            {"key": "api", "label": "API", "type": "text", "ai_fill": "ai*"},
            {"key": "integrations", "label": "Integrations", "type": "multi", "ai_fill": "ai"},
        ],
    },
    {
        "section": "Data",
        "fields": [
            {"key": "database", "label": "Database", "type": "multi", "ai_fill": "ai"},
            {"key": "orm", "label": "ORM / data layer", "type": "text", "ai_fill": "ai"},
            {"key": "cache", "label": "Cache", "type": "text", "ai_fill": "ai*"},
        ],
    },
    {
        "section": "Testing",
        "fields": [
            {"key": "unit", "label": "Unit", "type": "text", "ai_fill": "ai"},
            {"key": "e2e", "label": "E2E", "type": "text", "ai_fill": "ai*"},
            {"key": "ci", "label": "CI configured", "type": "bool", "ai_fill": "ai"},
        ],
    },
    {
        "section": "Security",
        "fields": [
            {"key": "auth", "label": "Auth", "type": "text", "ai_fill": "ai*"},
            {"key": "secrets", "label": "Secrets", "type": "text", "ai_fill": "ai*"},
        ],
    },
    {
        "section": "Deployment",
        "fields": [
            {"key": "hosting", "label": "Hosting", "type": "multi", "ai_fill": "ai"},
            {"key": "ci_cd", "label": "CI", "type": "text", "ai_fill": "ai"},
            {"key": "demo_url", "label": "Live demo URL", "type": "url", "required": True, "ai_fill": ""},
            {"key": "env_vars", "label": "Env vars required", "type": "multi", "ai_fill": "ai"},
        ],
    },
]

# flat index: "Section.key" -> field def
FIELD_INDEX: dict[str, dict] = {
    f"{sec['section']}.{f['key']}": f
    for sec in FORM_SCHEMA
    for f in sec["fields"]
}


def ai_fillable_keys() -> list[str]:
    return [k for k, f in FIELD_INDEX.items() if f.get("ai_fill") in ("ai", "ai*")]
