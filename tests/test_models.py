"""Unit tests for toml_doctor.models."""
from __future__ import annotations

import pytest
from toml_doctor.models import (
    FixResult,
    Issue,
    Severity,
    SortResult,
    TomlLine,
    TomlLineType,
    TomlSection,
    ValidationResult,
)


def test_issue_model_defaults():
    issue = Issue(rule_id="TOML001", message="Duplicate key 'foo'")
    assert issue.rule_id == "TOML001"
    assert issue.message == "Duplicate key 'foo'"
    assert issue.severity == Severity.ERROR
    assert issue.file_path is None
    assert issue.line_number is None

    d = issue.to_dict()
    assert d["rule_id"] == "TOML001"
    assert d["severity"] == "error"
    assert d["message"] == "Duplicate key 'foo'"


def test_issue_model_full():
    issue = Issue(
        rule_id="TOML005",
        message="Missing space",
        severity=Severity.WARNING,
        file_path="pyproject.toml",
        line_number=12,
        column=5,
        key="test_key",
        suggestion="test_key = 'val'",
    )
    d = issue.to_dict()
    assert d["severity"] == "warning"
    assert d["line_number"] == 12
    assert d["column"] == 5
    assert d["key"] == "test_key"
    assert d["suggestion"] == "test_key = 'val'"


def test_severity_enum():
    assert Severity.ERROR == "error"
    assert Severity.WARNING == "warning"
    assert Severity.INFO == "info"


def test_toml_section_properties():
    sec_root = TomlSection(header=None)
    assert sec_root.is_root is True

    sec_table = TomlSection(header="tool.ruff", is_array_table=False)
    assert sec_table.is_root is False
    assert sec_table.header == "tool.ruff"


def test_validation_result_has_errors():
    res = ValidationResult(file_path="test.toml")
    assert not res.has_errors
    assert res.is_valid

    res.issues.append(Issue(rule_id="TOML006", message="Warn", severity=Severity.WARNING))
    assert not res.has_errors

    res.issues.append(Issue(rule_id="TOML001", message="Err", severity=Severity.ERROR))
    assert res.has_errors

    d = res.to_dict()
    assert d["file_path"] == "test.toml"
    assert d["has_errors"] is True
    assert len(d["issues"]) == 2


def test_sort_result_dict():
    res = SortResult(
        file_path="test.toml",
        modified=True,
        backup_path="test.toml.bak",
        diff="--- a\n+++ b",
        sections_reordered=["build-system", "project"],
    )
    d = res.to_dict()
    assert d["modified"] is True
    assert d["backup_path"] == "test.toml.bak"
    assert d["sections_reordered"] == ["build-system", "project"]


def test_fix_result_dict():
    res = FixResult(
        file_path="test.toml",
        modified=True,
        fixed_issues_count=3,
        descriptions=["Fixed spacing", "Removed duplicate"],
    )
    d = res.to_dict()
    assert d["modified"] is True
    assert d["fixed_issues_count"] == 3
    assert len(d["descriptions"]) == 2
