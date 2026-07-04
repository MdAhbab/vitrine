"""
Identity service — signup, login, admin login, profile, student verification.

This is a WORKING vertical slice (the auth foundation the whole app needs).
Other services follow this exact shape. See backend.md step-by-step.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.models import User
from backend.shared.settings import settings
from backend.shared.schemas.auth import LoginIn, SignupIn, TokenOut, UserOut, RefreshIn, ProfileUpdateIn, ChangePasswordIn
from backend.shared.security import (
    Principal,
    current_user,
    hash_password,
    make_access_token,
    make_refresh_token,
    verify_password,
    decode_token,
    auth_rate_limit,
)

router = APIRouter(tags=["identity"])


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        name=u.display_name or u.email.split("@")[0],
        email=u.email,
        role=u.role,
        avatar=u.avatar_url,
        isStudent=u.is_student,
        plan=u.plan,
        bio=getattr(u, "bio", "") or "",
        location=getattr(u, "location", "") or "",
        themeDefault=getattr(u, "theme_default", "dark") or "dark",
        minimalProfile=getattr(u, "minimal_profile", False) or False,
        aiPoints=getattr(u, "ai_points", 0) if getattr(u, "ai_points", 0) is not None else 0,
    )


async def _issue(u: User) -> TokenOut:
    return TokenOut(
        access_token=make_access_token(u.id, u.role),
        refresh_token=make_refresh_token(u.id, u.role),
    )


@router.post("/auth/signup", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
async def signup(body: SignupIn, db: AsyncSession = Depends(get_session)) -> TokenOut:
    if body.role not in ("buyer", "seller"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role must be buyer or seller")
    exists = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    u = User(
        email=body.email, password_hash=hash_password(body.password),
        display_name=body.display_name, role=body.role,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    await bus.publish("user.created", {"user_id": u.id, "role": u.role}, actor=f"user:{u.id}")
    return await _issue(u)


@router.post("/auth/login", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
async def login(body: LoginIn, db: AsyncSession = Depends(get_session)) -> TokenOut:
    u = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if u.banned_until and u.banned_until > datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    return await _issue(u)


@router.post("/auth/admin/login", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
async def admin_login(body: LoginIn, db: AsyncSession = Depends(get_session)) -> TokenOut:
    u = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not u or u.role != "admin" or not verify_password(body.password, u.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid admin credentials")
    return await _issue(u)


@router.post("/auth/refresh", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_session)) -> TokenOut:
    claims = decode_token(body.refresh_token)
    if claims.get("kind") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not a refresh token")
    u = await db.get(User, claims["sub"])
    if not u:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return await _issue(u)


@router.get("/users/me", response_model=UserOut)
async def me(user: Principal = Depends(current_user),
             db: AsyncSession = Depends(get_session)) -> UserOut:
    u = await db.get(User, user.id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return _user_out(u)


@router.post("/users/verify-student", response_model=UserOut)
async def verify_student(user: Principal = Depends(current_user),
                         db: AsyncSession = Depends(get_session)) -> UserOut:
    u = await db.get(User, user.id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    # Require lightweight evidence: the account email must be from a recognised
    # academic domain. This closes the "any user self-flips for the discount"
    # hole; a full credential-upload flow can layer on top later.
    email = (u.email or "").lower()
    if not any(email.endswith(sfx) for sfx in settings.academic_email_suffixes):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Student status requires an academic email (e.g. .edu, .ac.uk).",
        )
    u.is_student = True
    u.student_verified = True
    await db.commit()
    await db.refresh(u)
    return _user_out(u)


@router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str, db: AsyncSession = Depends(get_session)) -> dict:
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    
    # Fetch active listings for this user if they are a seller
    listings = []
    if u.role == "seller":
        from backend.shared.models import Listing
        stmt = select(Listing).where(Listing.owner_id == u.id, Listing.status == "live")
        listing_rows = (await db.execute(stmt)).scalars().all()
        listings = [
            {
                "id": l.id,
                "name": l.name,
                "slug": l.slug,
                "tagline": l.tagline,
                "cover": l.cover,
                "price": l.price_cents / 100,
                "category": l.category,
                "rating": l.rating,
                "reviewsCount": l.reviews_count,
            }
            for l in listing_rows
        ]
    
    return {
        "id": u.id,
        "name": u.display_name or u.email.split("@")[0],
        "avatar": u.avatar_url,
        "role": u.role,
        "verified": u.verified,
        "trustScore": u.trust_score,
        "bio": getattr(u, "bio", "") or "",
        "location": getattr(u, "location", "") or "",
        "minimalProfile": getattr(u, "minimal_profile", False) or False,
        "listings": listings,
    }


@router.put("/users/me/profile", response_model=UserOut)
async def update_profile(body: ProfileUpdateIn, user: Principal = Depends(current_user), db: AsyncSession = Depends(get_session)) -> UserOut:
    u = await db.get(User, user.id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    
    if body.display_name is not None:
        u.display_name = body.display_name
    if body.bio is not None:
        u.bio = body.bio
    if body.location is not None:
        u.location = body.location
    if body.avatar_url is not None:
        u.avatar_url = body.avatar_url
    if body.theme_default is not None:
        u.theme_default = body.theme_default
    if body.minimal_profile is not None:
        u.minimal_profile = body.minimal_profile
        
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return _user_out(u)


@router.post("/users/me/change-password")
async def change_password_route(body: ChangePasswordIn, user: Principal = Depends(current_user), db: AsyncSession = Depends(get_session)) -> dict:
    u = await db.get(User, user.id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        
    if not verify_password(body.current_password, u.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect current password")
        
    u.password_hash = hash_password(body.new_password)
    db.add(u)
    await db.commit()
    return {"ok": True, "message": "Password changed successfully"}


@router.get("/users/me/billing")
async def get_billing_history(user: Principal = Depends(current_user), db: AsyncSession = Depends(get_session)) -> dict:
    u = await db.get(User, user.id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        
    from backend.shared.models import Order
    order_stmt = select(Order).where(Order.buyer_id == u.id).order_by(Order.created_at.desc())
    orders = (await db.execute(order_stmt)).scalars().all()
    
    from backend.shared.models import Subscription
    sub_stmt = select(Subscription).where(Subscription.seller_id == u.id).order_by(Subscription.created_at.desc())
    subs = (await db.execute(sub_stmt)).scalars().all()
    
    invoices = []
    for o in orders:
        invoices.append({
            "id": f"INV-{o.id[:8].upper()}",
            "date": o.created_at.strftime("%Y-%m-%d"),
            "description": f"Purchase of Listing Tier: {o.tier_name}",
            "amount": o.amount_cents / 100,
            "status": "paid" if o.status in ("paid", "delivered") else o.status
        })
        
    for s in subs:
        invoices.append({
            "id": f"SUB-{s.id[:8].upper()}",
            "date": s.start_date.strftime("%Y-%m-%d"),
            "description": f"Subscription tier: {s.tier.upper()}",
            "amount": s.price_cents / 100,
            "status": "paid" if s.active else "cancelled"
        })
        
    invoices.sort(key=lambda x: x["date"], reverse=True)
    
    return {
        "plan": u.plan,
        "paymentMethod": {
            "type": "card",
            "last4": "4242",
            "brand": "visa",
            "expiry": "12/28"
        },
        "invoices": invoices
    }


app = FastAPI(title="Vitrine identity")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "identity"}
