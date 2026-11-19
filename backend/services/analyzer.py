"""
Analysis service — drives drift detection for a specific code change.

Takes a repository and a diff (old SHA vs new SHA, or old/new file contents),
runs the detection pipeline, stores findings in the database.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from storage.models import (
    Repository, CodeSymbol, DocSection, CodeDocMapping, DriftIssue, SuggestionPatch,
    IssueType, IssueSeverity, IssueStatus,
)
from code_indexer.python_analyzer import PythonAnalyzer
from code_indexer.javascript_analyzer import JavaScriptAnalyzer
from code_indexer.symbol_types import ExtractedSymbol
from content_extractor.markdown_extractor import MarkdownExtractor, ParsedSection
from drift_detector.detector import DriftDetector, DriftFinding
from suggestion_engine.generator import SuggestionGenerator
from suggestion_engine.ai_client import AIClient
from backend.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_PYTHON_EXTS = {".py"}
_JS_EXTS = {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}

_ISSUE_TYPE_MAP = {
    "outdated": IssueType.outdated,
    "missing": IssueType.missing,
    "potentially_outdated": IssueType.potentially_outdated,
}

_SEVERITY_MAP = {
    "critical": IssueSeverity.critical,
    "high": IssueSeverity.high,
    "medium": IssueSeverity.medium,
    "low": IssueSeverity.low,
}


def _make_ai_client() -> Optional[AIClient]:
    s = settings
    if not s.ai_provider or s.ai_provider == "none":
        return None
    return AIClient(
        provider=s.ai_provider,
        groq_api_key=s.groq_api_key,
        openai_api_key=s.openai_api_key,
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        max_tokens=s.ai_max_tokens,
        temperature=s.ai_temperature,
    )


class DriftAnalyzer:
    def __init__(self):
        self.py_analyzer = PythonAnalyzer()
        self.js_analyzer = JavaScriptAnalyzer()
        self.md_extractor = MarkdownExtractor()
        self.detector = DriftDetector()
        self.ai = _make_ai_client()
        self.generator = SuggestionGenerator(ai_client=self.ai)

    async def analyze_diff(
        self,
        db: AsyncSession,
        repo: Repository,
        old_file_contents: dict[str, str],   # rel_path → content
        new_file_contents: dict[str, str],   # rel_path → content
        commit_sha: Optional[str] = None,
        affected_doc_files: Optional[list[str]] = None,
    ) -> list[DriftIssue]:
        """
        Core analysis pipeline.

        old_file_contents: source of changed files at old commit.
        new_file_contents: source of changed files at new commit.
        Returns stored DriftIssue objects.
        """
        changed_symbols: list[tuple[Optional[ExtractedSymbol], Optional[ExtractedSymbol]]] = []

        for rel_path in set(list(old_file_contents) + list(new_file_contents)):
            ext = Path(rel_path).suffix.lower()
            if ext not in _PYTHON_EXTS and ext not in _JS_EXTS:
                continue

            old_src = old_file_contents.get(rel_path)
            new_src = new_file_contents.get(rel_path)

            old_syms = self._extract_symbols(rel_path, old_src)
            new_syms = self._extract_symbols(rel_path, new_src)

            old_by_qname = {(s.qualified_name or s.name): s for s in old_syms}
            new_by_qname = {(s.qualified_name or s.name): s for s in new_syms}

            # Build pairs
            all_names = set(old_by_qname) | set(new_by_qname)
            for qname in all_names:
                old_s = old_by_qname.get(qname)
                new_s = new_by_qname.get(qname)
                if old_s or new_s:
                    changed_symbols.append((old_s, new_s))

        if not changed_symbols:
            return []

        # Load related doc sections from DB
        mapped_sections = await self._load_mapped_sections(db, repo.id, changed_symbols)

        # Also load all doc sections for the repo if affected_doc_files specified
        raw_doc_sections = await self._load_doc_sections(
            db, repo.id, affected_doc_files
        )

        # Merge mapped with raw
        for sym, sections in raw_doc_sections.items():
            if sym not in mapped_sections:
                mapped_sections[sym] = sections
            else:
                existing = {id(s) for s in mapped_sections[sym]}
                for s in sections:
                    if id(s) not in existing:
                        mapped_sections[sym].append(s)

        # Run drift detection
        findings = self.detector.detect(changed_symbols, mapped_sections)

        if not findings:
            return []

        # Generate suggestions and persist
        issues: list[DriftIssue] = []
        for finding in findings:
            if finding.confidence < settings.min_confidence_to_report:
                continue

            new_sym = next(
                (new for old, new in changed_symbols if new and new.name == finding.symbol_name),
                None,
            )
            section = self._find_section(finding, mapped_sections)

            # Generate suggestion
            suggestion = self.generator.generate(finding, new_sym, section)

            issue = DriftIssue(
                repo_id=repo.id,
                commit_sha=commit_sha,
                issue_type=_ISSUE_TYPE_MAP.get(finding.issue_type, IssueType.potentially_outdated),
                severity=_SEVERITY_MAP.get(finding.severity, IssueSeverity.medium),
                description=finding.description,
                evidence_code=finding.evidence_code,
                evidence_doc=finding.evidence_doc,
                doc_file_path=finding.doc_file_path,
                doc_start_line=finding.doc_start_line,
                doc_end_line=finding.doc_end_line,
                code_file_path=finding.code_file_path,
                suggested_correction=suggestion.replacement_text,
                confidence=finding.confidence,
                status=IssueStatus.open,
            )
            db.add(issue)
            issues.append(issue)

        await db.flush()

        # Store patches
        for issue, finding in zip(issues, findings[:len(issues)]):
            new_sym = next(
                (new for old, new in changed_symbols if new and new.name == finding.symbol_name),
                None,
            )
            section = self._find_section(finding, mapped_sections)
            if section and issue.suggested_correction:
                suggestion = self.generator.generate(finding, new_sym, section)
                if suggestion.method != "uncertain":
                    patch = SuggestionPatch(
                        issue_id=issue.id,
                        file_path=finding.doc_file_path,
                        original_text=suggestion.original_text,
                        replacement_text=suggestion.replacement_text,
                        start_line=finding.doc_start_line,
                        end_line=finding.doc_end_line,
                    )
                    db.add(patch)

        await db.commit()

        # Broadcast to SSE subscribers so the frontend updates immediately
        if issues:
            try:
                from backend.api.routes.events import broadcast
                broadcast("drift_detected", {
                    "repo_id": repo.id,
                    "repo_name": repo.name,
                    "commit_sha": commit_sha,
                    "count": len(issues),
                    "issues": [
                        {
                            "id": i.id,
                            "severity": i.severity.value,
                            "description": i.description[:120],
                            "doc_file_path": i.doc_file_path,
                        }
                        for i in issues
                    ],
                })
            except Exception:
                pass  # broadcasting is best-effort

        return issues

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_symbols(self, rel_path: str, source: Optional[str]) -> list[ExtractedSymbol]:
        if not source:
            return []
        ext = Path(rel_path).suffix.lower()
        if ext in _PYTHON_EXTS:
            return self.py_analyzer.analyze_file(rel_path, source=source)
        if ext in _JS_EXTS:
            return self.js_analyzer.analyze_file(rel_path, source=source)
        return []

    async def _load_mapped_sections(
        self,
        db: AsyncSession,
        repo_id: str,
        changed_symbols: list[tuple],
    ) -> dict[str, list[ParsedSection]]:
        """Load doc sections that are mapped to changed symbols."""
        result: dict[str, list[ParsedSection]] = {}

        for old_sym, new_sym in changed_symbols:
            sym = new_sym or old_sym
            if not sym:
                continue
            sym_name = sym.qualified_name or sym.name

            # Find DB symbol by name and file
            q = select(CodeSymbol).where(
                CodeSymbol.repo_id == repo_id,
                CodeSymbol.name == sym.name,
            )
            db_syms = (await db.execute(q)).scalars().all()

            for db_sym in db_syms:
                q2 = (
                    select(DocSection)
                    .join(CodeDocMapping, CodeDocMapping.section_id == DocSection.id)
                    .where(CodeDocMapping.symbol_id == db_sym.id)
                )
                sections_db = (await db.execute(q2)).scalars().all()
                parsed = [
                    ParsedSection(
                        file_path=s.file_path,
                        heading=s.section_heading,
                        heading_level=0,
                        content=s.content,
                        start_line=s.start_line,
                        end_line=s.end_line,
                    )
                    for s in sections_db
                ]
                if parsed:
                    result.setdefault(sym_name, []).extend(parsed)

        return result

    async def _load_doc_sections(
        self,
        db: AsyncSession,
        repo_id: str,
        file_paths: Optional[list[str]],
    ) -> dict[str, list[ParsedSection]]:
        """Load all doc sections for given files, keyed by keyword."""
        if not file_paths:
            return {}
        result: dict[str, list[ParsedSection]] = {}
        q = select(DocSection).where(
            DocSection.repo_id == repo_id,
            DocSection.file_path.in_(file_paths),
        )
        rows = (await db.execute(q)).scalars().all()
        for row in rows:
            sec = ParsedSection(
                file_path=row.file_path,
                heading=row.section_heading,
                heading_level=0,
                content=row.content,
                start_line=row.start_line,
                end_line=row.end_line,
            )
            result.setdefault(row.section_heading or "_preamble", []).append(sec)
        return result

    def _find_section(
        self,
        finding: DriftFinding,
        mapped_sections: dict[str, list[ParsedSection]],
    ) -> Optional[ParsedSection]:
        for sections in mapped_sections.values():
            for sec in sections:
                if (
                    sec.file_path == finding.doc_file_path
                    and sec.start_line <= finding.doc_start_line <= sec.end_line + 10
                ):
                    return sec
        return None
