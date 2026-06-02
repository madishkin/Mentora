"""
Billing service — quota management with row-level locking.

Uses PostgreSQL SELECT ... FOR UPDATE to prevent race conditions
during concurrent token deductions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import (
    QuotaExceededError,
    MonthlyGenerationLimitExceededError,
    SectionNotAvailableOnPlanError,
)
from app.common.logging import get_logger
from app.config import settings
from app.users.models import UserQuota, User
from app.billing.plans import PLAN_LIMITS

logger = get_logger("billing")


# ── PreCheck result ────────────────────────────────────────

@dataclass
class PreCheckResult:
    """Result of a generation precheck — tells the caller what will happen."""
    can_generate: bool
    reason: Optional[str] = None                   # error code if can_generate is False
    message: Optional[str] = None                  # user-facing message if can_generate is False

    # Text processing info
    document_chars: int = 0
    chars_to_process: int = 0
    truncated: bool = False
    truncation_message: Optional[str] = None

    # Section info
    available_sections: list = field(default_factory=list)
    locked_sections: list = field(default_factory=list)
    requested_sections_filtered: set = field(default_factory=set)

    # Quota info
    generations_used: int = 0
    generations_limit: int = 0
    generations_remaining: int = 0

    # Plan info
    plan: str = "free"
    difficulty_selection_enabled: bool = False

    # Warnings (non-blocking)
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "can_generate": self.can_generate,
            "reason": self.reason,
            "message": self.message,
            "document_chars": self.document_chars,
            "chars_to_process": self.chars_to_process,
            "truncated": self.truncated,
            "truncation_message": self.truncation_message,
            "available_sections": self.available_sections,
            "locked_sections": self.locked_sections,
            "generations_used": self.generations_used,
            "generations_limit": self.generations_limit,
            "generations_remaining": self.generations_remaining,
            "plan": self.plan,
            "difficulty_selection_enabled": self.difficulty_selection_enabled,
            "warnings": self.warnings,
        }


async def create_default_quota(db: AsyncSession, user_id: uuid.UUID) -> UserQuota:
    """Create a default quota record for a new user."""
    quota = UserQuota(
        id=uuid.uuid4(),
        user_id=user_id,
        daily_token_limit=settings.daily_token_limit,
        monthly_token_limit=settings.monthly_token_limit,
        daily_tokens_used=0,
        monthly_tokens_used=0,
        monthly_generations_used=0,
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
        quota.monthly_generations_used = 0
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
                "user_message": "Дневной лимит токенов исчерпан. Попробуйте завтра или обновите тариф.",
            },
        )

    if quota.monthly_tokens_used >= quota.monthly_token_limit:
        raise QuotaExceededError(
            message="Monthly token limit reached",
            details={
                "monthly_used": quota.monthly_tokens_used,
                "monthly_limit": quota.monthly_token_limit,
                "resets_at": (quota.last_monthly_reset + timedelta(days=30)).isoformat(),
                "user_message": "Месячный лимит токенов исчерпан. Обновите тариф для продолжения.",
            },
        )

    return quota


async def precheck_generation(
    db: AsyncSession,
    user: User,
    text_length: int,
    requested_sections: set[str] | None = None,
) -> PreCheckResult:
    """
    Non-destructive precheck: returns what WILL happen if generation is started.
    Does not create jobs, deduct tokens, or modify any state.

    Handles:
      1. Plan lookup
      2. Monthly generation limit check
      3. Text length check with truncation logic
      4. Section availability check
    """
    plan_name = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
    limits = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["free"])

    result = PreCheckResult(
        can_generate=True,
        plan=plan_name,
        document_chars=text_length,
        difficulty_selection_enabled=limits.get("difficulty_selection_enabled", False),
    )

    # ── 1. Check monthly generation limit ──
    # Use a non-locking read for precheck (no FOR UPDATE)
    quota_result = await db.execute(
        select(UserQuota).where(UserQuota.user_id == user.id)
    )
    quota = quota_result.scalar_one_or_none()

    if quota is not None:
        # Apply auto-resets for display purposes
        now = datetime.now(timezone.utc)
        gen_used = quota.monthly_generations_used
        if now - quota.last_monthly_reset > timedelta(days=30):
            gen_used = 0  # Would be reset

        max_gen = limits["max_generations_per_month"]
        result.generations_used = gen_used
        result.generations_limit = max_gen
        result.generations_remaining = max(0, max_gen - gen_used)

        if gen_used >= max_gen:
            reset_date = (quota.last_monthly_reset + timedelta(days=30)).strftime("%d.%m.%Y")
            result.can_generate = False
            result.reason = "monthly_generation_limit"
            result.message = (
                f"Вы использовали {gen_used} из {max_gen} генераций в этом месяце. "
                f"Лимит обновится {reset_date}."
            )
            return result
    else:
        result.generations_limit = limits["max_generations_per_month"]
        result.generations_remaining = result.generations_limit

    # ── 2. Text length + truncation ──
    max_chars = limits["max_input_chars_per_request"]
    truncation_enabled = limits.get("truncation_enabled", True)

    if text_length <= max_chars:
        result.chars_to_process = text_length
    elif truncation_enabled:
        result.chars_to_process = max_chars
        result.truncated = True
        est_pages = max_chars // 2000  # rough: ~2000 chars per page
        total_pages = text_length // 2000
        result.truncation_message = (
            f"Будут обработаны первые ~{max_chars:,} символов документа "
            f"(~{est_pages} из ~{total_pages} страниц)."
        )
        result.warnings.append(result.truncation_message)
    else:
        # Truncation disabled and text too long — reject
        result.can_generate = False
        result.reason = "document_too_large"
        result.message = (
            f"Документ содержит ~{text_length:,} символов. "
            f"Максимум для вашего тарифа — {max_chars:,}. "
            f"Попробуйте загрузить отдельную главу."
        )
        return result

    # ── 3. Section availability ──
    allowed_sections = limits["allowed_sections"]
    all_sections = {"summary", "test", "anki_cards", "mindmap", "sources", "presentation"}
    result.available_sections = sorted(allowed_sections)
    result.locked_sections = sorted(all_sections - allowed_sections)

    if requested_sections is not None:
        locked_requested = requested_sections - allowed_sections
        if locked_requested:
            # Filter out locked sections, warn the user
            result.requested_sections_filtered = requested_sections & allowed_sections
            for s in sorted(locked_requested):
                section_display = {
                    "anki_cards": "Anki карточки",
                    "mindmap": "MindMap",
                    "sources": "Источники",
                    "presentation": "Презентация",
                    "summary": "Конспект",
                    "test": "Тесты",
                }.get(s, s)
                result.warnings.append(
                    f"«{section_display}» доступна на тарифе PRO."
                )
            if not result.requested_sections_filtered:
                # All requested sections are locked — can't generate anything
                result.can_generate = False
                result.reason = "section_not_available_on_plan"
                result.message = "Все выбранные разделы недоступны на вашем тарифе."
                return result
        else:
            result.requested_sections_filtered = requested_sections
    else:
        result.requested_sections_filtered = allowed_sections

    return result


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


async def increment_generation_count(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Increment the monthly generations used counter."""
    result = await db.execute(
        select(UserQuota)
        .where(UserQuota.user_id == user_id)
        .with_for_update()
    )
    quota = result.scalar_one_or_none()
    if quota:
        quota.monthly_generations_used += 1
        await db.flush()


def get_plan_limits(plan_name: str) -> dict:
    """Return the plan limits dict for a given plan name. Used by /users/me."""
    return PLAN_LIMITS.get(plan_name, PLAN_LIMITS["free"])

