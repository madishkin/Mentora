from __future__ import annotations

import uuid
from typing import List

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import decode_token
from app.common.errors import AppError, ForbiddenError
from app.database import get_db
from app.users.models import User, UserRole


class AuthenticationError(AppError):
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(code="UNAUTHORIZED", message=message, status_code=401)


async def get_current_user(
    authorization: str = Header(..., description="Bearer <token>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate JWT from Authorization header.
    Returns the full User ORM object.
    """
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Authorization header must start with 'Bearer '")

    token = authorization[7:]

    try:
        payload = decode_token(token)
    except JWTError:
        raise AuthenticationError()

    if payload.get("type") != "access":
        raise AuthenticationError("Expected access token, got refresh token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token missing subject")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid user ID in token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    return user


def require_role(allowed_roles: List[UserRole]):
    """
    Dependency factory — restricts endpoint to specific roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role([UserRole.ADMIN]))])
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{user.role.value}' is not allowed. Required: {[r.value for r in allowed_roles]}"
            )
        return user
    return role_checker
