"""Unit tests for toml_doctor high-level API functions."""
from __future__ import annotations

import pytest
import toml_doctor
from toml_doctor import fix, parse, sort, validate


def test_api_version():
    assert toml_doctor.__version__ == "0.1.0"


def test_api_parse():
    doc = parse("[table]\nkey = 'val'\n")
    assert len(doc.sections) == 1
    assert doc.sections[0].header == "table"


def test_api_validate():
    res = validate("[table]\nkey = 'val'\n")
    assert res.is_valid is True
    assert len(res.issues) == 0


def test_api_sort():
    raw = "[tool.b]\nx = 1\n\n[tool.a]\ny = 2\n"
    res = sort(raw)
    assert res.modified is True
    assert "[tool.a]" in res.diff


def test_api_fix():
    raw = "[sec]\nfoo='bar'  \n"
    res = fix(raw)
    assert res.modified is True
    assert res.fixed_issues_count >= 2
