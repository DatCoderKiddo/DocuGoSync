"""
GitHub webhook handler.

Verifies webhook signatures and routes events to the analysis pipeline.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub's HMAC-SHA256 webhook signature."""
    if not secret:
        return True  # skip verification in dev mode
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_push_event(payload: dict) -> dict:
    """Extract relevant fields from a push webhook payload."""
    return {
        "repo_full_name": payload.get("repository", {}).get("full_name", ""),
        "repo_url": payload.get("repository", {}).get("clone_url", ""),
        "branch": payload.get("ref", "").replace("refs/heads/", ""),
        "before_sha": payload.get("before", ""),
        "after_sha": payload.get("after", ""),
        "commits": [
            {
                "sha": c.get("id", ""),
                "message": c.get("message", ""),
                "author": c.get("author", {}).get("name", ""),
                "added": c.get("added", []),
                "modified": c.get("modified", []),
                "removed": c.get("removed", []),
            }
            for c in payload.get("commits", [])
        ],
    }


def parse_pr_event(payload: dict) -> dict:
    """Extract relevant fields from a pull_request webhook payload."""
    pr = payload.get("pull_request", {})
    return {
        "action": payload.get("action", ""),
        "pr_number": pr.get("number", 0),
        "pr_title": pr.get("title", ""),
        "repo_full_name": payload.get("repository", {}).get("full_name", ""),
        "repo_url": payload.get("repository", {}).get("clone_url", ""),
        "base_branch": pr.get("base", {}).get("ref", ""),
        "head_branch": pr.get("head", {}).get("ref", ""),
        "base_sha": pr.get("base", {}).get("sha", ""),
        "head_sha": pr.get("head", {}).get("sha", ""),
    }
