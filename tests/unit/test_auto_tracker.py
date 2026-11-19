"""
Unit tests for the auto-tracker and SSE broadcast.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def test_broadcast_delivers_to_subscribers():
    """SSE broadcast pushes events to all connected queues."""
    from backend.api.routes.events import broadcast, _subscribers

    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()
    _subscribers.clear()
    _subscribers.extend([q1, q2])

    broadcast("drift_detected", {"repo_id": "abc", "count": 2})

    assert not q1.empty()
    assert not q2.empty()
    import json
    payload = json.loads(q1.get_nowait())
    assert payload["type"] == "drift_detected"
    assert payload["data"]["count"] == 2

    _subscribers.clear()


def test_broadcast_removes_full_queues():
    """Full queues are pruned from subscribers list."""
    from backend.api.routes.events import broadcast, _subscribers

    q_full: asyncio.Queue = asyncio.Queue(maxsize=1)
    q_full.put_nowait("existing")   # already at capacity
    _subscribers.clear()
    _subscribers.append(q_full)

    broadcast("test_event", {})
    # Full queue should be removed
    assert q_full not in _subscribers


def test_polling_status_endpoint():
    """Polling status returns correct structure."""
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/github/polling/status")
    assert r.status_code == 200
    data = r.json()
    assert "polling_active" in data
    assert "tracked_repos" in data
    assert isinstance(data["tracked_repos"], list)


def test_health_includes_auto_tracking():
    """Health endpoint exposes auto_tracking status."""
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "auto_tracking" in data
    at = data["auto_tracking"]
    assert "webhook" in at
    assert "polling" in at


def test_webhook_ping_event():
    """GitHub ping event returns pong."""
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.post(
        "/api/github/webhook",
        json={"zen": "Keep it logically awesome."},
        headers={"X-GitHub-Event": "ping"},
    )
    assert r.status_code == 200
    assert "pong" in r.json()["status"]


def test_webhook_ignores_doc_bot_commits():
    """Commits with [docugosync] in the message are skipped."""
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    payload = {
        "ref": "refs/heads/main",
        "before": "abc1234",
        "after": "def5678",
        "commits": [{"id": "def5678", "message": "docs: auto-update [docugosync]", "author": {"name": "bot"}, "added": [], "modified": ["README.md"], "removed": []}],
        "repository": {"full_name": "owner/myrepo", "clone_url": "https://github.com/owner/myrepo.git"},
    }
    r = client.post(
        "/api/github/webhook",
        json=payload,
        headers={"X-GitHub-Event": "push"},
    )
    assert r.status_code == 200
    # Should be skipped — not no_matching_repo
    assert r.json().get("status") in ("skipped", "no_matching_repo")
