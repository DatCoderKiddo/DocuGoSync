"""
Repository indexing orchestrator.

Coordinates: crawl → extract symbols → extract doc sections → build mappings.
Writes results to the database.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from storage.models import (
    Repository, CodeSymbol, DocSection, CodeDocMapping,
    SymbolType, SectionType, EvidenceType, IndexStatus,
)
from code_indexer.python_analyzer import PythonAnalyzer
from code_indexer.javascript_analyzer import JavaScriptAnalyzer
from code_indexer.symbol_types import SymbolKind
from content_extractor.markdown_extractor import MarkdownExtractor
from document_crawler.crawler import RepoCrawler
from relationship_engine.mapper import RelationshipMapper

logger = logging.getLogger(__name__)

_PYTHON_EXTS = {".py"}
_JS_EXTS = {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}

_KIND_MAP = {
    SymbolKind.function: SymbolType.function,
    SymbolKind.klass: SymbolType.klass,
    SymbolKind.method: SymbolType.method,
    SymbolKind.constant: SymbolType.constant,
    SymbolKind.route: SymbolType.route,
    SymbolKind.cli_arg: SymbolType.cli_arg,
    SymbolKind.env_var: SymbolType.env_var,
    SymbolKind.module: SymbolType.module,
}

_SEC_TYPE_MAP = {
    "readme": SectionType.readme,
    "api_doc": SectionType.api_doc,
    "guide": SectionType.guide,
    "changelog": SectionType.changelog,
    "generic": SectionType.generic,
}

_EV_TYPE_MAP = {
    "exact_name": EvidenceType.exact_name,
    "signature_ref": EvidenceType.signature_ref,
    "keyword": EvidenceType.keyword,
    "semantic": EvidenceType.semantic,
    "git_history": EvidenceType.git_history,
}


class RepositoryIndexer:
    def __init__(self):
        self.py_analyzer = PythonAnalyzer()
        self.js_analyzer = JavaScriptAnalyzer()
        self.md_extractor = MarkdownExtractor()
        self.crawler = RepoCrawler()
        self.mapper = RelationshipMapper()

    async def index_repository(
        self,
        db: AsyncSession,
        repo: Repository,
    ) -> None:
        """
        Full index of a repository.  Clears existing symbols/sections/mappings
        and rebuilds from scratch.
        """
        repo.index_status = IndexStatus.indexing
        await db.commit()

        try:
            await self._clear_index(db, repo.id)

            root = repo.local_path
            if not root or not Path(root).exists():
                raise ValueError(f"Repository path not found: {root}")

            crawl = self.crawler.crawl_path(root)
            commit_sha = repo.head_commit or "HEAD"

            # ── Index code files ──────────────────────────────────────────────
            all_symbols = []
            for f in crawl.code_files:
                ext = Path(f.relative_path).suffix.lower()
                if ext in _PYTHON_EXTS:
                    syms = self.py_analyzer.analyze_file(f.absolute_path)
                elif ext in _JS_EXTS:
                    syms = self.js_analyzer.analyze_file(f.absolute_path)
                else:
                    continue

                for sym in syms:
                    db_sym = CodeSymbol(
                        repo_id=repo.id,
                        file_path=f.relative_path,
                        symbol_type=_KIND_MAP.get(sym.kind, SymbolType.function),
                        name=sym.name,
                        qualified_name=sym.qualified_name,
                        signature=sym.signature,
                        parameters=json.dumps([
                            {"name": p.name, "annotation": p.annotation,
                             "default": p.default, "required": p.required}
                            for p in sym.parameters
                        ]),
                        return_type=sym.return_type,
                        docstring=sym.docstring,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        commit_sha=commit_sha,
                    )
                    db.add(db_sym)
                    all_symbols.append((sym, db_sym))

            await db.flush()

            # ── Index documentation files ─────────────────────────────────────
            all_sections = []
            for f in crawl.doc_files:
                if not f.relative_path.endswith(".md"):
                    continue
                sections = self.md_extractor.extract_file(f.absolute_path)
                for sec in sections:
                    db_sec = DocSection(
                        repo_id=repo.id,
                        file_path=f.relative_path,
                        section_heading=sec.heading,
                        content=sec.content,
                        start_line=sec.start_line,
                        end_line=sec.end_line,
                        section_type=_SEC_TYPE_MAP.get(sec.section_type, SectionType.generic),
                        commit_sha=commit_sha,
                    )
                    db.add(db_sec)
                    all_sections.append((sec, db_sec))

            await db.flush()

            # ── Build mappings ────────────────────────────────────────────────
            raw_symbols = [s for s, _ in all_symbols]
            raw_sections = [s for s, _ in all_sections]
            evidences = self.mapper.build_mappings(raw_symbols, raw_sections)

            # Build lookup maps
            sym_lookup: dict[tuple, any] = {}
            for raw_sym, db_sym in all_symbols:
                key = (raw_sym.file_path, raw_sym.name, raw_sym.start_line)
                sym_lookup[key] = db_sym

            sec_lookup: dict[tuple, any] = {}
            for raw_sec, db_sec in all_sections:
                key = (raw_sec.file_path, raw_sec.start_line)
                sec_lookup[key] = db_sec

            for ev in evidences:
                sym_key = (ev.symbol.file_path, ev.symbol.name, ev.symbol.start_line)
                sec_key = (ev.section.file_path, ev.section.start_line)
                db_sym = sym_lookup.get(sym_key)
                db_sec = sec_lookup.get(sec_key)
                if db_sym and db_sec:
                    mapping = CodeDocMapping(
                        repo_id=repo.id,
                        symbol_id=db_sym.id,
                        section_id=db_sec.id,
                        evidence_type=_EV_TYPE_MAP.get(ev.evidence_type, EvidenceType.keyword),
                        evidence_detail=ev.evidence_detail,
                        confidence=ev.confidence,
                    )
                    db.add(mapping)

            from datetime import datetime
            repo.index_status = IndexStatus.ready
            repo.last_indexed_at = datetime.utcnow()
            await db.commit()
            logger.info("Indexed repository %s: %d symbols, %d sections, %d mappings",
                        repo.name, len(all_symbols), len(all_sections), len(evidences))

        except Exception as e:
            repo.index_status = IndexStatus.error
            repo.error_message = str(e)
            await db.commit()
            logger.exception("Failed to index repository %s", repo.id)
            raise

    async def _clear_index(self, db: AsyncSession, repo_id: str) -> None:
        await db.execute(delete(CodeDocMapping).where(CodeDocMapping.repo_id == repo_id))
        await db.execute(delete(CodeSymbol).where(CodeSymbol.repo_id == repo_id))
        await db.execute(delete(DocSection).where(DocSection.repo_id == repo_id))
        await db.commit()
