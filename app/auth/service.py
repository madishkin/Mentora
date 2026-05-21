"""
Auth service — JWT token management and password hashing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import hashlib

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ── Password hashing ─────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _pre_hash(plain: str) -> str:
    """Pre-hash with SHA-256 to bypass bcrypt's 72-byte safety limit."""
    return hashlib.sha256(plain.encode()).hexdigest()


def hash_password(plain: str) -> str:
    return pwd_context.hash(_pre_hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_pre_hash(plain), hashed)


# ── JWT tokens ────────────────────────────────────────────

ALGORITHM = "HS256"


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises JWTError on invalid/expired tokens.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def create_token_pair(user_id: str, role: str) -> Dict[str, Any]:
    """Create both access and refresh tokens for a user."""
    payload = {"sub": user_id, "role": role}
    access = create_access_token(payload)
    refresh = create_refresh_token(payload)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }
