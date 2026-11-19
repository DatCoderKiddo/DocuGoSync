"""
Markdown documentation parser.

Splits a Markdown document into sections by heading, extracts content,
symbol references, and code blocks.  Returns structured DocSection objects
that can be stored and cross-referenced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s*#+)?$", re.MULTILINE)
_CODE_BLOCK_RE = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_FUNC_REF_RE = re.compile(r"`([A-Za-z_]\w*)\s*\(([^)]*)\)`")
_SYMBOL_RE = re.compile(r"`([A-Za-z_]\w+)`")
_ENV_VAR_RE = re.compile(r"\b([A-Z_]{2,}[A-Z0-9_]*)\b")
_FLAG_RE = re.compile(r"--([a-z][a-z0-9-]+)")


@dataclass
class ParsedSection:
    file_path: str
    heading: Optional[str]
    heading_level: int
    content: str
    start_line: int
    end_line: int
    code_blocks: list[str] = field(default_factory=list)
    referenced_symbols: list[str] = field(default_factory=list)   # backtick names
    referenced_functions: list[tuple[str, str]] = field(default_factory=list)  # (name, raw_params)
    env_vars: list[str] = field(default_factory=list)
    cli_flags: list[str] = field(default_factory=list)
    section_type: str = "generic"


def _classify_section(heading: Optional[str], content: str) -> str:
    if not heading:
        return "generic"
    h = heading.lower()
    if any(kw in h for kw in ("install", "setup", "getting started", "quick start")):
        return "guide"
    if any(kw in h for kw in ("api", "endpoint", "route")):
        return "api_doc"
    if any(kw in h for kw in ("auth", "authentication", "login", "security")):
        return "api_doc"
    if any(kw in h for kw in ("config", "configuration", "environment", "env")):
        return "guide"
    if any(kw in h for kw in ("cli", "command", "usage")):
        return "guide"
    if any(kw in h for kw in ("changelog", "release", "history")):
        return "changelog"
    return "generic"


def _enrich_section(section: ParsedSection) -> None:
    text = section.content
    section.code_blocks = _CODE_BLOCK_RE.findall(text)
    section.referenced_functions = [(m.group(1), m.group(2)) for m in _FUNC_REF_RE.finditer(text)]
    section.referenced_symbols = list({m.group(1) for m in _SYMBOL_RE.finditer(text)})
    section.env_vars = list({m.group(1) for m in _ENV_VAR_RE.finditer(text)})
    section.cli_flags = list({m.group(1) for m in _FLAG_RE.finditer(text)})
    section.section_type = _classify_section(section.heading, text)


class MarkdownExtractor:
    """
    Parses a Markdown file into ParsedSection objects.

    Each section corresponds to a heading block.  The content before the
    first heading (if any) becomes a section with heading=None.
    """

    def extract_file(self, file_path: str, content: Optional[str] = None) -> list[ParsedSection]:
        path = Path(file_path)
        if content is None:
            if not path.exists():
                return []
            content = path.read_text(encoding="utf-8", errors="replace")

        lines = content.splitlines()
        sections: list[ParsedSection] = []

        # find all headings and their line positions
        heading_positions: list[tuple[int, int, str]] = []  # (line_idx_0based, level, text)
        for i, line in enumerate(lines):
            m = _HEADING_RE.match(line)
            if m:
                heading_positions.append((i, len(m.group(1)), m.group(2).strip()))

        def _make_section(heading: Optional[str], level: int, start: int, end: int) -> ParsedSection:
            raw = "\n".join(lines[start:end])
            sec = ParsedSection(
                file_path=file_path,
                heading=heading,
                heading_level=level,
                content=raw,
                start_line=start + 1,   # 1-indexed
                end_line=end,
            )
            _enrich_section(sec)
            return sec

        if not heading_positions:
            # no headings — whole file is one section
            sec = _make_section(None, 0, 0, len(lines))
            sections.append(sec)
            return sections

        # preamble before first heading
        if heading_positions[0][0] > 0:
            sec = _make_section(None, 0, 0, heading_positions[0][0])
            sections.append(sec)

        for idx, (line_idx, level, heading_text) in enumerate(heading_positions):
            if idx + 1 < len(heading_positions):
                end = heading_positions[idx + 1][0]
            else:
                end = len(lines)
            sec = _make_section(heading_text, level, line_idx, end)
            sections.append(sec)

        return sections

    def extract_string(self, content: str, virtual_path: str = "document.md") -> list[ParsedSection]:
        return self.extract_file(virtual_path, content=content)
