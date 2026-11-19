"""
SQLAlchemy ORM models for DocuGoSync.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


# ── Enumerations ─────────────────────────────────────────────────────────────

class RepoSource(str, enum.Enum):
    github = "github"
    zip = "zip"
    local = "local"


class IndexStatus(str, enum.Enum):
    pending = "pending"
    indexing = "indexing"
    ready = "ready"
    error = "error"


class SymbolType(str, enum.Enum):
    function = "function"
    klass = "class"
    method = "method"
    constant = "constant"
    route = "route"
    cli_arg = "cli_arg"
    env_var = "env_var"
    module = "module"


class SectionType(str, enum.Enum):
    readme = "readme"
    api_doc = "api_doc"
    guide = "guide"
    changelog = "changelog"
    generic = "generic"


class EvidenceType(str, enum.Enum):
    exact_name = "exact_name"
    signature_ref = "signature_ref"
    keyword = "keyword"
    semantic = "semantic"
    git_history = "git_history"


class IssueType(str, enum.Enum):
    outdated = "outdated"
    missing = "missing"
    potentially_outdated = "potentially_outdated"


class IssueSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class IssueStatus(str, enum.Enum):
    open = "open"
    approved = "approved"
    rejected = "rejected"
    applied = "applied"


# ── Models ───────────────────────────────────────────────────────────────────

def _uuid() -> str:
    return str(uuid.uuid4())


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    branch: Mapped[str] = mapped_column(String(255), default="main")
    source: Mapped[RepoSource] = mapped_column(Enum(RepoSource), default=RepoSource.github)
    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    index_status: Mapped[IndexStatus] = mapped_column(Enum(IndexStatus), default=IndexStatus.pending)
    head_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    symbols: Mapped[list["CodeSymbol"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    doc_sections: Mapped[list["DocSection"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    drift_issues: Mapped[list["DriftIssue"]] = relationship(back_populates="repository", cascade="all, delete-orphan")


class CodeSymbol(Base):
    __tablename__ = "code_symbols"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_type: Mapped[SymbolType] = mapped_column(Enum(SymbolType), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    qualified_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON string
    return_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    docstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, default=0)
    end_line: Mapped[int] = mapped_column(Integer, default=0)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="symbols")
    mappings: Mapped[list["CodeDocMapping"]] = relationship(back_populates="symbol", cascade="all, delete-orphan")


class DocSection(Base):
    __tablename__ = "doc_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    file_path: Mapped[Text] = mapped_column(Text, nullable=False)
    section_heading: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, default=0)
    end_line: Mapped[int] = mapped_column(Integer, default=0)
    section_type: Mapped[SectionType] = mapped_column(Enum(SectionType), default=SectionType.generic)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="doc_sections")
    mappings: Mapped[list["CodeDocMapping"]] = relationship(back_populates="section", cascade="all, delete-orphan")


class CodeDocMapping(Base):
    __tablename__ = "code_doc_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    symbol_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_symbols.id"), nullable=False)
    section_id: Mapped[str] = mapped_column(String(36), ForeignKey("doc_sections.id"), nullable=False)
    evidence_type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType), nullable=False)
    evidence_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    symbol: Mapped["CodeSymbol"] = relationship(back_populates="mappings")
    section: Mapped["DocSection"] = relationship(back_populates="mappings")
    drift_issues: Mapped[list["DriftIssue"]] = relationship(back_populates="mapping", cascade="all, delete-orphan")


class DriftIssue(Base):
    __tablename__ = "drift_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    mapping_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("code_doc_mappings.id"), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    issue_type: Mapped[IssueType] = mapped_column(Enum(IssueType), nullable=False)
    severity: Mapped[IssueSeverity] = mapped_column(Enum(IssueSeverity), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_doc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_start_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    doc_end_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    code_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus), default=IssueStatus.open)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="drift_issues")
    mapping: Mapped[Optional["CodeDocMapping"]] = relationship(back_populates="drift_issues")
    patches: Mapped[list["SuggestionPatch"]] = relationship(back_populates="issue", cascade="all, delete-orphan")


class SuggestionPatch(Base):
    __tablename__ = "suggestion_patches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    issue_id: Mapped[str] = mapped_column(String(36), ForeignKey("drift_issues.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    replacement_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, default=0)
    end_line: Mapped[int] = mapped_column(Integer, default=0)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    issue: Mapped["DriftIssue"] = relationship(back_populates="patches")
