"""
Documentation drift detector.

Given:
  - A set of CodeDocMapping relationships (symbol ↔ doc section)
  - The CURRENT state of the symbol (possibly changed)
  - The CURRENT state of the doc section

Produces DriftFinding objects describing exactly what is out of date and why.

This module is deterministic — it does not call any LLM.
The suggestion_engine augments these findings with generated corrections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from code_indexer.symbol_types import ExtractedSymbol, SymbolKind, Parameter
from content_extractor.markdown_extractor import ParsedSection


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DriftFinding:
    issue_type: str          # outdated | missing | potentially_outdated
    severity: str            # critical | high | medium | low
    description: str
    evidence_code: str       # exact code excerpt
    evidence_doc: str        # exact doc text that is wrong
    doc_file_path: str
    doc_start_line: int
    doc_end_line: int
    code_file_path: str
    symbol_name: str
    confidence: float
    suggested_correction: Optional[str] = None   # filled in by suggestion_engine


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_param_in_text(param_name: str, text: str) -> bool:
    # backtick, bold, or plain word-boundary
    patterns = [
        f"`{param_name}`",
        f"**{param_name}**",
        f"*{param_name}*",
    ]
    if any(p in text for p in patterns):
        return True
    return bool(re.search(r"\b" + re.escape(param_name) + r"\b", text))


def _find_default_in_text(param_name: str, default_value: str, text: str) -> bool:
    """Check if the documentation mentions this param's default value near the param name."""
    # narrow window: find lines containing the param
    for line in text.splitlines():
        if _find_param_in_text(param_name, line):
            if default_value in line:
                return True
    return False


def _extract_documented_signature(symbol_name: str, section_text: str) -> Optional[str]:
    """
    Try to extract a function signature as written in the documentation.
    Looks for `name(...)` or `name(` patterns.
    """
    pattern = re.compile(
        r"`" + re.escape(symbol_name) + r"\s*\(([^`]*)\)`",
        re.DOTALL,
    )
    m = pattern.search(section_text)
    if m:
        return f"{symbol_name}({m.group(1)})"
    return None


def _params_in_documented_sig(doc_sig: str) -> list[str]:
    """Extract param names from a documented signature like `foo(a, b=1)`."""
    m = re.search(r"\(([^)]*)\)", doc_sig)
    if not m:
        return []
    raw = m.group(1)
    names = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        name = part.split("=")[0].split(":")[0].strip().lstrip("*")
        if name:
            names.append(name)
    return names


# ── Core checks ───────────────────────────────────────────────────────────────

def check_signature_drift(
    old_symbol: ExtractedSymbol,
    new_symbol: ExtractedSymbol,
    section: ParsedSection,
) -> list[DriftFinding]:
    """
    Compare old vs new symbol signature and check if the doc reflects the old one.
    If old signature is in the docs and new differs, flag it.
    """
    findings: list[DriftFinding] = []

    if new_symbol.signature == old_symbol.signature:
        return findings  # nothing changed

    # Check whether documentation mentions the old signature
    text = section.content
    old_doc_sig = _extract_documented_signature(old_symbol.name, text)
    if old_doc_sig:
        # Docs explicitly state the old signature — definite drift
        findings.append(DriftFinding(
            issue_type="outdated",
            severity="critical",
            description=(
                f"Function `{new_symbol.name}` signature changed from "
                f"`{old_symbol.signature}` to `{new_symbol.signature}`, "
                f"but documentation still shows `{old_doc_sig}`."
            ),
            evidence_code=new_symbol.signature or "",
            evidence_doc=old_doc_sig,
            doc_file_path=section.file_path,
            doc_start_line=section.start_line,
            doc_end_line=section.end_line,
            code_file_path=new_symbol.file_path,
            symbol_name=new_symbol.name,
            confidence=0.92,
        ))

    return findings


def check_parameter_drift(
    old_symbol: ExtractedSymbol,
    new_symbol: ExtractedSymbol,
    section: ParsedSection,
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    text = section.content
    old_params = {p.name: p for p in old_symbol.parameters}
    new_params = {p.name: p for p in new_symbol.parameters}

    # Removed parameters that are still mentioned in the docs
    for name, old_p in old_params.items():
        if name.startswith("*"):
            continue
        if name not in new_params:
            if _find_param_in_text(name, text):
                findings.append(DriftFinding(
                    issue_type="outdated",
                    severity="high",
                    description=(
                        f"Parameter `{name}` was removed from `{new_symbol.name}` "
                        f"but is still documented."
                    ),
                    evidence_code=f"{new_symbol.signature}",
                    evidence_doc=f"Section mentions removed parameter `{name}`",
                    doc_file_path=section.file_path,
                    doc_start_line=section.start_line,
                    doc_end_line=section.end_line,
                    code_file_path=new_symbol.file_path,
                    symbol_name=new_symbol.name,
                    confidence=0.85,
                ))

    # New required parameters not in docs
    for name, new_p in new_params.items():
        if name.startswith("*"):
            continue
        if name not in old_params and new_p.required:
            if not _find_param_in_text(name, text):
                findings.append(DriftFinding(
                    issue_type="missing",
                    severity="high",
                    description=(
                        f"New required parameter `{name}` was added to "
                        f"`{new_symbol.name}` but is not documented."
                    ),
                    evidence_code=f"{new_symbol.signature}",
                    evidence_doc="(not mentioned)",
                    doc_file_path=section.file_path,
                    doc_start_line=section.start_line,
                    doc_end_line=section.end_line,
                    code_file_path=new_symbol.file_path,
                    symbol_name=new_symbol.name,
                    confidence=0.80,
                ))

    # Changed default values
    for name, new_p in new_params.items():
        if name.startswith("*") or name not in old_params:
            continue
        old_p = old_params[name]
        if old_p.default != new_p.default:
            if old_p.default and new_p.default:
                # Check if old default is explicitly stated in docs
                if _find_default_in_text(name, old_p.default, text):
                    findings.append(DriftFinding(
                        issue_type="outdated",
                        severity="high",
                        description=(
                            f"Default value of `{name}` changed from "
                            f"`{old_p.default}` to `{new_p.default}` in `{new_symbol.name}`, "
                            f"but documentation still states `{old_p.default}`."
                        ),
                        evidence_code=f"{new_symbol.signature}",
                        evidence_doc=f"Documentation mentions default `{old_p.default}` for `{name}`",
                        doc_file_path=section.file_path,
                        doc_start_line=section.start_line,
                        doc_end_line=section.end_line,
                        code_file_path=new_symbol.file_path,
                        symbol_name=new_symbol.name,
                        confidence=0.88,
                    ))

    return findings


def check_symbol_removed(
    removed_symbol: ExtractedSymbol,
    section: ParsedSection,
) -> list[DriftFinding]:
    """Flag documentation that still mentions a deleted function/class."""
    findings: list[DriftFinding] = []
    text = section.content
    name = removed_symbol.name

    if _find_param_in_text(name, text) or f"{name}(" in text:
        findings.append(DriftFinding(
            issue_type="outdated",
            severity="critical",
            description=(
                f"`{name}` was removed from the codebase but is still "
                f"documented in '{section.file_path}' (section: '{section.heading}')."
            ),
            evidence_code=f"# Symbol `{name}` was deleted",
            evidence_doc=f"Section still references `{name}`",
            doc_file_path=section.file_path,
            doc_start_line=section.start_line,
            doc_end_line=section.end_line,
            code_file_path=removed_symbol.file_path,
            symbol_name=name,
            confidence=0.9,
        ))
    return findings


def check_symbol_renamed(
    old_symbol: ExtractedSymbol,
    new_name: str,
    section: ParsedSection,
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    text = section.content
    old_name = old_symbol.name

    if _find_param_in_text(old_name, text) or f"{old_name}(" in text:
        findings.append(DriftFinding(
            issue_type="outdated",
            severity="critical",
            description=(
                f"`{old_name}` was renamed to `{new_name}` but documentation "
                f"still uses the old name."
            ),
            evidence_code=f"{old_name} → {new_name}",
            evidence_doc=f"Section references old name `{old_name}`",
            doc_file_path=section.file_path,
            doc_start_line=section.start_line,
            doc_end_line=section.end_line,
            code_file_path=old_symbol.file_path,
            symbol_name=old_name,
            confidence=0.92,
        ))
    return findings


# ── Main detector class ───────────────────────────────────────────────────────

class DriftDetector:
    """
    Coordinates drift detection across changed symbols and their mapped sections.
    """

    def detect(
        self,
        changed_symbols: list[tuple[Optional[ExtractedSymbol], Optional[ExtractedSymbol]]],
        # (old_symbol, new_symbol) — None on add or delete
        mapped_sections: dict[str, list[ParsedSection]],
        # symbol qualified_name → list of sections
    ) -> list[DriftFinding]:
        all_findings: list[DriftFinding] = []

        for old_sym, new_sym in changed_symbols:
            # Deleted symbol
            if old_sym and new_sym is None:
                sections = mapped_sections.get(old_sym.qualified_name or old_sym.name, [])
                for sec in sections:
                    all_findings.extend(check_symbol_removed(old_sym, sec))
                continue

            # Added symbol — check if important new things need docs
            if old_sym is None and new_sym:
                # Only flag if it's a public function/class with no docs
                if (
                    new_sym.kind in (SymbolKind.function, SymbolKind.klass)
                    and not new_sym.name.startswith("_")
                    and not new_sym.docstring
                    and not mapped_sections.get(new_sym.qualified_name or new_sym.name)
                ):
                    all_findings.append(DriftFinding(
                        issue_type="missing",
                        severity="medium",
                        description=f"New public symbol `{new_sym.name}` has no documentation.",
                        evidence_code=new_sym.signature or new_sym.name,
                        evidence_doc="(no documentation found)",
                        doc_file_path="README.md",
                        doc_start_line=0,
                        doc_end_line=0,
                        code_file_path=new_sym.file_path,
                        symbol_name=new_sym.name,
                        confidence=0.6,
                    ))
                continue

            # Modified symbol
            if old_sym and new_sym:
                sections = mapped_sections.get(old_sym.qualified_name or old_sym.name, [])
                for sec in sections:
                    all_findings.extend(check_signature_drift(old_sym, new_sym, sec))
                    all_findings.extend(check_parameter_drift(old_sym, new_sym, sec))

        return all_findings
