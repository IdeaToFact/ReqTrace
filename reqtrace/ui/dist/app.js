// Copyright (C) 2026 Idea To Fact LLC
// SPDX-License-Identifier: AGPL-3.0-only

// ReqTrace UI Client Application v0.2.0
// Complies strictly with CSP (no inline scripts, no inline styles, no external network calls)

let matrixData = [];
let summaryData = null;
let currentPathLine = "";
let currentReviewContext = null;

document.addEventListener('DOMContentLoaded', () => {
  init();
});

async function init() {
  wireUIEvents();
  wireWorkspaceEvents();
  wireIngestionEvents();
  wireReviewModalEvents();
  await loadCurrentWorkspace();
  await loadSummary();
  await loadMatrixData();
  await updateCandidateBadge();
}

function showSessionAlert(message) {
  const alertEl = document.getElementById('session-alert');
  const alertMsg = document.getElementById('session-alert-msg');
  if (alertEl && alertMsg) {
    alertMsg.innerText = message;
    alertEl.classList.add('open');
  }
}

// --- Tab Navigation ---
function wireUIEvents() {
  const tabMatrix = document.getElementById('tab-matrix');
  const tabCandidates = document.getElementById('tab-candidates');
  const viewMatrix = document.getElementById('view-matrix');
  const viewCandidates = document.getElementById('view-candidates');

  if (tabMatrix && tabCandidates) {
    tabMatrix.addEventListener('click', () => {
      tabMatrix.classList.add('active');
      tabCandidates.classList.remove('active');
      viewMatrix.classList.remove('hidden');
      viewCandidates.classList.add('hidden');
    });

    tabCandidates.addEventListener('click', async () => {
      tabCandidates.classList.add('active');
      tabMatrix.classList.remove('active');
      viewCandidates.classList.remove('hidden');
      viewMatrix.classList.add('hidden');
      await loadCandidateQueue();
    });
  }

  // Search and Filter controls
  const searchBox = document.getElementById('search-box');
  const statusFilter = document.getElementById('status-filter');
  const methodFilter = document.getElementById('method-filter');
  const levelFilter = document.getElementById('level-filter');
  const btnRefresh = document.getElementById('btn-refresh');

  if (searchBox) searchBox.addEventListener('input', () => renderTable());
  if (statusFilter) statusFilter.addEventListener('change', () => renderTable());
  if (methodFilter) methodFilter.addEventListener('change', () => renderTable());
  if (levelFilter) levelFilter.addEventListener('change', () => renderTable());
  if (btnRefresh) {
    btnRefresh.addEventListener('click', async () => {
      await loadSummary();
      await loadMatrixData();
      await updateCandidateBadge();
    });
  }

  // Header actions
  const btnPrint = document.getElementById('btn-print');
  const btnAbout = document.getElementById('btn-about');
  const btnCloseAbout = document.getElementById('btn-close-about');
  const aboutModal = document.getElementById('about-modal');

  if (btnPrint) {
    btnPrint.addEventListener('click', () => {
      window.open('/print', '_blank');
    });
  }

  if (btnAbout && aboutModal) {
    btnAbout.addEventListener('click', () => aboutModal.classList.add('open'));
  }
  if (btnCloseAbout && aboutModal) {
    btnCloseAbout.addEventListener('click', () => aboutModal.classList.remove('open'));
  }
  if (aboutModal) {
    aboutModal.addEventListener('click', (e) => {
      if (e.target === aboutModal) aboutModal.classList.remove('open');
    });
  }

  // Export dropdown
  const btnExport = document.getElementById('btn-export-dropdown');
  const exportMenu = document.getElementById('export-menu');
  if (btnExport && exportMenu) {
    btnExport.addEventListener('click', (e) => {
      e.stopPropagation();
      exportMenu.classList.toggle('open');
    });
    document.addEventListener('click', () => exportMenu.classList.remove('open'));
  }

  // Drawer actions
  const btnCloseDrawer = document.getElementById('btn-close-drawer');
  const drawerOverlay = document.getElementById('drawer-overlay');
  if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', closeDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);

  // Delegated click listener for dynamic table buttons ("Inspect Evidence" & "Sign Off")
  const tableBody = document.getElementById('matrix-tbody');
  if (tableBody) {
    tableBody.addEventListener('click', (e) => {
      const target = e.target;
      if (!target) return;

      if (target.classList.contains('inspect-btn')) {
        const reqId = target.getAttribute('data-req-id');
        const testId = target.getAttribute('data-test-id');
        if (reqId) openDrawer(reqId, testId);
      } else if (target.classList.contains('btn-signoff')) {
        const reqId = target.getAttribute('data-req-id');
        const reqTitle = target.getAttribute('data-req-title') || reqId;
        const testId = target.getAttribute('data-test-id') || null;
        openReviewModal(reqId, reqTitle, testId);
      }
    });
  }

  // Hotkey focus guard (WCAG 2.1.4): '/' focuses search box
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== searchBox) {
      if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
      e.preventDefault();
      searchBox.focus();
    }
  });
}

// --- Workspace Lifecycle Manager ---
function wireWorkspaceEvents() {
  const btnPicker = document.getElementById('btn-workspace-picker');
  const modal = document.getElementById('workspace-modal');
  const btnClose = document.getElementById('btn-close-ws-modal');
  const btnOpen = document.getElementById('btn-submit-open-ws');
  const btnInit = document.getElementById('btn-submit-init-ws');

  if (btnPicker && modal) {
    btnPicker.addEventListener('click', async () => {
      await loadRecentWorkspaces();
      modal.classList.add('open');
    });
  }

  if (btnClose && modal) {
    btnClose.addEventListener('click', () => modal.classList.remove('open'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });
  }

  if (btnOpen) {
    btnOpen.addEventListener('click', async () => {
      const pathInput = document.getElementById('input-open-path');
      const targetPath = pathInput ? pathInput.value.trim() : '';
      if (!targetPath) return alert('Please enter a directory path.');

      try {
        const res = await fetch('/api/v1/workspaces/open', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: targetPath }),
        });
        if (!res.ok) {
          const err = await res.json();
          return alert(err.detail || 'Failed to open directory.');
        }
        modal.classList.remove('open');
        await loadCurrentWorkspace();
        await loadSummary();
        await loadMatrixData();
        await updateCandidateBadge();
      } catch (e) {
        alert('Network error opening workspace: ' + e.message);
      }
    });
  }

  if (btnInit) {
    btnInit.addEventListener('click', async () => {
      const pathInput = document.getElementById('input-init-path');
      const nameInput = document.getElementById('input-init-name');
      const stdSelect = document.getElementById('select-init-standard');

      const targetPath = pathInput ? pathInput.value.trim() : '';
      const projName = nameInput ? nameInput.value.trim() : '';
      const standard = stdSelect ? stdSelect.value : 'DO-178C DAL B';

      if (!targetPath) return alert('Target directory path is required.');
      if (!projName) return alert('Project friendly name is required.');

      try {
        const res = await fetch('/api/v1/workspaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: targetPath, project_name: projName, target_standard: standard }),
        });
        if (!res.ok) {
          const err = await res.json();
          return alert(err.detail || 'Initialization failed.');
        }
        modal.classList.remove('open');
        await loadCurrentWorkspace();
        await loadSummary();
        await loadMatrixData();
        await updateCandidateBadge();
      } catch (e) {
        alert('Error initializing workspace: ' + e.message);
      }
    });
  }
}

async function loadCurrentWorkspace() {
  try {
    const res = await fetch('/api/v1/workspace/current');
    if (!res.ok) return;
    const data = await res.json();

    const nameEl = document.getElementById('ws-display-name');
    const pathEl = document.getElementById('modal-ws-path');
    const projEl = document.getElementById('modal-ws-project');
    const stdEl = document.getElementById('modal-ws-standard');
    const baseEl = document.getElementById('modal-ws-baseline');

    const displayName = `${data.project.project_name} (${data.project.baseline_id || 'CURRENT'})`;
    if (nameEl) nameEl.textContent = displayName;
    if (pathEl) pathEl.textContent = data.workspace;
    if (projEl) projEl.textContent = data.project.project_name;
    if (stdEl) stdEl.textContent = data.project.target_standard || 'DO-178C';
    if (baseEl) baseEl.textContent = data.project.baseline_id || 'CURRENT';
  } catch (e) {
    console.error('Failed to load current workspace', e);
  }
}

async function loadRecentWorkspaces() {
  const listEl = document.getElementById('recent-workspaces-list');
  if (!listEl) return;
  try {
    const res = await fetch('/api/v1/workspaces');
    if (!res.ok) return;
    const workspaces = await res.json();
    if (!workspaces || workspaces.length === 0) {
      listEl.innerHTML = '<li class="text-muted-sm">No recent workspaces registered.</li>';
      return;
    }

    listEl.innerHTML = workspaces.map(w => `
      <li class="recent-item" data-path="${escapeHtml(w.path)}">
        <div>
          <div class="recent-name">${escapeHtml(w.name)}</div>
          <div class="recent-path">${escapeHtml(w.path)}</div>
        </div>
        <span class="badge badge-system">${escapeHtml(w.target_standard || 'DO-178C')}</span>
      </li>
    `).join('');

    // Attach click handlers
    listEl.querySelectorAll('.recent-item').forEach(item => {
      item.addEventListener('click', async () => {
        const path = item.getAttribute('data-path');
        if (path) {
          const res = await fetch('/api/v1/workspaces/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
          });
          if (res.ok) {
            document.getElementById('workspace-modal').classList.remove('open');
            await loadCurrentWorkspace();
            await loadSummary();
            await loadMatrixData();
            await updateCandidateBadge();
          }
        }
      });
    });
  } catch (e) {
    listEl.innerHTML = '<li class="text-muted-sm">Error loading recent workspaces.</li>';
  }
}

// --- Ingestion Dropzone Wizard ---
function wireIngestionEvents() {
  const btnModal = document.getElementById('btn-import-modal');
  const modal = document.getElementById('ingest-modal');
  const btnClose = document.getElementById('btn-close-ingest-modal');

  if (btnModal && modal) {
    btnModal.addEventListener('click', () => modal.classList.add('open'));
  }
  if (btnClose && modal) {
    btnClose.addEventListener('click', () => modal.classList.remove('open'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });
  }

  setupDropzone('dropzone-spec', 'file-input-spec', '/api/v1/ingest/spec', 'spec-upload-status');
  setupDropzone('dropzone-tests', 'file-input-tests', '/api/v1/ingest/tests', 'tests-upload-status');
}

function setupDropzone(boxId, inputId, endpoint, statusId) {
  const box = document.getElementById(boxId);
  const input = document.getElementById(inputId);
  const statusEl = document.getElementById(statusId);
  const feedbackEl = document.getElementById('ingest-feedback');

  if (!box || !input) return;

  box.addEventListener('click', () => input.click());

  ['dragenter', 'dragover'].forEach(name => {
    box.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      box.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    box.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      box.classList.remove('dragover');
    });
  });

  box.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) uploadFile(files[0], endpoint, statusEl, feedbackEl);
  });

  input.addEventListener('change', () => {
    if (input.files && input.files.length > 0) {
      const selected = input.files[0];
      input.value = '';
      uploadFile(selected, endpoint, statusEl, feedbackEl);
    }
  });
}

async function uploadFile(file, endpoint, statusEl, feedbackEl) {
  if (statusEl) statusEl.innerHTML = `Uploading <code>${escapeHtml(file.name)}</code> (${Math.round(file.size / 1024)} KB)...`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      body: formData,
    });

    const rawText = await res.text();
    let data = {};
    try {
      data = rawText ? JSON.parse(rawText) : {};
    } catch {
      data = { detail: rawText || res.statusText || 'Unexpected server response.' };
    }

    if (!res.ok) {
      if (statusEl) statusEl.textContent = '❌ Upload rejected';
      if (feedbackEl) {
        feedbackEl.className = 'ingest-feedback error';
        feedbackEl.textContent = data.detail || `Ingestion rejected (HTTP ${res.status}).`;
      }
      return;
    }

    if (statusEl) statusEl.textContent = '✅ Ingested successfully';
    if (feedbackEl) {
      feedbackEl.className = 'ingest-feedback success';
      if (data.total_requirements !== undefined) {
        feedbackEl.textContent = `Parsed ${data.total_requirements} requirements (${data.normative_requirements} normative). Matrix refreshed.`;
      } else if (data.attached_verdicts !== undefined) {
        feedbackEl.textContent = `Attached ${data.attached_verdicts} JUnit execution verdicts across ${data.total_tests} test artifacts. Matrix refreshed.`;
      } else {
        feedbackEl.textContent = `Parsed ${data.total_tests} test artifacts. Trace links updated.`;
      }
    }

    // Refresh application state
    await loadSummary();
    await loadMatrixData();
    await updateCandidateBadge();
  } catch (e) {
    if (statusEl) statusEl.textContent = '❌ Network error';
    if (feedbackEl) {
      feedbackEl.className = 'ingest-feedback error';
      feedbackEl.textContent = 'Network error uploading file: ' + e.message;
    }
  }
}

// --- Candidate Review Queue ---
async function updateCandidateBadge() {
  try {
    const res = await fetch('/api/v1/candidates');
    if (!res.ok) return;
    const candidates = await res.json();
    const count = candidates ? candidates.length : 0;
    const badge = document.getElementById('cand-badge');
    const totalEl = document.getElementById('queue-total');
    if (badge) badge.textContent = count;
    if (totalEl) totalEl.textContent = count;
  } catch (e) {}
}

async function loadCandidateQueue() {
  const container = document.getElementById('candidates-container');
  if (!container) return;

  try {
    const res = await fetch('/api/v1/candidates');
    if (!res.ok) return;
    const candidates = await res.json();
    await updateCandidateBadge();

    if (!candidates || candidates.length === 0) {
      container.innerHTML = '<div class="card-empty">No candidate links pending human review.</div>';
      return;
    }

    container.innerHTML = candidates.map(c => `
      <div class="candidate-card" id="cand-card-${escapeHtml(c.req_id)}">
        <div class="candidate-header">
          <div>
            <strong>${escapeHtml(c.req_id)}</strong>: ${escapeHtml(c.req_title || 'Normative Requirement')}
          </div>
          <span class="candidate-provenance">${Math.round(c.confidence_score * 100)}% Match &bull; ${escapeHtml(c.match_strategy || 'heuristic')}</span>
        </div>
        <div class="candidate-body">
          <div class="candidate-col">
            <h4>Requirement Evidence Target</h4>
            <p class="text-muted-sm">${escapeHtml(c.justification || 'Candidate link proposed via semantic similarity window.')}</p>
          </div>
          <div class="candidate-col">
            <h4>Matched Test Artifact</h4>
            <code>${escapeHtml(c.test_id)}</code>
            <p class="text-muted-xs" style="margin-top:0.4rem;">File: <code>${escapeHtml(c.test_file)}</code></p>
            <div class="evidence-box" style="margin-top:0.4rem;">
              <code>${escapeHtml(c.evidence_span || 'assert evidence')}</code>
            </div>
          </div>
        </div>
        <div class="candidate-actions">
          <button class="btn-reject cand-reject-btn" data-req-id="${escapeHtml(c.req_id)}" data-test-id="${escapeHtml(c.test_id)}">
            🔴 Reject Candidate
          </button>
          <button class="btn-approve cand-approve-btn" data-req-id="${escapeHtml(c.req_id)}" data-test-id="${escapeHtml(c.test_id)}">
            🟢 Approve Verification Link
          </button>
        </div>
      </div>
    `).join('');

    // Attach actions
    container.querySelectorAll('.cand-approve-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const reqId = btn.getAttribute('data-req-id');
        const testId = btn.getAttribute('data-test-id');
        await submitCandidateAction('approve', reqId, testId);
      });
    });

    container.querySelectorAll('.cand-reject-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const reqId = btn.getAttribute('data-req-id');
        const testId = btn.getAttribute('data-test-id');
        const reason = prompt('Please enter the reason for rejecting this candidate link:');
        if (reason) {
          await submitCandidateAction('reject', reqId, testId, reason);
        }
      });
    });
  } catch (e) {
    container.innerHTML = '<div class="card-empty">Error loading candidate queue.</div>';
  }
}

async function submitCandidateAction(action, reqId, testId, comment = '') {
  try {
    const res = await fetch('/api/v1/candidates/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, req_id: reqId, test_id: testId, comment }),
    });
    if (!res.ok) {
      const err = await res.json();
      return alert(err.detail || 'Action failed.');
    }
    await loadCandidateQueue();
    await loadSummary();
    await loadMatrixData();
  } catch (e) {
    alert('Error submitting action: ' + e.message);
  }
}

// --- Review Sign-Off Modal ---
function wireReviewModalEvents() {
  const modal = document.getElementById('review-modal');
  const btnClose = document.getElementById('btn-close-review-modal');
  const btnCancel = document.getElementById('btn-cancel-review');
  const btnSubmit = document.getElementById('btn-submit-review');

  if (btnClose && modal) btnClose.addEventListener('click', () => modal.classList.remove('open'));
  if (btnCancel && modal) btnCancel.addEventListener('click', () => modal.classList.remove('open'));

  // Toggle mandatory fields on radio change
  const radios = document.querySelectorAll('input[name="review-decision"]');
  const groupRefDoc = document.getElementById('group-review-ref-doc');
  radios.forEach(r => {
    r.addEventListener('change', () => {
      if (groupRefDoc) {
        if (r.value === 'waived_analysis') {
          groupRefDoc.classList.remove('hidden');
        } else {
          groupRefDoc.classList.add('hidden');
        }
      }
    });
  });

  if (btnSubmit) {
    btnSubmit.addEventListener('click', async () => {
      if (!currentReviewContext) return;
      const decision = document.querySelector('input[name="review-decision"]:checked').value;
      const reviewer = document.getElementById('review-input-name').value.trim() || 'Local Engineer';
      const comment = document.getElementById('review-input-comment').value.trim();
      const refDoc = document.getElementById('review-input-ref-doc').value.trim();

      if (decision === 'rejected' && (!comment || comment.length < 5)) {
        return alert('A rejection comment (minimum 5 characters) is mandatory.');
      }
      if (decision === 'waived_analysis' && !refDoc) {
        return alert('A reference document identifier is mandatory when waiving verification via non-test analysis.');
      }

      try {
        const res = await fetch('/api/v1/reviews', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            req_id: currentReviewContext.reqId,
            test_id: currentReviewContext.testId,
            status: decision,
            reviewer,
            comment,
            reference_doc: refDoc || null,
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          return alert(err.detail || 'Sign-off submission failed.');
        }

        modal.classList.remove('open');
        await loadSummary();
        await loadMatrixData();
        await updateCandidateBadge();
      } catch (e) {
        alert('Error recording review: ' + e.message);
      }
    });
  }

  // Keyboard shortcut guard (WCAG 2.1.4): a, r, w select decisions only when not in inputs
  document.addEventListener('keydown', (e) => {
    if (!modal.classList.contains('open')) return;
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

    if (e.key === 'a' || e.key === 'A') {
      const radio = document.querySelector('input[name="review-decision"][value="approved"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    } else if (e.key === 'r' || e.key === 'R') {
      const radio = document.querySelector('input[name="review-decision"][value="rejected"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    } else if (e.key === 'w' || e.key === 'W') {
      const radio = document.querySelector('input[name="review-decision"][value="waived_analysis"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    }
  });
}

function openReviewModal(reqId, reqTitle, testId) {
  currentReviewContext = { reqId, reqTitle, testId };
  const modal = document.getElementById('review-modal');
  const reqIdEl = document.getElementById('review-modal-req-id');
  const reqTitleEl = document.getElementById('review-modal-req-title');
  const testIdEl = document.getElementById('review-modal-test-id');
  const testGroup = document.getElementById('review-modal-test-group');

  if (reqIdEl) reqIdEl.textContent = reqId;
  if (reqTitleEl) reqTitleEl.textContent = reqTitle;
  if (testIdEl) {
    if (testId) {
      testIdEl.textContent = testId;
      testGroup.classList.remove('hidden');
    } else {
      testGroup.classList.add('hidden');
    }
  }

  if (modal) modal.classList.add('open');
}

// --- Data Fetching & Rendering ---

async function loadSummary() {
  try {
    const res = await fetch('/api/v1/summary');
    if (!res.ok) {
      if (res.status === 401) showSessionAlert('Unauthorized: Please launch through `reqtrace ui`');
      return;
    }
    summaryData = await res.json();
    renderKPIs(summaryData);
    renderReasonPills(summaryData);
  } catch (e) {
    console.error('Failed to load summary', e);
  }
}

async function loadMatrixData() {
  try {
    const res = await fetch('/api/v1/matrix');
    if (!res.ok) return;
    const json = await res.json();
    matrixData = json.items || [];
    renderTable();
  } catch (e) {
    console.error('Failed to load matrix data', e);
  }
}

function renderKPIs(data) {
  if (!data) return;
  setText('kpi-verified', data.verified_count);
  setText('kpi-passing', data.linked_passing_count);
  setText('kpi-gaps', data.unverified_gaps);
  setText('kpi-cov-verified', `${data.audit_verified_coverage_pct}%`);
  setText('kpi-cov-eng', `${data.engineering_pass_coverage_pct}%`);
  setText('kpi-rogue', data.rogue_tests_unlinked);
}

function renderReasonPills(data) {
  const container = document.getElementById('reason-pills-list');
  const totalGapsEl = document.getElementById('reasons-total');
  if (!container || !data) return;

  if (totalGapsEl) totalGapsEl.innerText = data.unverified_gaps;
  container.innerHTML = '';

  const reasons = data.gap_reasons || {};
  const reasonKeys = Object.keys(reasons);

  if (reasonKeys.length === 0) {
    container.innerHTML = '<span class="text-muted-xs">Zero unverified gaps. Full audit coverage achieved.</span>';
    return;
  }

  reasonKeys.forEach(reason => {
    const count = reasons[reason];
    if (count > 0) {
      const pill = document.createElement('div');
      pill.className = 'reason-pill';
      pill.innerHTML = `<span class="pill-title">${formatReason(reason)}</span><span class="pill-count">${count}</span>`;
      pill.addEventListener('click', () => {
        const searchBox = document.getElementById('search-box');
        if (searchBox) {
          searchBox.value = reason;
          renderTable();
        }
      });
      container.appendChild(pill);
    }
  });
}

function renderTable() {
  const tbody = document.getElementById('matrix-tbody');
  if (!tbody) return;

  const searchBox = document.getElementById('search-box');
  const statusFilter = document.getElementById('status-filter');
  const methodFilter = document.getElementById('method-filter');
  const levelFilter = document.getElementById('level-filter');

  const searchTerm = searchBox ? searchBox.value.toLowerCase().trim() : '';
  const statusVal = statusFilter ? statusFilter.value : '';
  const methodVal = methodFilter ? methodFilter.value : '';
  const levelVal = levelFilter ? levelFilter.value : '';

  const filtered = matrixData.filter(item => {
    if (statusVal && item.verification_status !== statusVal) return false;
    if (methodVal && item.verification_method !== methodVal) return false;
    if (levelVal && item.level !== levelVal) return false;

    if (searchTerm) {
      const idMatch = item.id.toLowerCase().includes(searchTerm);
      const titleMatch = item.title.toLowerCase().includes(searchTerm);
      const reasonMatch = item.all_reasons && item.all_reasons.some(r => r.toLowerCase().includes(searchTerm));
      const testMatch = item.linked_tests && item.linked_tests.some(t => t.test_id.toLowerCase().includes(searchTerm));
      if (!idMatch && !titleMatch && !reasonMatch && !testMatch) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="table-placeholder">No matching requirements found.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(req => {
    const statusBadge = getStatusBadge(req.verification_status);
    const reasonText = req.primary_reason ? formatReason(req.primary_reason) : '—';
    const firstTest = req.linked_tests && req.linked_tests.length > 0 ? req.linked_tests[0] : null;

    let evidenceSnippet = '—';
    if (firstTest) {
      evidenceSnippet = `<button class="inspect-btn" data-req-id="${escapeHtml(req.id)}" data-test-id="${escapeHtml(firstTest.test_id)}">🔍 Inspect Evidence</button>`;
    }

    return `
      <tr>
        <td><strong>${escapeHtml(req.id)}</strong></td>
        <td>
          <div style="font-weight: 600;">${escapeHtml(req.title)}</div>
          <div class="text-muted-xs" style="margin-top: 0.2rem;">${escapeHtml(req.description)}</div>
        </td>
        <td><span class="badge badge-system">${escapeHtml(req.verification_method)}</span></td>
        <td><span class="badge badge-system">${escapeHtml(req.level)}</span></td>
        <td>${statusBadge}</td>
        <td><span class="text-muted-xs">${escapeHtml(reasonText)}</span></td>
        <td>${evidenceSnippet}</td>
        <td>
          <button class="btn-signoff" data-req-id="${escapeHtml(req.id)}" data-req-title="${escapeHtml(req.title)}" data-test-id="${firstTest ? escapeHtml(firstTest.test_id) : ''}">
            ✍️ Sign Off
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// --- Evidence Drawer ---

async function openDrawer(reqId, testId) {
  const drawer = document.getElementById('drawer');
  const overlay = document.getElementById('drawer-overlay');
  const content = document.getElementById('drawer-content');
  const reqTitleEl = document.getElementById('drawer-req-id');

  if (!drawer || !overlay || !content) return;

  if (reqTitleEl) reqTitleEl.innerText = `${reqId} - Evidence Inspector`;
  content.innerHTML = '<div class="table-placeholder">Fetching Grounded AST Evidence...</div>';

  drawer.classList.add('open');
  overlay.classList.add('open');

  try {
    const url = testId ? `/api/v1/evidence/${reqId}?test_id=${encodeURIComponent(testId)}` : `/api/v1/evidence/${reqId}`;
    const res = await fetch(url);
    if (!res.ok) {
      content.innerHTML = '<div class="table-placeholder">Failed to load evidence details.</div>';
      return;
    }

    const data = await res.json();
    currentPathLine = data.path_line || '';

    const req = data.req;
    const test = data.test;
    const link = data.link;

    let testHtml = '<p class="text-muted-sm">No linked test execution grounded for this requirement.</p>';
    if (test) {
      testHtml = `
        <div class="drawer-test-header">
          <div>
            <strong>${escapeHtml(test.id)}</strong>
            <div class="text-muted-xs">${escapeHtml(test.file_path)} (Lines ${test.line_start}-${test.line_end})</div>
          </div>
          <button id="btn-copy-path" class="copy-btn">📋 Copy Path:Line</button>
        </div>
        <div class="evidence-box">
          <code>${escapeHtml(link.evidence_span || '// No affirmative assertions captured')}</code>
        </div>
        <div class="drawer-meta-badges">
          <span class="badge ${test.execution_status === 'passed' ? 'badge-verified' : 'badge-gap'}">Verdict: ${escapeHtml(test.execution_status)}</span>
          <span class="badge badge-system">Confidence: ${escapeHtml(link.confidence)} (${link.confidence_score})</span>
          ${link.match_strategy ? `<span class="badge badge-system">Strategy: ${escapeHtml(link.match_strategy)}</span>` : ''}
        </div>
      `;
    }

    content.innerHTML = `
      <div class="drawer-section">
        <h3>Normative Requirement Statement</h3>
        <p><strong>${escapeHtml(req.title)}</strong></p>
        <p class="text-muted-sm">${escapeHtml(req.description)}</p>
        <div class="drawer-meta-badges">
          <span class="badge badge-system">${escapeHtml(req.verification_method)}</span>
          <span class="badge badge-system">${escapeHtml(req.level)}</span>
          <span class="badge badge-system">${req.is_normative ? 'Normative' : 'Informative'}</span>
        </div>
      </div>

      <div class="drawer-section">
        <h3>Linked Verification Evidence</h3>
        ${testHtml}
      </div>

      <div class="drawer-section" style="display:flex; justify-content:flex-end;">
        <button id="btn-drawer-signoff" class="btn-signoff" style="font-size:0.85rem; padding:0.4rem 0.8rem;">
          ✍️ Sign Off on This Link
        </button>
      </div>
    `;

    const copyBtn = document.getElementById('btn-copy-path');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        if (currentPathLine) {
          navigator.clipboard.writeText(currentPathLine);
          copyBtn.innerText = '✅ Copied!';
          setTimeout(() => { copyBtn.innerText = '📋 Copy Path:Line'; }, 2000);
        }
      });
    }

    const drawerSignoff = document.getElementById('btn-drawer-signoff');
    if (drawerSignoff) {
      drawerSignoff.addEventListener('click', () => {
        openReviewModal(req.id, req.title, test ? test.id : null);
      });
    }
  } catch (e) {
    content.innerHTML = '<div class="table-placeholder">Error rendering evidence.</div>';
  }
}

function closeDrawer() {
  const drawer = document.getElementById('drawer');
  const overlay = document.getElementById('drawer-overlay');
  if (drawer) drawer.classList.remove('open');
  if (overlay) overlay.classList.remove('open');
}

// --- Utilities ---

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerText = text;
}

function getStatusBadge(status) {
  switch (status) {
    case 'verified':
      return '<span class="badge badge-verified">VERIFIED</span>';
    case 'linked_passing':
      return '<span class="badge badge-passing">LINKED PASSING</span>';
    case 'unverified_gap':
      return '<span class="badge badge-gap">UNVERIFIED GAP</span>';
    default:
      return `<span class="badge badge-system">${escapeHtml(status)}</span>`;
  }
}

function formatReason(code) {
  if (!code) return '—';
  return code
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());
}
