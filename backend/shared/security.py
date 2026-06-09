"""
Auth & security helpers: password hashing, JWT, RBAC dependencies.

Used by the identity service (issue tokens) and every other service / the
gateway (verify tokens + enforce roles). See backend.md §10.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from .settings import settings
from .db import get_session

Role = Literal["buyer", "seller", "admin"]

# pbkdf2_sha256 is pure-Python (no native bcrypt build — portable across
# Python versions). Swap to bcrypt/argon2 for production if desired.
_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


# ── passwords ──────────────────────────────────────────────────────────
def hash_password(raw: str) -> str:
    return _pwd.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return _pwd.verify(raw, hashed)


# ── tokens ─────────────────────────────────────────────────────────────
def _encode(sub: str, role: str, ttl: int, kind: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "role": role, "kind": kind,
               "iat": now, "exp": now + timedelta(seconds=ttl)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALG)


def make_access_token(user_id: str, role: str) -> str:
    return _encode(user_id, role, settings.JWT_ACCESS_TTL, "access")


def make_refresh_token(user_id: str, role: str) -> str:
    return _encode(user_id, role, settings.JWT_REFRESH_TTL, "refresh")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALG])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc


# ── FastAPI dependencies ───────────────────────────────────────────────
class Principal:
    def __init__(self, user_id: str, role: str):
        self.id = user_id
        self.role = role


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session)
) -> Principal:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    claims = decode_token(creds.credentials)
    if claims.get("kind") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")
    
    from .models import User
    u = await db.get(User, claims["sub"])
    if not u:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if u.banned_until and u.banned_until > datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
        
    return Principal(u.id, u.role)


async def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session)
) -> Principal | None:
    if not creds:
        return None
    try:
        claims = decode_token(creds.credentials)
        if claims.get("kind") != "access":
            return None
        from .models import User
        u = await db.get(User, claims["sub"])
        if not u or (u.banned_until and u.banned_until > datetime.now(timezone.utc)):
            return None
        return Principal(u.id, u.role)
    except Exception:
        return None


def require_role(*roles: Role):
    async def _guard(user: Principal = Depends(current_user)) -> Principal:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return _guard


from .ratelimit import enforce_rate_limit


def rate_limit(limit: int = 60, window: int = 60, scope: str = "api"):
    """FastAPI dependency — token-bucket per client IP."""

    async def _guard(request: Request) -> None:
        await enforce_rate_limit(request, scope=scope, limit=limit, window=window)

    return _guard


# Preset limiters (stricter on AI + auth)
auth_rate_limit = rate_limit(limit=20, window=60, scope="auth")


async def ai_rate_limit(request: Request) -> None:
    """FastAPI dependency — composite limiter to stop AI token abuse.
    Max 10 requests per 60 seconds (burst protection), and max 100 requests per hour (volume limit).
    """
    await enforce_rate_limit(request, scope="ai_short", limit=10, window=60)
    await enforce_rate_limit(request, scope="ai_long", limit=100, window=3600)
