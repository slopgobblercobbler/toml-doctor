"""toml-doctor: Production-grade TOML 1.0 validator, PEP 518/621 table sorter, duplicate detector, and autofixer."""
from __future__ import annotations

from toml_doctor.fixer import TomlFixer, fix
from toml_doctor.models import (
    FixResult,
    Issue,
    Severity,
    SortResult,
    TomlLine,
    TomlLineType,
    TomlSection,
    ValidationResult,
)
from toml_doctor.parser import TomlDocument, TomlParser
from toml_doctor.sorter import TomlSorter, sort
from toml_doctor.validator import TomlValidator, validate

__version__ = "0.1.0"
parse = TomlParser.parse

__all__ = [
    "__version__",
    "parse",
    "validate",
    "sort",
    "fix",
    "TomlParser",
    "TomlDocument",
    "TomlValidator",
    "TomlSorter",
    "TomlFixer",
    "Issue",
    "Severity",
    "ValidationResult",
    "SortResult",
    "FixResult",
    "TomlLine",
    "TomlLineType",
    "TomlSection",
]
