"""
Auth & security helpers: password hashing, JWT, RBAC dependencies.

Used by the identity service (issue tokens) and every other service / the
gateway (verify tokens + enforce roles). See backend.md §10.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from .settings import settings

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
) -> Principal:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    claims = decode_token(creds.credentials)
    if claims.get("kind") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")
    return Principal(claims["sub"], claims.get("role", "buyer"))


async def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal | None:
    if not creds:
        return None
    try:
        claims = decode_token(creds.credentials)
        if claims.get("kind") != "access":
            return None
        return Principal(claims["sub"], claims.get("role", "buyer"))
    except Exception:
        return None


def require_role(*roles: Role):
    async def _guard(user: Principal = Depends(current_user)) -> Principal:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return _guard


# TODO(Phase 2): Redis token-bucket rate limiter dependency (stricter on /ai/*).
