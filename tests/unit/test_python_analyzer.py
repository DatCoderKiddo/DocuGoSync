"""
Unit tests for the Python AST analyzer.
Covers all major symbol extraction scenarios.
"""

import pytest
from code_indexer.python_analyzer import PythonAnalyzer
from code_indexer.symbol_types import SymbolKind


@pytest.fixture
def analyzer():
    return PythonAnalyzer()


def test_simple_function(analyzer):
    source = """
def greet(name: str, greeting: str = "Hello") -> str:
    '''Greet a user.'''
    return f"{greeting}, {name}"
"""
    syms = analyzer.analyze_file("test.py", source=source)
    funcs = [s for s in syms if s.kind == SymbolKind.function]
    assert len(funcs) == 1
    f = funcs[0]
    assert f.name == "greet"
    assert len(f.parameters) == 2
    assert f.parameters[0].name == "name"
    assert f.parameters[0].required is True
    assert f.parameters[1].name == "greeting"
    # ast.unparse may use single or double quotes depending on Python version
    assert f.parameters[1].default in ('"Hello"', "'Hello'")
    assert f.parameters[1].required is False
    assert f.return_type == "str"
    assert "Greet a user" in f.docstring


def test_class_with_methods(analyzer):
    source = """
class AuthManager:
    def login(self, username, password, remember=False):
        pass

    def logout(self, user_id):
        pass
"""
    syms = analyzer.analyze_file("test.py", source=source)
    classes = [s for s in syms if s.kind == SymbolKind.klass]
    methods = [s for s in syms if s.kind == SymbolKind.method]
    assert any(c.name == "AuthManager" for c in classes)
    assert any(m.name == "login" for m in methods)
    assert any(m.name == "logout" for m in methods)


def test_method_excludes_self(analyzer):
    source = """
class Foo:
    def bar(self, x, y=1):
        pass
"""
    syms = analyzer.analyze_file("test.py", source=source)
    method = next(s for s in syms if s.name == "bar")
    param_names = [p.name for p in method.parameters]
    assert "self" not in param_names
    assert "x" in param_names
    assert "y" in param_names


def test_constants_extracted(analyzer):
    source = """
MAX_RETRIES = 5
DEFAULT_TIMEOUT = 30
internal_var = "not a constant"
"""
    syms = analyzer.analyze_file("test.py", source=source)
    consts = [s for s in syms if s.kind == SymbolKind.constant]
    names = {c.name for c in consts}
    assert "MAX_RETRIES" in names
    assert "DEFAULT_TIMEOUT" in names
    assert "internal_var" not in names


def test_env_vars_extracted(analyzer):
    source = """
import os
db_url = os.environ.get("DATABASE_URL", "sqlite:///default.db")
secret = os.environ["SECRET_KEY"]
token = os.getenv("API_TOKEN")
"""
    syms = analyzer.analyze_file("test.py", source=source)
    env_vars = [s for s in syms if s.kind == SymbolKind.env_var]
    names = {s.name for s in env_vars}
    assert "DATABASE_URL" in names
    assert "SECRET_KEY" in names
    assert "API_TOKEN" in names


def test_async_function(analyzer):
    source = """
async def fetch(url: str, timeout: int = 30) -> dict:
    pass
"""
    syms = analyzer.analyze_file("test.py", source=source)
    funcs = [s for s in syms if s.kind == SymbolKind.function]
    assert len(funcs) == 1
    assert funcs[0].name == "fetch"


def test_qualified_name_for_method(analyzer):
    source = """
class Repo:
    def clone(self, url):
        pass
"""
    syms = analyzer.analyze_file("test.py", source=source)
    method = next(s for s in syms if s.name == "clone")
    assert method.qualified_name == "Repo.clone"


def test_no_params(analyzer):
    source = """
def hello():
    pass
"""
    syms = analyzer.analyze_file("test.py", source=source)
    f = next(s for s in syms if s.name == "hello")
    assert f.parameters == []


def test_changed_default_value(analyzer):
    """TC3 — changing a default parameter value."""
    old_source = """
def connect(host, port=5432, timeout=30):
    pass
"""
    new_source = """
def connect(host, port=5432, timeout=60):
    pass
"""
    old_syms = analyzer.analyze_file("db.py", source=old_source)
    new_syms = analyzer.analyze_file("db.py", source=new_source)
    old_fn = old_syms[0]
    new_fn = new_syms[0]
    old_defaults = old_fn.defaults()
    new_defaults = new_fn.defaults()
    assert old_defaults["timeout"] == "30"
    assert new_defaults["timeout"] == "60"
