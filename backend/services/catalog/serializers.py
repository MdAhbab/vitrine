"""Compose the frontend `Product` shape from DB rows.

This is the contract bridge: the UI expects exactly `ProductOut`
(see frontend mockData.ts). Keep this function in sync with that type.
"""
from __future__ import annotations

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


def _spec_from_fields(fields: list[ListingField]) -> list[SpecSection]:
    by_section: dict[str, list[SpecField]] = {}
    for f in fields:
        conf = {None: None, 0.0: "low"}.get(f.confidence)
        if f.confidence is not None:
            conf = "high" if f.confidence >= 0.75 else "med" if f.confidence >= 0.4 else "low"
        by_section.setdefault(f.section, []).append(
            SpecField(label=f.key, value=str(f.value), auto=f.source == "ai", confidence=conf)
        )
    return [SpecSection(title=s, fields=fl) for s, fl in by_section.items()]


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
