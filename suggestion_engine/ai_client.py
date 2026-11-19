"""
AI client abstraction layer.

Priority: Groq (free tier) → OpenAI → Ollama (local) → None (deterministic only).

The system retains full functionality without an AI provider — the AI
augments correction quality but deterministic logic handles detection.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AIClient:
    """
    Thin wrapper over multiple LLM providers.
    Returns None if no provider is configured or available.
    """

    def __init__(
        self,
        provider: str = "none",
        groq_api_key: str = "",
        openai_api_key: str = "",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "llama3",
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ):
        self.provider = provider
        self.groq_api_key = groq_api_key
        self.openai_api_key = openai_api_key
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def available(self) -> bool:
        if self.provider == "groq":
            return bool(self.groq_api_key)
        if self.provider == "openai":
            return bool(self.openai_api_key)
        if self.provider == "ollama":
            return True  # assume local is running
        return False

    def complete(self, prompt: str) -> Optional[str]:
        if not self.available():
            return None
        try:
            if self.provider == "groq":
                return self._groq(prompt)
            if self.provider == "openai":
                return self._openai(prompt)
            if self.provider == "ollama":
                return self._ollama(prompt)
        except Exception as e:
            logger.warning("AI completion failed (%s): %s", self.provider, e)
        return None

    # ── Provider implementations ──────────────────────────────────────────────

    def _groq(self, prompt: str) -> Optional[str]:
        import httpx
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _openai(self, prompt: str) -> Optional[str]:
        import httpx
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _ollama(self, prompt: str) -> Optional[str]:
        import httpx
        resp = httpx.post(
            f"{self.ollama_base_url}/api/generate",
            json={
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json().get("response")
