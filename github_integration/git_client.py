"""
Git diff client — extracts code changes between two commits or file versions.

Works with local git repositories.  For GitHub-hosted repos, works on the
cloned copy.  No GitHub API calls needed for diff extraction.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FileDiff:
    file_path: str
    status: str            # added | modified | deleted | renamed
    old_path: Optional[str] = None    # for renames
    hunks: list[str] = field(default_factory=list)
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    is_binary: bool = False


class GitClient:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + list(args),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=check,
        )

    def head_sha(self) -> str:
        result = self._run("rev-parse", "HEAD")
        return result.stdout.strip()

    def get_diff(self, old_sha: str, new_sha: str) -> list[FileDiff]:
        """Return parsed file diffs between two commits."""
        result = self._run("diff", "--name-status", old_sha, new_sha)
        diffs: list[FileDiff] = []

        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if not parts:
                continue
            status_char = parts[0][0]
            if status_char == "A":
                diffs.append(FileDiff(file_path=parts[1], status="added"))
            elif status_char == "D":
                diffs.append(FileDiff(file_path=parts[1], status="deleted"))
            elif status_char == "M":
                diffs.append(FileDiff(file_path=parts[1], status="modified"))
            elif status_char == "R":
                diffs.append(FileDiff(file_path=parts[2], status="renamed", old_path=parts[1]))

        # Enrich with actual diff content
        for fd in diffs:
            if fd.status == "deleted":
                content = self._get_file_at(fd.file_path, old_sha) or ""
                fd.removed_lines = [l for l in content.splitlines() if l]
            elif fd.status == "added":
                content = self._get_file_at(fd.file_path, new_sha) or ""
                fd.added_lines = [l for l in content.splitlines() if l]
            elif fd.status in ("modified", "renamed"):
                old_path = fd.old_path or fd.file_path
                self._fill_diff_lines(fd, old_sha, new_sha, old_path)

        return diffs

    def _fill_diff_lines(
        self,
        fd: FileDiff,
        old_sha: str,
        new_sha: str,
        old_path: str,
    ) -> None:
        result = self._run(
            "diff",
            f"{old_sha}:{old_path}",
            f"{new_sha}:{fd.file_path}",
            check=False,
        )
        for line in result.stdout.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                fd.added_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                fd.removed_lines.append(line[1:])

    def _get_file_at(self, file_path: str, sha: str) -> Optional[str]:
        result = self._run("show", f"{sha}:{file_path}", check=False)
        if result.returncode == 0:
            return result.stdout
        return None

    def get_file_content(self, file_path: str, sha: Optional[str] = None) -> Optional[str]:
        if sha:
            return self._get_file_at(file_path, sha)
        full_path = self.repo_path / file_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8", errors="replace")
        return None

    def log(self, limit: int = 20) -> list[dict]:
        result = self._run(
            "log",
            f"-{limit}",
            "--pretty=format:%H|%s|%an|%ai",
            check=False,
        )
        commits = []
        for line in result.stdout.splitlines():
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append({
                    "sha": parts[0],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                })
        return commits
