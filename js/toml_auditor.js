/**
 * TOML Doctor — Client-Side In-Browser TOML 1.0 Parser, Validator & Sorter Engine
 * Zero-dependency parser, duplicate detector, PEP 518 / PEP 621 schema auditor, and canonical sorter.
 */

(function (global) {
  'use strict';

  // Severity Definitions
  const Severity = {
    ERROR: 'error',
    WARNING: 'warning',
    INFO: 'info'
  };

  const Category = {
    SYNTAX: 'TOML 1.0 Syntax',
    DUPLICATE: 'Duplicate Definition',
    SCHEMA_PEP: 'PEP 518 / PEP 621 Schema',
    SCHEMA_CARGO: 'Cargo Manifest Schema',
    ORDERING: 'Section & Key Ordering',
    HYGIENE: 'Formatting & Hygiene'
  };

  // Canonical Section Priority for PEP 518 / PEP 621 pyproject.toml
  const PYPROJECT_TABLE_PRIORITY = {
    'build-system': 10,
    'project': 20,
    'project.optional-dependencies': 30,
    'project.scripts': 40,
    'project.gui-scripts': 50,
    'project.entry-points': 60,
    'project.urls': 70,
  };

  const PROJECT_KEY_PRIORITY = {
    'name': 1,
    'version': 2,
    'description': 3,
    'readme': 4,
    'requires-python': 5,
    'license': 6,
    'authors': 7,
    'maintainers': 8,
    'keywords': 9,
    'classifiers': 10,
    'dependencies': 11,
    'dynamic': 12
  };

  // Canonical Section Priority for Cargo.toml
  const CARGO_TABLE_PRIORITY = {
    'package': 10,
    'lib': 15,
    'bin': 18,
    'dependencies': 20,
    'dev-dependencies': 30,
    'build-dependencies': 40,
    'target': 50,
    'features': 60,
    'workspace': 70,
    'profile': 80,
    'patch': 90
  };

  const CARGO_PACKAGE_KEY_PRIORITY = {
    'name': 1,
    'version': 2,
    'edition': 3,
    'rust-version': 4,
    'authors': 5,
    'description': 6,
    'readme': 7,
    'license': 8,
    'repository': 9,
    'keywords': 10,
    'categories': 11
  };

  const RE_BARE_KEY = /^[A-Za-z0-9_-]+$/;
  const RE_PEP621_NAME = /^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$/i;

  // Lightweight AST & Parser
  class TomlParser {
    constructor() {}

    countBracketDelta(str) {
      let delta = 0;
      let inQuote = false;
      let quoteChar = '';
      for (let i = 0; i < str.length; i++) {
        const ch = str[i];
        if (ch === '#' && !inQuote) break;
        if (ch === '"' || ch === "'") {
          if (!inQuote) {
            inQuote = true;
            quoteChar = ch;
          } else if (quoteChar === ch && (i === 0 || str[i - 1] !== '\\')) {
            inQuote = false;
          }
        } else if (!inQuote) {
          if (ch === '[' || ch === '{') delta++;
          else if (ch === ']' || ch === '}') delta--;
        }
      }
      return delta;
    }

    /**
     * Parse raw TOML text into structured sections and AST
     */
    parse(text) {
      const rawLines = text.split(/\r?\n/);
      const sections = [];
      let currentSection = {
        name: '',
        headerLine: 0,
        isArrayOfTables: false,
        lines: [],
        entries: []
      };
      sections.push(currentSection);

      const tableDefinitions = new Map(); // name -> [{ line, isArray }]
      const definedKeys = new Map(); // "section" -> Set of keys
      const issues = [];
      let inMultilineString = false;
      let multilineDelimiter = '';
      let inMultilineArray = false;
      let arrayBracketDepth = 0;
      let currentEntry = null;

      for (let lineIdx = 0; lineIdx < rawLines.length; lineIdx++) {
        const lineNum = lineIdx + 1;
        const line = rawLines[lineIdx];
        const trimmed = line.trim();

        // Check multiline strings
        if (inMultilineString) {
          currentSection.lines.push(line);
          if (currentEntry) currentEntry.value += '\n' + line;
          if (line.includes(multilineDelimiter)) {
            inMultilineString = false;
          }
          continue;
        }

        // Check multiline arrays / inline tables
        if (inMultilineArray) {
          currentSection.lines.push(line);
          if (currentEntry) currentEntry.value += '\n' + line;
          arrayBracketDepth += this.countBracketDelta(line);
          if (arrayBracketDepth <= 0) {
            inMultilineArray = false;
            currentEntry = null;
            arrayBracketDepth = 0;
          }
          continue;
        }

        const multiMatch = trimmed.match(/("""|''')/);
        if (multiMatch) {
          const delim = multiMatch[1];
          const count = (trimmed.match(new RegExp(delim, 'g')) || []).length;
          if (count % 2 !== 0) {
            inMultilineString = true;
            multilineDelimiter = delim;
          }
        }

        // Check empty lines or full comment lines
        if (!trimmed || trimmed.startsWith('#')) {
          currentSection.lines.push(line);
          continue;
        }

        // Check Table Header: [[table]] or [table]
        const arrayTableMatch = trimmed.match(/^\[\[\s*([^\]]+?)\s*\]\]$/);
        const standardTableMatch = !arrayTableMatch && trimmed.match(/^\[\s*([^\]]+?)\s*\]$/);

        if (arrayTableMatch || standardTableMatch) {
          const isArray = Boolean(arrayTableMatch);
          const tableName = (isArray ? arrayTableMatch[1] : standardTableMatch[1]).trim();

          // Validate table name
          if (!tableName) {
            issues.push({
              id: 'TOML003',
              name: 'invalid-table-header',
              category: Category.SYNTAX,
              severity: Severity.ERROR,
              line: lineNum,
              message: 'Empty table header definition [].',
              recommendation: 'Specify a valid table identifier.'
            });
            continue;
          }

          // Duplicate & collision checks
          if (tableDefinitions.has(tableName)) {
            const prev = tableDefinitions.get(tableName);
            if (!isArray && !prev[0].isArray) {
              issues.push({
                id: 'TOML002',
                name: 'duplicate-table-header',
                category: Category.DUPLICATE,
                severity: Severity.ERROR,
                line: lineNum,
                message: `Duplicate table header '[${tableName}]' previously defined at line ${prev[0].line}.`,
                recommendation: 'Combine keys into a single table or use an array of tables [[...]] if intended.'
              });
            } else if (isArray !== prev[0].isArray) {
              issues.push({
                id: 'TOML006',
                name: 'table-array-collision',
                category: Category.DUPLICATE,
                severity: Severity.ERROR,
                line: lineNum,
                message: `Conflict between standard table and array of tables for '${tableName}'. First defined at line ${prev[0].line}.`,
                recommendation: 'Standard tables [table] and arrays of tables [[table]] cannot share the same path.'
              });
            }
            prev.push({ line: lineNum, isArray });
          } else {
            tableDefinitions.set(tableName, [{ line: lineNum, isArray }]);
          }

          currentSection = {
            name: tableName,
            headerLine: lineNum,
            isArrayOfTables: isArray,
            lines: [line],
            entries: []
          };
          sections.push(currentSection);
          continue;
        }

        // Key-Value Pair Check
        const eqIdx = this.findAssignmentOperator(trimmed);
        if (eqIdx !== -1) {
          const rawKey = trimmed.substring(0, eqIdx).trim();
          const rawValue = trimmed.substring(eqIdx + 1).trim();

          currentSection.lines.push(line);

          // Track key duplicates
          const sectionKeyMap = definedKeys.get(currentSection.name) || new Set();
          definedKeys.set(currentSection.name, sectionKeyMap);

          if (sectionKeyMap.has(rawKey)) {
            issues.push({
              id: 'TOML001',
              name: 'duplicate-key-definition',
              category: Category.DUPLICATE,
              severity: Severity.ERROR,
              line: lineNum,
              message: `Duplicate key '${rawKey}' in section '${currentSection.name || "root"}'.`,
              recommendation: `Remove or rename the duplicate key definition.`
            });
          } else {
            sectionKeyMap.add(rawKey);
          }

          // Key validation
          if (!this.isValidKey(rawKey)) {
            issues.push({
              id: 'TOML003',
              name: 'invalid-bare-key',
              category: Category.SYNTAX,
              severity: Severity.ERROR,
              line: lineNum,
              message: `Invalid bare key '${rawKey}'. Bare keys must only contain letters, numbers, underscores, or dashes, or be quoted.`,
              recommendation: `Enclose complex keys in quotes: "${rawKey}" = ...`
            });
          }

          // Value validation
          const delta = this.countBracketDelta(rawValue);
          const entry = {
            key: rawKey,
            value: rawValue,
            line: lineNum
          };
          currentSection.entries.push(entry);

          if (delta > 0) {
            inMultilineArray = true;
            arrayBracketDepth = delta;
            currentEntry = entry;
          } else {
            this.validateValue(rawValue, lineNum, rawKey, issues);
          }
          continue;
        }

        // If line is neither comment, blank, table, nor key=value, it's a syntax anomaly
        currentSection.lines.push(line);
        issues.push({
          id: 'TOML003',
          name: 'unrecognized-syntax',
          category: Category.SYNTAX,
          severity: Severity.ERROR,
          line: lineNum,
          message: `Unrecognized TOML statement at line ${lineNum}: "${trimmed}".`,
          recommendation: 'Ensure line is a valid key-value pair, table header, or comment.'
        });
      }

      if (inMultilineString) {
        issues.push({
          id: 'TOML003',
          name: 'unclosed-multiline-string',
          category: Category.SYNTAX,
          severity: Severity.ERROR,
          line: rawLines.length,
          message: `Unclosed multiline string ${multilineDelimiter} reaching end of file.`,
          recommendation: `Close the multiline string with matching ${multilineDelimiter}.`
        });
      }

      if (inMultilineArray) {
        issues.push({
          id: 'TOML003',
          name: 'unclosed-multiline-array',
          category: Category.SYNTAX,
          severity: Severity.ERROR,
          line: rawLines.length,
          message: `Unclosed array or inline structure reaching end of file.`,
          recommendation: `Close array with matching ']'.`
        });
      }

      return {
        sections: sections.filter(s => s.name || s.lines.some(l => l.trim() && !l.trim().startsWith('#'))),
        tableDefinitions,
        issues
      };
    }

    findAssignmentOperator(str) {
      let inQuote = false;
      let quoteChar = '';
      for (let i = 0; i < str.length; i++) {
        const ch = str[i];
        if (ch === '"' || ch === "'") {
          if (!inQuote) {
            inQuote = true;
            quoteChar = ch;
          } else if (quoteChar === ch && str[i - 1] !== '\\') {
            inQuote = false;
          }
        } else if (ch === '=' && !inQuote) {
          return i;
        }
      }
      return -1;
    }

    isValidKey(key) {
      if (!key) return false;
      // Dotted keys e.g. a.b.c
      const parts = key.split('.');
      return parts.every(p => {
        const t = p.trim();
        if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
          return true;
        }
        return RE_BARE_KEY.test(t);
      });
    }

    validateValue(val, lineNum, key, issues) {
      const stripped = val.replace(/#.*$/, '').trim();
      if (!stripped) {
        issues.push({
          id: 'TOML003',
          name: 'empty-assignment',
          category: Category.SYNTAX,
          severity: Severity.ERROR,
          line: lineNum,
          message: `Empty value assigned to key '${key}'.`,
          recommendation: 'Assign a valid TOML value (string, number, boolean, array, or inline table).'
        });
        return;
      }

      // Check unclosed basic string
      if (stripped.startsWith('"') && !stripped.endsWith('"') && !stripped.startsWith('"""')) {
        issues.push({
          id: 'TOML003',
          name: 'unclosed-string',
          category: Category.SYNTAX,
          severity: Severity.ERROR,
          line: lineNum,
          message: `Unclosed string literal for key '${key}'.`,
          recommendation: 'Ensure strings end with matching quote "'
        });
      }

      // Check unclosed literal string
      if (stripped.startsWith("'") && !stripped.endsWith("'") && !stripped.startsWith("'''")) {
        issues.push({
          id: 'TOML003',
          name: 'unclosed-literal-string',
          category: Category.SYNTAX,
          severity: Severity.ERROR,
          line: lineNum,
          message: `Unclosed literal string for key '${key}'.`,
          recommendation: "Ensure literal strings end with matching quote '"
        });
      }

      // Check unclosed inline tables
      if (stripped.startsWith('{') && !stripped.endsWith('}')) {
        issues.push({
          id: 'TOML003',
          name: 'unclosed-inline-table',
          category: Category.SYNTAX,
          severity: Severity.ERROR,
          line: lineNum,
          message: `Inline tables must be closed on the same line: '${key}'.`,
          recommendation: 'Close inline table with } or expand into a standard [table] section.'
        });
      }
    }
  }

  // Main Auditor Class
  class TomlAuditor {
    constructor() {
      this.parser = new TomlParser();
    }

    audit(text) {
      const parseResult = this.parser.parse(text);
      const issues = [...parseResult.issues];
      const sections = parseResult.sections;
      const rawLines = text.split(/\r?\n/);

      const tableNames = sections.map(s => s.name).filter(Boolean);
      const isPyproject = tableNames.includes('build-system') || tableNames.includes('project') || tableNames.some(t => t.startsWith('tool.'));
      const isCargo = tableNames.includes('package') || tableNames.includes('dependencies') || tableNames.includes('workspace');

      // 1. PEP 518 & PEP 621 Schema Auditing
      if (isPyproject) {
        this.auditPyproject(sections, issues);
      }

      // 2. Cargo Schema Auditing
      if (isCargo) {
        this.auditCargo(sections, issues);
      }

      // 3. Section Ordering Checks
      this.auditOrdering(sections, isPyproject, isCargo, issues);

      // 4. Formatting & Hygiene Checks
      this.auditHygiene(rawLines, issues);

      // Statistics & Score
      const stats = this.computeStats(sections, rawLines);
      const score = this.computeScore(issues);

      return {
        isValid: issues.filter(i => i.severity === Severity.ERROR).length === 0,
        score: score.numeric,
        grade: score.grade,
        ratingLabel: score.label,
        manifestType: isPyproject ? 'pyproject.toml (PEP 518/621)' : (isCargo ? 'Cargo.toml (Rust)' : 'Generic TOML'),
        sections,
        issues: issues.sort((a, b) => a.line - b.line),
        stats,
        summary: {
          total: issues.length,
          errors: issues.filter(i => i.severity === Severity.ERROR).length,
          warnings: issues.filter(i => i.severity === Severity.WARNING).length,
          info: issues.filter(i => i.severity === Severity.INFO).length
        }
      };
    }

    auditPyproject(sections, issues) {
      const buildSec = sections.find(s => s.name === 'build-system');
      const projSec = sections.find(s => s.name === 'project');

      if (!buildSec) {
        issues.push({
          id: 'PEP518',
          name: 'missing-build-system',
          category: Category.SCHEMA_PEP,
          severity: Severity.WARNING,
          line: 1,
          message: "PEP 518 recommends defining a '[build-system]' table to specify build requirements.",
          recommendation: "Add '[build-system]' with 'requires' and 'build-backend'."
        });
      } else {
        const reqEntry = buildSec.entries.find(e => e.key === 'requires');
        const backendEntry = buildSec.entries.find(e => e.key === 'build-backend');

        if (!reqEntry) {
          issues.push({
            id: 'PEP518',
            name: 'missing-build-requires',
            category: Category.SCHEMA_PEP,
            severity: Severity.ERROR,
            line: buildSec.headerLine,
            message: "Table '[build-system]' must specify 'requires = [...]'.",
            recommendation: "Specify build dependencies, e.g. requires = ['setuptools>=61.0']."
          });
        }
        if (!backendEntry) {
          issues.push({
            id: 'PEP518',
            name: 'missing-build-backend',
            category: Category.SCHEMA_PEP,
            severity: Severity.WARNING,
            line: buildSec.headerLine,
            message: "Table '[build-system]' should specify 'build-backend' (e.g. 'setuptools.build_meta' or 'hatchling.build').",
            recommendation: "Add build-backend = 'setuptools.build_meta'"
          });
        }
      }

      if (projSec) {
        const nameEntry = projSec.entries.find(e => e.key === 'name');
        const versionEntry = projSec.entries.find(e => e.key === 'version');
        const dynamicEntry = projSec.entries.find(e => e.key === 'dynamic');

        if (!nameEntry) {
          issues.push({
            id: 'PEP621',
            name: 'missing-project-name',
            category: Category.SCHEMA_PEP,
            severity: Severity.ERROR,
            line: projSec.headerLine,
            message: "PEP 621 requires a project 'name' in '[project]'.",
            recommendation: "Define name = 'my-package'"
          });
        } else {
          const rawName = nameEntry.value.replace(/^['"]|['"]$/g, '').trim();
          if (!RE_PEP621_NAME.test(rawName)) {
            issues.push({
              id: 'PEP621',
              name: 'invalid-pep621-name',
              category: Category.SCHEMA_PEP,
              severity: Severity.ERROR,
              line: nameEntry.line,
              message: `Project name '${rawName}' does not conform to PEP 621 naming normalization.`,
              recommendation: "Project names must only contain alphanumeric characters, '.', '_', and '-'."
            });
          }
        }

        const isDynamicVersion = dynamicEntry && dynamicEntry.value.includes('version');
        if (!versionEntry && !isDynamicVersion) {
          issues.push({
            id: 'PEP621',
            name: 'missing-project-version',
            category: Category.SCHEMA_PEP,
            severity: Severity.ERROR,
            line: projSec.headerLine,
            message: "PEP 621 requires 'version' in '[project]' unless listed under 'dynamic = [...]'.",
            recommendation: "Add version = '0.1.0' or declare dynamic = ['version']."
          });
        }
      }
    }

    auditCargo(sections, issues) {
      const pkgSec = sections.find(s => s.name === 'package');
      if (pkgSec) {
        const nameEntry = pkgSec.entries.find(e => e.key === 'name');
        const versionEntry = pkgSec.entries.find(e => e.key === 'version');
        const editionEntry = pkgSec.entries.find(e => e.key === 'edition');

        if (!nameEntry) {
          issues.push({
            id: 'CARGO001',
            name: 'missing-cargo-package-name',
            category: Category.SCHEMA_CARGO,
            severity: Severity.ERROR,
            line: pkgSec.headerLine,
            message: "Rust '[package]' table requires 'name'.",
            recommendation: "Add name = 'crate-name'"
          });
        }
        if (!versionEntry) {
          issues.push({
            id: 'CARGO001',
            name: 'missing-cargo-version',
            category: Category.SCHEMA_CARGO,
            severity: Severity.ERROR,
            line: pkgSec.headerLine,
            message: "Rust '[package]' table requires 'version'.",
            recommendation: "Add version = '0.1.0'"
          });
        }
        if (!editionEntry) {
          issues.push({
            id: 'CARGO001',
            name: 'missing-cargo-edition',
            category: Category.SCHEMA_CARGO,
            severity: Severity.WARNING,
            line: pkgSec.headerLine,
            message: "Rust '[package]' should specify Rust edition (e.g. edition = '2021').",
            recommendation: "Add edition = '2021'"
          });
        }
      }
    }

    auditOrdering(sections, isPyproject, isCargo, issues) {
      const namedSections = sections.filter(s => s.name);
      if (namedSections.length <= 1) return;

      const priorityMap = isPyproject ? PYPROJECT_TABLE_PRIORITY : (isCargo ? CARGO_TABLE_PRIORITY : null);

      if (priorityMap) {
        for (let i = 0; i < namedSections.length - 1; i++) {
          const current = namedSections[i];
          const next = namedSections[i + 1];

          const currPrio = priorityMap[current.name] || 999;
          const nextPrio = priorityMap[next.name] || 999;

          if (currPrio > nextPrio) {
            issues.push({
              id: 'SORT001',
              name: 'non-canonical-section-order',
              category: Category.ORDERING,
              severity: Severity.WARNING,
              line: next.headerLine,
              message: `Table '[${next.name}]' appears after '[${current.name}]'. Canonical ordering places core metadata first.`,
              recommendation: `Use TOML Doctor's 'Sort & Format' to auto-order sections.`
            });
            break;
          }
        }
      }
    }

    auditHygiene(rawLines, issues) {
      for (let i = 0; i < rawLines.length; i++) {
        const line = rawLines[i];
        const lineNum = i + 1;

        // Trailing whitespace
        if (/[ \t]+$/.test(line)) {
          issues.push({
            id: 'FMT001',
            name: 'trailing-whitespace',
            category: Category.HYGIENE,
            severity: Severity.INFO,
            line: lineNum,
            message: `Trailing whitespace detected on line ${lineNum}.`,
            recommendation: 'Remove extraneous whitespace at the end of the line.'
          });
        }

        // Inconsistent spacing around = (e.g. foo=1 or foo= 1 or foo =1)
        if (/^\s*[A-Za-z0-9_-]+\s*(?:=\S|\S=)\s*/.test(line) && !line.includes('==') && !line.trim().startsWith('#')) {
          issues.push({
            id: 'FMT002',
            name: 'irregular-operator-spacing',
            category: Category.HYGIENE,
            severity: Severity.INFO,
            line: lineNum,
            message: `Irregular spacing around '=' operator on line ${lineNum}. Standard style is 'key = value'.`,
            recommendation: "Format with single space on each side of '='."
          });
        }
      }
    }

    /**
     * Reformat and canonically sort TOML
     */
    sortAndFormat(text, mode = 'pyproject') {
      const parseResult = this.parser.parse(text);
      let sections = parseResult.sections;

      const priorityMap = mode === 'cargo' ? CARGO_TABLE_PRIORITY : PYPROJECT_TABLE_PRIORITY;

      // Sort sections
      sections.sort((a, b) => {
        // Root section always first
        if (!a.name) return -1;
        if (!b.name) return 1;

        const prioA = priorityMap[a.name] || 900;
        const prioB = priorityMap[b.name] || 900;

        if (prioA !== prioB) return prioA - prioB;
        return a.name.localeCompare(b.name);
      });

      // Format lines inside sections
      const formattedParts = [];

      sections.forEach(sec => {
        const cleanLines = [];

        sec.lines.forEach(l => {
          let line = l.trimEnd();

          // Format spacing around = for key-values
          if (!line.trim().startsWith('#') && !line.trim().startsWith('[')) {
            const eqIdx = line.indexOf('=');
            if (eqIdx !== -1 && !line.includes('==')) {
              const k = line.substring(0, eqIdx).trim();
              const v = line.substring(eqIdx + 1).trim();
              line = `${k} = ${v}`;
            }
          }
          if (line) cleanLines.push(line);
        });

        if (cleanLines.length > 0) {
          formattedParts.push(cleanLines.join('\n'));
        }
      });

      return formattedParts.join('\n\n') + '\n';
    }

    computeStats(sections, rawLines) {
      let keyCount = 0;
      sections.forEach(s => {
        keyCount += s.entries.length;
      });

      return {
        lineCount: rawLines.length,
        tableCount: sections.filter(s => s.name).length,
        keyCount: keyCount
      };
    }

    computeScore(issues) {
      let penalty = 0;
      issues.forEach(i => {
        if (i.severity === Severity.ERROR) penalty += 25;
        else if (i.severity === Severity.WARNING) penalty += 10;
        else if (i.severity === Severity.INFO) penalty += 2;
      });

      const score = Math.max(0, 100 - penalty);
      let grade = 'A+';
      let label = 'Clean & Standard-Compliant';

      if (score >= 90) {
        grade = 'A+';
        label = 'Fully Compliant TOML 1.0';
      } else if (score >= 80) {
        grade = 'A';
        label = 'Valid — Minor Ordering Warnings';
      } else if (score >= 70) {
        grade = 'B';
        label = 'Valid — Needs Section Sorting';
      } else if (score >= 50) {
        grade = 'C';
        label = 'Syntax Errors or Duplicate Keys';
      } else {
        grade = 'F';
        label = 'Critical Malformed TOML';
      }

      return { numeric: score, grade, label };
    }
  }

  // Pre-configured Presets
  const Presets = {
    PYPROJECT_STANDARD: `[build-system]
requires = ["hatchling>=1.20.0"]
build-backend = "hatchling.build"

[project]
name = "toml-doctor"
version = "0.2.0"
description = "Production-grade TOML 1.0 validator, PEP 518/621 table sorter, and fixer."
readme = "README.md"
requires-python = ">=3.9"
license = "MIT"
authors = [
    { name = "Stephen Cork", email = "slopgobblercobbler@users.noreply.github.com" }
]
keywords = ["toml", "validator", "pep518", "pep621", "linter", "formatter"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12"
]
dependencies = [
    "tomli>=2.0.1; python_version < '3.11'"
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.8.0",
    "ruff>=0.3.0"
]

[project.scripts]
toml-doctor = "toml_doctor.cli:main"

[project.urls]
Homepage = "https://slopgobblercobbler.github.io/toml-doctor/"
Repository = "https://github.com/slopgobblercobbler/toml-doctor"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=toml_doctor --cov-report=term-missing"

[tool.ruff]
line-length = 100
target-version = "py310"
`,

    CARGO_WORKSPACE: `[package]
name = "rust-service"
version = "0.1.0"
edition = "2021"
authors = ["Stephen Cork <slopgobblercobbler@users.noreply.github.com>"]
description = "High-performance asynchronous data parsing engine."
license = "MIT"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1.36", features = ["full"] }
tracing = "0.1"

[dev-dependencies]
criterion = "0.5"
tempfile = "3.10"

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
panic = "abort"
strip = true
`,

    BROKEN_DUPLICATES: `title = "Application Config"
owner = "Platform Team"

# Duplicate table definition
[database]
server = "192.168.1.1"
port = 5432
max_connections = 100
port = 5433

# Duplicate table header
[database]
server = "10.0.0.1"
timeout = 30

[server]
host = "0.0.0.0"
bad_key_@#$ = true
unclosed_string = "missing closing quote
broken_inline = { key1 = "val1"
`,

    UNSORTED_MESSY: `[tool.ruff]
line-length = 100

[project.scripts]
run-app = "app:cli"

[tool.pytest.ini_options]
testpaths = ["tests"]

[project]
name = "messy-project"
version = "1.0.0"
dependencies = ["requests>=2.0"]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
`
  };

  // Export module for Node.js test suite or browser global
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      TomlAuditor,
      TomlParser,
      Severity,
      Category,
      Presets
    };
  }

  global.TomlAuditor = TomlAuditor;
  global.TomlAuditorPresets = Presets;

})(typeof window !== 'undefined' ? window : this);
