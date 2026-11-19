"""
Drift issue endpoints — view, approve, reject, apply corrections.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from storage.models import (
    DriftIssue, SuggestionPatch, Repository, IssueStatus,
)

router = APIRouter(prefix="/api/drift", tags=["drift"])


class StatusUpdate(BaseModel):
    status: str   # approved | rejected


@router.get("")
async def list_all_issues(
    repo_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(DriftIssue)
    if repo_id:
        q = q.where(DriftIssue.repo_id == repo_id)
    if status:
        q = q.where(DriftIssue.status == status)
    if severity:
        q = q.where(DriftIssue.severity == severity)
    q = q.order_by(DriftIssue.created_at.desc())
    issues = (await db.execute(q)).scalars().all()
    return [_format(i) for i in issues]


@router.get("/{issue_id}")
async def get_issue(issue_id: str, db: AsyncSession = Depends(get_db)):
    issue = await db.get(DriftIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    patches = (await db.execute(
        select(SuggestionPatch).where(SuggestionPatch.issue_id == issue_id)
    )).scalars().all()
    result = _format(issue)
    result["patches"] = [
        {
            "id": p.id,
            "file_path": p.file_path,
            "original_text": p.original_text,
            "replacement_text": p.replacement_text,
            "start_line": p.start_line,
            "end_line": p.end_line,
            "applied_at": p.applied_at,
        }
        for p in patches
    ]
    return result


@router.patch("/{issue_id}/status")
async def update_issue_status(
    issue_id: str,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    issue = await db.get(DriftIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    valid = {s.value for s in IssueStatus}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {valid}")

    issue.status = IssueStatus(body.status)
    if body.status in ("approved", "rejected", "applied"):
        issue.resolved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(issue)
    return _format(issue)


@router.post("/{issue_id}/apply")
async def apply_patch(issue_id: str, db: AsyncSession = Depends(get_db)):
    """Apply the suggestion patch directly to the local file."""
    issue = await db.get(DriftIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    repo = await db.get(Repository, issue.repo_id)
    if not repo or not repo.local_path:
        raise HTTPException(status_code=409, detail="Repository has no local path")

    patches = (await db.execute(
        select(SuggestionPatch).where(SuggestionPatch.issue_id == issue_id)
    )).scalars().all()

    if not patches:
        raise HTTPException(status_code=409, detail="No patches to apply")

    applied = []
    for patch in patches:
        file_path = Path(repo.local_path) / patch.file_path
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")
        if patch.original_text in content:
            new_content = content.replace(patch.original_text, patch.replacement_text, 1)
            file_path.write_text(new_content, encoding="utf-8")
            patch.applied_at = datetime.utcnow()
            applied.append(patch.file_path)

    issue.status = IssueStatus.applied
    issue.resolved_at = datetime.utcnow()
    await db.commit()

    return {
        "applied": applied,
        "issue_status": issue.status.value,
    }


@router.get("/{issue_id}/diff")
async def get_diff(issue_id: str, db: AsyncSession = Depends(get_db)):
    """Return a before/after text diff for the issue."""
    issue = await db.get(DriftIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    patches = (await db.execute(
        select(SuggestionPatch).where(SuggestionPatch.issue_id == issue_id)
    )).scalars().all()

    return {
        "evidence_doc": issue.evidence_doc,
        "suggested_correction": issue.suggested_correction,
        "patches": [
            {
                "file_path": p.file_path,
                "original": p.original_text,
                "replacement": p.replacement_text,
            }
            for p in patches
        ],
    }


def _format(issue: DriftIssue) -> dict:
    return {
        "id": issue.id,
        "repo_id": issue.repo_id,
        "severity": issue.severity.value,
        "issue_type": issue.issue_type.value,
        "status": issue.status.value,
        "description": issue.description,
        "evidence_code": issue.evidence_code,
        "evidence_doc": issue.evidence_doc,
        "doc_file_path": issue.doc_file_path,
        "doc_start_line": issue.doc_start_line,
        "code_file_path": issue.code_file_path,
        "suggested_correction": issue.suggested_correction,
        "confidence": issue.confidence,
        "commit_sha": issue.commit_sha,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
    }
