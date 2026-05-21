"""
Auth request / response schemas.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.users.models import UserRole


# ── Requests ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72, description="Between 8 and 72 characters")
    full_name: str = Field(..., min_length=1, max_length=256)
    role: Optional[UserRole] = Field(default=UserRole.STUDENT)

    @field_validator("role", mode="before")
    @classmethod
    def lowercase_role(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

    model_config = {"json_schema_extra": {
        "examples": [{
            "email": "teacher@edu.com",
            "password": "securePass123",
            "full_name": "Jane Smith",
        }]
    }}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    model_config = {"json_schema_extra": {
        "examples": [{
            "email": "teacher@edu.com",
            "password": "securePass123",
        }]
    }}


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Responses ─────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RegisterResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    tokens: TokenResponse
