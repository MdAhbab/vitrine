from __future__ import annotations

from pydantic import BaseModel

# These mirror frontend `Product` / `SpecSection` (mockData.ts) EXACTLY so the
# catalog serializer can return them unchanged to the existing UI.


class SellerOut(BaseModel):
    name: str
    handle: str
    verified: bool


class TierOut(BaseModel):
    name: str
    price: float
    features: list[str]
    recommended: bool = False


class ScoreItem(BaseModel):
    label: str
    value: float


class SpecField(BaseModel):
    label: str
    value: str
    auto: bool | None = None
    confidence: str | None = None  # 'high' | 'med' | 'low'


class SpecSection(BaseModel):
    title: str
    fields: list[SpecField]


class Sdlc(BaseModel):
    problem: str = ""
    solution: str = ""
    methodology: str = ""
    discussions: str = ""


class BusinessModel(BaseModel):
    kind: str = "for-profit"  # for-profit|non-profit|sole-purpose|open-source
    pitch: str = ""
    revenueStreams: list[str] = []


class ProductOut(BaseModel):
    id: str
    slug: str
    name: str
    tagline: str
    seller: SellerOut
    category: str
    subcategory: str | None = None
    tags: list[str] = []
    price: float
    tiers: list[TierOut] = []
    vitrineScore: float
    scoreBreakdown: list[ScoreItem] = []
    demoUrl: str
    demoHealth: str = "live"
    badges: list[str] = []
    screenshots: list[str] = []
    cover: str
    ratingDistribution: list[int] = []
    rating: float
    reviewsCount: int
    description: str
    spec: list[SpecSection] = []
    framework: str
    license: str
    hasLiveDemo: bool
    createdAt: str
    sdlc: Sdlc
    businessModel: BusinessModel
    techStack: list[str] = []
    aiDraft: bool | None = None
    # ownership + lifecycle — required by the frontend `Listing` type so the
    # gallery (status==='live' filter) and seller/admin dashboards (ownerId) work.
    status: str = "live"
    ownerId: str = ""


class ListingCreateIn(BaseModel):
    name: str
    category: str
    tagline: str = ""
    price: float = 0


class IntakeIn(BaseModel):
    """Repo-Intake trigger: a repo URL OR pasted README text."""

    repo_url: str | None = None
    readme_text: str | None = None
