"""
Auth router — registration, login, token refresh.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.auth.service import (
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.billing.service import create_default_quota
from app.common.errors import AppError, ConflictError
from app.common.logging import get_logger
from app.database import get_db
from app.users.models import User, UserRole

router = APIRouter()
logger = get_logger("auth")


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    summary="Register a new user",
    responses={409: {"description": "Email already registered"}},
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new user account and return JWT tokens.
    A default usage quota is automatically created.
    """
    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise ConflictError("A user with this email already exists")

    # Create user
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()  # Get the user.id before creating quota

    # Create default quota
    await create_default_quota(db, user.id)

    await db.commit()
    await db.refresh(user)

    logger.info("User registered", extra={"user_id": str(user.id), "email": user.email})

    tokens = create_token_pair(str(user.id), user.role.value)

    return RegisterResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        tokens=TokenResponse(**tokens),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    responses={401: {"description": "Invalid credentials"}},
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token pair."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise AppError(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )

    if not user.is_active:
        raise AppError(
            code="ACCOUNT_DISABLED",
            message="Account is deactivated",
            status_code=403,
        )

    logger.info("User logged in", extra={"user_id": str(user.id)})

    tokens = create_token_pair(str(user.id), user.role.value)
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={401: {"description": "Invalid refresh token"}},
)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new token pair."""
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise AppError(
            code="INVALID_TOKEN",
            message="Invalid or expired refresh token",
            status_code=401,
        )

    if payload.get("type") != "refresh":
        raise AppError(
            code="INVALID_TOKEN",
            message="Expected refresh token",
            status_code=401,
        )

    user_id = payload.get("sub")
    if not user_id:
        raise AppError(
            code="INVALID_TOKEN",
            message="Token missing subject",
            status_code=401,
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise AppError(
            code="INVALID_TOKEN",
            message="User not found or deactivated",
            status_code=401,
        )

    tokens = create_token_pair(str(user.id), user.role.value)
    return TokenResponse(**tokens)
