"""Compose the frontend `Product` shape from DB rows.

This is the contract bridge: the UI expects exactly `ProductOut`
(see frontend mockData.ts). Keep this function in sync with that type.
"""
from __future__ import annotations

from backend.shared.form_schema import FIELD_LABELS
from backend.shared.models import Listing, ListingField, ListingTier, User
from backend.shared.schemas.listing import (
    BusinessModel,
    ProductOut,
    Sdlc,
    SellerOut,
    SpecField,
    SpecSection,
    TierOut,
)


#  Sections render in the order a reader expects, not dict-insertion order.
_SECTION_ORDER = ["Planning", "Design", "Development", "Architecture", "Data",
                  "Testing", "Security", "Deployment"]


def _spec_value(value) -> str:
    """Render a stored field value as display text.

    Values arrive as JSON, so a multi-valued field is a real list and a bool is a
    real bool — `str()` alone would print "['React', 'Vite']" and "True".
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if str(v).strip())
    if isinstance(value, dict):
        if "value" in value:
            return _spec_value(value["value"])
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def _spec_from_fields(fields: list[ListingField]) -> list[SpecSection]:
    by_section: dict[str, list[SpecField]] = {}
    for f in fields:
        conf = None
        if f.confidence is not None:
            conf = "high" if f.confidence >= 0.75 else "med" if f.confidence >= 0.4 else "low"
        text = _spec_value(f.value)
        if not text:
            continue  # an empty row is noise in the Spec Sheet
        by_section.setdefault(f.section, []).append(
            SpecField(label=FIELD_LABELS.get(f.key, f.key.replace("_", " ").capitalize()),
                      value=text, auto=f.source == "ai", confidence=conf)
        )
    ordered = sorted(by_section.items(),
                     key=lambda kv: (_SECTION_ORDER.index(kv[0]) if kv[0] in _SECTION_ORDER else 99, kv[0]))
    return [SpecSection(title=s, fields=fl) for s, fl in ordered]


def to_product(listing: Listing, seller: User | None,
               tiers: list[ListingTier], fields: list[ListingField]) -> ProductOut:
    return ProductOut(
        id=listing.id,
        slug=listing.slug,
        name=listing.name,
        tagline=listing.tagline,
        seller=SellerOut(
            name=(seller.display_name if seller else "Unknown"),
            handle=(seller.handle or "@studio") if seller else "@studio",
            verified=bool(seller.verified) if seller else False,
        ),
        category=listing.category,
        subcategory=listing.subcategory,
        tags=listing.tags or [],
        price=listing.price_cents / 100,
        tiers=[TierOut(name=t.name, price=t.price_cents / 100, features=t.features or [],
                       recommended=t.recommended) for t in tiers],
        vitrineScore=listing.vitrine_score,
        scoreBreakdown=listing.score_breakdown or [],
        demoUrl=listing.demo_url or "",
        demoHealth=listing.demo_health,
        badges=listing.badges or [],
        screenshots=listing.screenshots or [],
        cover=listing.cover or "",
        ratingDistribution=listing.rating_distribution or [],
        rating=listing.rating,
        reviewsCount=listing.reviews_count,
        description=listing.description,
        spec=_spec_from_fields(fields),
        framework=listing.framework or "",
        license=listing.license,
        hasLiveDemo=bool(listing.demo_url),
        createdAt=listing.created_at.isoformat(),
        sdlc=Sdlc(**(listing.sdlc or {})),
        businessModel=BusinessModel(**(listing.business_model or {})),
        techStack=listing.tech_stack or [],
        aiDraft=listing.ai_draft,
        status=listing.status,
        ownerId=listing.owner_id,
        expiresAt=listing.expires_at.isoformat() if listing.expires_at else None,
    )
