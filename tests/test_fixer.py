"""Unit tests for toml_doctor.fixer."""
from __future__ import annotations

import pytest
from toml_doctor.fixer import TomlFixer, fix


def test_fixer_spacing_around_equals():
    content = """[config]
host="127.0.0.1"
port= 8080
timeout =30
"""
    fixer = TomlFixer()
    fixed_text, modified, count, descs = fixer.fix_text(content)

    assert modified is True
    assert count >= 3
    assert 'host = "127.0.0.1"' in fixed_text
    assert "port = 8080" in fixed_text
    assert "timeout = 30" in fixed_text


def test_fixer_trailing_whitespace():
    content = "[settings]\nname = 'test'  \nenabled = true\t\n"
    fixer = TomlFixer()
    fixed_text, modified, count, descs = fixer.fix_text(content)

    assert modified is True
    for line in fixed_text.splitlines():
        assert not line.endswith(" ")
        assert not line.endswith("\t")


def test_fixer_deduplicate_keys():
    content = """[server]
port = 8080
host = "0.0.0.0"
port = 9090
"""
    fixer = TomlFixer(deduplicate_keys=True)
    fixed_text, modified, count, descs = fixer.fix_text(content)

    assert modified is True
    assert fixed_text.count("port =") == 1
    assert "port = 9090" in fixed_text
    assert "port = 8080" not in fixed_text


def test_fixer_collapse_blank_lines():
    content = """[sec1]
a = 1


[sec2]
b = 2
"""
    fixer = TomlFixer(collapse_blank_lines=True)
    fixed_text, modified, count, descs = fixer.fix_text(content)
    assert modified is True
    assert "\n\n\n" not in fixed_text


def test_fixer_clean_content_unmodified():
    content = """[clean]
key = "value"
num = 42
"""
    fixer = TomlFixer()
    fixed_text, modified, count, descs = fixer.fix_text(content)
    assert modified is False
    assert count == 0


def test_fixer_file_in_place_and_backup(tmp_path):
    f = tmp_path / "test.toml"
    original = "[test]\nkey= 'value'  \n"
    f.write_text(original, encoding="utf-8")

    result = fix(f, in_place=True, backup=True)
    assert result.modified is True
    assert result.backup_path is not None

    bak = tmp_path / "test.toml.bak"
    assert bak.exists()
    assert bak.read_text(encoding="utf-8") == original

    updated = f.read_text(encoding="utf-8")
    assert "key = 'value'" in updated
    assert not updated.endswith("  \n")
