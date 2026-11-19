"""
JavaScript / TypeScript code analyzer.

Uses regex-based extraction for the MVP.  Designed to be replaced or
augmented with Tree-sitter when that dependency is available.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .symbol_types import ExtractedSymbol, Parameter, SymbolKind


# ── Patterns ──────────────────────────────────────────────────────────────────

# function foo(a, b = 1) {
_FUNC_DECL = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
    re.MULTILINE,
)

# const foo = (a, b) => {   OR  const foo = async (a, b) => {
_ARROW_FUNC = re.compile(
    r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
    re.MULTILINE,
)

# class Foo {
_CLASS_DECL = re.compile(r"(?:export\s+)?class\s+(\w+)", re.MULTILINE)

# const FOO = "bar"  (all-caps constants)
_CONST_DECL = re.compile(r"(?:export\s+)?const\s+([A-Z_][A-Z0-9_]{2,})\s*=", re.MULTILINE)

# app.get('/path', ...)  app.post('/path', ...)
_ROUTE_DECL = re.compile(
    r"(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)

# process.env.FOO
_ENV_VAR = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)")


def _parse_js_params(raw: str) -> list[Parameter]:
    params: list[Parameter] = []
    if not raw.strip():
        return params
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        # destructuring: skip for now
        if part.startswith("{") or part.startswith("["):
            params.append(Parameter(name=part, required=True))
            continue
        # default: a = 1
        if "=" in part:
            name, _, default = part.partition("=")
            params.append(Parameter(name=name.strip(), default=default.strip(), required=False))
        else:
            # TypeScript: name: Type
            name = part.split(":")[0].strip()
            params.append(Parameter(name=name, required=True))
    return params


class JavaScriptAnalyzer:
    """
    Extracts code symbols from JS/TS files using regex.
    Covers the common patterns; a Tree-sitter integration would be more complete.
    """

    def analyze_file(self, file_path: str, source: Optional[str] = None) -> list[ExtractedSymbol]:
        path = Path(file_path)
        if source is None:
            if not path.exists():
                return []
            source = path.read_text(encoding="utf-8", errors="replace")

        symbols: list[ExtractedSymbol] = []
        lines = source.splitlines()

        def line_of(match: re.Match) -> int:
            return source[: match.start()].count("\n") + 1

        # Function declarations
        for m in _FUNC_DECL.finditer(source):
            name = m.group(1)
            params = _parse_js_params(m.group(2))
            ln = line_of(m)
            sig = f"function {name}({m.group(2).strip()})"
            symbols.append(ExtractedSymbol(
                name=name,
                kind=SymbolKind.function,
                file_path=file_path,
                start_line=ln,
                end_line=ln,
                signature=sig,
                parameters=params,
            ))

        # Arrow functions
        for m in _ARROW_FUNC.finditer(source):
            name = m.group(1)
            params = _parse_js_params(m.group(2))
            ln = line_of(m)
            sig = f"const {name} = ({m.group(2).strip()}) =>"
            symbols.append(ExtractedSymbol(
                name=name,
                kind=SymbolKind.function,
                file_path=file_path,
                start_line=ln,
                end_line=ln,
                signature=sig,
                parameters=params,
            ))

        # Classes
        for m in _CLASS_DECL.finditer(source):
            name = m.group(1)
            ln = line_of(m)
            symbols.append(ExtractedSymbol(
                name=name,
                kind=SymbolKind.klass,
                file_path=file_path,
                start_line=ln,
                end_line=ln,
            ))

        # Constants
        seen_names: set[str] = set()
        for m in _CONST_DECL.finditer(source):
            name = m.group(1)
            if name not in seen_names:
                seen_names.add(name)
                ln = line_of(m)
                symbols.append(ExtractedSymbol(
                    name=name,
                    kind=SymbolKind.constant,
                    file_path=file_path,
                    start_line=ln,
                    end_line=ln,
                ))

        # Routes
        for m in _ROUTE_DECL.finditer(source):
            method = m.group(1).upper()
            path_str = m.group(2)
            name = f"{method} {path_str}"
            ln = line_of(m)
            symbols.append(ExtractedSymbol(
                name=name,
                kind=SymbolKind.route,
                file_path=file_path,
                start_line=ln,
                end_line=ln,
                signature=name,
            ))

        # Env vars
        seen_env: set[str] = set()
        for m in _ENV_VAR.finditer(source):
            name = m.group(1)
            if name not in seen_env:
                seen_env.add(name)
                ln = line_of(m)
                symbols.append(ExtractedSymbol(
                    name=name,
                    kind=SymbolKind.env_var,
                    file_path=file_path,
                    start_line=ln,
                    end_line=ln,
                ))

        return symbols
