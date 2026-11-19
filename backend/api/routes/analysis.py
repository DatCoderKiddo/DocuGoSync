"""
Analysis endpoints — trigger drift detection on specific commits or file contents.
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from storage.models import Repository, DriftIssue, IndexStatus
from backend.services.analyzer import DriftAnalyzer
from github_integration.git_client import GitClient

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
_analyzer = DriftAnalyzer()


class AnalyzeCommitRequest(BaseModel):
    old_sha: str
    new_sha: str
    doc_files: Optional[list[str]] = None


class AnalyzeFilesRequest(BaseModel):
    """
    Analyze a specific pair of old/new file contents.
    Useful for testing without a full git history.
    """
    files: list[dict]   # [{path, old_content, new_content}]
    doc_file_path: str = "README.md"
    doc_content: str = ""


@router.post("/{repo_id}/commits")
async def analyze_commit_range(
    repo_id: str,
    body: AnalyzeCommitRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze drift between two commits of an indexed repository."""
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.index_status != IndexStatus.ready:
        raise HTTPException(status_code=409, detail="Repository not yet indexed")
    if not repo.local_path:
        raise HTTPException(status_code=409, detail="No local path for repository")

    git = GitClient(repo.local_path)
    diffs = git.get_diff(body.old_sha, body.new_sha)

    old_contents: dict[str, str] = {}
    new_contents: dict[str, str] = {}

    for diff in diffs:
        if diff.status == "deleted":
            old_src = git.get_file_content(diff.file_path, body.old_sha)
            if old_src:
                old_contents[diff.file_path] = old_src
        elif diff.status == "added":
            new_src = git.get_file_content(diff.file_path, body.new_sha)
            if new_src:
                new_contents[diff.file_path] = new_src
        else:
            old_src = git.get_file_content(diff.file_path, body.old_sha)
            new_src = git.get_file_content(diff.file_path, body.new_sha)
            if old_src:
                old_contents[diff.file_path] = old_src
            if new_src:
                new_contents[diff.file_path] = new_src

    issues = await _analyzer.analyze_diff(
        db, repo,
        old_contents, new_contents,
        commit_sha=body.new_sha,
        affected_doc_files=body.doc_files,
    )

    return {
        "issues_found": len(issues),
        "issue_ids": [i.id for i in issues],
    }


@router.post("/{repo_id}/files")
async def analyze_file_contents(
    repo_id: str,
    body: AnalyzeFilesRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze provided file contents directly — no git required.
    Used for ZIP uploads and testing.
    """
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    old_contents: dict[str, str] = {}
    new_contents: dict[str, str] = {}

    for item in body.files:
        path = item.get("path", "")
        old = item.get("old_content")
        new = item.get("new_content")
        if old:
            old_contents[path] = old
        if new:
            new_contents[path] = new

    # Temporarily update doc section from provided content if any
    # (The indexer must have already run; this is for ad-hoc checks)
    issues = await _analyzer.analyze_diff(
        db, repo,
        old_contents, new_contents,
        commit_sha=None,
        affected_doc_files=[body.doc_file_path] if body.doc_file_path else None,
    )

    return {
        "issues_found": len(issues),
        "issues": [_format_issue(i) for i in issues],
    }


def _format_issue(issue: DriftIssue) -> dict:
    return {
        "id": issue.id,
        "severity": issue.severity.value,
        "issue_type": issue.issue_type.value,
        "description": issue.description,
        "evidence_code": issue.evidence_code,
        "evidence_doc": issue.evidence_doc,
        "doc_file_path": issue.doc_file_path,
        "doc_start_line": issue.doc_start_line,
        "code_file_path": issue.code_file_path,
        "suggested_correction": issue.suggested_correction,
        "confidence": issue.confidence,
        "status": issue.status.value,
    }
