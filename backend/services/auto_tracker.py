"""
Auto-tracker — the central pipeline that runs whenever new commits are detected,
whether triggered by a GitHub webhook or the polling loop.

Responsibilities:
  1. Pull/fetch the new commit content
  2. Compute the diff against the last known SHA
  3. Run drift analysis
  4. Store results
  5. Optionally notify (SSE event, log, future: Slack/email)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import Repository, DriftIssue, IndexStatus
from backend.services.analyzer import DriftAnalyzer
from github_integration.git_client import GitClient

logger = logging.getLogger(__name__)

_analyzer = DriftAnalyzer()


async def process_new_commits(
    db: AsyncSession,
    repo: Repository,
    old_sha: str,
    new_sha: str,
) -> list[DriftIssue]:
    """
    Core pipeline called by both webhook handler and poller.

    old_sha: the SHA that was previously HEAD
    new_sha: the new HEAD after the push
    """
    if not repo.local_path:
        logger.warning("Repo %s has no local path, skipping auto-analysis", repo.name)
        return []

    git = GitClient(repo.local_path)

    # Build old/new file content maps
    diffs = git.get_diff(old_sha, new_sha)
    if not diffs:
        logger.debug("No code file diffs between %s and %s", old_sha[:7], new_sha[:7])
        return []

    old_contents: dict[str, str] = {}
    new_contents: dict[str, str] = {}
    changed_paths: list[str] = []

    for diff in diffs:
        # Only process code files — doc files are handled by the mapping lookup
        old = git.get_file_content(diff.file_path, old_sha)
        new = git.get_file_content(diff.file_path, new_sha)
        if old:
            old_contents[diff.file_path] = old
        if new:
            new_contents[diff.file_path] = new
        changed_paths.append(diff.file_path)

    logger.info(
        "Auto-analyzing %s: %d changed files between %s→%s",
        repo.name, len(changed_paths), old_sha[:7], new_sha[:7],
    )

    issues = await _analyzer.analyze_diff(
        db=db,
        repo=repo,
        old_file_contents=old_contents,
        new_file_contents=new_contents,
        commit_sha=new_sha,
    )

    # Update repo tracking state
    repo.head_commit = new_sha
    repo.last_indexed_at = datetime.now(timezone.utc)
    await db.commit()

    if issues:
        severities = [i.severity.value for i in issues]
        logger.info(
            "Auto-analysis complete for %s: %d issues %s",
            repo.name, len(issues), severities,
        )
    else:
        logger.info("Auto-analysis complete for %s: no drift detected", repo.name)

    return issues


async def handle_webhook_push(
    db: AsyncSession,
    repo: Repository,
    before_sha: str,
    after_sha: str,
    pull_first: bool = True,
) -> list[DriftIssue]:
    """
    Called by the webhook handler immediately after receiving a push event.
    Optionally pulls first (for GitHub-cloned repos).
    """
    if pull_first and repo.local_path:
        import subprocess
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo.local_path,
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(
                "git pull failed for %s: %s",
                repo.name, result.stderr.decode()
            )

    return await process_new_commits(db, repo, before_sha, after_sha)
