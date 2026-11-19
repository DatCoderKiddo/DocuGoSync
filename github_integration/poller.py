"""
Commit poller — polls GitHub API for new commits on tracked repositories.

Used when you can't expose a public webhook URL (local dev, private network).
Runs as a background asyncio task inside the FastAPI process.

For every tracked repo:
  1. Fetch latest commit SHA from GitHub API
  2. Compare with stored head_commit
  3. If different: git pull, run drift analysis, update head_commit
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class CommitPoller:
    """
    Polls GitHub for new commits at a configurable interval.
    Instantiated once; runs until the app shuts down.
    """

    def __init__(
        self,
        interval_seconds: int = 60,
        github_token: str = "",
    ):
        self.interval = interval_seconds
        self.token = github_token
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Commit poller started (interval=%ds)", self.interval)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Commit poller stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._poll_all()
            except Exception as e:
                logger.warning("Poller error: %s", e)
            await asyncio.sleep(self.interval)

    async def _poll_all(self) -> None:
        from backend.core.database import AsyncSessionLocal
        from storage.models import Repository, IndexStatus, RepoSource

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(Repository).where(
                    Repository.index_status == IndexStatus.ready,
                    Repository.source == RepoSource.github,
                    Repository.url.isnot(None),
                )
            )
            repos = result.scalars().all()

        for repo in repos:
            try:
                await self._poll_repo(repo.id)
            except Exception as e:
                logger.warning("Failed to poll repo %s: %s", repo.name, e)

    async def _poll_repo(self, repo_id: str) -> None:
        from backend.core.database import AsyncSessionLocal
        from storage.models import Repository
        from backend.services.analyzer import DriftAnalyzer
        from github_integration.git_client import GitClient

        async with AsyncSessionLocal() as db:
            repo = await db.get(Repository, repo_id)
            if not repo or not repo.url or not repo.local_path:
                return

            # Get latest SHA from GitHub API
            latest_sha = await self._fetch_latest_sha(repo.url, repo.branch)
            if not latest_sha:
                return

            current_sha = repo.head_commit or ""
            if latest_sha == current_sha:
                return  # no new commits

            logger.info(
                "New commits detected on %s: %s → %s",
                repo.name,
                (current_sha or "none")[:7],
                latest_sha[:7],
            )

            # Pull the latest changes
            if not self._git_pull(repo.local_path):
                logger.warning("git pull failed for %s", repo.name)
                return

            # Run drift analysis
            git = GitClient(repo.local_path)
            if current_sha:
                diffs = git.get_diff(current_sha, latest_sha)
                old_contents: dict[str, str] = {}
                new_contents: dict[str, str] = {}
                for diff in diffs:
                    old = git.get_file_content(diff.file_path, current_sha)
                    new = git.get_file_content(diff.file_path, latest_sha)
                    if old:
                        old_contents[diff.file_path] = old
                    if new:
                        new_contents[diff.file_path] = new

                analyzer = DriftAnalyzer()
                issues = await analyzer.analyze_diff(
                    db, repo,
                    old_contents, new_contents,
                    commit_sha=latest_sha,
                )
                if issues:
                    logger.info(
                        "Found %d drift issue(s) in %s after commit %s",
                        len(issues), repo.name, latest_sha[:7],
                    )

            # Update stored SHA
            repo.head_commit = latest_sha
            repo.last_indexed_at = datetime.now(timezone.utc)
            await db.commit()

    async def _fetch_latest_sha(self, repo_url: str, branch: str) -> Optional[str]:
        """
        Get the latest commit SHA via GitHub REST API (no auth needed for public repos).
        """
        # Convert clone URL to API URL
        # https://github.com/owner/repo → owner/repo
        # https://github.com/owner/repo.git → owner/repo
        repo_path = (
            repo_url
            .replace("https://github.com/", "")
            .replace(".git", "")
            .strip("/")
        )
        if not repo_path or "/" not in repo_path:
            return None

        api_url = f"https://api.github.com/repos/{repo_path}/commits/{branch}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(api_url, headers=headers)
                if r.status_code == 200:
                    return r.json().get("sha")
                elif r.status_code == 404:
                    logger.debug("Branch %s not found for %s", branch, repo_path)
                else:
                    logger.debug("GitHub API returned %d for %s", r.status_code, repo_path)
        except Exception as e:
            logger.debug("GitHub API fetch failed: %s", e)

        return None

    def _git_pull(self, repo_path: str) -> bool:
        """Pull latest changes into the local clone."""
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=repo_path,
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0:
                return True
            logger.warning("git pull output: %s", result.stderr.decode())
            return False
        except Exception as e:
            logger.warning("git pull exception: %s", e)
            return False


# Singleton instance — started/stopped by the app lifespan
_poller: Optional[CommitPoller] = None


def get_poller() -> Optional[CommitPoller]:
    return _poller


def init_poller(interval_seconds: int = 60, github_token: str = "") -> CommitPoller:
    global _poller
    _poller = CommitPoller(interval_seconds=interval_seconds, github_token=github_token)
    return _poller
