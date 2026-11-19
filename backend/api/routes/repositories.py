"""
Repository management endpoints.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.core.database import get_db
from backend.core.config import get_settings
from storage.models import (
    Repository, CodeSymbol, DocSection, CodeDocMapping, DriftIssue,
    IndexStatus, RepoSource,
)
from backend.services.indexer import RepositoryIndexer
from document_crawler.crawler import RepoCrawler

router = APIRouter(prefix="/api/repositories", tags=["repositories"])
settings = get_settings()
indexer = RepositoryIndexer()
crawler = RepoCrawler()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConnectRepoRequest(BaseModel):
    url: str
    branch: str = "main"
    name: Optional[str] = None


class RepoResponse(BaseModel):
    id: str
    name: str
    url: Optional[str]
    branch: str
    source: str
    index_status: str
    last_indexed_at: Optional[datetime]
    head_commit: Optional[str]
    error_message: Optional[str]
    stats: Optional[dict] = None


# ── Background tasks ──────────────────────────────────────────────────────────

async def _run_indexing(repo_id: str) -> None:
    """Run indexing in a background task."""
    from backend.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        repo = await db.get(Repository, repo_id)
        if not repo:
            return
        idx = RepositoryIndexer()
        await idx.index_repository(db, repo)


async def _clone_and_index(repo_id: str, url: str, branch: str, token: str) -> None:
    from backend.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        repo = await db.get(Repository, repo_id)
        if not repo:
            return
        try:
            crawl = await crawler.crawl_github(url, branch=branch, token=token)
            repo.local_path = crawl.root_path
            await db.commit()
            idx = RepositoryIndexer()
            await idx.index_repository(db, repo)
        except Exception as e:
            repo.index_status = IndexStatus.error
            repo.error_message = str(e)
            await db.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=RepoResponse, status_code=201)
async def connect_repository(
    body: ConnectRepoRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Connect a GitHub repository by URL."""
    name = body.name or body.url.rstrip("/").split("/")[-1]
    repo = Repository(
        name=name,
        url=body.url,
        branch=body.branch,
        source=RepoSource.github,
        index_status=IndexStatus.pending,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    token = settings.github_token
    background_tasks.add_task(_clone_and_index, repo.id, body.url, body.branch, token)

    return _repo_response(repo)


@router.post("/upload", response_model=RepoResponse, status_code=201)
async def upload_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a ZIP archive of a repository."""
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    zip_path = upload_dir / file.filename
    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Extract immediately to get the name
    tmp = tempfile.mkdtemp(prefix="docugosync_up_")
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp)

    entries = list(Path(tmp).iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        root = str(entries[0])
        name = entries[0].name
    else:
        root = tmp
        name = file.filename.replace(".zip", "")

    repo = Repository(
        name=name,
        url=None,
        branch="main",
        source=RepoSource.zip,
        local_path=root,
        index_status=IndexStatus.pending,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    background_tasks.add_task(_run_indexing, repo.id)
    return _repo_response(repo)


@router.get("", response_model=list[RepoResponse])
async def list_repositories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Repository))
    repos = result.scalars().all()
    out = []
    for repo in repos:
        out.append(_repo_response(repo))
    return out


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repository(repo_id: str, db: AsyncSession = Depends(get_db)):
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    stats = await _get_stats(db, repo_id)
    r = _repo_response(repo)
    r.stats = stats
    return r


@router.delete("/{repo_id}", status_code=204)
async def delete_repository(repo_id: str, db: AsyncSession = Depends(get_db)):
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    await db.delete(repo)
    await db.commit()


@router.post("/{repo_id}/reindex", status_code=202)
async def reindex_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo = await db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.index_status = IndexStatus.pending
    await db.commit()
    background_tasks.add_task(_run_indexing, repo.id)
    return {"status": "reindexing"}


@router.get("/{repo_id}/symbols")
async def get_symbols(repo_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CodeSymbol).where(CodeSymbol.repo_id == repo_id)
    )
    syms = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "qualified_name": s.qualified_name,
            "symbol_type": s.symbol_type.value,
            "file_path": s.file_path,
            "signature": s.signature,
            "start_line": s.start_line,
            "end_line": s.end_line,
        }
        for s in syms
    ]


@router.get("/{repo_id}/docs")
async def get_doc_sections(repo_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DocSection).where(DocSection.repo_id == repo_id)
    )
    secs = result.scalars().all()
    return [
        {
            "id": s.id,
            "file_path": s.file_path,
            "heading": s.section_heading,
            "section_type": s.section_type.value,
            "start_line": s.start_line,
            "end_line": s.end_line,
            "content_preview": (s.content or "")[:300],
        }
        for s in secs
    ]


@router.get("/{repo_id}/mappings")
async def get_mappings(repo_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CodeDocMapping, CodeSymbol, DocSection)
        .join(CodeSymbol, CodeDocMapping.symbol_id == CodeSymbol.id)
        .join(DocSection, CodeDocMapping.section_id == DocSection.id)
        .where(CodeDocMapping.repo_id == repo_id)
    )
    rows = result.all()
    return [
        {
            "id": m.id,
            "symbol_name": sym.name,
            "symbol_type": sym.symbol_type.value,
            "symbol_file": sym.file_path,
            "doc_file": sec.file_path,
            "doc_heading": sec.section_heading,
            "evidence_type": m.evidence_type.value,
            "evidence_detail": m.evidence_detail,
            "confidence": m.confidence,
        }
        for m, sym, sec in rows
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _repo_response(repo: Repository, stats: dict | None = None) -> RepoResponse:
    return RepoResponse(
        id=repo.id,
        name=repo.name,
        url=repo.url,
        branch=repo.branch,
        source=repo.source.value,
        index_status=repo.index_status.value,
        last_indexed_at=repo.last_indexed_at,
        head_commit=repo.head_commit,
        error_message=repo.error_message,
        stats=stats,
    )


async def _get_stats(db: AsyncSession, repo_id: str) -> dict:
    sym_count = (await db.execute(
        select(func.count(CodeSymbol.id)).where(CodeSymbol.repo_id == repo_id)
    )).scalar() or 0
    doc_count = (await db.execute(
        select(func.count(DocSection.id)).where(DocSection.repo_id == repo_id)
    )).scalar() or 0
    drift_count = (await db.execute(
        select(func.count(DriftIssue.id)).where(
            DriftIssue.repo_id == repo_id,
            DriftIssue.status == "open",
        )
    )).scalar() or 0
    mapping_count = (await db.execute(
        select(func.count(CodeDocMapping.id)).where(CodeDocMapping.repo_id == repo_id)
    )).scalar() or 0
    return {
        "symbols": sym_count,
        "doc_sections": doc_count,
        "open_drift_issues": drift_count,
        "mappings": mapping_count,
    }
