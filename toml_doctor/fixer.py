"""Autofixer for TOML syntax, duplicate keys, equals spacing, and formatting."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from toml_doctor.models import FixResult, TomlLine, TomlLineType, TomlSection
from toml_doctor.parser import TomlDocument, TomlParser, split_key_value


class TomlFixer:
    """Repairs common TOML issues: spacing around '=', trailing whitespace, and duplicate keys."""

    def __init__(
        self,
        fix_spacing: bool = True,
        fix_trailing: bool = True,
        deduplicate_keys: bool = True,
        collapse_blank_lines: bool = True,
    ):
        self.fix_spacing = fix_spacing
        self.fix_trailing = fix_trailing
        self.deduplicate_keys = deduplicate_keys
        self.collapse_blank_lines = collapse_blank_lines

    def fix_text(self, text: str) -> Tuple[str, bool, int, List[str]]:
        """Fix TOML text and return (repaired_text, modified, fixes_count, descriptions)."""
        doc = TomlParser.parse(text)
        fixes_count = 0
        descriptions: List[str] = []

        fixed_lines: List[str] = []
        last_was_blank = False

        for sec in doc.sections:
            # Check duplicate keys in this section
            keys_to_keep_last: Dict[str, int] = {}
            if self.deduplicate_keys:
                for k, line_indices in sec.keys.items():
                    if len(line_indices) > 1:
                        # Keep the last occurrence line number
                        keys_to_keep_last[k] = line_indices[-1]

            for line in sec.lines:
                # 1. Blank line handling
                if line.line_type == TomlLineType.EMPTY:
                    if self.collapse_blank_lines and last_was_blank:
                        fixes_count += 1
                        descriptions.append("Removed consecutive redundant blank line")
                        continue
                    fixed_lines.append("")
                    last_was_blank = True
                    continue

                last_was_blank = False

                # 2. Duplicate key removal (skip earlier occurrences)
                if (
                    self.deduplicate_keys
                    and line.line_type == TomlLineType.KEY_VALUE
                    and line.key in keys_to_keep_last
                ):
                    if line.line_number != keys_to_keep_last[line.key]:
                        fixes_count += 1
                        descriptions.append(
                            f"Removed earlier duplicate key '{line.key}' at line {line.line_number}"
                        )
                        continue

                current_raw = line.raw

                # 3. Strip trailing whitespace
                if self.fix_trailing and (current_raw.endswith(" ") or current_raw.endswith("\t")):
                    current_raw = current_raw.rstrip()
                    fixes_count += 1
                    descriptions.append(
                        f"Stripped trailing whitespace at line {line.line_number}"
                    )

                # 4. Spacing around '=' for key-value pairs
                if self.fix_spacing and line.line_type == TomlLineType.KEY_VALUE:
                    kv = split_key_value(current_raw.strip())
                    if kv is not None:
                        raw_key, val, comment, has_spacing = kv
                        if not has_spacing and line.indent is not None:
                            # Reformat with standard single space around '='
                            cmt_part = f" {comment}" if comment else ""
                            reformatted = f"{line.indent}{raw_key} = {val}{cmt_part}"
                            if reformatted != current_raw:
                                current_raw = reformatted
                                fixes_count += 1
                                descriptions.append(
                                    f"Normalized '=' spacing for '{raw_key}' at line {line.line_number}"
                                )

                fixed_lines.append(current_raw)

        new_text = "\n".join(fixed_lines)
        if text.endswith("\n"):
            new_text += "\n"

        modified = new_text != text
        return new_text, modified, fixes_count, descriptions

    def fix_file(
        self,
        file_path: Union[str, Path],
        in_place: bool = False,
        backup: bool = False,
    ) -> FixResult:
        """Autofix a TOML file on disk."""
        path = Path(file_path)
        if not path.is_file():
            return FixResult(file_path=str(path), modified=False)

        content = path.read_text(encoding="utf-8")
        new_content, modified, fixes_count, descriptions = self.fix_text(content)

        diff_str: Optional[str] = None
        backup_path: Optional[str] = None

        if modified:
            diff_lines = list(
                difflib.unified_diff(
                    content.splitlines(),
                    new_content.splitlines(),
                    fromfile=f"{path.name} (original)",
                    tofile=f"{path.name} (fixed)",
                    lineterm="",
                )
            )
            diff_str = "\n".join(diff_lines)

            if in_place:
                if backup:
                    bak = path.with_suffix(path.suffix + ".bak")
                    bak.write_text(content, encoding="utf-8")
                    backup_path = str(bak)
                path.write_text(new_content, encoding="utf-8")

        return FixResult(
            file_path=str(path),
            modified=modified,
            backup_path=backup_path,
            diff=diff_str,
            fixed_issues_count=fixes_count,
            descriptions=descriptions,
        )


def fix(
    target: Union[str, Path],
    in_place: bool = False,
    backup: bool = False,
    fix_spacing: bool = True,
    fix_trailing: bool = True,
    deduplicate_keys: bool = True,
) -> FixResult:
    """Convenience function to automatically fix TOML issues."""
    fixer = TomlFixer(
        fix_spacing=fix_spacing,
        fix_trailing=fix_trailing,
        deduplicate_keys=deduplicate_keys,
    )
    if isinstance(target, Path):
        return fixer.fix_file(target, in_place=in_place, backup=backup)

    target_str = str(target)
    if "\n" not in target_str and "\r" not in target_str and not target_str.strip().startswith("["):
        try:
            p = Path(target_str)
            if p.is_file() or p.suffix.lower() == ".toml":
                return fixer.fix_file(p, in_place=in_place, backup=backup)
        except OSError:
            pass

    new_text, modified, count, descs = fixer.fix_text(target_str)
    diff_lines = list(
        difflib.unified_diff(
            target_str.splitlines(),
            new_text.splitlines(),
            fromfile="<stdin> (original)",
            tofile="<stdin> (fixed)",
            lineterm="",
        )
    )
    diff_str = "\n".join(diff_lines) if modified else None
    return FixResult(
        file_path="<stdin>",
        modified=modified,
        diff=diff_str,
        fixed_issues_count=count,
        descriptions=descs,
    )
