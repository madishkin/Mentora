"""
Billing service — quota management with row-level locking.

Uses PostgreSQL SELECT ... FOR UPDATE to prevent race conditions
during concurrent token deductions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import QuotaExceededError
from app.common.logging import get_logger
from app.config import settings
from app.users.models import UserQuota

logger = get_logger("billing")


async def create_default_quota(db: AsyncSession, user_id: uuid.UUID) -> UserQuota:
    """Create a default quota record for a new user."""
    quota = UserQuota(
        id=uuid.uuid4(),
        user_id=user_id,
        daily_token_limit=settings.daily_token_limit,
        monthly_token_limit=settings.monthly_token_limit,
        daily_tokens_used=0,
        monthly_tokens_used=0,
    )
    db.add(quota)
    return quota


async def check_quota(db: AsyncSession, user_id: uuid.UUID) -> UserQuota:
    """
    Check if user has remaining quota. Resets counters if needed.
    Raises QuotaExceededError if limit reached.

    Uses SELECT ... FOR UPDATE to lock the row during the check,
    preventing concurrent requests from both passing the check.
    """
    result = await db.execute(
        select(UserQuota)
        .where(UserQuota.user_id == user_id)
        .with_for_update()
    )
    quota = result.scalar_one_or_none()

    if quota is None:
        # Auto-create quota if missing (defensive)
        quota = await create_default_quota(db, user_id)
        await db.flush()
        return quota

    now = datetime.now(timezone.utc)

    # Auto-reset daily counter
    if now - quota.last_daily_reset > timedelta(days=1):
        quota.daily_tokens_used = 0
        quota.last_daily_reset = now
        logger.info("Daily quota reset", extra={"user_id": str(user_id)})

    # Auto-reset monthly counter
    if now - quota.last_monthly_reset > timedelta(days=30):
        quota.monthly_tokens_used = 0
        quota.last_monthly_reset = now
        logger.info("Monthly quota reset", extra={"user_id": str(user_id)})

    # Check limits
    if quota.daily_tokens_used >= quota.daily_token_limit:
        raise QuotaExceededError(
            message="Daily token limit reached",
            details={
                "daily_used": quota.daily_tokens_used,
                "daily_limit": quota.daily_token_limit,
                "resets_at": (quota.last_daily_reset + timedelta(days=1)).isoformat(),
            },
        )

    if quota.monthly_tokens_used >= quota.monthly_token_limit:
        raise QuotaExceededError(
            message="Monthly token limit reached",
            details={
                "monthly_used": quota.monthly_tokens_used,
                "monthly_limit": quota.monthly_token_limit,
                "resets_at": (quota.last_monthly_reset + timedelta(days=30)).isoformat(),
            },
        )

    return quota


async def deduct_tokens(
    db: AsyncSession,
    user_id: uuid.UUID,
    total_tokens: int,
) -> None:
    """
    Atomically deduct tokens from user quota.

    Uses SELECT ... FOR UPDATE to lock the quota row during deduction,
    preventing double-charging from concurrent requests.
    """
    result = await db.execute(
        select(UserQuota)
        .where(UserQuota.user_id == user_id)
        .with_for_update()
    )
    quota = result.scalar_one_or_none()

    if quota is None:
        logger.error("Quota row missing during deduction", extra={"user_id": str(user_id)})
        return

    quota.daily_tokens_used += total_tokens
    quota.monthly_tokens_used += total_tokens

    logger.info(
        "Tokens deducted",
        extra={
            "user_id": str(user_id),
            "tokens": total_tokens,
            "daily_used": quota.daily_tokens_used,
            "monthly_used": quota.monthly_tokens_used,
        },
    )

    await db.flush()
