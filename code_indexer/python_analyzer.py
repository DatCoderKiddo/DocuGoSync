"""
Python AST-based code analyzer.

Extracts functions, classes, methods, constants, environment variables,
and CLI arguments from Python source files without executing the code.
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path
from typing import Optional

from .symbol_types import ExtractedSymbol, Parameter, SymbolKind


# ── Helpers ───────────────────────────────────────────────────────────────────

def _node_source(source_lines: list[str], node: ast.AST) -> str:
    """Return the original source text for an AST node."""
    start = node.lineno - 1  # type: ignore[attr-defined]
    end = node.end_lineno     # type: ignore[attr-defined]
    return "\n".join(source_lines[start:end])


def _annotation_str(node: Optional[ast.expr]) -> Optional[str]:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _default_str(node: Optional[ast.expr]) -> Optional[str]:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _build_signature(name: str, args: ast.arguments, returns: Optional[ast.expr]) -> str:
    """Reconstruct a readable function signature string."""
    parts: list[str] = []

    # positional-or-keyword args (without defaults)
    all_args = args.posonlyargs + args.args
    defaults = args.defaults
    # defaults are right-aligned
    n_no_default = len(all_args) - len(defaults)

    for i, arg in enumerate(all_args):
        annotation = _annotation_str(arg.annotation)
        default_idx = i - n_no_default
        if default_idx >= 0:
            default = _default_str(defaults[default_idx])
        else:
            default = None

        param_str = arg.arg
        if annotation:
            param_str += f": {annotation}"
        if default is not None:
            param_str += f" = {default}"
        parts.append(param_str)

    if args.vararg:
        a = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            a += f": {_annotation_str(args.vararg.annotation)}"
        parts.append(a)

    if args.kwarg:
        a = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            a += f": {_annotation_str(args.kwarg.annotation)}"
        parts.append(a)

    for kwarg in args.kwonlyargs:
        # find in kw_defaults
        # kw_defaults are parallel, may contain None
        annotation = _annotation_str(kwarg.annotation)
        param_str = kwarg.arg
        if annotation:
            param_str += f": {annotation}"
        parts.append(param_str)

    ret = ""
    if returns:
        ret = f" -> {_annotation_str(returns)}"

    return f"{name}({', '.join(parts)}){ret}"


def _extract_parameters(args: ast.arguments) -> list[Parameter]:
    params: list[Parameter] = []
    all_args = args.posonlyargs + args.args
    defaults = args.defaults
    n_no_default = len(all_args) - len(defaults)

    for i, arg in enumerate(all_args):
        if arg.arg in ("self", "cls"):
            continue
        annotation = _annotation_str(arg.annotation)
        default_idx = i - n_no_default
        default = _default_str(defaults[default_idx]) if default_idx >= 0 else None
        params.append(Parameter(
            name=arg.arg,
            annotation=annotation,
            default=default,
            required=(default is None),
        ))

    if args.vararg:
        params.append(Parameter(name=f"*{args.vararg.arg}", required=False))

    for i, kwarg in enumerate(args.kwonlyargs):
        kw_default = args.kw_defaults[i] if i < len(args.kw_defaults) else None
        default = _default_str(kw_default) if kw_default else None
        params.append(Parameter(
            name=kwarg.arg,
            annotation=_annotation_str(kwarg.annotation),
            default=default,
            required=(default is None),
        ))

    if args.kwarg:
        params.append(Parameter(name=f"**{args.kwarg.arg}", required=False))

    return params


def _get_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> Optional[str]:
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        return textwrap.dedent(node.body[0].value.value).strip()
    return None


# ── Env-var and CLI extraction via heuristics ────────────────────────────────

_ENV_PATTERNS = [
    re.compile(r'os\.environ\.get\(["\']([A-Z_][A-Z0-9_]*)["\']'),
    re.compile(r'os\.environ\[["\']([A-Z_][A-Z0-9_]*)["\']'),
    re.compile(r'os\.getenv\(["\']([A-Z_][A-Z0-9_]*)["\']'),
]


def _find_env_vars(source: str, file_path: str) -> list[ExtractedSymbol]:
    symbols: list[ExtractedSymbol] = []
    seen: set[str] = set()
    for i, line in enumerate(source.splitlines(), start=1):
        for pattern in _ENV_PATTERNS:
            for m in pattern.finditer(line):
                name = m.group(1)
                if name not in seen:
                    seen.add(name)
                    symbols.append(ExtractedSymbol(
                        name=name,
                        kind=SymbolKind.env_var,
                        file_path=file_path,
                        start_line=i,
                        end_line=i,
                        signature=f"os.environ['{name}']",
                    ))
    return symbols


# ── Main analyzer ─────────────────────────────────────────────────────────────

class PythonAnalyzer:
    """
    Analyzes a Python source file and returns a list of ExtractedSymbol objects.
    Uses the stdlib ast module — no code execution.
    """

    def analyze_file(self, file_path: str, source: Optional[str] = None) -> list[ExtractedSymbol]:
        path = Path(file_path)
        if source is None:
            if not path.exists():
                return []
            source = path.read_text(encoding="utf-8", errors="replace")

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        source_lines = source.splitlines()
        symbols: list[ExtractedSymbol] = []

        self._walk(tree, source_lines, file_path, symbols, class_name=None)
        symbols.extend(_find_env_vars(source, file_path))
        return symbols

    def _walk(
        self,
        node: ast.AST,
        source_lines: list[str],
        file_path: str,
        symbols: list[ExtractedSymbol],
        class_name: Optional[str],
    ) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                sym = ExtractedSymbol(
                    name=child.name,
                    kind=SymbolKind.klass,
                    file_path=file_path,
                    start_line=child.lineno,
                    end_line=child.end_lineno,  # type: ignore[attr-defined]
                    docstring=_get_docstring(child),
                    source_text=_node_source(source_lines, child),
                )
                symbols.append(sym)
                # recurse into class body, tracking class_name
                self._walk(child, source_lines, file_path, symbols, class_name=child.name)

            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = _extract_parameters(child.args)
                sig = _build_signature(child.name, child.args, child.returns)
                kind = SymbolKind.method if class_name else SymbolKind.function
                qname = f"{class_name}.{child.name}" if class_name else child.name

                sym = ExtractedSymbol(
                    name=child.name,
                    kind=kind,
                    file_path=file_path,
                    start_line=child.lineno,
                    end_line=child.end_lineno,  # type: ignore[attr-defined]
                    signature=sig,
                    parameters=params,
                    return_type=_annotation_str(child.returns),
                    docstring=_get_docstring(child),
                    qualified_name=qname,
                    decorators=[ast.unparse(d) for d in child.decorator_list],
                    source_text=_node_source(source_lines, child),
                )
                symbols.append(sym)
                # recurse for nested functions
                self._walk(child, source_lines, file_path, symbols, class_name=class_name)

            elif isinstance(child, ast.Assign) and class_name is None:
                # module-level constants: NAME = value (all caps)
                for target in child.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        symbols.append(ExtractedSymbol(
                            name=target.id,
                            kind=SymbolKind.constant,
                            file_path=file_path,
                            start_line=child.lineno,
                            end_line=child.end_lineno,  # type: ignore[attr-defined]
                            signature=f"{target.id} = {ast.unparse(child.value)}",
                        ))
            else:
                self._walk(child, source_lines, file_path, symbols, class_name=class_name)
