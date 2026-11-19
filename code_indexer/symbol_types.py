"""
Data classes representing extracted code symbols.
These are language-agnostic; each language analyzer produces these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SymbolKind(str, Enum):
    function = "function"
    klass = "class"
    method = "method"
    constant = "constant"
    route = "route"
    cli_arg = "cli_arg"
    env_var = "env_var"
    module = "module"


@dataclass
class Parameter:
    name: str
    annotation: Optional[str] = None
    default: Optional[str] = None      # string representation of the default
    required: bool = True


@dataclass
class ExtractedSymbol:
    name: str
    kind: SymbolKind
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    parameters: list[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    qualified_name: Optional[str] = None   # Class.method format
    decorators: list[str] = field(default_factory=list)
    source_text: Optional[str] = None      # raw function/class body

    def param_names(self) -> list[str]:
        return [p.name for p in self.parameters]

    def required_params(self) -> list[str]:
        return [p.name for p in self.parameters if p.required]

    def defaults(self) -> dict[str, str]:
        return {p.name: p.default for p in self.parameters if p.default is not None}
