"""
Users schemas — request/response models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
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


class UserProfileWithQuota(BaseModel):
    user: UserProfile
    quota: Optional[QuotaInfo] = None
