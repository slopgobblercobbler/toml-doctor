"""Unit tests for toml_doctor.parser."""
from __future__ import annotations

import pytest
from toml_doctor.models import TomlLineType
from toml_doctor.parser import TomlParser, split_key_value, unquote_key


def test_split_key_value_standard():
    res = split_key_value("name = 'toml-doctor'")
    assert res is not None
    k, v, c, spacing = res
    assert k == "name"
    assert v == "'toml-doctor'"
    assert c is None
    assert spacing is True


def test_split_key_value_no_spacing():
    res = split_key_value("version='0.1.0'")
    assert res is not None
    k, v, c, spacing = res
    assert k == "version"
    assert v == "'0.1.0'"
    assert spacing is False


def test_split_key_value_with_comment():
    res = split_key_value("timeout = 30 # in seconds")
    assert res is not None
    k, v, c, spacing = res
    assert k == "timeout"
    assert v == "30"
    assert c == "# in seconds"
    assert spacing is True


def test_split_key_value_comment_inside_string():
    res = split_key_value('msg = "hello # not a comment"')
    assert res is not None
    k, v, c, spacing = res
    assert k == "msg"
    assert v == '"hello # not a comment"'
    assert c is None


def test_unquote_key():
    assert unquote_key("bare_key") == "bare_key"
    assert unquote_key('"quoted.key"') == "quoted.key"
    assert unquote_key("'single.quoted'") == "single.quoted"


def test_parser_sections_and_lines():
    content = """# Lead comment
title = "TOML Doctor"

[project]
name = "toml-doctor"
version = "0.1.0"

[tool.pytest]
minversion = "7.0"

[[authors]]
name = "Tester"
"""
    doc = TomlParser.parse(content)
    assert len(doc.sections) == 4

    # Root section
    root = doc.sections[0]
    assert root.is_root
    assert "title" in root.keys

    # [project]
    proj = doc.get_section("project")
    assert proj is not None
    assert "name" in proj.keys
    assert "version" in proj.keys
    assert proj.is_array_table is False

    # [[authors]]
    authors = doc.get_all_sections("authors")
    assert len(authors) == 1
    assert authors[0].is_array_table is True
    assert "name" in authors[0].keys


def test_parser_multiline_string():
    content = '''description = """
A multiline
description here.
"""
version = "1.0"
'''
    doc = TomlParser.parse(content)
    assert doc.lines[0].line_type == TomlLineType.KEY_VALUE
    assert doc.lines[1].line_type == TomlLineType.MULTILINE
    assert doc.lines[2].line_type == TomlLineType.MULTILINE
    assert doc.lines[3].line_type == TomlLineType.MULTILINE
    assert doc.lines[4].line_type == TomlLineType.KEY_VALUE


def test_parser_multiline_array():
    content = """dependencies = [
    "tomli>=1.1.0",
    "requests",
]
"""
    doc = TomlParser.parse(content)
    assert doc.lines[0].line_type == TomlLineType.KEY_VALUE
    assert doc.lines[1].line_type == TomlLineType.MULTILINE
    assert doc.lines[2].line_type == TomlLineType.MULTILINE


def test_parser_duplicate_keys_tracked():
    content = """[server]
port = 8080
host = "127.0.0.1"
port = 9090
"""
    doc = TomlParser.parse(content)
    sec = doc.get_section("server")
    assert sec is not None
    assert len(sec.keys["port"]) == 2
    assert sec.keys["port"] == [2, 4]
