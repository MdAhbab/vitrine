"""
Identity service — signup, login, admin login, profile, student verification.

This is a WORKING vertical slice (the auth foundation the whole app needs).
Other services follow this exact shape. See backend.md step-by-step.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.db import get_session
from backend.shared.events import bus
from backend.shared.models import User
from backend.shared.schemas.auth import LoginIn, SignupIn, TokenOut, UserOut, RefreshIn
from backend.shared.security import (
    Principal,
    current_user,
    hash_password,
    make_access_token,
    make_refresh_token,
    verify_password,
    decode_token,
)

router = APIRouter(tags=["identity"])


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, name=u.display_name or u.email.split("@")[0], email=u.email,
        role=u.role, avatar=u.avatar_url, isStudent=u.is_student, plan=u.plan,
    )


async def _issue(u: User) -> TokenOut:
    return TokenOut(
        access_token=make_access_token(u.id, u.role),
        refresh_token=make_refresh_token(u.id, u.role),
    )


@router.post("/auth/signup", response_model=TokenOut)
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


@router.post("/auth/login", response_model=TokenOut)
async def login(body: LoginIn, db: AsyncSession = Depends(get_session)) -> TokenOut:
    u = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return await _issue(u)


@router.post("/auth/admin/login", response_model=TokenOut)
async def admin_login(body: LoginIn, db: AsyncSession = Depends(get_session)) -> TokenOut:
    u = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not u or u.role != "admin" or not verify_password(body.password, u.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid admin credentials")
    return await _issue(u)


@router.post("/auth/refresh", response_model=TokenOut)
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
    # TODO: accept an academic-email / credential upload and verify it.
    # Scaffold: flip the flag so the 25% student discount becomes available.
    u = await db.get(User, user.id)
    u.is_student = True
    u.student_verified = True
    await db.commit()
    await db.refresh(u)
    return _user_out(u)


app = FastAPI(title="Vitrine identity")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "identity"}
