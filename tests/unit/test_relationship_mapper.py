"""
Unit tests for the relationship mapper.
"""

import pytest
from code_indexer.symbol_types import ExtractedSymbol, Parameter, SymbolKind
from content_extractor.markdown_extractor import MarkdownExtractor
from relationship_engine.mapper import RelationshipMapper


@pytest.fixture
def mapper():
    return RelationshipMapper()


@pytest.fixture
def extractor():
    return MarkdownExtractor()


def _func(name, file="src/main.py", params=None):
    return ExtractedSymbol(
        name=name,
        kind=SymbolKind.function,
        file_path=file,
        start_line=1,
        end_line=5,
        qualified_name=name,
        parameters=[Parameter(name=p, required=True) for p in (params or [])],
    )


def _sections(content, file="README.md"):
    extractor = MarkdownExtractor()
    secs = extractor.extract_string(content, virtual_path=file)
    return secs


def test_backtick_function_match(mapper):
    syms = [_func("login", params=["username", "password"])]
    secs = _sections("## Auth\n\nUse `login(username, password)` to log in.")
    evidences = mapper.build_mappings(syms, secs)
    assert len(evidences) >= 1
    assert evidences[0].evidence_type in ("exact_name", "signature_ref")
    assert evidences[0].confidence >= 0.8


def test_plain_name_match(mapper):
    syms = [_func("register")]
    secs = _sections("## Registration\n\nCall register to create an account.")
    evidences = mapper.build_mappings(syms, secs)
    assert len(evidences) >= 1


def test_heading_match(mapper):
    syms = [_func("authenticate")]
    secs = _sections("## Authenticate\n\nSend your credentials here.")
    evidences = mapper.build_mappings(syms, secs)
    assert len(evidences) >= 1
    # Heading match should fire
    assert any(e.evidence_type == "keyword" for e in evidences)


def test_no_match_unrelated(mapper):
    syms = [_func("completely_unrelated_xyz")]
    secs = _sections("## Installation\n\nRun pip install to install.")
    evidences = mapper.build_mappings(syms, secs, min_confidence=0.5)
    assert len(evidences) == 0


def test_env_var_match(mapper):
    from code_indexer.symbol_types import SymbolKind
    env_sym = ExtractedSymbol(
        name="DATABASE_URL",
        kind=SymbolKind.env_var,
        file_path="config.py",
        start_line=1,
        end_line=1,
    )
    secs = _sections("## Configuration\n\nSet DATABASE_URL to your connection string.")
    evidences = mapper.build_mappings([env_sym], secs)
    assert len(evidences) >= 1
    assert evidences[0].confidence >= 0.8
