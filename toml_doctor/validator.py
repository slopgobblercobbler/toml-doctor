"""TOML 1.0 validator, duplicate detector, and PEP 518/621 schema auditor."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from toml_doctor.models import Issue, Severity, ValidationResult
from toml_doctor.parser import RE_BARE_KEY, TomlDocument, TomlParser


RE_VALID_PEP621_NAME = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", re.IGNORECASE)


class TomlValidator:
    """Performs comprehensive TOML 1.0 syntax, duplication, and PEP schema validation."""

    def __init__(self, check_pep: bool = True, strict_formatting: bool = False):
        self.check_pep = check_pep
        self.strict_formatting = strict_formatting

    def validate_text(self, text: str, file_path: str = "<stdin>") -> ValidationResult:
        """Validate TOML text and return ValidationResult."""
        result = ValidationResult(file_path=file_path)

        # 1. Parse with standard TOML decoder
        parsed_data: Optional[Dict[str, Any]] = None
        try:
            parsed_data = tomllib.loads(text)
        except Exception as err:
            result.is_valid = False
            line_no: Optional[int] = None
            col_no: Optional[int] = None

            # Attempt to extract line and column from error object or message
            if hasattr(err, "lineno"):
                line_no = getattr(err, "lineno")
            if hasattr(err, "colno"):
                col_no = getattr(err, "colno")

            if line_no is None:
                # Parse message like: "Invalid statement at line 5, col 2"
                match = re.search(r"line\s+(\d+)(?:,\s*col\s+(\d+))?", str(err), re.IGNORECASE)
                if match:
                    line_no = int(match.group(1))
                    if match.group(2):
                        col_no = int(match.group(2))

            result.issues.append(
                Issue(
                    rule_id="TOML003",
                    message=f"TOML syntax error: {err}",
                    severity=Severity.ERROR,
                    file_path=file_path,
                    line_number=line_no,
                    column=col_no,
                )
            )

        # 2. Structural line-by-line inspection (find duplicate keys, table headers, formatting)
        doc: TomlDocument = TomlParser.parse(text)
        self._audit_structural_integrity(doc, file_path, result)

        # 3. PEP 518 & PEP 621 pyproject schema audit
        is_pyproject = (
            file_path.endswith("pyproject.toml")
            or (parsed_data is not None and ("project" in parsed_data or "build-system" in parsed_data))
        )
        if self.check_pep and is_pyproject and parsed_data is not None:
            self._audit_pep_schemas(parsed_data, file_path, result)

        # Determine overall validity
        if any(i.severity == Severity.ERROR for i in result.issues):
            result.is_valid = False

        return result

    def validate_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """Read and validate a TOML file from disk."""
        path = Path(file_path)
        if not path.is_file():
            result = ValidationResult(file_path=str(path), is_valid=False)
            result.issues.append(
                Issue(
                    rule_id="IO001",
                    message=f"File not found or unreadable: {path}",
                    severity=Severity.ERROR,
                    file_path=str(path),
                )
            )
            return result

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="latin-1")
            except Exception as e:
                result = ValidationResult(file_path=str(path), is_valid=False)
                result.issues.append(
                    Issue(
                        rule_id="IO002",
                        message=f"Failed to read file: {e}",
                        severity=Severity.ERROR,
                        file_path=str(path),
                    )
                )
                return result

        return self.validate_text(content, file_path=str(path))

    def _audit_structural_integrity(
        self, doc: TomlDocument, file_path: str, result: ValidationResult
    ) -> None:
        """Inspect sections for duplicate keys, duplicate headers, and formatting issues."""
        seen_tables: Dict[str, int] = {}

        for sec in doc.sections:
            # Check duplicate table headers
            if sec.header is not None and not sec.is_array_table:
                if sec.header in seen_tables:
                    prev_line = seen_tables[sec.header]
                    msg = f"Duplicate table '[{sec.header}]' previously declared at line {prev_line}"
                    result.duplicate_tables.append(sec.header)
                    result.issues.append(
                        Issue(
                            rule_id="TOML002",
                            message=msg,
                            severity=Severity.ERROR,
                            file_path=file_path,
                            line_number=sec.header_line,
                            key=sec.header,
                            suggestion=f"Consolidate keys into the single '[{sec.header}]' definition.",
                        )
                    )
                else:
                    seen_tables[sec.header] = sec.header_line or 0

            # Check duplicate keys within the section
            for key_name, occurrences in sec.keys.items():
                if len(occurrences) > 1:
                    first_line = occurrences[0]
                    for dup_line in occurrences[1:]:
                        sec_desc = f"in table '[{sec.header}]'" if sec.header else "at root level"
                        msg = f"Duplicate key '{key_name}' {sec_desc}; first defined at line {first_line}"
                        if key_name not in result.duplicate_keys:
                            result.duplicate_keys.append(key_name)
                        result.issues.append(
                            Issue(
                                rule_id="TOML001",
                                message=msg,
                                severity=Severity.ERROR,
                                file_path=file_path,
                                line_number=dup_line,
                                key=key_name,
                                suggestion=f"Remove or rename duplicate '{key_name}'.",
                            )
                        )

            # Check line formatting
            for line in sec.lines:
                if line.has_trailing_whitespace:
                    result.issues.append(
                        Issue(
                            rule_id="TOML006",
                            message="Trailing whitespace detected.",
                            severity=Severity.WARNING,
                            file_path=file_path,
                            line_number=line.line_number,
                            suggestion="Strip trailing whitespace from line.",
                        )
                    )

                if line.line_type.value == "key_value":
                    if not line.has_whitespace_around_equals and line.raw_key and line.value:
                        result.issues.append(
                            Issue(
                                rule_id="TOML005",
                                message=f"Inconsistent spacing around '=' for key '{line.key}'. Expected 'key = value'.",
                                severity=Severity.WARNING,
                                file_path=file_path,
                                line_number=line.line_number,
                                key=line.key,
                                suggestion=f"{line.raw_key} = {line.value}",
                            )
                        )

    def _audit_pep_schemas(
        self, data: Dict[str, Any], file_path: str, result: ValidationResult
    ) -> None:
        """Validate PEP 518 ([build-system]) and PEP 621 ([project]) metadata."""
        # 1. PEP 518: [build-system]
        if "build-system" in data:
            bs = data["build-system"]
            if not isinstance(bs, dict):
                msg = "[build-system] must be a TOML table."
                result.pep_issues.append(msg)
                result.issues.append(
                    Issue(rule_id="PEP518", message=msg, severity=Severity.ERROR, file_path=file_path)
                )
            else:
                if "requires" not in bs:
                    msg = "[build-system] missing mandatory field 'requires'."
                    result.pep_issues.append(msg)
                    result.issues.append(
                        Issue(
                            rule_id="PEP518",
                            message=msg,
                            severity=Severity.ERROR,
                            file_path=file_path,
                            suggestion='requires = ["setuptools>=61.0.0", "wheel"]',
                        )
                    )
                elif not isinstance(bs["requires"], list):
                    msg = "[build-system].requires must be a list of string specifications."
                    result.pep_issues.append(msg)
                    result.issues.append(
                        Issue(rule_id="PEP518", message=msg, severity=Severity.ERROR, file_path=file_path)
                    )

                if "build-backend" in bs and not isinstance(bs["build-backend"], str):
                    msg = "[build-system].build-backend must be a string."
                    result.pep_issues.append(msg)
                    result.issues.append(
                        Issue(rule_id="PEP518", message=msg, severity=Severity.ERROR, file_path=file_path)
                    )

        # 2. PEP 621: [project]
        if "project" in data:
            proj = data["project"]
            if not isinstance(proj, dict):
                msg = "[project] must be a TOML table."
                result.pep_issues.append(msg)
                result.issues.append(
                    Issue(rule_id="PEP621", message=msg, severity=Severity.ERROR, file_path=file_path)
                )
                return

            dynamic_fields = proj.get("dynamic", [])
            if not isinstance(dynamic_fields, list):
                dynamic_fields = []

            # Name requirement
            if "name" not in proj:
                msg = "[project] missing mandatory field 'name'."
                result.pep_issues.append(msg)
                result.issues.append(
                    Issue(rule_id="PEP621", message=msg, severity=Severity.ERROR, file_path=file_path)
                )
            else:
                name_val = proj["name"]
                if not isinstance(name_val, str) or not RE_VALID_PEP621_NAME.match(name_val):
                    msg = f"[project].name '{name_val}' is invalid according to PEP 621 / PEP 508 naming rules."
                    result.pep_issues.append(msg)
                    result.issues.append(
                        Issue(rule_id="PEP621", message=msg, severity=Severity.ERROR, file_path=file_path)
                    )

            # Version requirement: must have 'version' unless marked in 'dynamic'
            if "version" not in proj and "version" not in dynamic_fields:
                msg = "[project] must define 'version' or declare 'version' in 'dynamic'."
                result.pep_issues.append(msg)
                result.issues.append(
                    Issue(
                        rule_id="PEP621",
                        message=msg,
                        severity=Severity.ERROR,
                        file_path=file_path,
                        suggestion='version = "0.1.0"',
                    )
                )
            elif "version" in proj and not isinstance(proj["version"], str):
                msg = "[project].version must be a string."
                result.pep_issues.append(msg)
                result.issues.append(
                    Issue(rule_id="PEP621", message=msg, severity=Severity.ERROR, file_path=file_path)
                )

            # Dependencies requirement
            if "dependencies" in proj:
                if not isinstance(proj["dependencies"], list):
                    msg = "[project].dependencies must be a list of PEP 508 requirement strings."
                    result.pep_issues.append(msg)
                    result.issues.append(
                        Issue(rule_id="PEP621", message=msg, severity=Severity.ERROR, file_path=file_path)
                    )

            # Authors requirement
            if "authors" in proj:
                if not isinstance(proj["authors"], list):
                    msg = "[project].authors must be an array of tables, e.g. [{ name = '...', email = '...' }]."
                    result.pep_issues.append(msg)
                    result.issues.append(
                        Issue(rule_id="PEP621", message=msg, severity=Severity.ERROR, file_path=file_path)
                    )


def validate(
    target: Union[str, Path],
    check_pep: bool = True,
    strict_formatting: bool = False,
) -> ValidationResult:
    """Convenience function to validate a file or text."""
    validator = TomlValidator(check_pep=check_pep, strict_formatting=strict_formatting)
    if isinstance(target, Path):
        return validator.validate_file(target)

    target_str = str(target)
    if "\n" not in target_str and "\r" not in target_str and not target_str.strip().startswith("["):
        try:
            p = Path(target_str)
            if p.is_file() or p.suffix.lower() == ".toml":
                return validator.validate_file(p)
        except OSError:
            pass

    return validator.validate_text(target_str)
