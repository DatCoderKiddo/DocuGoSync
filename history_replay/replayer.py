"""
Historical PR replay engine.

Runs DocuGoSync against known historical cases where:
  - Code changed
  - Documentation was NOT updated at that commit
  - A later commit fixed the documentation

This is used to validate the detection accuracy against real-world cases.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from code_indexer.python_analyzer import PythonAnalyzer
from code_indexer.javascript_analyzer import JavaScriptAnalyzer
from content_extractor.markdown_extractor import MarkdownExtractor
from relationship_engine.mapper import RelationshipMapper
from drift_detector.detector import DriftDetector, DriftFinding
from suggestion_engine.generator import SuggestionGenerator

logger = logging.getLogger(__name__)


@dataclass
class ReplayCase:
    """One historical test case."""
    repo_name: str
    repo_url: str
    code_change_commit: str         # the commit that changed code (but not docs)
    doc_fix_commit: str             # the later commit that fixed the docs
    description: str
    # Pre-fetched file contents (to avoid hitting GitHub during tests)
    old_code_path: str
    old_code: str
    new_code_path: str
    new_code: str
    old_doc_path: str
    old_doc: str
    expected_symbol_name: str       # symbol that should be flagged
    expected_issue_type: str        # outdated | missing
    historical_fix: str             # the actual correction made in doc_fix_commit


@dataclass
class ReplayResult:
    case: ReplayCase
    findings: list[DriftFinding]
    detected: bool                  # did we find the expected issue?
    suggestion_matches: bool        # does our suggestion resemble the historical fix?
    false_positives: int
    notes: str = ""


class HistoryReplayer:
    def __init__(self):
        self.py_analyzer = PythonAnalyzer()
        self.js_analyzer = JavaScriptAnalyzer()
        self.md_extractor = MarkdownExtractor()
        self.mapper = RelationshipMapper()
        self.detector = DriftDetector()
        self.generator = SuggestionGenerator()

    def replay(self, case: ReplayCase) -> ReplayResult:
        logger.info("Replaying case: %s — %s", case.repo_name, case.description)

        # 1. Extract old and new symbols
        ext = Path(case.new_code_path).suffix.lower()
        if ext == ".py":
            old_syms = self.py_analyzer.analyze_file(case.old_code_path, source=case.old_code)
            new_syms = self.py_analyzer.analyze_file(case.new_code_path, source=case.new_code)
        else:
            old_syms = self.js_analyzer.analyze_file(case.old_code_path, source=case.old_code)
            new_syms = self.js_analyzer.analyze_file(case.new_code_path, source=case.new_code)

        # 2. Build pairs
        old_by_name = {(s.qualified_name or s.name): s for s in old_syms}
        new_by_name = {(s.qualified_name or s.name): s for s in new_syms}
        all_names = set(old_by_name) | set(new_by_name)
        pairs = [(old_by_name.get(n), new_by_name.get(n)) for n in all_names]

        # 3. Extract doc sections
        sections = self.md_extractor.extract_string(case.old_doc, case.old_doc_path)

        # 4. Build mappings
        all_syms = list(old_by_name.values()) + [s for s in new_by_name.values()
                                                   if s.name not in old_by_name]
        evidences = self.mapper.build_mappings(all_syms, sections)
        mapped: dict[str, list] = {}
        for ev in evidences:
            key = ev.symbol.qualified_name or ev.symbol.name
            mapped.setdefault(key, []).append(ev.section)

        # 5. Detect
        findings = self.detector.detect(pairs, mapped)

        # 6. Evaluate
        detected = any(
            case.expected_symbol_name in f.symbol_name or
            case.expected_symbol_name in f.description
            for f in findings
        )

        # Count false positives (findings not related to expected)
        fps = sum(
            1 for f in findings
            if case.expected_symbol_name not in f.symbol_name
            and case.expected_symbol_name not in f.description
        )

        # 7. Generate suggestions for the detected findings
        suggestion_matches = False
        for finding in findings:
            if case.expected_symbol_name in finding.symbol_name:
                # Find matching symbol and section
                new_sym = new_by_name.get(case.expected_symbol_name)
                sec = None
                for s in sections:
                    if s.start_line <= finding.doc_start_line <= s.end_line + 10:
                        sec = s
                        break
                result = self.generator.generate(finding, new_sym, sec)
                # Very loose match — just check if key terms appear
                fix_lower = case.historical_fix.lower()
                suggestion_lower = result.replacement_text.lower()
                suggestion_matches = any(
                    word in suggestion_lower
                    for word in fix_lower.split()
                    if len(word) > 4
                )
                break

        return ReplayResult(
            case=case,
            findings=findings,
            detected=detected,
            suggestion_matches=suggestion_matches,
            false_positives=fps,
        )

    def replay_all(self, cases: list[ReplayCase]) -> list[ReplayResult]:
        return [self.replay(c) for c in cases]

    def print_report(self, results: list[ReplayResult]) -> str:
        lines = [
            "=" * 70,
            "DOCUGOSYNC — HISTORICAL REPLAY REPORT",
            "=" * 70,
        ]
        detected_count = sum(1 for r in results if r.detected)
        total = len(results)

        for r in results:
            status = "DETECTED" if r.detected else "MISSED"
            match = "MATCHES" if r.suggestion_matches else "DIFFERENT"
            lines += [
                f"\n[{status}] {r.case.repo_name} — {r.case.description}",
                f"  Commit: {r.case.code_change_commit}",
                f"  Expected symbol: {r.case.expected_symbol_name}",
                f"  Findings: {len(r.findings)} total, {r.false_positives} false positives",
                f"  Suggestion: {match}",
                f"  Historical fix: {r.case.historical_fix[:80]}…",
            ]
            if r.notes:
                lines.append(f"  Notes: {r.notes}")

        lines += [
            "",
            "=" * 70,
            f"SUMMARY: {detected_count}/{total} cases detected correctly",
            f"Detection rate: {detected_count/total*100:.0f}%" if total else "N/A",
            "=" * 70,
        ]
        return "\n".join(lines)


def load_fixture_cases(fixture_path: str) -> list[ReplayCase]:
    """Load replay cases from a JSON fixture file."""
    data = json.loads(Path(fixture_path).read_text())
    return [ReplayCase(**item) for item in data]
