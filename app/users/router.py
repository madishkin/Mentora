"""
Users router — profile and user management endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.billing.service import get_plan_limits
from app.users.models import User
from app.users.schemas import QuotaInfo, UserProfile, UserProfileWithQuota

router = APIRouter()


@router.get(
    "/me",
    response_model=UserProfileWithQuota,
    summary="Get current user profile with quota info",
)
async def get_me(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile and remaining quota."""
    plan_str = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
    limits = get_plan_limits(plan_str)

    quota_info = None
    if user.quota:
        quota_info = QuotaInfo(
            daily_tokens_used=user.quota.daily_tokens_used,
            daily_token_limit=user.quota.daily_token_limit,
            monthly_tokens_used=user.quota.monthly_tokens_used,
            monthly_token_limit=user.quota.monthly_token_limit,
            daily_remaining=max(0, user.quota.daily_token_limit - user.quota.daily_tokens_used),
            monthly_remaining=max(0, user.quota.monthly_token_limit - user.quota.monthly_tokens_used),
            monthly_generations_used=user.quota.monthly_generations_used,
            max_generations_per_month=limits["max_generations_per_month"],
            max_input_chars_per_request=limits["max_input_chars_per_request"],
            allowed_sections=sorted(limits["allowed_sections"]),
            difficulty_selection_enabled=limits.get("difficulty_selection_enabled", False),
        )

    return UserProfileWithQuota(
        user=UserProfile(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            plan=plan_str,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        quota=quota_info,
    )

