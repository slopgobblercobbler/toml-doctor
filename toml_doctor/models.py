"""Data models and issue types for toml-doctor."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Diagnostic severity level."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """Represents a single TOML lint or validation issue."""
    rule_id: str
    message: str
    severity: Severity = Severity.ERROR
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column: Optional[int] = None
    key: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert issue to JSON-serializable dictionary."""
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "key": self.key,
            "suggestion": self.suggestion,
        }


class TomlLineType(str, Enum):
    """Type of line inside a TOML file."""
    EMPTY = "empty"
    COMMENT = "comment"
    TABLE_HEADER = "table_header"
    ARRAY_TABLE_HEADER = "array_table_header"
    KEY_VALUE = "key_value"
    MULTILINE = "multiline"
    INVALID = "invalid"


@dataclass
class TomlLine:
    """Represents a parsed line within a TOML document."""
    raw: str
    line_number: int
    line_type: TomlLineType
    indent: str = ""
    key: Optional[str] = None
    raw_key: Optional[str] = None
    value: Optional[str] = None
    comment: Optional[str] = None
    has_whitespace_around_equals: bool = False
    has_trailing_whitespace: bool = False


@dataclass
class TomlSection:
    """Represents a table section in TOML, e.g. [project] or [[bin]]."""
    header: Optional[str] = None
    is_array_table: bool = False
    header_line: Optional[int] = None
    lead_comments: List[str] = field(default_factory=list)
    lines: List[TomlLine] = field(default_factory=list)
    keys: Dict[str, List[int]] = field(default_factory=dict)

    @property
    def is_root(self) -> bool:
        """Return True if section represents keys before any table header."""
        return self.header is None


@dataclass
class ValidationResult:
    """Result of a TOML validation check."""
    file_path: str
    is_valid: bool = True
    issues: List[Issue] = field(default_factory=list)
    duplicate_keys: List[str] = field(default_factory=list)
    duplicate_tables: List[str] = field(default_factory=list)
    pep_issues: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any critical errors exist."""
        return any(i.severity == Severity.ERROR for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON output."""
        return {
            "file_path": self.file_path,
            "is_valid": self.is_valid,
            "has_errors": self.has_errors,
            "issues": [i.to_dict() for i in self.issues],
            "duplicate_keys": self.duplicate_keys,
            "duplicate_tables": self.duplicate_tables,
            "pep_issues": self.pep_issues,
        }


@dataclass
class SortResult:
    """Result of a table/key sort operation."""
    file_path: str
    modified: bool = False
    backup_path: Optional[str] = None
    diff: Optional[str] = None
    sections_reordered: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON output."""
        return {
            "file_path": self.file_path,
            "modified": self.modified,
            "backup_path": self.backup_path,
            "diff": self.diff,
            "sections_reordered": self.sections_reordered,
        }


@dataclass
class FixResult:
    """Result of an automated repair operation."""
    file_path: str
    modified: bool = False
    backup_path: Optional[str] = None
    diff: Optional[str] = None
    fixed_issues_count: int = 0
    descriptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON output."""
        return {
            "file_path": self.file_path,
            "modified": self.modified,
            "backup_path": self.backup_path,
            "diff": self.diff,
            "fixed_issues_count": self.fixed_issues_count,
            "descriptions": self.descriptions,
        }
