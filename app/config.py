"""
EduCraft AI — Application Configuration.

All settings loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

import json
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"

    # --- Security ---
    secret_key: str = "CHANGE-ME"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://educraft:educraft_pass@localhost:5433/educraft"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Auth (JWT) ---
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- CORS ---
    cors_origins: str = '["http://localhost:3000","http://localhost:5173"]'

    @property
    def cors_origin_list(self) -> List[str]:
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return [self.cors_origins]

    # --- File Upload ---
    max_file_size_mb: int = 20

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    # --- Quotas ---
    daily_token_limit: int = 100_000
    monthly_token_limit: int = 2_000_000

    # --- Rate Limiting ---
    rate_limit_per_minute: int = 60
    generation_rate_limit_per_minute: int = 5

    # --- OpenAI generation ---
    max_text_length: int = 15_000

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
