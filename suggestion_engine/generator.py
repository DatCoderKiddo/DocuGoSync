"""
Suggestion engine — generates documentation corrections.

Strategy:
1. Deterministic correction for common patterns (signature updates, default changes).
2. AI-augmented rewrite for prose corrections when an AI provider is available.
3. Never invents code behaviour — all corrections are grounded in evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from code_indexer.symbol_types import ExtractedSymbol
from content_extractor.markdown_extractor import ParsedSection
from drift_detector.detector import DriftFinding
from .ai_client import AIClient


@dataclass
class SuggestionResult:
    finding: DriftFinding
    original_text: str
    replacement_text: str
    explanation: str
    confidence: float
    method: str            # deterministic | ai_assisted | uncertain


class SuggestionGenerator:
    def __init__(self, ai_client: Optional[AIClient] = None):
        self.ai = ai_client

    def generate(
        self,
        finding: DriftFinding,
        new_symbol: Optional[ExtractedSymbol],
        section: Optional[ParsedSection],
    ) -> SuggestionResult:
        # Try deterministic first
        result = self._deterministic(finding, new_symbol, section)
        if result:
            return result

        # Try AI augmentation
        if self.ai and self.ai.available() and section:
            result = self._ai_assisted(finding, new_symbol, section)
            if result:
                return result

        # Fallback: flag as uncertain, provide partial suggestion
        return SuggestionResult(
            finding=finding,
            original_text=finding.evidence_doc,
            replacement_text="[Review needed: insufficient evidence for automatic correction]",
            explanation=finding.description,
            confidence=0.2,
            method="uncertain",
        )

    # ── Deterministic patterns ────────────────────────────────────────────────

    def _deterministic(
        self,
        finding: DriftFinding,
        new_symbol: Optional[ExtractedSymbol],
        section: Optional[ParsedSection],
    ) -> Optional[SuggestionResult]:
        if new_symbol is None or section is None:
            return None

        text = section.content

        # Case 1: Outdated function signature documented explicitly
        if finding.issue_type == "outdated" and new_symbol.signature:
            old_sig_match = self._find_old_signature(new_symbol.name, text, new_symbol)
            if old_sig_match and new_symbol.signature:
                # Replace old signature with new one (preserve backtick formatting)
                new_text = text.replace(f"`{old_sig_match}`", f"`{new_symbol.signature}`")
                if new_text != text:
                    return SuggestionResult(
                        finding=finding,
                        original_text=f"`{old_sig_match}`",
                        replacement_text=f"`{new_symbol.signature}`",
                        explanation=(
                            f"Replaced old signature `{old_sig_match}` with "
                            f"current `{new_symbol.signature}`."
                        ),
                        confidence=0.90,
                        method="deterministic",
                    )

        # Case 2: Removed parameter still documented
        if "was removed" in finding.description and "parameter" in finding.description:
            removed_param = self._extract_param_name(finding.description, "removed from")
            if removed_param:
                # Suggest removing lines that document this param
                new_lines = []
                for line in text.splitlines():
                    if re.search(r"\b" + re.escape(removed_param) + r"\b", line):
                        continue  # skip the line
                    new_lines.append(line)
                new_text = "\n".join(new_lines)
                if new_text != text:
                    return SuggestionResult(
                        finding=finding,
                        original_text=finding.evidence_doc,
                        replacement_text=f"[Remove lines referencing `{removed_param}`]",
                        explanation=f"Parameter `{removed_param}` no longer exists.",
                        confidence=0.75,
                        method="deterministic",
                    )

        # Case 3: Changed default value
        if "default value" in finding.description and new_symbol.parameters:
            # Extract param name and old/new defaults from description
            m = re.search(r"Default value of `(\w+)` changed from `([^`]+)` to `([^`]+)`", finding.description)
            if m:
                param_name = m.group(1)
                old_default = m.group(2)
                new_default = m.group(3)
                new_text = text.replace(old_default, new_default)
                if new_text != text:
                    return SuggestionResult(
                        finding=finding,
                        original_text=old_default,
                        replacement_text=new_default,
                        explanation=(
                            f"Updated default value of `{param_name}` from "
                            f"`{old_default}` to `{new_default}`."
                        ),
                        confidence=0.88,
                        method="deterministic",
                    )

        return None

    def _find_old_signature(self, name: str, text: str, new_symbol: ExtractedSymbol) -> Optional[str]:
        """
        Find a documented function signature that differs from the current one.
        """
        pattern = re.compile(
            r"`" + re.escape(name) + r"\s*\([^`]*\)`",
            re.DOTALL,
        )
        for m in pattern.finditer(text):
            candidate = m.group(0).strip("`")
            if candidate != new_symbol.signature:
                return candidate
        return None

    def _extract_param_name(self, text: str, before_phrase: str) -> Optional[str]:
        m = re.search(r"`(\w+)`\s+was\s+removed", text)
        if m:
            return m.group(1)
        return None

    # ── AI-assisted correction ─────────────────────────────────────────────────

    def _ai_assisted(
        self,
        finding: DriftFinding,
        new_symbol: Optional[ExtractedSymbol],
        section: ParsedSection,
    ) -> Optional[SuggestionResult]:
        if self.ai is None:
            return None

        prompt = self._build_prompt(finding, new_symbol, section)
        response = self.ai.complete(prompt)
        if not response:
            return None

        # Parse response — expect JSON with original/replacement
        replacement = self._parse_ai_response(response, section.content)
        if not replacement:
            return None

        return SuggestionResult(
            finding=finding,
            original_text=finding.evidence_doc,
            replacement_text=replacement,
            explanation=f"AI-generated correction based on current code.",
            confidence=min(finding.confidence, 0.75),
            method="ai_assisted",
        )

    def _build_prompt(
        self,
        finding: DriftFinding,
        new_symbol: Optional[ExtractedSymbol],
        section: ParsedSection,
    ) -> str:
        return f"""You are a documentation corrector. Update only the specific outdated part of the documentation.

DOCUMENTATION SECTION (file: {section.file_path}, section: {section.heading}):
{section.content[:2000]}

DETECTED ISSUE:
{finding.description}

CURRENT CODE (ground truth):
{finding.evidence_code}

TASK: Rewrite only the specific outdated sentence or paragraph so it accurately reflects the current code.
- Do not add information not present in the code.
- Do not change unrelated parts of the documentation.
- Preserve formatting style (backticks, bullet points, etc.).
- Output ONLY the corrected text, nothing else.

CORRECTED TEXT:"""

    def _parse_ai_response(self, response: str, original: str) -> Optional[str]:
        # Strip common AI preamble patterns
        response = response.strip()
        for prefix in ["CORRECTED TEXT:", "Here is the correction:", "Updated:"]:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix):].strip()
        if response:
            return response
        return None
