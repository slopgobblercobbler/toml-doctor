"""Unit tests for toml_doctor.formatter."""
from __future__ import annotations

import json
import pytest
from toml_doctor.formatter import (
    Color,
    colorize,
    format_diff,
    format_fix_result,
    format_sort_result,
    format_validation_result,
)
from toml_doctor.models import FixResult, Issue, Severity, SortResult, ValidationResult


def test_colorize_forced():
    res = colorize("Hello", Color.RED, force=True)
    assert Color.RED in res
    assert "Hello" in res


def test_format_validation_result_formats():
    res = ValidationResult(file_path="test.toml", is_valid=True)
    res.issues.append(
        Issue(
            rule_id="TOML005",
            message="Spacing issue",
            severity=Severity.WARNING,
            line_number=10,
            column=4,
            suggestion="key = value",
        )
    )

    pretty = format_validation_result(res, output_format="pretty", color=False)
    assert "WARN" in pretty
    assert "Line 10:4" in pretty
    assert "(TOML005)" in pretty

    simple = format_validation_result(res, output_format="simple", color=False)
    assert "test.toml:10:4 [WARNING] (TOML005) Spacing issue" in simple

    json_str = format_validation_result(res, output_format="json")
    data = json.loads(json_str)
    assert data["file_path"] == "test.toml"
    assert len(data["issues"]) == 1


def test_format_diff():
    diff_text = "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n"
    formatted = format_diff(diff_text, color=False)
    assert formatted == diff_text


def test_format_sort_result_formats():
    res = SortResult(
        file_path="pyproject.toml",
        modified=True,
        backup_path="pyproject.toml.bak",
        diff="--- a\n+++ b\n",
        sections_reordered=["build-system", "project"],
    )
    pretty = format_sort_result(res, output_format="pretty", color=False)
    assert "[SORTED]" in pretty
    assert "Sections ordered: build-system, project" in pretty

    simple = format_sort_result(res, output_format="simple", color=False)
    assert "pyproject.toml: REORDERED" in simple

    json_str = format_sort_result(res, output_format="json")
    data = json.loads(json_str)
    assert data["modified"] is True


def test_format_fix_result_formats():
    res = FixResult(
        file_path="pyproject.toml",
        modified=True,
        fixed_issues_count=2,
        descriptions=["Fixed spacing", "Removed trailing space"],
    )
    pretty = format_fix_result(res, output_format="pretty", color=False)
    assert "[FIXED]" in pretty
    assert "Total fixes applied: 2" in pretty

    simple = format_fix_result(res, output_format="simple", color=False)
    assert "pyproject.toml: FIXED (2 fixes)" in simple

    json_str = format_fix_result(res, output_format="json")
    data = json.loads(json_str)
    assert data["fixed_issues_count"] == 2
