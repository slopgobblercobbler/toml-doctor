"""Formatting and terminal color utilities for toml-doctor."""
from __future__ import annotations

import difflib
import json
import os
import sys
from typing import List, Optional

from toml_doctor.models import FixResult, Issue, Severity, SortResult, ValidationResult


class Color:
    """ANSI color codes."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    @classmethod
    def enabled(cls) -> bool:
        """Check if terminal supports colors and NO_COLOR is not set."""
        if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
            return False
        return sys.stdout.isatty()


def colorize(text: str, color_code: str, force: bool = False) -> str:
    """Colorize text if enabled or forced."""
    if not force and not Color.enabled():
        return text
    return f"{color_code}{text}{Color.RESET}"


def format_validation_result(
    result: ValidationResult,
    output_format: str = "pretty",
    color: bool = True,
) -> str:
    """Format validation result for console display."""
    if output_format == "json":
        return json.dumps(result.to_dict(), indent=2)

    lines: List[str] = []
    use_color = color and Color.enabled()

    if output_format == "simple":
        if result.is_valid and not result.issues:
            lines.append(f"{result.file_path}: OK")
        else:
            for issue in result.issues:
                loc = f"{issue.line_number or 0}:{issue.column or 0}"
                sev = issue.severity.value.upper()
                lines.append(f"{result.file_path}:{loc} [{sev}] ({issue.rule_id}) {issue.message}")
        return "\n".join(lines)

    # Pretty format
    status_sym = "✔" if result.is_valid and not result.issues else ("✖" if result.has_errors else "⚠")
    status_text = "PASS" if result.is_valid and not result.issues else ("FAIL" if result.has_errors else "WARN")

    header_color = Color.GREEN if result.is_valid and not result.issues else (Color.RED if result.has_errors else Color.YELLOW)
    badge = colorize(f"[{status_sym} {status_text}]", header_color, force=use_color)
    lines.append(f"{badge} {colorize(result.file_path, Color.BOLD, force=use_color)}")

    if not result.issues:
        lines.append(colorize("  All TOML 1.0 and schema checks passed cleanly.", Color.GREEN, force=use_color))
        return "\n".join(lines)

    for issue in result.issues:
        if issue.severity == Severity.ERROR:
            sev_badge = colorize("ERROR", Color.RED, force=use_color)
        elif issue.severity == Severity.WARNING:
            sev_badge = colorize("WARN ", Color.YELLOW, force=use_color)
        else:
            sev_badge = colorize("INFO ", Color.CYAN, force=use_color)

        loc_str = ""
        if issue.line_number is not None:
            loc_str = f"Line {issue.line_number}"
            if issue.column is not None:
                loc_str += f":{issue.column}"
            loc_str = colorize(f"[{loc_str}]", Color.DIM, force=use_color) + " "

        rule_str = colorize(f"({issue.rule_id})", Color.CYAN, force=use_color)
        lines.append(f"  {sev_badge} {loc_str}{rule_str} {issue.message}")
        if issue.suggestion:
            lines.append(f"         {colorize('Suggestion:', Color.DIM, force=use_color)} {issue.suggestion}")

    return "\n".join(lines)


def format_diff(diff_text: str, color: bool = True) -> str:
    """Format unified diff text with optional syntax coloring."""
    if not color or not Color.enabled():
        return diff_text

    formatted_lines: List[str] = []
    for line in diff_text.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            formatted_lines.append(colorize(line, Color.BOLD))
        elif line.startswith("@@"):
            formatted_lines.append(colorize(line, Color.CYAN))
        elif line.startswith("+"):
            formatted_lines.append(colorize(line, Color.GREEN))
        elif line.startswith("-"):
            formatted_lines.append(colorize(line, Color.RED))
        else:
            formatted_lines.append(line)
    return "\n".join(formatted_lines)


def format_sort_result(
    result: SortResult,
    output_format: str = "pretty",
    color: bool = True,
) -> str:
    """Format table/key sort result for console display."""
    if output_format == "json":
        return json.dumps(result.to_dict(), indent=2)

    use_color = color and Color.enabled()
    lines: List[str] = []

    if output_format == "simple":
        status = "REORDERED" if result.modified else "UNCHANGED"
        lines.append(f"{result.file_path}: {status}")
        return "\n".join(lines)

    if result.modified:
        badge = colorize("[SORTED]", Color.GREEN, force=use_color)
        lines.append(f"{badge} {colorize(result.file_path, Color.BOLD, force=use_color)}")
        if result.sections_reordered:
            reordered = ", ".join(result.sections_reordered[:6])
            if len(result.sections_reordered) > 6:
                reordered += f" ... (+{len(result.sections_reordered) - 6} more)"
            lines.append(f"  Sections ordered: {colorize(reordered, Color.CYAN, force=use_color)}")
        if result.backup_path:
            lines.append(f"  Backup created: {result.backup_path}")
        if result.diff:
            lines.append("")
            lines.append(format_diff(result.diff, color=use_color))
    else:
        badge = colorize("[CLEAN]", Color.GREEN, force=use_color)
        lines.append(f"{badge} {colorize(result.file_path, Color.BOLD, force=use_color)} - Already sorted.")

    return "\n".join(lines)


def format_fix_result(
    result: FixResult,
    output_format: str = "pretty",
    color: bool = True,
) -> str:
    """Format fix result for console display."""
    if output_format == "json":
        return json.dumps(result.to_dict(), indent=2)

    use_color = color and Color.enabled()
    lines: List[str] = []

    if output_format == "simple":
        status = f"FIXED ({result.fixed_issues_count} fixes)" if result.modified else "CLEAN"
        lines.append(f"{result.file_path}: {status}")
        return "\n".join(lines)

    if result.modified:
        badge = colorize("[FIXED]", Color.GREEN, force=use_color)
        lines.append(f"{badge} {colorize(result.file_path, Color.BOLD, force=use_color)}")
        lines.append(f"  Total fixes applied: {colorize(str(result.fixed_issues_count), Color.BOLD, force=use_color)}")
        for desc in result.descriptions:
            lines.append(f"  • {desc}")
        if result.backup_path:
            lines.append(f"  Backup created: {result.backup_path}")
        if result.diff:
            lines.append("")
            lines.append(format_diff(result.diff, color=use_color))
    else:
        badge = colorize("[CLEAN]", Color.GREEN, force=use_color)
        lines.append(f"{badge} {colorize(result.file_path, Color.BOLD, force=use_color)} - No fixable issues detected.")

    return "\n".join(lines)
