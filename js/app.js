/**
 * TOML Doctor Application Logic
 */

(function () {
  'use strict';

  const auditor = new TomlAuditor();

  // Elements
  const editor = document.getElementById('toml-editor');
  const lineNumbers = document.getElementById('line-numbers');
  const editorStats = document.getElementById('editor-stats');
  const findingsContainer = document.getElementById('findings-container');
  const treeContainer = document.getElementById('tree-container');
  const filterBar = document.getElementById('filter-bar-container');
  const dropZone = document.getElementById('editor-drop-zone');
  const fileUpload = document.getElementById('file-upload');
  const toast = document.getElementById('toast-notice');

  // Score Elements
  const scoreValue = document.getElementById('score-value');
  const scoreGrade = document.getElementById('score-grade');
  const scoreCircle = document.getElementById('score-circle');
  const scoreTitle = document.getElementById('score-title');
  const scoreDescription = document.getElementById('score-description');

  // Metrics Elements
  const metricManifest = document.getElementById('metric-manifest');
  const metricManifestBadge = document.getElementById('metric-manifest-badge');
  const metricTables = document.getElementById('metric-tables');
  const metricTablesBadge = document.getElementById('metric-tables-badge');
  const metricKeys = document.getElementById('metric-keys');
  const metricKeysBadge = document.getElementById('metric-keys-badge');
  const metricOrdering = document.getElementById('metric-ordering');
  const metricOrderingBadge = document.getElementById('metric-ordering-badge');

  // Counts
  const countAll = document.getElementById('count-all');
  const countError = document.getElementById('count-error');
  const countWarning = document.getElementById('count-warning');
  const countInfo = document.getElementById('count-info');

  let currentAuditResult = null;
  let activeFilter = 'all';
  let activeTab = 'diagnostics';
  let debounceTimer = null;

  // Initialize
  function init() {
    setupEventListeners();
    loadPreset('PYPROJECT_STANDARD');
  }

  function setupEventListeners() {
    // Editor typing & scrolling
    editor.addEventListener('input', () => {
      updateLineNumbers();
      updateEditorStats();
      triggerAuditDebounced();
    });

    editor.addEventListener('scroll', () => {
      lineNumbers.scrollTop = editor.scrollTop;
    });

    // Preset buttons
    document.querySelectorAll('.btn-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const presetKey = btn.dataset.preset;
        loadPreset(presetKey);
      });
    });

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeTab = btn.dataset.tab;

        if (activeTab === 'diagnostics') {
          findingsContainer.style.display = 'flex';
          filterBar.style.display = 'flex';
          treeContainer.style.display = 'none';
        } else {
          findingsContainer.style.display = 'none';
          filterBar.style.display = 'none';
          treeContainer.style.display = 'flex';
          renderTree();
        }
      });
    });

    // Filter pills
    document.querySelectorAll('.filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeFilter = pill.dataset.filter;
        renderFindings();
      });
    });

    // Sort & Format Button
    document.getElementById('btn-sort-format').addEventListener('click', () => {
      if (!editor.value.trim()) return;
      const isCargo = editor.value.includes('[package]');
      const sorted = auditor.sortAndFormat(editor.value, isCargo ? 'cargo' : 'pyproject');
      editor.value = sorted;
      updateLineNumbers();
      updateEditorStats();
      runAudit();
      showToast('Document canonically sorted & formatted!');
    });

    // Clear Button
    document.getElementById('btn-clear').addEventListener('click', () => {
      editor.value = '';
      updateLineNumbers();
      updateEditorStats();
      runAudit();
      showToast('Editor cleared');
    });

    // Copy TOML
    document.getElementById('btn-copy-toml').addEventListener('click', () => {
      if (!editor.value.trim()) return;
      navigator.clipboard.writeText(editor.value).then(() => {
        showToast('TOML copied to clipboard!');
      });
    });

    // Export File (.toml download)
    document.getElementById('btn-export-file').addEventListener('click', () => {
      if (!editor.value.trim()) return;
      const blob = new Blob([editor.value], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = editor.value.includes('[package]') ? 'Cargo.toml' : (editor.value.includes('[project]') ? 'pyproject.toml' : 'config.toml');
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Downloaded clean TOML file!');
    });

    // File Upload via picker
    fileUpload.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) readFile(file);
    });

    // Drag and Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
      e.preventDefault();
      e.stopPropagation();
    }

    dropZone.addEventListener('dragover', () => {
      dropZone.style.boxShadow = 'inset 0 0 0 2px var(--border-highlight)';
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.style.boxShadow = 'none';
    });

    dropZone.addEventListener('drop', (e) => {
      dropZone.style.boxShadow = 'none';
      const dt = e.dataTransfer;
      const file = dt.files[0];
      if (file) readFile(file);
    });
  }

  function readFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      editor.value = e.target.result;
      updateLineNumbers();
      updateEditorStats();
      runAudit();
      showToast(`Loaded: ${file.name}`);
      document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
    };
    reader.readAsText(file);
  }

  function loadPreset(key) {
    if (TomlAuditorPresets[key]) {
      editor.value = TomlAuditorPresets[key].trim();
      updateLineNumbers();
      updateEditorStats();
      runAudit();
    }
  }

  function updateLineNumbers() {
    const lines = editor.value.split('\n').length;
    let numbersHtml = '';
    for (let i = 1; i <= Math.max(1, lines); i++) {
      numbersHtml += `${i}\n`;
    }
    lineNumbers.textContent = numbersHtml;
  }

  function updateEditorStats() {
    const text = editor.value;
    const lines = text.length > 0 ? text.split('\n').length : 0;
    const chars = text.length;
    editorStats.textContent = `Lines: ${lines} · Chars: ${chars}`;
  }

  function triggerAuditDebounced() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      runAudit();
    }, 200);
  }

  function runAudit() {
    const tomlContent = editor.value;
    currentAuditResult = auditor.audit(tomlContent);

    updateScoreDisplay(currentAuditResult);
    updateMetrics(currentAuditResult);
    updateFilterCounts(currentAuditResult);
    renderFindings();
    if (activeTab === 'tree') {
      renderTree();
    }
  }

  function updateScoreDisplay(result) {
    const score = result.score;
    const grade = result.grade;
    scoreValue.textContent = score;
    scoreGrade.textContent = grade;

    let scoreColor = '#3fb950'; // green
    if (score < 50) scoreColor = '#f85149'; // red
    else if (score < 70) scoreColor = '#d29922'; // yellow
    else if (score < 90) scoreColor = '#58a6ff'; // blue

    scoreCircle.style.setProperty('--score-pct', score);
    scoreCircle.style.setProperty('--score-color', scoreColor);

    scoreTitle.textContent = `${grade} — ${result.ratingLabel}`;
    scoreDescription.textContent = score === 100 ?
      'All syntax, duplicate, and PEP/Cargo schema requirements satisfied!' :
      `Identified ${result.summary.total} findings (${result.summary.errors} errors, ${result.summary.warnings} warnings).`;
  }

  function updateMetrics(result) {
    const stats = result.stats;

    // Manifest type
    metricManifest.textContent = result.manifestType.split(' ')[0];
    metricManifestBadge.textContent = result.manifestType;

    // Table count
    metricTables.textContent = stats.tableCount;
    const hasDupTables = result.issues.some(i => i.id === 'TOML002' || i.id === 'TOML006');
    if (hasDupTables) {
      metricTablesBadge.textContent = 'Collision Detected';
      metricTablesBadge.style.background = 'rgba(248, 81, 73, 0.15)';
      metricTablesBadge.style.color = '#f85149';
    } else {
      metricTablesBadge.textContent = 'No Collisions';
      metricTablesBadge.style.background = 'rgba(63, 185, 80, 0.15)';
      metricTablesBadge.style.color = '#3fb950';
    }

    // Key count
    metricKeys.textContent = stats.keyCount;
    const hasDupKeys = result.issues.some(i => i.id === 'TOML001');
    if (hasDupKeys) {
      metricKeysBadge.textContent = 'Duplicate Keys';
      metricKeysBadge.style.background = 'rgba(248, 81, 73, 0.15)';
      metricKeysBadge.style.color = '#f85149';
    } else {
      metricKeysBadge.textContent = 'Unique';
      metricKeysBadge.style.background = 'rgba(63, 185, 80, 0.15)';
      metricKeysBadge.style.color = '#3fb950';
    }

    // Ordering
    const hasOrderingIssues = result.issues.some(i => i.id === 'SORT001');
    if (hasOrderingIssues) {
      metricOrdering.textContent = 'Unsorted';
      metricOrderingBadge.textContent = 'Sort Required';
      metricOrderingBadge.style.background = 'rgba(210, 153, 34, 0.15)';
      metricOrderingBadge.style.color = '#d29922';
    } else {
      metricOrdering.textContent = 'Canonical';
      metricOrderingBadge.textContent = 'Standard';
      metricOrderingBadge.style.background = 'rgba(63, 185, 80, 0.15)';
      metricOrderingBadge.style.color = '#3fb950';
    }
  }

  function updateFilterCounts(result) {
    countAll.textContent = result.summary.total;
    countError.textContent = result.summary.errors;
    countWarning.textContent = result.summary.warnings;
    countInfo.textContent = result.summary.info;
  }

  function renderFindings() {
    findingsContainer.innerHTML = '';
    if (!currentAuditResult) return;

    let filtered = currentAuditResult.issues;
    if (activeFilter !== 'all') {
      filtered = filtered.filter(i => i.severity === activeFilter);
    }

    if (filtered.length === 0) {
      if (currentAuditResult.issues.length === 0) {
        findingsContainer.innerHTML = `
          <div class="clean-posture-card">
            <div class="clean-icon">✓</div>
            <div class="clean-title">100% Valid & Compliant TOML Document</div>
            <div class="clean-text">
              Zero syntax errors, zero duplicate key/table collisions, and fully standardized schema ordering.
            </div>
          </div>
        `;
      } else {
        findingsContainer.innerHTML = `
          <div style="text-align: center; color: var(--text-muted); padding: 2.5rem 1rem;">
            No issues match the selected filter '${activeFilter}'.
          </div>
        `;
      }
      return;
    }

    filtered.forEach(issue => {
      const card = document.createElement('div');
      card.className = `finding-card ${issue.severity}`;

      card.innerHTML = `
        <div class="finding-header">
          <div class="finding-tags">
            <span class="badge-id">${issue.id}</span>
            <span class="badge-severity ${issue.severity}">${issue.severity}</span>
            <span class="badge-category">${issue.category}</span>
          </div>
          <button class="badge-line" data-line="${issue.line}" title="Jump to line ${issue.line}">
            Line ${issue.line}
          </button>
        </div>
        <div class="finding-message">${escapeHtml(issue.message)}</div>
        <div class="finding-recommendation"><strong>Recommendation:</strong> ${escapeHtml(issue.recommendation)}</div>
      `;

      findingsContainer.appendChild(card);
    });

    // Attach click events to line badges
    findingsContainer.querySelectorAll('.badge-line').forEach(btn => {
      btn.addEventListener('click', () => {
        const line = parseInt(btn.dataset.line, 10);
        highlightEditorLine(line);
      });
    });
  }

  function renderTree() {
    treeContainer.innerHTML = '';
    if (!currentAuditResult || !currentAuditResult.sections) return;

    const sections = currentAuditResult.sections;

    if (sections.length === 0) {
      treeContainer.innerHTML = '<div style="color:var(--text-muted);">No tables or keys found.</div>';
      return;
    }

    sections.forEach(sec => {
      const node = document.createElement('div');
      node.className = 'tree-node';

      const header = document.createElement('div');
      header.className = 'tree-table-header';
      header.innerHTML = sec.name ?
        `<span>📁 ${sec.isArrayOfTables ? `[[${sec.name}]]` : `[${sec.name}]`}</span>` :
        `<span>🌐 (root table)</span>`;

      node.appendChild(header);

      if (sec.entries.length === 0) {
        const empty = document.createElement('div');
        empty.style.color = 'var(--text-muted)';
        empty.style.fontSize = '0.75rem';
        empty.textContent = '(no key-value pairs)';
        node.appendChild(empty);
      } else {
        sec.entries.forEach(e => {
          const item = document.createElement('div');
          item.className = 'tree-key-item';
          item.innerHTML = `
            <span class="tree-key-name">${escapeHtml(e.key)}:</span>
            <span class="tree-key-val" title="${escapeAttr(e.value)}">${escapeHtml(e.value)}</span>
          `;
          node.appendChild(item);
        });
      }

      treeContainer.appendChild(node);
    });
  }

  function highlightEditorLine(lineNumber) {
    const text = editor.value;
    const lines = text.split('\n');
    let charStart = 0;

    for (let i = 0; i < lineNumber - 1 && i < lines.length; i++) {
      charStart += lines[i].length + 1;
    }

    const lineLength = lines[lineNumber - 1] ? lines[lineNumber - 1].length : 0;
    const charEnd = charStart + lineLength;

    editor.focus();
    editor.setSelectionRange(charStart, charEnd);

    const approxLineHeight = 22;
    editor.scrollTop = Math.max(0, (lineNumber - 5) * approxLineHeight);
    lineNumbers.scrollTop = editor.scrollTop;
  }

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 2400);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, function (m) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      }[m];
    });
  }

  function escapeAttr(str) {
    if (!str) return '';
    return str.replace(/"/g, '&quot;');
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
