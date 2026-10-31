# toml-doctor

[![Live Web App](https://img.shields.io/badge/Live%20App-GitHub%20Pages-success?logo=github&style=flat)](https://slopgobblercobbler.github.io/toml-doctor/)
[![CI](https://github.com/slopgobblercobbler/toml-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopgobblercobbler/toml-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](pyproject.toml)

> Production-grade TOML 1.0 validator, PEP 518 / PEP 621 table sorter, duplicate detector, and automated fixer.

---

## Features

- **TOML 1.0 Strict Syntax Audit**: Validates syntax, dates, multiline strings, inline tables, and unicode escapes.
- **Duplicate Detection**: Accurately flags duplicate table headers, conflicting array-of-tables, and redefined keys across deep hierarchies.
- **PEP 518 & PEP 621 Compliance**: Audits `[build-system]`, `[project]`, and `[project.optional-dependencies]` metadata against Python packaging standards.
- **Deterministic Table Sorter**: Canonical ordering for standard Python and Rust manifests (`[build-system]`, `[project]`, `[tool.*]`).
- **In-Place Autofixer**: Safe, dry-run-capable fixer for invalid spacing around `=` operators, unquoted dotted keys, and trailing whitespace.
- **Multiple Output Formats**: Rich color terminal output, compact format for CI, and machine-readable JSON.

---

## Installation

```bash
pip install toml-doctor
```

Or run directly with `pipx`:

```bash
pipx run toml-doctor validate pyproject.toml
```

---

## Usage

### 1. Validate TOML Files

```bash
# Validate standard pyproject.toml
toml-doctor validate pyproject.toml

# Strict mode: treat all warnings as errors
toml-doctor check --strict Cargo.toml pyproject.toml

# Output as JSON for automated pipelines
toml-doctor validate pyproject.toml --format json
```

### 2. Deterministic Table Sorting

Sort tables and key-value pairs into canonical order:

```bash
# Dry run: view diff without modifying files
toml-doctor sort pyproject.toml --diff

# Apply in-place sorting
toml-doctor sort pyproject.toml -i
```

### 3. Automated Fixing

```bash
# Preview fixes
toml-doctor fix pyproject.toml --diff

# Apply fixes directly
toml-doctor fix pyproject.toml -i
```

---

## Diagnostic Rules

| Rule ID | Severity | Description |
|---|---|---|
| `TOML001` | Error | Invalid TOML syntax or unparsable literal |
| `TOML002` | Error | Duplicate key detected within table |
| `TOML003` | Error | Redefined table header or conflicting table type |
| `TOML004` | Warning | Missing recommended PEP 518 / 621 metadata |
| `TOML005` | Warning | Irregular spacing around key-value delimiter |
| `TOML006` | Warning | Out-of-order table structure |

---

## Continuous Integration

Add `toml-doctor` to your GitHub Actions workflow:

```yaml
- name: Lint TOML configuration
  run: |
    pip install toml-doctor
    toml-doctor validate pyproject.toml --strict
```

---

## License

MIT © [Stephen Cork (slopgobblercobbler)](https://github.com/slopgobblercobbler)
