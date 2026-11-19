"""
GitHub integration endpoints — webhooks, polling status, PR creation.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.config import get_settings
from storage.models import Repository, IndexStatus, RepoSource
from github_integration.webhook_handler import (
    verify_webhook_signature, parse_push_event, parse_pr_event,
)

router = APIRouter(prefix="/api/github", tags=["github"])
settings = get_settings()
logger = logging.getLogger(__name__)


# ── Webhook ───────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive GitHub webhook events (push, pull_request).

    GitHub sends this automatically on every push/PR — no manual trigger needed.
    Set up: GitHub repo → Settings → Webhooks → add URL + secret.
    """
    payload_bytes = await request.body()

    if settings.github_webhook_secret:
        sig = x_hub_signature_256 or ""
        if not verify_webhook_signature(payload_bytes, sig, settings.github_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    payload = json.loads(payload_bytes)
    event = x_github_event or ""

    if event == "push":
        return await _handle_push(payload, background_tasks, db)
    elif event == "pull_request":
        return await _handle_pr(payload, background_tasks, db)
    elif event == "ping":
        return {"status": "pong", "message": "DocuGoSync webhook connected."}
    else:
        return {"status": "ignored", "event": event}


async def _handle_push(payload: dict, background_tasks: BackgroundTasks, db: AsyncSession):
    parsed = parse_push_event(payload)
    repo_name = parsed["repo_full_name"]
    branch = parsed["branch"]
    before_sha = parsed["before_sha"]
    after_sha = parsed["after_sha"]

    # Skip merge commits to prevent documentation-bot loop
    commits = parsed.get("commits", [])
    if commits and all(
        "[docugosync]" in c.get("message", "").lower() or
        "docs: auto-update" in c.get("message", "").lower()
        for c in commits
    ):
        logger.info("Skipping doc-bot commit for %s", repo_name)
        return {"status": "skipped", "reason": "documentation-only commit"}

    # Find matching repo in DB
    result = await db.execute(
        select(Repository).where(
            Repository.name.like(f"%{repo_name.split('/')[-1]}%"),
            Repository.branch == branch,
            Repository.index_status == IndexStatus.ready,
        )
    )
    repo = result.scalars().first()

    if not repo:
        # Auto-register if we have a token and the repo URL matches something we know
        logger.info("Webhook push for unregistered repo %s/%s", repo_name, branch)
        return {"status": "no_matching_repo", "repo": repo_name, "branch": branch}

    logger.info(
        "Webhook push received: %s %s→%s — queuing auto-analysis",
        repo.name, before_sha[:7], after_sha[:7],
    )

    async def _run_analysis():
        from backend.core.database import AsyncSessionLocal
        from backend.services.auto_tracker import handle_webhook_push
        from backend.api.routes.events import broadcast

        async with AsyncSessionLocal() as session:
            r = await session.get(Repository, repo.id)
            if not r:
                return

            # Broadcast "analysis started"
            broadcast("analysis_started", {
                "repo_id": r.id,
                "repo_name": r.name,
                "commit": after_sha[:7],
            })

            issues = await handle_webhook_push(
                session, r,
                before_sha=before_sha,
                after_sha=after_sha,
                pull_first=True,
            )

            # Broadcast results
            broadcast("analysis_complete", {
                "repo_id": r.id,
                "repo_name": r.name,
                "commit": after_sha[:7],
                "issues_found": len(issues),
                "issues": [
                    {
                        "id": i.id,
                        "severity": i.severity.value,
                        "description": i.description[:120],
                        "doc_file": i.doc_file_path,
                    }
                    for i in issues
                ],
            })

    background_tasks.add_task(_run_analysis)
    return {
        "status": "queued",
        "repo": repo.name,
        "before": before_sha[:7],
        "after": after_sha[:7],
    }


async def _handle_pr(payload: dict, background_tasks: BackgroundTasks, db: AsyncSession):
    parsed = parse_pr_event(payload)
    action = parsed["action"]
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    repo_name = parsed["repo_full_name"]
    base_sha = parsed["base_sha"]
    head_sha = parsed["head_sha"]
    pr_number = parsed["pr_number"]

    result = await db.execute(
        select(Repository).where(
            Repository.name.like(f"%{repo_name.split('/')[-1]}%"),
            Repository.index_status == IndexStatus.ready,
        )
    )
    repo = result.scalars().first()
    if not repo:
        return {"status": "no_matching_repo"}

    logger.info("PR #%d webhook for %s — queuing PR analysis", pr_number, repo_name)

    async def _run_pr_analysis():
        from backend.core.database import AsyncSessionLocal
        from backend.services.auto_tracker import process_new_commits
        from backend.api.routes.events import broadcast

        async with AsyncSessionLocal() as session:
            r = await session.get(Repository, repo.id)
            if not r:
                return
            broadcast("analysis_started", {
                "repo_id": r.id,
                "repo_name": r.name,
                "pr_number": pr_number,
                "commit": head_sha[:7],
            })
            issues = await process_new_commits(session, r, base_sha, head_sha)
            broadcast("analysis_complete", {
                "repo_id": r.id,
                "repo_name": r.name,
                "pr_number": pr_number,
                "issues_found": len(issues),
                "issues": [
                    {"id": i.id, "severity": i.severity.value, "description": i.description[:120]}
                    for i in issues
                ],
            })

    background_tasks.add_task(_run_pr_analysis)
    return {"status": "queued", "pr_number": pr_number}


# ── Polling status ─────────────────────────────────────────────────────────────

@router.get("/polling/status")
async def polling_status(db: AsyncSession = Depends(get_db)):
    """Return the current state of the commit poller."""
    from github_integration.poller import get_poller
    p = get_poller()
    result = await db.execute(
        select(Repository).where(
            Repository.source == RepoSource.github,
            Repository.index_status == IndexStatus.ready,
        )
    )
    tracked_repos = result.scalars().all()

    return {
        "polling_active": p is not None and p._running,
        "interval_seconds": p.interval if p else None,
        "tracked_repos": [
            {
                "id": r.id,
                "name": r.name,
                "branch": r.branch,
                "head_commit": r.head_commit,
                "last_checked": r.last_indexed_at.isoformat() if r.last_indexed_at else None,
            }
            for r in tracked_repos
        ],
    }


@router.post("/polling/trigger")
async def manual_poll(db: AsyncSession = Depends(get_db)):
    """Manually trigger a poll cycle right now (useful for testing)."""
    from github_integration.poller import get_poller, CommitPoller
    p = get_poller()
    if p is None:
        # Allow manual trigger even if automatic polling is off
        p = CommitPoller(github_token=settings.github_token)

    import asyncio
    asyncio.create_task(p._poll_all())
    return {"status": "poll_triggered"}


# ── PR creation ───────────────────────────────────────────────────────────────

class CreatePRRequest(BaseModel):
    repo_id: str
    issue_ids: list[str]
    branch_name: Optional[str] = None
    pr_title: Optional[str] = None


@router.post("/create-pr")
async def create_documentation_pr(
    body: CreatePRRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a documentation-only pull request with approved corrections."""
    if not settings.github_token:
        raise HTTPException(status_code=400, detail="GitHub token not configured")

    repo = await db.get(Repository, body.repo_id)
    if not repo or not repo.local_path:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Collect approved issues with patches
    from storage.models import DriftIssue, SuggestionPatch, IssueStatus
    from sqlalchemy import select as sa_select

    patches_applied = []
    for issue_id in body.issue_ids:
        issue = await db.get(DriftIssue, issue_id)
        if not issue or issue.status != IssueStatus.approved:
            continue
        patches = (await db.execute(
            sa_select(SuggestionPatch).where(SuggestionPatch.issue_id == issue_id)
        )).scalars().all()
        for patch in patches:
            fp = Path(repo.local_path) / patch.file_path
            if fp.exists():
                content = fp.read_text(encoding="utf-8")
                if patch.original_text in content:
                    fp.write_text(
                        content.replace(patch.original_text, patch.replacement_text, 1),
                        encoding="utf-8",
                    )
                    patches_applied.append(patch.file_path)

    if not patches_applied:
        return {"status": "no_patches_applied", "details": "No matching text found in files."}

    # Create a git commit with the doc changes
    import subprocess
    from pathlib import Path as P

    branch = body.branch_name or f"docugosync/doc-update"
    title = body.pr_title or "docs: auto-update documentation [docugosync]"

    cmds = [
        ["git", "checkout", "-b", branch],
        ["git", "add"] + [str(P(repo.local_path) / f) for f in set(patches_applied)],
        ["git", "commit", "-m", title],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=repo.local_path, capture_output=True)
        if result.returncode != 0:
            logger.warning("git cmd %s failed: %s", cmd[1], result.stderr.decode())

    return {
        "status": "committed",
        "branch": branch,
        "files_updated": list(set(patches_applied)),
        "note": "Push the branch manually or add GitHub write token to push automatically.",
    }
