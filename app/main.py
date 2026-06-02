"""
EduCraft AI — FastAPI application factory.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.common.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from app.common.logging import (
    generate_request_id,
    get_logger,
    request_id_ctx,
    setup_logging,
)
from app.config import settings
from app.database import engine

logger = get_logger("main")


# ── Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()
    logger.info("EduCraft AI starting up", extra={"env": settings.app_env})
    yield
    await engine.dispose()
    logger.info("EduCraft AI shut down")


# ── App factory ───────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="EduCraft AI",
        version="2.0.0",
        description="AI-powered educational content generation platform",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # ── Request‑ID middleware ──
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = generate_request_id()
        request_id_ctx.set(rid)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    # ── Exception handlers ──
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Routers ──
    from app.auth.router import router as auth_router
    from app.users.router import router as users_router
    from app.documents.router import router as documents_router
    from app.generation.router import router as generation_router
    from app.courses.router import router as courses_router
    from app.export.router import router as export_router
    from app.study.router import router as study_router

    app.include_router(auth_router, prefix="/auth", tags=["Auth"])
    app.include_router(users_router, prefix="/users", tags=["Users"])
    app.include_router(documents_router, prefix="/documents", tags=["Documents"])
    app.include_router(generation_router, prefix="/generation", tags=["Generation"])
    app.include_router(courses_router, prefix="/courses", tags=["Courses"])
    app.include_router(export_router, prefix="/export", tags=["Export"])
    app.include_router(study_router, prefix="/study", tags=["Study"])

    # ── Health check ──
    @app.get("/health", tags=["System"])
    async def health_check():
        """
        Health check — verifies API server and database connectivity.
        """
        db_ok = False
        try:
            from sqlalchemy import text
            from app.database import async_session_factory

            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            pass

        return {
            "status": "healthy" if db_ok else "degraded",
            "database": "connected" if db_ok else "disconnected",
            "version": "2.0.0",
        }

    return app


app = create_app()
