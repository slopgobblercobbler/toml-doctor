"""TOML line-by-line and section parser preserving formatting and comments."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from toml_doctor.models import TomlLine, TomlLineType, TomlSection


# Regex for standard TOML table header: [table.sub_table] or [[array_table]]
RE_TABLE_HEADER = re.compile(r"^\s*\[(?P<header>[^\[\].]+(?:\.[^\[\].]+|\.\"[^\"]+\"|\.'[^']+')*)\]\s*(?:#.*)?$")
RE_ARRAY_HEADER = re.compile(r"^\s*\[\[(?P<header>[^\[\].]+(?:\.[^\[\].]+|\.\"[^\"]+\"|\.'[^']+')*)\]\]\s*(?:#.*)?$")

# Regex to check bare keys: ASCII letters, digits, underscores, dashes
RE_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def split_key_value(line_text: str) -> Optional[Tuple[str, str, Optional[str], bool]]:
    """
    Split a TOML key-value line into (key_part, val_part, inline_comment, has_standard_spacing).
    Handles quoted keys and quoted strings containing '#' or '='.
    """
    in_single_quote = False
    in_double_quote = False
    escape = False
    equals_idx = -1

    # Scan for '=' outside of quotes
    for i, ch in enumerate(line_text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_double_quote:
            escape = True
            continue
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue
        if ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue
        if ch == "=" and not in_single_quote and not in_double_quote:
            equals_idx = i
            break

    if equals_idx == -1:
        return None

    raw_before_eq = line_text[:equals_idx]
    raw_after_eq = line_text[equals_idx + 1:]

    # Check spacing around '=': must have space before and after
    # e.g. "key = val" -> True; "key=val" -> False; "key =val" -> False
    has_space_before = raw_before_eq.endswith(" ")
    has_space_after = raw_after_eq.startswith(" ")
    has_standard_spacing = has_space_before and has_space_after

    key_part = raw_before_eq.strip()
    if not key_part:
        return None

    # Now parse after_eq to separate value and optional comment
    val_in_single = False
    val_in_double = False
    val_escape = False
    comment_idx = -1

    for j, c in enumerate(raw_after_eq):
        if val_escape:
            val_escape = False
            continue
        if c == "\\" and val_in_double:
            val_escape = True
            continue
        if c == "'" and not val_in_double:
            val_in_single = not val_in_single
            continue
        if c == '"' and not val_in_single:
            val_in_double = not val_in_double
            continue
        if c == "#" and not val_in_single and not val_in_double:
            comment_idx = j
            break

    if comment_idx != -1:
        val_part = raw_after_eq[:comment_idx].strip()
        comment = raw_after_eq[comment_idx:].strip()
    else:
        val_part = raw_after_eq.strip()
        comment = None

    return key_part, val_part, comment, has_standard_spacing


def unquote_key(key_str: str) -> str:
    """Unquote bare or quoted keys, normalizing dotted keys."""
    key_str = key_str.strip()
    if (key_str.startswith('"') and key_str.endswith('"')) or (key_str.startswith("'") and key_str.endswith("'")):
        return key_str[1:-1]
    return key_str


@dataclass
class TomlDocument:
    """High-level representation of parsed TOML document structure."""
    sections: List[TomlSection] = field(default_factory=list)
    lines: List[TomlLine] = field(default_factory=list)
    raw_text: str = ""

    def get_section(self, header: Optional[str]) -> Optional[TomlSection]:
        """Find the first section matching the given header."""
        for sec in self.sections:
            if sec.header == header:
                return sec
        return None

    def get_all_sections(self, header: Optional[str]) -> List[TomlSection]:
        """Find all sections matching the given header (useful for array tables)."""
        return [sec for sec in self.sections if sec.header == header]

    def to_toml(self) -> str:
        """Render all lines back to TOML string."""
        return "\n".join(line.raw for line in self.lines)


class TomlParser:
    """Parses TOML source code into TomlDocument and TomlLine structures."""

    @classmethod
    def parse(cls, content: str) -> TomlDocument:
        """Parse TOML string into structured TomlDocument."""
        raw_lines = content.splitlines()
        parsed_lines: List[TomlLine] = []

        # Current section being populated
        root_section = TomlSection(header=None, is_array_table=False, header_line=None)
        current_section = root_section
        sections: List[TomlSection] = [root_section]

        in_multiline_str: Optional[str] = None  # '"""' or "'''"
        bracket_depth = 0
        brace_depth = 0

        pending_lead_comments: List[str] = []

        for idx, line in enumerate(raw_lines, start=1):
            stripped = line.strip()
            trailing_ws = len(line) > len(line.rstrip())
            indent = line[: len(line) - len(line.lstrip())]

            # 1. Check if inside multiline string
            if in_multiline_str:
                parsed_line = TomlLine(
                    raw=line,
                    line_number=idx,
                    line_type=TomlLineType.MULTILINE,
                    indent=indent,
                    has_trailing_whitespace=trailing_ws,
                )
                current_section.lines.append(parsed_line)
                parsed_lines.append(parsed_line)
                if in_multiline_str in line:
                    # Closing multiline string found
                    in_multiline_str = None
                continue

            # 2. Check if inside multiline array or inline table
            if bracket_depth > 0 or brace_depth > 0:
                # Count brackets/braces outside comments and strings
                bracket_depth, brace_depth, in_multiline_str = cls._update_nesting(
                    line, bracket_depth, brace_depth
                )
                parsed_line = TomlLine(
                    raw=line,
                    line_number=idx,
                    line_type=TomlLineType.MULTILINE,
                    indent=indent,
                    has_trailing_whitespace=trailing_ws,
                )
                current_section.lines.append(parsed_line)
                parsed_lines.append(parsed_line)
                continue

            # 3. Empty line
            if not stripped:
                parsed_line = TomlLine(
                    raw=line,
                    line_number=idx,
                    line_type=TomlLineType.EMPTY,
                    has_trailing_whitespace=trailing_ws,
                )
                current_section.lines.append(parsed_line)
                parsed_lines.append(parsed_line)
                continue

            # 4. Full comment line
            if stripped.startswith("#"):
                parsed_line = TomlLine(
                    raw=line,
                    line_number=idx,
                    line_type=TomlLineType.COMMENT,
                    indent=indent,
                    comment=stripped,
                    has_trailing_whitespace=trailing_ws,
                )
                current_section.lines.append(parsed_line)
                parsed_lines.append(parsed_line)
                pending_lead_comments.append(line)
                continue

            # 5. Table Header [[array_table]]
            array_match = RE_ARRAY_HEADER.match(stripped)
            if array_match:
                header_name = array_match.group("header").strip()
                current_section = TomlSection(
                    header=header_name,
                    is_array_table=True,
                    header_line=idx,
                    lead_comments=pending_lead_comments.copy(),
                )
                pending_lead_comments.clear()
                sections.append(current_section)

                parsed_line = TomlLine(
                    raw=line,
                    line_number=idx,
                    line_type=TomlLineType.ARRAY_TABLE_HEADER,
                    indent=indent,
                    key=header_name,
                    has_trailing_whitespace=trailing_ws,
                )
                current_section.lines.append(parsed_line)
                parsed_lines.append(parsed_line)
                continue

            # 6. Standard Table Header [table]
            table_match = RE_TABLE_HEADER.match(stripped)
            if table_match:
                header_name = table_match.group("header").strip()
                current_section = TomlSection(
                    header=header_name,
                    is_array_table=False,
                    header_line=idx,
                    lead_comments=pending_lead_comments.copy(),
                )
                pending_lead_comments.clear()
                sections.append(current_section)

                parsed_line = TomlLine(
                    raw=line,
                    line_number=idx,
                    line_type=TomlLineType.TABLE_HEADER,
                    indent=indent,
                    key=header_name,
                    has_trailing_whitespace=trailing_ws,
                )
                current_section.lines.append(parsed_line)
                parsed_lines.append(parsed_line)
                continue

            # 7. Key = Value line
            kv = split_key_value(stripped)
            if kv is not None:
                raw_key, val, comment, has_spacing = kv
                normalized_key = unquote_key(raw_key)

                # Record key occurrence in current section
                if normalized_key not in current_section.keys:
                    current_section.keys[normalized_key] = []
                current_section.keys[normalized_key].append(idx)

                parsed_line = TomlLine(
                    raw=line,
                    line_number=idx,
                    line_type=TomlLineType.KEY_VALUE,
                    indent=indent,
                    key=normalized_key,
                    raw_key=raw_key,
                    value=val,
                    comment=comment,
                    has_whitespace_around_equals=has_spacing,
                    has_trailing_whitespace=trailing_ws,
                )
                current_section.lines.append(parsed_line)
                parsed_lines.append(parsed_line)
                pending_lead_comments.clear()

                # Check if this line opened a multiline construct
                bracket_depth, brace_depth, in_multiline_str = cls._update_nesting(
                    val, bracket_depth, brace_depth
                )
                continue

            # 8. Unrecognized / Invalid line
            parsed_line = TomlLine(
                raw=line,
                line_number=idx,
                line_type=TomlLineType.INVALID,
                indent=indent,
                has_trailing_whitespace=trailing_ws,
            )
            current_section.lines.append(parsed_line)
            parsed_lines.append(parsed_line)
            pending_lead_comments.clear()

        # Clean empty root section if it has no lines
        if not root_section.lines and len(sections) > 1:
            sections.pop(0)

        return TomlDocument(sections=sections, lines=parsed_lines, raw_text=content)

    @staticmethod
    def _update_nesting(
        line_text: str, current_bracket: int, current_brace: int
    ) -> Tuple[int, int, Optional[str]]:
        """Track brackets, braces and multiline string tokens across text."""
        in_s = False
        in_d = False
        escape = False
        i = 0
        n = len(line_text)

        while i < n:
            # Check triple quotes
            if not in_s and line_text[i : i + 3] == '"""':
                return current_bracket, current_brace, '"""'
            if not in_d and line_text[i : i + 3] == "'''":
                return current_bracket, current_brace, "'''"

            ch = line_text[i]
            if escape:
                escape = False
                i += 1
                continue
            if ch == "\\" and in_d:
                escape = True
                i += 1
                continue
            if ch == "'" and not in_d:
                in_s = not in_s
                i += 1
                continue
            if ch == '"' and not in_s:
                in_d = not in_d
                i += 1
                continue
            if ch == "#" and not in_s and not in_d:
                # Rest of line is comment
                break

            if not in_s and not in_d:
                if ch == "[":
                    current_bracket += 1
                elif ch == "]":
                    current_bracket = max(0, current_bracket - 1)
                elif ch == "{":
                    current_brace += 1
                elif ch == "}":
                    current_brace = max(0, current_brace - 1)

            i += 1

        return current_bracket, current_brace, None
