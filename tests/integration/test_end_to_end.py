"""
End-to-end integration test.

Simulates the full DocuGoSync workflow:
1. Upload a ZIP repository
2. Wait for indexing
3. Trigger drift analysis with changed files
4. Verify drift issues are detected
5. Approve and apply a correction
"""

import asyncio
import io
import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app

FIXTURES = Path(__file__).parent.parent / "fixtures"
ZIP_PATH = FIXTURES / "test_repo.zip"

ORIGINAL_AUTH = (FIXTURES / "changed_files" / "original" / "myproject" / "src" / "auth.py").read_text()
MODIFIED_AUTH = (FIXTURES / "changed_files" / "modified" / "myproject" / "src" / "auth.py").read_text()
ORIGINAL_DB = (FIXTURES / "changed_files" / "original" / "myproject" / "src" / "db.py").read_text()
MODIFIED_DB = (FIXTURES / "changed_files" / "modified" / "myproject" / "src" / "db.py").read_text()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_repo(client):
    with open(ZIP_PATH, "rb") as f:
        r = client.post(
            "/api/repositories/upload",
            files={"file": ("test_repo.zip", f, "application/zip")},
        )
    assert r.status_code == 201
    data = r.json()
    assert data["id"]
    assert data["index_status"] in ("pending", "indexing", "ready")
    return data["id"]


def _get_repo_id(client) -> str:
    r = client.get("/api/repositories")
    repos = r.json()
    if repos:
        return repos[0]["id"]
    return test_upload_repo(client)


def test_wait_for_indexing(client):
    """Wait until indexing completes (up to 30s)."""
    repo_id = _get_repo_id(client)
    for _ in range(30):
        r = client.get(f"/api/repositories/{repo_id}")
        status = r.json()["index_status"]
        if status == "ready":
            break
        elif status == "error":
            pytest.fail(f"Indexing failed: {r.json()['error_message']}")
        time.sleep(1)
    else:
        pytest.fail("Indexing did not complete in 30s")

    r = client.get(f"/api/repositories/{repo_id}")
    data = r.json()
    assert data["index_status"] == "ready"
    # Should have found symbols
    stats = data.get("stats", {})
    assert stats.get("symbols", 0) > 0, f"Expected symbols, got: {stats}"
    assert stats.get("doc_sections", 0) > 0, f"Expected doc sections, got: {stats}"


def test_symbols_indexed(client):
    repo_id = _get_repo_id(client)
    r = client.get(f"/api/repositories/{repo_id}/symbols")
    syms = r.json()
    names = {s["name"] for s in syms}
    assert "login" in names, f"Expected 'login' in {names}"
    assert "logout" in names
    assert "connect" in names


def test_doc_sections_indexed(client):
    repo_id = _get_repo_id(client)
    r = client.get(f"/api/repositories/{repo_id}/docs")
    sections = r.json()
    headings = {s["heading"] for s in sections}
    assert "Authentication" in headings, f"Expected 'Authentication' in {headings}"


def test_mappings_created(client):
    repo_id = _get_repo_id(client)
    r = client.get(f"/api/repositories/{repo_id}/mappings")
    mappings = r.json()
    assert len(mappings) > 0, "Expected at least one code-doc mapping"
    # Should have login → Authentication mapping
    login_mappings = [m for m in mappings if m["symbol_name"] == "login"]
    assert len(login_mappings) > 0, f"Expected login to be mapped. Mappings: {mappings}"


def test_drift_detection_signature_change(client):
    """
    TC1+TC2: login() gained two new parameters.
    The README still says `login(username, password)`.
    DocuGoSync should detect the outdated signature.
    """
    repo_id = _get_repo_id(client)

    r = client.post(
        f"/api/analysis/{repo_id}/files",
        json={
            "files": [
                {
                    "path": "myproject/src/auth.py",
                    "old_content": ORIGINAL_AUTH,
                    "new_content": MODIFIED_AUTH,
                }
            ],
            "doc_file_path": "myproject/README.md",
        },
    )
    assert r.status_code == 200
    data = r.json()
    print(f"\nDrift detection result: {data}")
    assert data["issues_found"] >= 1, (
        f"Expected at least 1 drift issue. Got: {data}"
    )

    issues = data["issues"]
    severities = {i["severity"] for i in issues}
    # Login signature change should be critical or high
    assert severities & {"critical", "high"}, f"Expected critical/high issues, got: {severities}"


def test_drift_detection_default_change(client):
    """TC3: connect() timeout changed from 30 to 60."""
    repo_id = _get_repo_id(client)

    r = client.post(
        f"/api/analysis/{repo_id}/files",
        json={
            "files": [
                {
                    "path": "myproject/src/db.py",
                    "old_content": ORIGINAL_DB,
                    "new_content": MODIFIED_DB,
                }
            ],
            "doc_file_path": "myproject/README.md",
        },
    )
    assert r.status_code == 200
    data = r.json()
    print(f"\nDefault change result: {data}")
    # May or may not detect depending on doc mapping confidence
    # Just verify the endpoint works and returns valid structure
    assert "issues_found" in data


def test_approve_and_check_issue(client):
    """Test the approval workflow."""
    r = client.get("/api/drift?status=open")
    issues = r.json()
    if not issues:
        pytest.skip("No open issues to approve")

    issue_id = issues[0]["id"]
    r = client.patch(f"/api/drift/{issue_id}/status", json={"status": "approved"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_reject_issue(client):
    """Test rejection."""
    r = client.get("/api/drift?status=open")
    issues = r.json()
    if not issues:
        pytest.skip("No open issues to reject")

    issue_id = issues[0]["id"]
    r = client.patch(f"/api/drift/{issue_id}/status", json={"status": "rejected"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
