"""
Vitrine data model — SQLAlchemy 2.0, dialect-agnostic.

Portable on SQLite (now) and Postgres (later). Notes:
  * IDs are string UUIDs (SQLite has no native UUID).
  * Money is stored as integer **cents**.
  * `JSON` maps to TEXT on SQLite / JSONB on Postgres automatically.
  * Embeddings are stored as a JSON float-array for the SQLite brute-force
    vector store; on Postgres this column is replaced by pgvector `vector(1536)`
    via migration (see ai/vectorstore.py + backend.md DB plan).
  * Enums are plain strings validated by Pydantic at the edges — keeps SQLite
    migrations painless. Allowed values are documented next to each column.

This file is the single source of truth for persistence. Endpoints/services
read & write these models. See backend.md §"Step-by-step" for what to build on top.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PK:
    """Mixin: string-uuid primary key + created_at."""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ── identity ────────────────────────────────────────────────────────────────
class User(PK, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="buyer")  # buyer|seller|admin
    display_name: Mapped[str] = mapped_column(String(120), default="")
    handle: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # seller badge
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_student: Mapped[bool] = mapped_column(Boolean, default=False)
    student_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free|studio|atelier|maison


# ── catalog ─────────────────────────────────────────────────────────────────
class Listing(PK, Base):
    __tablename__ = "listings"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    tagline: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(64), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list] = mapped_column(SAJSON, default=list)
    framework: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    license: Mapped[str] = mapped_column(String(32), default="MIT")
    delivery_method: Mapped[str] = mapped_column(String(32), default="source")
    # draft|enriching|review|live|flagged|paused|archived|rejected
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    demo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    demo_health: Mapped[str] = mapped_column(String(16), default="live")  # live|degraded|down
    managed_hosting: Mapped[str] = mapped_column(String(16), default="no")  # no|demo|full

    # ranking
    vitrine_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[list] = mapped_column(SAJSON, default=list)  # [{label,value}]
    badges: Mapped[list] = mapped_column(SAJSON, default=list)

    # media + presentation (mirror frontend Product shape)
    cover: Mapped[str | None] = mapped_column(String(512), nullable=True)
    screenshots: Mapped[list] = mapped_column(SAJSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")

    # reviews rollup (denormalized for fast cards)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_distribution: Mapped[list] = mapped_column(SAJSON, default=list)  # [c1..c5]

    # rich plan-added blocks (see README §3 / mockData Product)
    sdlc: Mapped[dict] = mapped_column(SAJSON, default=dict)            # {problem,solution,methodology,discussions}
    business_model: Mapped[dict] = mapped_column(SAJSON, default=dict)  # {kind,pitch,revenueStreams}
    tech_stack: Mapped[list] = mapped_column(SAJSON, default=list)
    ai_draft: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    tiers: Mapped[list["ListingTier"]] = relationship(cascade="all, delete-orphan")
    fields: Mapped[list["ListingField"]] = relationship(cascade="all, delete-orphan")


class ListingField(PK, Base):
    """One row per intake form-sheet field (see shared/form_schema.py)."""

    __tablename__ = "listing_fields"

    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    section: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict | list | str | int | float | None] = mapped_column(SAJSON, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="seller")  # ai|seller|heuristic
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class ListingTier(PK, Base):
    __tablename__ = "listing_tiers"

    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[list] = mapped_column(SAJSON, default=list)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)


class ListingMedia(PK, Base):
    __tablename__ = "listing_media"

    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="screenshot")  # screenshot|video|gif
    url: Mapped[str] = mapped_column(String(512))
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class ListingEmbedding(Base):
    __tablename__ = "listing_embeddings"

    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    # SQLite: JSON float array. Postgres: migrate to pgvector vector(1536).
    embedding: Mapped[list] = mapped_column(SAJSON, default=list)
    text_hash: Mapped[str] = mapped_column(String(64), default="")


# ── commerce ────────────────────────────────────────────────────────────────
class Order(PK, Base):
    __tablename__ = "orders"

    buyer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    seller_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tier_id: Mapped[str | None] = mapped_column(ForeignKey("listing_tiers.id"), nullable=True)
    tier_name: Mapped[str] = mapped_column(String(80), default="")
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)      # gross
    commission_cents: Mapped[int] = mapped_column(Integer, default=0)  # platform cut
    kind: Mapped[str] = mapped_column(String(16), default="purchase")  # purchase|advance
    # pending|paid|delivered|refunded|disputed
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(16), default="mock")
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Delivery(PK, Base):
    __tablename__ = "deliveries"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    artifact_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    license_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payout(PK, Base):
    __tablename__ = "payouts"

    seller_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|processed|failed
    payout_method: Mapped[str] = mapped_column(String(16), default="bank")  # bank|mobile_wallet
    payout_details: Mapped[dict] = mapped_column(SAJSON, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Subscription(PK, Base):
    __tablename__ = "subscriptions"

    seller_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tier: Mapped[str] = mapped_column(String(16), default="free")  # free|studio|atelier|maison
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_student: Mapped[bool] = mapped_column(Boolean, default=False)


class FeatureRequest(PK, Base):
    __tablename__ = "feature_requests"

    buyer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_charge_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)  # AI estimate
    developer_charge_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seller quote
    developer_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    # pending_estimate|pending_dev_approval|pending_buyer_approval|approved|rejected
    status: Mapped[str] = mapped_column(String(32), default="pending_estimate")


# ── chats / negotiation ─────────────────────────────────────────────────────
class Chat(PK, Base):
    __tablename__ = "chats"

    buyer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    seller_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    is_agent: Mapped[bool] = mapped_column(Boolean, default=False)  # buyer using AI rep
    agent_budget_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|closed|settled
    unread_for: Mapped[list] = mapped_column(SAJSON, default=list)   # ['buyer'|'seller']


class ChatMessage(PK, Base):
    __tablename__ = "chat_messages"

    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id"), index=True)
    sender_id: Mapped[str] = mapped_column(String(32))  # user id or 'agent'
    sender_name: Mapped[str] = mapped_column(String(120), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    is_agent_rep: Mapped[bool] = mapped_column(Boolean, default=False)


class Negotiation(PK, Base):
    __tablename__ = "negotiations"

    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|closed
    budget_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buyer_readme_context: Mapped[str] = mapped_column(Text, default="")


# ── reviews ─────────────────────────────────────────────────────────────────
class Review(PK, Base):
    __tablename__ = "reviews"

    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    body: Mapped[str] = mapped_column(Text, default="")
    verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False)


# ── notifications ───────────────────────────────────────────────────────────
class Notification(PK, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="info")
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict] = mapped_column(SAJSON, default=dict)


# ── ai / ops ────────────────────────────────────────────────────────────────
class AgentRun(PK, Base):
    __tablename__ = "agent_runs"

    agent: Mapped[str] = mapped_column(String(48), index=True)
    listing_id: Mapped[str | None] = mapped_column(ForeignKey("listings.id"), nullable=True)
    trigger_event: Mapped[str] = mapped_column(String(64), default="")
    input_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    model: Mapped[str] = mapped_column(String(48), default="")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[dict] = mapped_column(SAJSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok|degraded|error


class AiCache(Base):
    __tablename__ = "ai_cache"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(SAJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ttl: Mapped[int] = mapped_column(Integer, default=0)


class AdminConfig(Base):
    """Runtime-editable config (system prompts, api keys, flags, fees, …).

    Stored as keyed JSON documents so `GET /admin/config` can assemble the
    frontend AdminConfig object. See AGENTS.md principle #8 (admin-configurable).
    Keys: system_prompts | api_keys | flags | fees | escrow | branding | notes
    """

    __tablename__ = "admin_configs"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[dict | list | str] = mapped_column(SAJSON, default=dict)
    description: Mapped[str] = mapped_column(String(255), default="")
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AuditLog(PK, Base):
    __tablename__ = "audit_log"

    actor: Mapped[str] = mapped_column(String(64), default="system")
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128), default="")
    meta: Mapped[dict] = mapped_column(SAJSON, default=dict)
