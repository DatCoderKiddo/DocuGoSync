"""
Unit tests for the drift detector.
Tests all 12 test cases from the specification.
"""

import pytest
from code_indexer.symbol_types import ExtractedSymbol, Parameter, SymbolKind
from content_extractor.markdown_extractor import ParsedSection, MarkdownExtractor
from drift_detector.detector import (
    DriftDetector,
    check_signature_drift,
    check_parameter_drift,
    check_symbol_removed,
    check_symbol_renamed,
)


def _make_func(name, params=None, sig=None, file="src/main.py", defaults=None):
    parameters = []
    for p_name in (params or []):
        default = (defaults or {}).get(p_name)
        parameters.append(Parameter(
            name=p_name,
            default=default,
            required=default is None,
        ))
    return ExtractedSymbol(
        name=name,
        kind=SymbolKind.function,
        file_path=file,
        start_line=1,
        end_line=10,
        signature=sig or f"{name}({', '.join(p.name for p in parameters)})",
        parameters=parameters,
    )


def _make_section(content, heading="Usage", file="README.md"):
    extractor = MarkdownExtractor()
    md = f"## {heading}\n\n{content}"
    sections = extractor.extract_string(md)
    return next(s for s in sections if s.heading == heading)


# ── TC1: Rename a function referenced in README ───────────────────────────────

def test_tc1_renamed_function():
    """TC1 — Renaming a function referenced in the README."""
    old_sym = _make_func("login", ["username", "password"])
    section = _make_section(
        "Call `login(username, password)` to authenticate.\n\nSee also `login`.",
    )
    findings = check_symbol_renamed(old_sym, "authenticate", section)
    assert len(findings) == 1
    assert findings[0].issue_type == "outdated"
    assert findings[0].severity == "critical"
    assert "login" in findings[0].description


# ── TC2: Adding a new function parameter ──────────────────────────────────────

def test_tc2_new_parameter():
    """TC2 — Adding a new required parameter."""
    old_sym = _make_func("send_email", ["to", "subject", "body"])
    new_sym = _make_func("send_email", ["to", "subject", "body", "from_address"])

    section = _make_section(
        "Use `send_email(to, subject, body)` to send emails.\n\n- `to`: recipient\n- `subject`: email subject",
    )
    findings = check_parameter_drift(old_sym, new_sym, section)
    assert any("from_address" in f.description for f in findings)
    assert any(f.issue_type == "missing" for f in findings)


# ── TC3: Changing a default parameter value ───────────────────────────────────

def test_tc3_changed_default():
    """TC3 — Default value changed from 30 to 60."""
    old_sym = _make_func("connect", ["host", "timeout"], defaults={"timeout": "30"})
    new_sym = _make_func("connect", ["host", "timeout"], defaults={"timeout": "60"})

    section = _make_section(
        "Call `connect(host, timeout=30)` to connect.\n\nThe default timeout is 30 seconds.",
    )
    findings = check_parameter_drift(old_sym, new_sym, section)
    assert len(findings) >= 1
    assert any("timeout" in f.description and "30" in f.description for f in findings)


# ── TC4: Removing a configuration option ──────────────────────────────────────

def test_tc4_removed_config_symbol():
    """TC4 — Removing a function that was documented."""
    removed = _make_func("set_debug_mode", ["enabled"])
    section = _make_section(
        "Call `set_debug_mode(enabled)` to toggle debug logging.\n\nPass `True` or `False`.",
    )
    findings = check_symbol_removed(removed, section)
    assert len(findings) == 1
    assert findings[0].severity == "critical"


# ── TC5: Changing an API endpoint ─────────────────────────────────────────────

def test_tc5_renamed_function_api():
    """TC5 — API function renamed."""
    old = _make_func("get_user", ["user_id"])
    section = _make_section(
        "Use `get_user(user_id)` to fetch a user by ID.\n\nReturns a User object.",
    )
    findings = check_symbol_renamed(old, "fetch_user", section)
    assert any("get_user" in f.description for f in findings)


# ── TC6: Adding a new CLI command (not in docs) ───────────────────────────────

def test_tc6_new_undocumented_function():
    """TC6 — New public function with no documentation."""
    detector = DriftDetector()
    new_sym = _make_func("deploy", ["env", "version"])
    # No doc sections mapped to it
    findings = detector.detect([(None, new_sym)], {})
    assert any("deploy" in f.description for f in findings)
    assert any(f.issue_type == "missing" for f in findings)


# ── TC7: Removing a documented function ──────────────────────────────────────

def test_tc7_remove_documented_function():
    """TC7 — Old CLI command still in docs."""
    old = _make_func("backup", [])
    section = _make_section(
        "Run `backup()` to create a database backup."
    )
    findings = check_symbol_removed(old, section)
    assert len(findings) == 1


# ── TC8: Changed environment variable name ───────────────────────────────────

def test_tc8_env_var_removed():
    """TC8 — Env var removed from code but still in docs."""
    old_ev = ExtractedSymbol(
        name="DB_HOST",
        kind=SymbolKind.env_var,
        file_path="config.py",
        start_line=5,
        end_line=5,
    )
    section = _make_section(
        "Set the `DB_HOST` environment variable to point to your database."
    )
    findings = check_symbol_removed(old_ev, section)
    assert len(findings) == 1
    assert "DB_HOST" in findings[0].description


# ── TC9: Refactor without public API change ───────────────────────────────────

def test_tc9_refactor_no_public_change():
    """TC9 — Refactoring internal implementation; signature unchanged."""
    old = _make_func("process", ["data"], sig="process(data)")
    new = _make_func("process", ["data"], sig="process(data)")
    section = _make_section("Use `process(data)` to transform your data.")
    findings = check_signature_drift(old, new, section)
    assert len(findings) == 0  # no drift


# ── TC10: CSS / unrelated file change ────────────────────────────────────────

def test_tc10_unrelated_file():
    """TC10 — Changing CSS or internal implementation; no code symbols extracted."""
    from code_indexer.python_analyzer import PythonAnalyzer
    analyzer = PythonAnalyzer()
    css_source = ".btn { color: red; }"
    # CSS files won't be parsed; simulate by checking JS analyzer on a CSS-like string
    # In practice, the system skips non-code extensions
    # Here we just verify that a pure CSS string gives no Python symbols
    syms = analyzer.analyze_file("style.py", source=css_source)
    # syntactically invalid Python — should return empty
    assert syms == []


# ── TC11: Code change with no documentation ──────────────────────────────────

def test_tc11_private_function_no_doc():
    """TC11 — Private function changed; no documentation expected."""
    old = _make_func("_internal_helper", ["x"])
    new = _make_func("_internal_helper", ["x", "y"])
    detector = DriftDetector()
    findings = detector.detect([(old, new)], {})
    # Private functions should not trigger missing-doc findings
    assert all("_internal_helper" not in f.description for f in
               [f for f in findings if f.issue_type == "missing"])


# ── TC12: Multiple documentation files ───────────────────────────────────────

def test_tc12_multiple_doc_files():
    """TC12 — Same symbol referenced in both README.md and docs/api.md."""
    old_sym = _make_func("authenticate", ["token"])
    new_sym = _make_func("authenticate", ["token", "scope"])
    sec_readme = _make_section(
        "Use `authenticate(token)` for authentication.",
        heading="Auth",
        file="README.md",
    )
    sec_readme.file_path = "README.md"
    sec_api = _make_section(
        "Call `authenticate(token)` to verify a JWT.",
        heading="Authenticate",
        file="docs/api.md",
    )
    sec_api.file_path = "docs/api.md"

    mapped = {
        "authenticate": [sec_readme, sec_api],
    }
    detector = DriftDetector()
    findings = detector.detect([(old_sym, new_sym)], mapped)
    doc_files = {f.doc_file_path for f in findings}
    assert "README.md" in doc_files
    assert "docs/api.md" in doc_files
