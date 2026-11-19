"""
Unit tests for the Markdown extractor.
"""

import pytest
from content_extractor.markdown_extractor import MarkdownExtractor


@pytest.fixture
def extractor():
    return MarkdownExtractor()


SAMPLE_README = """# My Library

A simple library for doing things.

## Installation

```bash
pip install mylib
```

## Authentication

Use the `login(username, password)` function to authenticate.

Parameters:
- `username` - the user's email
- `password` - the user's password
- `remember` - set to True to persist session (default: False)

## API Reference

### GET /users

Returns a list of users.
"""


def test_sections_extracted(extractor):
    sections = extractor.extract_string(SAMPLE_README)
    headings = [s.heading for s in sections]
    assert "My Library" in headings
    assert "Installation" in headings
    assert "Authentication" in headings
    assert "API Reference" in headings


def test_function_refs_extracted(extractor):
    sections = extractor.extract_string(SAMPLE_README)
    auth_sec = next(s for s in sections if s.heading == "Authentication")
    func_names = [name for name, _ in auth_sec.referenced_functions]
    assert "login" in func_names


def test_symbol_refs_extracted(extractor):
    sections = extractor.extract_string(SAMPLE_README)
    auth_sec = next(s for s in sections if s.heading == "Authentication")
    assert "username" in auth_sec.referenced_symbols
    assert "password" in auth_sec.referenced_symbols


def test_line_numbers_correct(extractor):
    sections = extractor.extract_string(SAMPLE_README)
    # Installation section starts after "My Library" heading
    install = next(s for s in sections if s.heading == "Installation")
    assert install.start_line > 0


def test_section_type_classification(extractor):
    sections = extractor.extract_string(SAMPLE_README)
    install = next(s for s in sections if s.heading == "Installation")
    assert install.section_type == "guide"
    api = next(s for s in sections if s.heading == "API Reference")
    assert api.section_type == "api_doc"


def test_no_headings(extractor):
    content = "Just some plain text with no headings at all."
    sections = extractor.extract_string(content)
    assert len(sections) == 1
    assert sections[0].heading is None


def test_env_vars_in_section(extractor):
    content = """## Configuration

Set `DATABASE_URL` and `SECRET_KEY` environment variables.
"""
    sections = extractor.extract_string(content)
    config = sections[-1]
    assert "DATABASE_URL" in config.env_vars
    assert "SECRET_KEY" in config.env_vars
