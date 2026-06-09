from __future__ import annotations

from pydantic import BaseModel, EmailStr


class SignupIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str = ""
    role: str = "buyer"  # buyer | seller  (admin via /auth/admin/login only)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Mirrors frontend `User` (store.ts)."""

    id: str
    name: str            # <- display_name
    email: EmailStr
    role: str
    avatar: str | None = None
    isStudent: bool = False
    plan: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str
