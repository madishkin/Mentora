from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    plan: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class QuotaInfo(BaseModel):
    daily_tokens_used: int
    daily_token_limit: int
    monthly_tokens_used: int
    monthly_token_limit: int
    daily_remaining: int
    monthly_remaining: int
    monthly_generations_used: int
    # Plan limits (from PLAN_LIMITS config)
    max_generations_per_month: int = 0
    max_input_chars_per_request: int = 0
    allowed_sections: List[str] = []
    difficulty_selection_enabled: bool = False


class UserProfileWithQuota(BaseModel):
    user: UserProfile
    quota: Optional[QuotaInfo] = None

