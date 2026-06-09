from __future__ import annotations

from pydantic import BaseModel

# Mirrors frontend `AdminConfig` (store.ts). Assembled from the admin_configs
# keyed JSON rows by GET /admin/config; PATCH writes the changed keys back.


class ApiKeyOut(BaseModel):
    id: str
    provider: str  # openai|anthropic|gemini|mistral|cohere|stripe|custom
    label: str
    key: str       # masked on read (sk-••••QF7)
    enabled: bool
    createdAt: int


class SystemPrompts(BaseModel):
    concierge: str = ""
    buyerRep: str = ""
    pricingAgent: str = ""
    verification: str = ""


class FeatureFlags(BaseModel):
    aiBargain: bool = True
    conciergeSearch: bool = True
    enterpriseTier: bool = True
    studentDiscount: bool = True
    newSignupsOpen: bool = True


class Fees(BaseModel):
    commissionFree: float = 12
    commissionStudio: float = 8
    commissionAtelier: float = 5
    commissionMaison: float = 3
    enterprise: float = 2
    processing: float = 2.5


class Escrow(BaseModel):
    holdHours: int = 48
    refundWindow: int = 7
    autoRelease: bool = True


class Branding(BaseModel):
    headline: str = ""
    tagline: str = ""
    supportEmail: str = ""


class AdminConfigOut(BaseModel):
    systemPrompts: SystemPrompts
    apiKeys: list[ApiKeyOut]
    flags: FeatureFlags
    fees: Fees
    escrow: Escrow
    branding: Branding
    notes: str = ""
    featuredIds: list[str] = []


class AdminConfigPatch(BaseModel):
    systemPrompts: SystemPrompts | None = None
    flags: FeatureFlags | None = None
    fees: Fees | None = None
    escrow: Escrow | None = None
    branding: Branding | None = None
    notes: str | None = None
    featuredIds: list[str] | None = None


class AddApiKeyIn(BaseModel):
    provider: str
    label: str
    key: str
    enabled: bool = True
