/**
 * Automated Node.js Test Suite for TOML Doctor Client Engine
 */

const assert = require('node:assert');
const test = require('node:test');
const { TomlAuditor, TomlParser, Presets } = require('../js/toml_auditor.js');

test('TOML Parser: parses valid standard pyproject.toml', () => {
  const auditor = new TomlAuditor();
  const result = auditor.audit(Presets.PYPROJECT_STANDARD);

  assert.strictEqual(result.isValid, true, 'Standard pyproject.toml should be 100% valid');
  assert.strictEqual(result.summary.errors, 0, 'Should have 0 errors');
  assert.strictEqual(result.score >= 90, true, 'Score should be in A+ range');
  assert.strictEqual(result.stats.tableCount >= 5, true, 'Should detect tables');
  assert.strictEqual(result.manifestType, 'pyproject.toml (PEP 518/621)');
});

test('TOML Parser: parses valid Cargo workspace manifest', () => {
  const auditor = new TomlAuditor();
  const result = auditor.audit(Presets.CARGO_WORKSPACE);

  assert.strictEqual(result.isValid, true, 'Cargo manifest should be valid');
  assert.strictEqual(result.summary.errors, 0, 'Should have 0 errors');
  assert.strictEqual(result.manifestType, 'Cargo.toml (Rust)');
});

test('Duplicate Detection: catches duplicate keys and duplicate table headers', () => {
  const auditor = new TomlAuditor();
  const result = auditor.audit(Presets.BROKEN_DUPLICATES);

  assert.strictEqual(result.isValid, false, 'Broken TOML should fail validation');
  assert.strictEqual(result.summary.errors > 0, true, 'Should find multiple errors');

  // Verify TOML001 (Duplicate key)
  const dupKey = result.issues.find(i => i.id === 'TOML001');
  assert.ok(dupKey, 'Should detect TOML001 duplicate key');
  assert.match(dupKey.message, /duplicate key 'port'/i);

  // Verify TOML002 (Duplicate table header)
  const dupTable = result.issues.find(i => i.id === 'TOML002');
  assert.ok(dupTable, 'Should detect TOML002 duplicate table header');
  assert.match(dupTable.message, /duplicate table header '\[database\]'/i);

  // Verify Syntax Errors
  const syntaxErr = result.issues.find(i => i.id === 'TOML003');
  assert.ok(syntaxErr, 'Should detect syntax errors');
});

test('Table Collision: flags conflict between standard table and array of tables', () => {
  const auditor = new TomlAuditor();
  const toml = `
[fruits]
name = "apple"

[[fruits]]
name = "banana"
`;
  const result = auditor.audit(toml);
  const collision = result.issues.find(i => i.id === 'TOML006');
  assert.ok(collision, 'Should detect TOML006 table-array-collision');
});

test('PEP 518/621: detects missing requires and invalid project names', () => {
  const auditor = new TomlAuditor();
  const invalidPep = `
[project]
name = "invalid_name_@"
version = "1.0.0"
`;
  const result = auditor.audit(invalidPep);
  const pep621Err = result.issues.find(i => i.id === 'PEP621');
  assert.ok(pep621Err, 'Should flag invalid PEP 621 project name');
});

test('Canonical Sorter: reorganizes pyproject sections in canonical order', () => {
  const auditor = new TomlAuditor();
  const sorted = auditor.sortAndFormat(Presets.UNSORTED_MESSY, 'pyproject');

  // [build-system] must appear before [project], which must appear before [tool.*]
  const buildSysIdx = sorted.indexOf('[build-system]');
  const projIdx = sorted.indexOf('[project]');
  const ruffIdx = sorted.indexOf('[tool.ruff]');

  assert.strictEqual(buildSysIdx !== -1, true, '[build-system] should be present');
  assert.strictEqual(projIdx !== -1, true, '[project] should be present');
  assert.strictEqual(ruffIdx !== -1, true, '[tool.ruff] should be present');

  assert.strictEqual(buildSysIdx < projIdx, true, '[build-system] must precede [project]');
  assert.strictEqual(projIdx < ruffIdx, true, '[project] must precede [tool.*]');

  // Audit the sorted output
  const auditSorted = auditor.audit(sorted);
  const orderingIssue = auditSorted.issues.find(i => i.id === 'SORT001');
  assert.strictEqual(orderingIssue, undefined, 'Sorted output should have 0 ordering issues');
});
