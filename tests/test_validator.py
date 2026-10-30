"""Unit tests for toml_doctor.validator."""
from __future__ import annotations

import pytest
from toml_doctor.models import Severity
from toml_doctor.validator import TomlValidator, validate


def test_validator_clean_document():
    content = """[package]
name = "my-package"
version = "1.0.0"
description = "A clean TOML file"
"""
    result = validate(content)
    assert result.is_valid is True
    assert not result.has_errors
    assert len(result.issues) == 0


def test_validator_syntax_error():
    content = """[table
name = "unclosed table header
"""
    result = validate(content)
    assert result.is_valid is False
    assert result.has_errors is True
    assert any(i.rule_id == "TOML003" for i in result.issues)


def test_validator_duplicate_key():
    content = """[config]
timeout = 30
debug = true
timeout = 60
"""
    result = validate(content)
    assert result.is_valid is False
    assert result.has_errors is True
    assert "timeout" in result.duplicate_keys
    assert any(i.rule_id == "TOML001" and i.key == "timeout" for i in result.issues)


def test_validator_duplicate_table():
    content = """[database]
host = "localhost"

[server]
port = 8080

[database]
port = 5432
"""
    result = validate(content)
    assert result.is_valid is False
    assert "database" in result.duplicate_tables
    assert any(i.rule_id == "TOML002" and i.key == "database" for i in result.issues)


def test_validator_formatting_warnings():
    content = """[settings]
bad_spacing=123
trailing_space = "test"  
"""
    result = validate(content)
    # Warnings do not cause is_valid = False by default
    assert any(i.rule_id == "TOML005" for i in result.issues)
    assert any(i.rule_id == "TOML006" for i in result.issues)


def test_validator_missing_file(tmp_path):
    non_existent = tmp_path / "does_not_exist.toml"
    result = validate(non_existent)
    assert result.is_valid is False
    assert any(i.rule_id == "IO001" for i in result.issues)
