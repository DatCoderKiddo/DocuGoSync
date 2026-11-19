"""
DocuGoSync — FastAPI application entry point.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.core.config import get_settings
from backend.core.database import init_db
from backend.api.routes import repositories, analysis, drift, github, events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DocuGoSync starting up")
    await init_db()

    # Create required directories
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)

    # ── Start commit poller (polling fallback for when webhook is not set up) ─
    poller = None
    if settings.polling_enabled and settings.github_token:
        from github_integration.poller import init_poller
        poller = init_poller(
            interval_seconds=settings.polling_interval_seconds,
            github_token=settings.github_token,
        )
        poller.start()
        logger.info(
            "Commit polling enabled (every %ds). "
            "GitHub-connected repos will be checked automatically.",
            settings.polling_interval_seconds,
        )
    else:
        logger.info(
            "Commit polling disabled. "
            "Set GITHUB_TOKEN and POLLING_ENABLED=true to enable auto-tracking, "
            "or configure a GitHub webhook to /api/github/webhook."
        )

    yield

    if poller:
        poller.stop()
    logger.info("DocuGoSync shutting down")


app = FastAPI(
    title="DocuGoSync",
    description="AI-powered code-to-documentation synchronization",
    version=settings.app_version,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(repositories.router)
app.include_router(analysis.router)
app.include_router(drift.router)
app.include_router(github.router)
app.include_router(events.router)


@app.get("/api/health")
async def health():
    from github_integration.poller import get_poller
    p = get_poller()
    return {
        "status": "ok",
        "version": settings.app_version,
        "auto_tracking": {
            "webhook": bool(settings.github_webhook_secret),
            "polling": p is not None and p._running,
            "polling_interval_seconds": settings.polling_interval_seconds if p else None,
        },
    }


# ── Serve frontend static files in production ─────────────────────────────────
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
