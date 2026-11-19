"""
DocuGoSync — central configuration.
All settings read from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "DocuGoSync"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./docugosync.db"

    # ── Storage ───────────────────────────────────────────────────────────────
    upload_dir: Path = Path("./uploads")
    index_dir: Path = Path("./index_cache")

    # ── GitHub ───────────────────────────────────────────────────────────────
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_webhook_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    github_token: str = ""          # personal access token for MVP

    # ── AI / LLM ─────────────────────────────────────────────────────────────
    # Provider priority: groq → openai → ollama → none (deterministic only)
    ai_provider: str = "none"       # groq | openai | ollama | none
    groq_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ai_max_tokens: int = 1024
    ai_temperature: float = 0.1

    # ── Drift detection ───────────────────────────────────────────────────────
    min_confidence_to_report: float = 0.4
    auto_apply_min_confidence: float = 0.9

    # ── Auto-tracking ─────────────────────────────────────────────────────────
    # Polling fallback when no public webhook URL is available
    polling_enabled: bool = True
    polling_interval_seconds: int = 60     # how often to check GitHub for new commits

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @classmethod
    def settings_customise_sources(cls, settings_cls, **kwargs):  # type: ignore[override]
        # Allow comma-separated string in .env for list fields
        sources = super().settings_customise_sources(settings_cls, **kwargs)
        return sources


@lru_cache
def get_settings() -> Settings:
    return Settings()
