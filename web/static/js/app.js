// QA Platform Vanilla JS

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initMobileNav();
    initSearch('#search-tests', '#tests-table');
    initSearch('#search-runs', '#runs-table');
    initLightbox();
    initCommandPalette();
    pollRecordingStatus();
    
    // Check if we need to poll run status
    const runDetail = document.querySelector('.run-detail');
    if (runDetail && (runDetail.dataset.runStatus === 'running' || runDetail.dataset.runStatus === 'pending')) {
        pollRunStatus(runDetail.dataset.runId);
    }
    
    // Init drag reorder if on test detail
    if (document.getElementById('steps-tbody')) {
        initDragReorder();
    }
});

// 1. Toast System
function showToast(message, type = "success") {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = type === 'success' ? '✓' : (type === 'error' ? '✕' : 'ℹ');
    
    toast.innerHTML = `
        <div style="font-weight: bold; font-size: 16px;">${icon}</div>
        <div>${message}</div>
    `;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 2. Tabs
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all tabs in this container
            const container = tab.closest('.tabs');
            container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Hide all content, show target
            const tabId = tab.dataset.tab;
            const parent = container.parentElement;
            parent.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
            const target = parent.querySelector(`.tab-content[data-tab-content="${tabId}"]`);
            if (target) target.classList.remove('hidden');
        });
    });
}

// 3. Recording Controls
async function pollRecordingStatus() {
    try {
        const res = await fetch('/api/recording/status');
        const data = await res.json();
        
        const dot = document.getElementById('rec-status-dot');
        const text = document.getElementById('rec-status-text');
        
        if (dot && text) {
            if (data.is_recording) {
                dot.className = 'dot bg-green pulse';
                text.textContent = 'Recording';
            } else {
                dot.className = 'dot bg-gray';
                text.textContent = 'Idle';
            }
        }
    } catch (e) {
        console.error(e);
    }
    setTimeout(pollRecordingStatus, 3000);
}

async function startQuickRecord() {
    const url = document.getElementById('qr-url').value;
    const name = document.getElementById('qr-name').value;
    
    if (!url || !name) {
        showToast("URL and Test Name are required", "error");
        return;
    }
    
    const btn = document.getElementById('btn-qr-start');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div>';
    
    try {
        // Create test first
        const tRes = await fetch('/api/tests', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, url: url, mode: 'recorded'})
        });
        
        if (!tRes.ok) throw new Error("Failed to create test");
        const testData = await tRes.json();
        
        // Start recording
        const rRes = await fetch('/api/recording/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({test_id: testData.data.id, url: url})
        });
        
        if (!rRes.ok) throw new Error(await rRes.text());
        
        document.getElementById('qr-status').textContent = "Recording in progress...";
        document.getElementById('btn-qr-stop').disabled = false;
        
        // Store test ID for stop
        window.currentRecordingTestId = testData.data.id;
        
    } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
        btn.textContent = "Start Recording";
    }
}

async function stopQuickRecord() {
    const btn = document.getElementById('btn-qr-stop');
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/recording/stop', { method: 'POST' });
        if (!res.ok) throw new Error(await res.text());
        
        const data = await res.json();
        showToast(data.message, "success");
        
        setTimeout(() => {
            window.location.href = `/tests/${window.currentRecordingTestId}`;
        }, 1500);
        
    } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
    }
}

// For tests/create.html
async function startTestRecord() {
    const url = document.getElementById('cr-url').value;
    const name = document.getElementById('cr-name').value;
    const desc = document.getElementById('cr-desc').value;
    
    if (!url || !name) {
        showToast("URL and Test Name are required", "error");
        return;
    }
    
    const btn = document.getElementById('btn-cr-start');
    btn.disabled = true;
    
    try {
        const tRes = await fetch('/api/tests', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, url: url, mode: 'recorded', description: desc})
        });
        
        if (!tRes.ok) throw new Error("Failed to create test");
        const testData = await tRes.json();
        
        const envSelect = document.getElementById('cr-env');
        const envId = envSelect ? envSelect.value : null;
        
        const rRes = await fetch('/api/recording/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({test_id: testData.data.id, url: url, env_id: envId})
        });
        
        if (!rRes.ok) throw new Error(await rRes.text());
        
        document.getElementById('cr-recording-panel').classList.remove('hidden');
        btn.classList.add('hidden');
        
        window.currentRecordingTestId = testData.data.id;
        
    } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
    }
}

async function stopTestRecord() {
    const btn = document.getElementById('btn-cr-stop');
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/recording/stop', { method: 'POST' });
        if (!res.ok) throw new Error(await res.text());
        
        showToast("Recording saved successfully", "success");
        setTimeout(() => {
            window.location.href = `/tests/${window.currentRecordingTestId}`;
        }, 1000);
    } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
    }
}

// 4. Live run polling
async function pollRunStatus(runId) {
    try {
        const res = await fetch(`/api/runs/${runId}/status`);
        if (res.ok) {
            const data = await res.json();
            if (data.data.status !== 'running' && data.data.status !== 'pending') {
                window.location.reload();
                return;
            }
            // Update progress bar
            const passed = data.data.passed || 0;
            const failed = data.data.failed || 0;
            const total = data.data.step_count || 1;
            const progress = Math.min(100, Math.round(((passed + failed) / total) * 100));
            const bar = document.getElementById('rd-progress');
            if (bar) bar.style.width = `${progress}%`;
        }
        
        setTimeout(() => pollRunStatus(runId), 3000);
        
    } catch (e) {
        console.error(e);
    }
}

async function cancelRun(runId) {
    if (!confirm("Are you sure you want to cancel this run?")) return;
    try {
        const res = await fetch(`/api/runs/${runId}/cancel`, {method: 'POST'});
        if (res.ok) {
            window.location.reload();
        } else {
            showToast("Failed to cancel", "error");
        }
    } catch(e) {
        showToast(e.message, "error");
    }
}

// 5. Lightbox
let currentImages = [];
let currentImgIdx = 0;

function initLightbox() {
    const images = Array.from(document.querySelectorAll('.screenshot-thumb'));
    if (!images.length) return;
    
    currentImages = images.map(img => img.src);
    
    images.forEach((img, idx) => {
        img.addEventListener('click', (e) => {
            e.stopPropagation();
            openLightbox(idx);
        });
    });
    
    document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
    document.getElementById('lightbox-prev').addEventListener('click', () => {
        currentImgIdx = (currentImgIdx - 1 + currentImages.length) % currentImages.length;
        updateLightboxImg();
    });
    document.getElementById('lightbox-next').addEventListener('click', () => {
        currentImgIdx = (currentImgIdx + 1) % currentImages.length;
        updateLightboxImg();
    });
}

function openLightbox(idx) {
    currentImgIdx = idx;
    updateLightboxImg();
    document.getElementById('lightbox').classList.remove('hidden');
}

function updateLightboxImg() {
    document.getElementById('lightbox-img').src = currentImages[currentImgIdx];
}

function closeLightbox() {
    document.getElementById('lightbox').classList.add('hidden');
}

// 6. Replay Modal
function openReplayModal(testId, testName) {
    window.currentReplayTestId = testId;
    document.getElementById('rm-test-name').textContent = testName;
    document.getElementById('replay-modal').classList.remove('hidden');
}

async function submitReplay() {
    const headless = document.getElementById('rm-headless').checked;
    const speed = parseInt(document.getElementById('rm-speed').value);
    const envSelect = document.getElementById('rm-env');
    const envId = envSelect ? envSelect.value : null;
    
    const btn = document.getElementById('rm-start');
    btn.disabled = true;
    
    try {
        const payload = {headless, slow_mo: speed};
        if (envId) {
            payload.env_id = envId;
        }
        
        const res = await fetch(`/api/replay/${window.currentReplayTestId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to start replay");
        
        window.location.href = `/runs/${data.run_id}`;
    } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
    }
}

// 7. Delete confirmations
async function confirmDelete(url, name, redirectUrl) {
    if (!confirm(`Are you sure you want to delete ${name}? This cannot be undone.`)) return;
    
    try {
        const res = await fetch(url, { method: 'DELETE' });
        if (!res.ok) throw new Error("Failed to delete");
        
        showToast("Deleted successfully", "success");
        if (redirectUrl) {
            setTimeout(() => window.location.href = redirectUrl, 1000);
        } else {
            setTimeout(() => window.location.reload(), 1000);
        }
    } catch(e) {
        showToast(e.message, "error");
    }
}

async function deleteStep(testId, stepId) {
    if (!confirm("Delete this step?")) return;
    try {
        const res = await fetch(`/api/tests/${testId}/steps/${stepId}`, { method: 'DELETE' });
        if (res.ok) window.location.reload();
        else showToast("Failed to delete step", "error");
    } catch(e) { showToast(e.message, "error"); }
}

function openEditStepModal(buttonEl) {
    const tr = buttonEl.closest('tr');
    const table = tr.closest('table');
    const testId = table.dataset.testId;
    
    const stepId = tr.dataset.stepId;
    const action = tr.dataset.action;
    const selector = tr.dataset.selector;
    const value = tr.dataset.value;
    const description = tr.dataset.description;
    
    document.getElementById('es-step-id').value = stepId;
    document.getElementById('es-test-id').value = testId;
    document.getElementById('es-action').value = action;
    document.getElementById('es-selector').value = selector || '';
    document.getElementById('es-value').value = value || '';
    document.getElementById('es-description').value = description || '';
    
    document.getElementById('edit-step-modal').classList.remove('hidden');
}

async function saveStepEdit() {
    const stepId = document.getElementById('es-step-id').value;
    const testId = document.getElementById('es-test-id').value;
    const action = document.getElementById('es-action').value;
    const selector = document.getElementById('es-selector').value;
    const value = document.getElementById('es-value').value;
    const description = document.getElementById('es-description').value;
    
    const btn = document.getElementById('es-save');
    btn.disabled = true;
    btn.innerText = "Saving...";
    
    try {
        const res = await fetch(`/api/tests/${testId}/steps/${stepId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action,
                selector: selector || null,
                value: value || null,
                description: description || null
            })
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast("Step updated successfully", "success");
            setTimeout(() => window.location.reload(), 500);
        } else {
            throw new Error(data.detail || data.message || "Failed to update step");
        }
    } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
        btn.innerText = "Save Changes";
    }
}


// Add Step Modal Functions
function openAddStepModal(testId) {
    document.getElementById('as-test-id').value = testId;
    
    // Clear previous values
    document.getElementById('as-action').value = 'click';
    document.getElementById('as-selector').value = '';
    document.getElementById('as-value').value = '';
    document.getElementById('as-description').value = '';
    
    document.getElementById('add-step-modal').classList.remove('hidden');
}

async function saveAddStep() {
    const testId = document.getElementById('as-test-id').value;
    const action = document.getElementById('as-action').value;
    const selector = document.getElementById('as-selector').value;
    const value = document.getElementById('as-value').value;
    const description = document.getElementById('as-description').value;
    
    const btn = document.getElementById('as-save');
    btn.disabled = true;
    btn.innerText = "Adding...";
    
    try {
        // Calculate the next sequence number by looking at the existing rows
        const table = document.getElementById('steps-tbody');
        let nextSequence = 1;
        if (table) {
            const rows = Array.from(table.querySelectorAll('tr[data-seq]'));
            if (rows.length > 0) {
                const maxSeq = Math.max(...rows.map(r => parseInt(r.dataset.seq) || 0));
                nextSequence = maxSeq + 1;
            }
        }

        const res = await fetch(`/api/tests/${testId}/steps`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                sequence: nextSequence,
                action,
                selector: selector || null,
                value: value || null,
                description: description || null
            })
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast("Step added successfully", "success");
            setTimeout(() => window.location.reload(), 500);
        } else {
            throw new Error(data.detail || data.message || "Failed to add step");
        }
    } catch (e) {
        showToast(e.message, "error");
        btn.disabled = false;
        btn.innerText = "Add Step";
    }
}


// 8. Client-side search
function initSearch(inputSelector, tableSelector) {
    const input = document.querySelector(inputSelector);
    const table = document.querySelector(tableSelector);
    if (!input || !table) return;
    
    input.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(term)) row.style.display = '';
            else row.style.display = 'none';
        });
    });
}

// 9. Mobile nav
function initMobileNav() {
    const toggle = document.getElementById('mobile-nav-toggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

// 10. Drag and drop
function initDragReorder() {
    const tbody = document.getElementById('steps-tbody');
    const rows = tbody.querySelectorAll('.drag-row');
    
    let dragSrcEl = null;
    
    rows.forEach(row => {
        row.addEventListener('dragstart', function(e) {
            dragSrcEl = this;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/html', this.innerHTML);
            this.style.opacity = '0.4';
        });
        
        row.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            this.classList.add('drag-over');
        });
        
        row.addEventListener('dragleave', function(e) {
            this.classList.remove('drag-over');
        });
        
        row.addEventListener('drop', async function(e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            
            if (dragSrcEl !== this) {
                // Determine direction and insert
                const allRows = Array.from(tbody.querySelectorAll('.drag-row'));
                const srcIdx = allRows.indexOf(dragSrcEl);
                const targetIdx = allRows.indexOf(this);
                
                if (srcIdx < targetIdx) {
                    this.after(dragSrcEl);
                } else {
                    this.before(dragSrcEl);
                }
                
                // Collect new order
                const allRowsNow = Array.from(tbody.querySelectorAll('.drag-row'));
                const newOrder = allRowsNow.map((r, index) => ({
                    id: r.dataset.stepId,
                    sequence: index + 1
                }));
                const testId = tbody.closest('table').dataset.testId;
                
                try {
                    const res = await fetch(`/api/tests/${testId}/steps/reorder`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(newOrder)
                    });
                    
                    if (res.ok) window.location.reload();
                    else showToast("Failed to reorder", "error");
                } catch(e) {
                    showToast(e.message, "error");
                }
            }
        });
        
        row.addEventListener('dragend', function(e) {
            this.style.opacity = '1';
            rows.forEach(r => r.classList.remove('drag-over'));
        });
    });
}

// Extra: Reports and Logs
async function generateReport(runId, type) {
    showToast(`Generating ${type} report...`, "info");
    try {
        window.location.href = `/api/reports/${runId}/${type}`;
    } catch (e) {
        showToast("Failed to generate report", "error");
    }
}

async function loadRunLog(runId) {
    const el = document.getElementById('run-log-content');
    if (!el) return;
    
    try {
        const res = await fetch(`/api/runs/${runId}/log`);
        if (res.ok) {
            const text = await res.text();
            el.textContent = text;
        } else {
            el.textContent = "Log file not found or empty.";
        }
    } catch(e) {
        el.textContent = "Error loading logs.";
    }
}

// 11. Excel Import
let uploadedFilePath = '';

async function uploadExcelForImport() {
    const fileInput = document.getElementById('imp-file');
    const nameInput = document.getElementById('imp-name');
    const urlInput = document.getElementById('imp-url');
    const btn = document.getElementById('btn-imp-upload');
    
    if (!fileInput.files.length || !nameInput.value || !urlInput.value) {
        showToast("Please fill in all fields and select a file.", "error");
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Analyzing...';
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    try {
        const res = await fetch('/api/reports/import-excel', {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload failed");
        
        uploadedFilePath = data.file_path;
        
        const select = document.getElementById('imp-scenario');
        select.innerHTML = '<option value="">-- Import All Scenarios --</option>';
        
        data.scenarios.forEach(scen => {
            const opt = document.createElement('option');
            opt.value = scen.id;
            opt.textContent = `${scen.id} - ${scen.name} (${scen.step_count} steps)`;
            select.appendChild(opt);
        });
        
        document.getElementById('imp-scen-count').textContent = data.scenarios.length;
        document.getElementById('import-step-1').classList.add('hidden');
        document.getElementById('import-step-2').classList.remove('hidden');
        
    } catch(e) {
        showToast(e.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Analyze File";
    }
}

async function confirmExcelImport() {
    const nameInput = document.getElementById('imp-name');
    const urlInput = document.getElementById('imp-url');
    const scenarioSelect = document.getElementById('imp-scenario');
    const btn = document.getElementById('btn-imp-confirm');
    
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Importing...';
    
    try {
        // First create the test
        const tRes = await fetch('/api/tests', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: nameInput.value, url: urlInput.value, mode: 'excel'})
        });
        
        if (!tRes.ok) throw new Error("Failed to create test entry");
        const testData = await tRes.json();
        
        // Then import the steps
        const iRes = await fetch(`/api/reports/import-excel/${testData.id}/confirm`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                scenario_id: scenarioSelect.value || null,
                xlsx_path: uploadedFilePath
            })
        });
        
        const iData = await iRes.json();
        if (!iRes.ok) throw new Error(iData.detail || "Import failed");
        
        showToast(iData.message, "success");
        setTimeout(() => {
            window.location.href = `/tests/${testData.id}`;
        }, 1500);
        
    } catch(e) {
        showToast(e.message, "error");
        btn.disabled = false;
        btn.textContent = "Import Steps";
    }
}

// 12. Command Palette
function initCommandPalette() {
    const palette = document.getElementById('command-palette');
    const input = document.getElementById('cmd-input');
    const results = document.getElementById('cmd-results');
    if (!palette || !input) return;
    
    const commands = [
        { label: 'Go to Home', url: '/' },
        { label: 'Go to Tests', url: '/tests' },
        { label: 'Go to Runs', url: '/runs' },
        { label: 'Go to Settings', url: '/settings' },
        { label: 'Go to AI Studio', url: '/ai/studio' },
        { label: 'Create New Test', url: '/tests/create' }
    ];
    
    // Toggle with Ctrl+K or Cmd+K
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            togglePalette();
        }
        if (e.key === 'Escape' && !palette.classList.contains('hidden')) {
            togglePalette(false);
        }
    });
    
    function togglePalette(show) {
        const isHidden = palette.classList.contains('hidden');
        if (show === undefined) show = isHidden;
        
        if (show) {
            palette.classList.remove('hidden');
            input.value = '';
            renderResults('');
            setTimeout(() => input.focus(), 50);
        } else {
            palette.classList.add('hidden');
            input.blur();
        }
    }
    
    input.addEventListener('input', (e) => {
        renderResults(e.target.value);
    });
    
    function renderResults(query) {
        const term = query.toLowerCase();
        const filtered = commands.filter(c => c.label.toLowerCase().includes(term));
        
        results.innerHTML = '';
        if (filtered.length === 0) {
            results.innerHTML = '<div class="p-3 text-secondary text-center">No commands found.</div>';
            return;
        }
        
        filtered.forEach((cmd, i) => {
            const btn = document.createElement('button');
            btn.className = 'w-full text-left p-3 rounded-md hover:bg-hover hover:text-accent transition-colors flex items-center justify-between group text-sm';
            btn.innerHTML = `
                <span>${cmd.label}</span>
                <span class="text-xs text-secondary group-hover:text-accent opacity-0 group-hover:opacity-100 transition-opacity">Jump ↵</span>
            `;
            btn.onclick = () => {
                togglePalette(false);
                window.location.href = cmd.url;
            };
            results.appendChild(btn);
        });
    }
}
