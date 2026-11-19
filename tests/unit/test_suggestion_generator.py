"""
Unit tests for the suggestion generator (deterministic path).
"""

import pytest
from code_indexer.symbol_types import ExtractedSymbol, Parameter, SymbolKind
from content_extractor.markdown_extractor import MarkdownExtractor
from drift_detector.detector import DriftFinding
from suggestion_engine.generator import SuggestionGenerator


@pytest.fixture
def generator():
    return SuggestionGenerator(ai_client=None)


def _finding(description, evidence_code="", evidence_doc="", doc_file="README.md"):
    return DriftFinding(
        issue_type="outdated",
        severity="high",
        description=description,
        evidence_code=evidence_code,
        evidence_doc=evidence_doc,
        doc_file_path=doc_file,
        doc_start_line=5,
        doc_end_line=10,
        code_file_path="src/main.py",
        symbol_name="login",
        confidence=0.9,
    )


def _func(name, params, sig=None):
    parameters = [Parameter(name=p, required=True) for p in params]
    return ExtractedSymbol(
        name=name,
        kind=SymbolKind.function,
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        signature=sig or f"{name}({', '.join(params)})",
        parameters=parameters,
    )


def test_signature_replacement(generator):
    extractor = MarkdownExtractor()
    section = extractor.extract_string(
        "## Auth\n\nUse `login(username, password)` to log in."
    )[-1]

    new_sym = _func("login", ["username", "password", "remember"],
                    sig="login(username, password, remember=False)")
    finding = _finding(
        "login signature changed",
        evidence_code="login(username, password, remember=False)",
        evidence_doc="`login(username, password)`",
    )

    result = generator.generate(finding, new_sym, section)
    assert result.method == "deterministic"
    assert "login(username, password, remember=False)" in result.replacement_text


def test_default_value_replacement(generator):
    extractor = MarkdownExtractor()
    section = extractor.extract_string(
        "## Connect\n\nUse `connect(host, timeout=30)`. Default timeout is 30 seconds."
    )[-1]

    new_sym = _func("connect", ["host", "timeout"], sig="connect(host, timeout=60)")
    # Manually set param defaults
    new_sym.parameters[1] = Parameter(name="timeout", default="60", required=False)

    finding = DriftFinding(
        issue_type="outdated",
        severity="high",
        description="Default value of `timeout` changed from `30` to `60` in `connect`, "
                    "but documentation still states `30`.",
        evidence_code="connect(host, timeout=60)",
        evidence_doc="default timeout is 30",
        doc_file_path="README.md",
        doc_start_line=5,
        doc_end_line=10,
        code_file_path="src/main.py",
        symbol_name="connect",
        confidence=0.88,
    )

    result = generator.generate(finding, new_sym, section)
    # The generator should update either via signature replacement or direct value replacement
    assert result.method == "deterministic"
    assert "60" in result.replacement_text or "connect(host, timeout=60)" in result.replacement_text


def test_uncertain_fallback(generator):
    finding = _finding(
        "Some obscure change",
        evidence_code="something()",
        evidence_doc="old thing",
    )
    extractor = MarkdownExtractor()
    section = extractor.extract_string("## Misc\n\nSome content.")[-1]
    result = generator.generate(finding, None, section)
    assert result.method == "uncertain"
    assert result.confidence < 0.4
