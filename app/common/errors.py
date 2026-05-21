"""
EduCraft AI — Standardized error handling.

Provides a uniform error response format across the entire API:
  {
    "error": {
      "code": "QUOTA_EXCEEDED",
      "message": "Daily token limit reached.",
      "details": { ... }
    }
  }
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ── Error response schema ──────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ── Domain exceptions ──────────────────────────────────────

class AppError(Exception):
    """Base application error."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str = ""):
        detail = f"{resource} not found"
        if resource_id:
            detail = f"{resource} '{resource_id}' not found"
        super().__init__(
            code="NOT_FOUND",
            message=detail,
            status_code=404,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied"):
        super().__init__(code="FORBIDDEN", message=message, status_code=403)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(code="CONFLICT", message=message, status_code=409)


class QuotaExceededError(AppError):
    def __init__(self, message: str = "Token quota exceeded", details: dict | None = None):
        super().__init__(
            code="QUOTA_EXCEEDED",
            message=message,
            status_code=429,
            details=details,
        )


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(code="RATE_LIMITED", message=message, status_code=429)


class FileTooLargeError(AppError):
    def __init__(self, max_mb: int):
        super().__init__(
            code="FILE_TOO_LARGE",
            message=f"File exceeds maximum size of {max_mb} MB",
            status_code=413,
        )


class InvalidFileTypeError(AppError):
    def __init__(self, allowed: list[str]):
        super().__init__(
            code="INVALID_FILE_TYPE",
            message=f"Only {', '.join(allowed)} files are accepted",
            status_code=400,
        )


# ── Exception handlers ────────────────────────────────────

async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        ).model_dump(),
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(
                code="HTTP_ERROR",
                message=str(exc.detail),
            )
        ).model_dump(),
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    # In production, do NOT leak internal error details
    from app.config import settings

    message = "Internal server error"
    details = None
    if not settings.is_production:
        message = str(exc)
        details = {"type": type(exc).__name__}

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message=message,
                details=details,
            )
        ).model_dump(),
    )
