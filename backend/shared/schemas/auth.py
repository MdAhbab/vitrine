from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class _EmailNormalized(BaseModel):
    """Fold the address to lowercase before it reaches a lookup.

    The user row is matched with an exact string comparison, so without this a
    touch keyboard's auto-capitalisation ("Admin@vitrine.io") reads as a
    different account and the login comes back 401. Signup normalises through
    the same base, so an address can never be *stored* in a form that login
    would fail to find.
    """

    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class SignupIn(_EmailNormalized):
    password: str
    display_name: str = ""
    role: str = "buyer"  # buyer | seller  (admin via /auth/admin/login only)


class LoginIn(_EmailNormalized):
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
    bio: str = ""
    location: str = ""
    themeDefault: str = "dark"
    minimalProfile: bool = False
    aiPoints: int = 100


class RefreshIn(BaseModel):
    refresh_token: str


class ProfileUpdateIn(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    location: str | None = None
    avatar_url: str | None = None
    theme_default: str | None = None
    minimal_profile: bool | None = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str
