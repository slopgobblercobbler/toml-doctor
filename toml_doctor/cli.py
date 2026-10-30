"""Command-line interface for toml-doctor."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from toml_doctor import __version__
from toml_doctor.fixer import TomlFixer
from toml_doctor.formatter import (
    format_fix_result,
    format_sort_result,
    format_validation_result,
)
from toml_doctor.sorter import TomlSorter
from toml_doctor.validator import TomlValidator


def create_parser() -> argparse.ArgumentParser:
    """Construct command-line parser."""
    parser = argparse.ArgumentParser(
        prog="toml-doctor",
        description="Production-grade TOML 1.0 validator, PEP 518/621 table sorter, duplicate detector, and autofixer.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: validate / check
    for cmd_name in ("validate", "check"):
        val_parser = subparsers.add_parser(
            cmd_name,
            help="Validate TOML syntax, detect duplicate keys/tables, and audit PEP 518/621 metadata.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        val_parser.add_argument(
            "files",
            nargs="*",
            default=["pyproject.toml"],
            help="TOML file(s) to validate.",
        )
        val_parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as errors (exit code 1).",
        )
        val_parser.add_argument(
            "--no-pep",
            action="store_true",
            help="Disable PEP 518 and PEP 621 schema verification.",
        )
        val_parser.add_argument(
            "--format",
            choices=["pretty", "simple", "json"],
            default="pretty",
            help="Output formatting style.",
        )
        val_parser.add_argument(
            "--no-color",
            action="store_true",
            help="Disable colorized terminal output.",
        )

    # Subcommand: sort
    sort_parser = subparsers.add_parser(
        "sort",
        help="Order tables canonically according to PEP 518 / PEP 621 conventions and tool guidelines.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sort_parser.add_argument(
        "files",
        nargs="*",
        default=["pyproject.toml"],
        help="TOML file(s) to sort.",
    )
    sort_parser.add_argument(
        "-i",
        "--in-place",
        action="store_true",
        help="Apply changes directly to the target file.",
    )
    sort_parser.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="Create a .bak backup file before modifying in-place.",
    )
    sort_parser.add_argument(
        "--sort-keys",
        action="store_true",
        help="Also sort keys within sections (canonical for [project], alphabetical otherwise).",
    )
    sort_parser.add_argument(
        "--diff",
        action="store_true",
        help="Print unified diff of changes.",
    )
    sort_parser.add_argument(
        "--format",
        choices=["pretty", "simple", "json"],
        default="pretty",
        help="Output formatting style.",
    )
    sort_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colorized terminal output.",
    )

    # Subcommand: fix
    fix_parser = subparsers.add_parser(
        "fix",
        help="Automatically repair formatting, normalize '=' spacing, remove duplicate keys, and strip trailing whitespace.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    fix_parser.add_argument(
        "files",
        nargs="*",
        default=["pyproject.toml"],
        help="TOML file(s) to repair.",
    )
    fix_parser.add_argument(
        "-i",
        "--in-place",
        action="store_true",
        help="Apply changes directly to the target file.",
    )
    fix_parser.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="Create a .bak backup file before modifying in-place.",
    )
    fix_parser.add_argument(
        "--diff",
        action="store_true",
        help="Print unified diff of applied fixes.",
    )
    fix_parser.add_argument(
        "--all",
        action="store_true",
        help="Apply both syntax/whitespace repairs and table sorting.",
    )
    fix_parser.add_argument(
        "--no-spacing",
        action="store_true",
        help="Do not normalize '=' spacing.",
    )
    fix_parser.add_argument(
        "--no-trailing",
        action="store_true",
        help="Do not strip trailing whitespace.",
    )
    fix_parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Do not remove duplicate keys.",
    )
    fix_parser.add_argument(
        "--format",
        choices=["pretty", "simple", "json"],
        default="pretty",
        help="Output formatting style.",
    )
    fix_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colorized terminal output.",
    )

    return parser


def handle_validate(args: argparse.Namespace) -> int:
    """Execute validate/check command."""
    validator = TomlValidator(check_pep=not args.no_pep)
    exit_code = 0

    for file_path in args.files:
        path = Path(file_path)
        result = validator.validate_file(path)
        print(
            format_validation_result(
                result, output_format=args.format, color=not args.no_color
            )
        )
        if result.has_errors or not result.is_valid:
            exit_code = 1
        elif args.strict and result.issues:
            exit_code = 1

    return exit_code


def handle_sort(args: argparse.Namespace) -> int:
    """Execute sort command."""
    sorter = TomlSorter(sort_keys=args.sort_keys)
    exit_code = 0

    for file_path in args.files:
        path = Path(file_path)
        result = sorter.sort_file(
            path, in_place=args.in_place, backup=args.backup
        )
        if not args.diff and not args.in_place and result.diff:
            # If not in-place and not explicit --diff, still include diff in pretty mode
            pass
        elif not args.diff and args.in_place:
            result.diff = None

        print(
            format_sort_result(
                result, output_format=args.format, color=not args.no_color
            )
        )
        if result.modified and not args.in_place:
            # Indicate changes needed
            exit_code = 1

    return exit_code


def handle_fix(args: argparse.Namespace) -> int:
    """Execute fix command."""
    fixer = TomlFixer(
        fix_spacing=not args.no_spacing,
        fix_trailing=not args.no_trailing,
        deduplicate_keys=not args.no_dedup,
    )
    sorter = TomlSorter() if args.all else None
    exit_code = 0

    for file_path in args.files:
        path = Path(file_path)
        result = fixer.fix_file(
            path, in_place=args.in_place, backup=args.backup
        )

        if args.all and path.is_file():
            # Also run table sorter in-place if requested
            sort_res = sorter.sort_file(path, in_place=args.in_place, backup=False)
            if sort_res.modified:
                result.modified = True
                result.fixed_issues_count += 1
                result.descriptions.append("Sorted tables to PEP 518/621 canonical order")
                if result.diff and sort_res.diff:
                    result.diff += "\n" + sort_res.diff
                elif sort_res.diff:
                    result.diff = sort_res.diff

        if not args.diff and args.in_place:
            result.diff = None

        print(
            format_fix_result(
                result, output_format=args.format, color=not args.no_color
            )
        )
        if result.modified and not args.in_place:
            exit_code = 1

    return exit_code


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command in ("validate", "check"):
        return handle_validate(args)
    if args.command == "sort":
        return handle_sort(args)
    if args.command == "fix":
        return handle_fix(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
