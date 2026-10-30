"""PEP 518 / PEP 621 table sorter and TOML section organizer."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from toml_doctor.models import SortResult, TomlLine, TomlLineType, TomlSection
from toml_doctor.parser import TomlDocument, TomlParser


# Canonical section order for PEP 518 / PEP 621 pyproject.toml
PYPROJECT_TABLE_PRIORITY = {
    "build-system": 10,
    "project": 20,
    "project.optional-dependencies": 30,
    "project.scripts": 40,
    "project.gui-scripts": 50,
    "project.entry-points": 60,
    "project.urls": 70,
}

# Canonical key order inside [project] table
PROJECT_KEY_PRIORITY = {
    "name": 1,
    "version": 2,
    "description": 3,
    "readme": 4,
    "requires-python": 5,
    "license": 6,
    "authors": 7,
    "maintainers": 8,
    "keywords": 9,
    "classifiers": 10,
    "dependencies": 11,
    "dynamic": 12,
}

BUILD_SYSTEM_KEY_PRIORITY = {
    "requires": 1,
    "build-backend": 2,
    "backend-path": 3,
}


def section_sort_key(sec: TomlSection, is_pyproject: bool = True) -> Tuple[int, str]:
    """Calculate sorting rank for a TOML section."""
    if sec.is_root or sec.header is None:
        return 0, ""

    header = sec.header.strip()

    if is_pyproject:
        # Check explicit priority
        if header in PYPROJECT_TABLE_PRIORITY:
            return PYPROJECT_TABLE_PRIORITY[header], header

        # Match project.entry-points.* sub-tables
        if header.startswith("project.entry-points"):
            return 65, header

        # Match [tool.*] tables
        if header.startswith("tool."):
            return 100, header

        # Match other tables
        return 200, header

    # General TOML: root first, then alphabetical
    return 100, header


def key_sort_key(key: str, section_header: Optional[str]) -> Tuple[int, str]:
    """Calculate sorting rank for a key within a section."""
    if section_header == "project" and key in PROJECT_KEY_PRIORITY:
        return PROJECT_KEY_PRIORITY[key], key
    if section_header == "build-system" and key in BUILD_SYSTEM_KEY_PRIORITY:
        return BUILD_SYSTEM_KEY_PRIORITY[key], key
    return 100, key


class TomlSorter:
    """Sorts TOML tables and keys according to PEP standards or alphabetical conventions."""

    def __init__(self, sort_keys: bool = False):
        self.sort_keys = sort_keys

    def sort_text(
        self, text: str, is_pyproject: bool = True
    ) -> Tuple[str, bool, List[str]]:
        """Sort TOML text and return (new_text, modified, reordered_sections)."""
        doc = TomlParser.parse(text)
        if not doc.sections:
            return text, False, []

        orig_sections = [sec.header for sec in doc.sections if sec.header is not None]

        # Partition sections: root section (if any) and table sections
        root_section = doc.sections[0] if doc.sections[0].is_root else None
        other_sections = doc.sections[1:] if root_section else list(doc.sections)

        # Sort non-root sections stably
        sorted_sections = sorted(
            other_sections,
            key=lambda sec: section_sort_key(sec, is_pyproject=is_pyproject),
        )

        final_sections: List[TomlSection] = []
        if root_section and root_section.lines:
            final_sections.append(root_section)
        final_sections.extend(sorted_sections)

        new_sections_order = [sec.header for sec in final_sections if sec.header is not None]
        sections_reordered = [h for h in new_sections_order if h is not None]

        # Format reconstructed sections into lines
        rendered_lines: List[str] = []
        for s_idx, sec in enumerate(final_sections):
            sec_lines = self._render_section(sec, is_pyproject)
            if not sec_lines:
                continue

            # Ensure single blank line separation between sections
            if rendered_lines and rendered_lines[-1] != "":
                rendered_lines.append("")

            # Remove leading blank lines from section
            while sec_lines and sec_lines[0] == "":
                sec_lines.pop(0)

            # Remove trailing blank lines from section
            while sec_lines and sec_lines[-1] == "":
                sec_lines.pop()

            rendered_lines.extend(sec_lines)

        # Ensure single trailing newline
        new_text = "\n".join(rendered_lines)
        if text.endswith("\n"):
            new_text += "\n"

        modified = new_text != text
        return new_text, modified, sections_reordered

    def _render_section(self, sec: TomlSection, is_pyproject: bool) -> List[str]:
        """Render a single section, optionally sorting its keys."""
        if not self.sort_keys:
            return [line.raw for line in sec.lines]

        # Sort keys while preserving table header and comments
        header_lines: List[str] = []
        key_blocks: Dict[str, List[str]] = {}
        ordered_keys: List[str] = []
        trailing_comments: List[str] = []

        current_key: Optional[str] = None
        current_block: List[str] = []

        for line in sec.lines:
            if line.line_type in (TomlLineType.TABLE_HEADER, TomlLineType.ARRAY_TABLE_HEADER):
                header_lines.append(line.raw)
            elif line.line_type == TomlLineType.KEY_VALUE and line.key:
                if current_key is not None:
                    key_blocks[current_key] = current_block
                current_key = line.key
                current_block = [line.raw]
                if current_key not in ordered_keys:
                    ordered_keys.append(current_key)
            elif current_key is not None:
                # Continuation or comment belonging to previous key
                current_block.append(line.raw)
            else:
                if line.line_type == TomlLineType.EMPTY:
                    continue
                header_lines.append(line.raw)

        if current_key is not None:
            key_blocks[current_key] = current_block

        # Sort keys according to priority or alphabetically
        sorted_keys = sorted(
            ordered_keys,
            key=lambda k: key_sort_key(k, sec.header),
        )

        res: List[str] = list(header_lines)
        for k in sorted_keys:
            res.extend(key_blocks.get(k, []))
        res.extend(trailing_comments)
        return res

    def sort_file(
        self,
        file_path: Union[str, Path],
        in_place: bool = False,
        backup: bool = False,
    ) -> SortResult:
        """Sort a TOML file on disk."""
        path = Path(file_path)
        if not path.is_file():
            return SortResult(file_path=str(path), modified=False)

        content = path.read_text(encoding="utf-8")
        is_pyproject = path.name.lower() == "pyproject.toml"

        new_content, modified, sections_reordered = self.sort_text(
            content, is_pyproject=is_pyproject
        )

        diff_str: Optional[str] = None
        backup_path: Optional[str] = None

        if modified:
            diff_lines = list(
                difflib.unified_diff(
                    content.splitlines(),
                    new_content.splitlines(),
                    fromfile=f"{path.name} (original)",
                    tofile=f"{path.name} (sorted)",
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

        return SortResult(
            file_path=str(path),
            modified=modified,
            backup_path=backup_path,
            diff=diff_str,
            sections_reordered=sections_reordered,
        )


def sort(
    target: Union[str, Path],
    sort_keys: bool = False,
    in_place: bool = False,
    backup: bool = False,
) -> SortResult:
    """Convenience function to sort tables and keys in a TOML file."""
    sorter = TomlSorter(sort_keys=sort_keys)
    if isinstance(target, Path):
        return sorter.sort_file(target, in_place=in_place, backup=backup)

    target_str = str(target)
    if "\n" not in target_str and "\r" not in target_str and not target_str.strip().startswith("["):
        try:
            p = Path(target_str)
            if p.is_file() or p.suffix.lower() == ".toml":
                return sorter.sort_file(p, in_place=in_place, backup=backup)
        except OSError:
            pass

    new_text, modified, reordered = sorter.sort_text(target_str)
    diff_lines = list(
        difflib.unified_diff(
            target_str.splitlines(),
            new_text.splitlines(),
            fromfile="<stdin> (original)",
            tofile="<stdin> (sorted)",
            lineterm="",
        )
    )
    diff_str = "\n".join(diff_lines) if modified else None
    return SortResult(
        file_path="<stdin>",
        modified=modified,
        diff=diff_str,
        sections_reordered=reordered,
    )
