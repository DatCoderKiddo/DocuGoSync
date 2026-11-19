"""
Relationship Engine — maps code symbols to documentation sections.

Uses a multi-strategy approach (no single-point-of-failure):

  1. Exact name match       — symbol name appears verbatim in section text
  2. Function-ref match     — `name(...)` backtick syntax in Markdown
  3. Keyword/phrase match   — name appears as word boundary in prose
  4. Env-var match          — UPPERCASE_NAMES matched in both doc and code
  5. Config/constant match  — constant names matched
  6. Section-heading match  — heading text relates to the symbol

Each match produces an Evidence object with a confidence score.
Mappings with confidence < threshold are discarded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from code_indexer.symbol_types import ExtractedSymbol, SymbolKind
from content_extractor.markdown_extractor import ParsedSection


MIN_CONFIDENCE = 0.3


@dataclass
class MappingEvidence:
    symbol: ExtractedSymbol
    section: ParsedSection
    evidence_type: str           # exact_name | signature_ref | keyword | semantic | git_history
    evidence_detail: str
    confidence: float


def _word_in_text(word: str, text: str) -> bool:
    pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
    return bool(pattern.search(text))


def _exact_name_match(symbol: ExtractedSymbol, section: ParsedSection) -> Optional[MappingEvidence]:
    """Symbol name appears in section content (backtick or plain)."""
    name = symbol.name
    if not name or len(name) < 2:
        return None
    text = (section.heading or "") + "\n" + section.content
    # backtick reference — highest confidence
    if f"`{name}`" in text or f"`{name}(" in text:
        return MappingEvidence(
            symbol=symbol,
            section=section,
            evidence_type="exact_name",
            evidence_detail=f"Backtick reference to `{name}` found in section '{section.heading}'",
            confidence=0.9,
        )
    # word-boundary plain text
    if _word_in_text(name, text):
        confidence = 0.65 if len(name) > 4 else 0.4
        return MappingEvidence(
            symbol=symbol,
            section=section,
            evidence_type="exact_name",
            evidence_detail=f"Name '{name}' mentioned in section '{section.heading}'",
            confidence=confidence,
        )
    return None


def _signature_ref_match(symbol: ExtractedSymbol, section: ParsedSection) -> Optional[MappingEvidence]:
    """The section contains a function call syntax matching this symbol."""
    if symbol.kind not in (SymbolKind.function, SymbolKind.method):
        return None
    # find `name(...)` patterns in section
    for func_name, _ in section.referenced_functions:
        if func_name == symbol.name:
            return MappingEvidence(
                symbol=symbol,
                section=section,
                evidence_type="signature_ref",
                evidence_detail=f"Function call `{func_name}(...)` found in section '{section.heading}'",
                confidence=0.95,
            )
    return None


def _env_var_match(symbol: ExtractedSymbol, section: ParsedSection) -> Optional[MappingEvidence]:
    if symbol.kind != SymbolKind.env_var:
        return None
    if symbol.name in section.env_vars:
        return MappingEvidence(
            symbol=symbol,
            section=section,
            evidence_type="keyword",
            evidence_detail=f"Environment variable {symbol.name} mentioned in section '{section.heading}'",
            confidence=0.85,
        )
    return None


def _heading_match(symbol: ExtractedSymbol, section: ParsedSection) -> Optional[MappingEvidence]:
    if not section.heading:
        return None
    heading_lower = section.heading.lower()
    name_lower = symbol.name.lower()
    # strip leading underscores for private methods
    clean_name = name_lower.lstrip("_")
    if clean_name in heading_lower:
        return MappingEvidence(
            symbol=symbol,
            section=section,
            evidence_type="keyword",
            evidence_detail=f"Symbol name '{symbol.name}' appears in heading '{section.heading}'",
            confidence=0.7,
        )
    return None


def _keyword_phrase_match(symbol: ExtractedSymbol, section: ParsedSection) -> Optional[MappingEvidence]:
    """
    For multi-word or camelCase names, split and check if key words appear.
    Only applies when name length > 4.
    """
    name = symbol.name
    if len(name) < 5:
        return None
    # split camelCase / snake_case
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("_", " ").lower().split()
    if len(words) < 2:
        return None
    text = (section.heading or "").lower() + " " + section.content.lower()
    matched = sum(1 for w in words if len(w) > 3 and w in text)
    if matched >= max(2, len(words) // 2):
        return MappingEvidence(
            symbol=symbol,
            section=section,
            evidence_type="keyword",
            evidence_detail=f"Keywords from '{name}' found in section '{section.heading}'",
            confidence=0.45,
        )
    return None


class RelationshipMapper:
    """
    Given lists of code symbols and documentation sections,
    produces a list of MappingEvidence objects.

    Callers persist these as CodeDocMapping rows.
    """

    def build_mappings(
        self,
        symbols: list[ExtractedSymbol],
        sections: list[ParsedSection],
        min_confidence: float = MIN_CONFIDENCE,
    ) -> list[MappingEvidence]:
        results: list[MappingEvidence] = []
        # de-duplicate: keep only the best evidence per (symbol, section) pair
        best: dict[tuple[str, int, int], MappingEvidence] = {}

        for symbol in symbols:
            for section in sections:
                candidates: list[MappingEvidence] = []
                for strategy in [
                    _signature_ref_match,
                    _exact_name_match,
                    _env_var_match,
                    _heading_match,
                    _keyword_phrase_match,
                ]:
                    ev = strategy(symbol, section)
                    if ev and ev.confidence >= min_confidence:
                        candidates.append(ev)

                if not candidates:
                    continue

                # keep highest confidence
                best_candidate = max(candidates, key=lambda e: e.confidence)
                key = (symbol.file_path + symbol.name, section.start_line, id(section))
                existing = best.get(key)
                if existing is None or best_candidate.confidence > existing.confidence:
                    best[key] = best_candidate

        return list(best.values())
