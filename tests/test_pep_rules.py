"""Unit tests for PEP 518 and PEP 621 schema validation."""
from __future__ import annotations

import pytest
from toml_doctor.validator import validate


def test_pep518_missing_requires():
    content = """[build-system]
build-backend = "flit_core.buildapi"
"""
    res = validate(content, check_pep=True)
    assert res.is_valid is False
    assert any(i.rule_id == "PEP518" and "requires" in i.message for i in res.issues)


def test_pep518_valid_build_system():
    content = """[build-system]
requires = ["flit_core >=3.2,<4"]
build-backend = "flit_core.buildapi"
"""
    res = validate(content, check_pep=True)
    assert res.is_valid is True
    assert not any(i.rule_id == "PEP518" for i in res.issues)


def test_pep621_missing_name():
    content = """[project]
version = "0.1.0"
description = "Missing name test"
"""
    res = validate(content, check_pep=True)
    assert res.is_valid is False
    assert any(i.rule_id == "PEP621" and "name" in i.message for i in res.issues)


def test_pep621_missing_version_without_dynamic():
    content = """[project]
name = "my-tool"
description = "Missing version test"
"""
    res = validate(content, check_pep=True)
    assert res.is_valid is False
    assert any(i.rule_id == "PEP621" and "version" in i.message for i in res.issues)


def test_pep621_version_in_dynamic_is_valid():
    content = """[project]
name = "my-tool"
dynamic = ["version"]
description = "Dynamic version is valid"
"""
    res = validate(content, check_pep=True)
    assert res.is_valid is True
    assert not any(i.rule_id == "PEP621" for i in res.issues)


def test_pep621_invalid_package_name():
    content = """[project]
name = "invalid name with spaces"
version = "1.0.0"
"""
    res = validate(content, check_pep=True)
    assert res.is_valid is False
    assert any(i.rule_id == "PEP621" and "naming" in i.message for i in res.issues)


def test_pep621_invalid_dependencies_type():
    content = """[project]
name = "my-tool"
version = "1.0.0"
dependencies = "should-be-a-list"
"""
    res = validate(content, check_pep=True)
    assert res.is_valid is False
    assert any(i.rule_id == "PEP621" and "dependencies" in i.message for i in res.issues)


def test_pep_checks_disabled():
    content = """[project]
name = "invalid name with spaces"
"""
    res = validate(content, check_pep=False)
    assert res.is_valid is True
    assert not any(i.rule_id == "PEP621" for i in res.issues)
