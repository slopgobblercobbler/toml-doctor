"""Unit tests for toml_doctor.sorter."""
from __future__ import annotations

import pytest
from toml_doctor.sorter import TomlSorter, sort


def test_sorter_pyproject_canonical_order():
    content = """[tool.ruff]
line-length = 88

[project]
name = "my-pkg"
version = "0.1.0"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
"""
    sorter = TomlSorter()
    sorted_text, modified, reordered = sorter.sort_text(content, is_pyproject=True)

    assert modified is True
    # [build-system] must come before [project], which must come before [tool.ruff]
    pos_build = sorted_text.index("[build-system]")
    pos_proj = sorted_text.index("[project]")
    pos_tool = sorted_text.index("[tool.ruff]")
    assert pos_build < pos_proj < pos_tool


def test_sorter_sort_keys_inside_project():
    content = """[project]
dependencies = ["requests"]
version = "0.1.0"
name = "my-pkg"
description = "A great package"
"""
    sorter = TomlSorter(sort_keys=True)
    sorted_text, modified, reordered = sorter.sort_text(content, is_pyproject=True)

    assert modified is True
    # Canonical order: name, version, description, dependencies
    pos_name = sorted_text.index("name =")
    pos_ver = sorted_text.index("version =")
    pos_desc = sorted_text.index("description =")
    pos_deps = sorted_text.index("dependencies =")
    assert pos_name < pos_ver < pos_desc < pos_deps


def test_sorter_preserves_comments():
    content = """# Global tool settings
[tool.pytest]
# Minimum pytest version required
minversion = "7.0"

# Main project declaration
[project]
name = "demo"
version = "1.0"
"""
    sorter = TomlSorter()
    sorted_text, modified, reordered = sorter.sort_text(content, is_pyproject=True)
    assert "# Global tool settings" in sorted_text
    assert "# Minimum pytest version required" in sorted_text
    assert "# Main project declaration" in sorted_text


def test_sorter_file_in_place_and_backup(tmp_path):
    f = tmp_path / "pyproject.toml"
    original = """[tool.black]
line-length = 100

[build-system]
requires = ["wheel"]
"""
    f.write_text(original, encoding="utf-8")

    result = sort(f, in_place=True, backup=True)
    assert result.modified is True
    assert result.backup_path is not None

    # Check backup content equals original
    bak_path = tmp_path / "pyproject.toml.bak"
    assert bak_path.exists()
    assert bak_path.read_text(encoding="utf-8") == original

    # Check modified content
    new_content = f.read_text(encoding="utf-8")
    assert new_content.index("[build-system]") < new_content.index("[tool.black]")
