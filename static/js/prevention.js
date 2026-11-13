/**
 * DefectGuard - Prevention Knowledge Base Controller
 * Subprocess 1: Root Cause Analysis, Patterns & Prevention Guidelines
 * Role-Aware (Admin can edit/create/delete; Developer & Tester view-only)
 */

const PreventionModule = (function () {
    let preventionCache = [];
    let currentFilters = {};

    function init() {
        setupFilterListeners();
        setupFormListeners();
    }

    function setupFilterListeners() {
        const searchInput = document.getElementById('preventionSearchInput');
        const filterModule = document.getElementById('preventionFilterModule');
        const filterCategory = document.getElementById('preventionFilterCategory');
        const resetBtn = document.getElementById('preventionResetBtn');

        let debounceTimer;
        searchInput?.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                applyFilters();
            }, 300);
        });

        filterModule?.addEventListener('change', applyFilters);
        filterCategory?.addEventListener('change', applyFilters);

        resetBtn?.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            if (filterModule) filterModule.value = '';
            if (filterCategory) filterCategory.value = '';
            currentFilters = {};
            loadPrevention();
        });

        document.getElementById('openAddPreventionModalBtn')?.addEventListener('click', () => {
            if (App.getCurrentRole() !== 'Admin') {
                App.showToast('Forbidden: Only Admin can add prevention guidelines.', 'danger');
                return;
            }
            openAddModal();
        });
    }

    function applyFilters() {
        currentFilters = {
            search: document.getElementById('preventionSearchInput')?.value.trim() || '',
            module: document.getElementById('preventionFilterModule')?.value || '',
            category: document.getElementById('preventionFilterCategory')?.value || ''
        };
        loadPrevention(currentFilters);
    }

    function applyRoleUI(role) {
        const addBtn = document.getElementById('openAddPreventionModalBtn');
        if (addBtn) {
            if (role === 'Admin') {
                addBtn.classList.remove('d-none');
            } else {
                addBtn.classList.add('d-none');
            }
        }
        renderPreventionGrid();
    }

    function setupFormListeners() {
        const form = document.getElementById('preventionGuidelineForm');
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (App.getCurrentRole() !== 'Admin') {
                App.showToast('Forbidden: Only Admin can save prevention guidelines.', 'danger');
                return;
            }

            const guidelineId = document.getElementById('preventionGuidelineId')?.value;
            const payload = {
                module: document.getElementById('preventionFormModule')?.value,
                category: document.getElementById('preventionFormCategory')?.value.trim(),
                root_cause: document.getElementById('preventionFormRootCause')?.value.trim(),
                guideline: document.getElementById('preventionFormGuideline')?.value.trim()
            };

            if (!payload.module || !payload.root_cause || !payload.guideline) {
                App.showToast('Please fill all mandatory fields.', 'warning');
                return;
            }

            try {
                let url = '/api/prevention';
                let method = 'POST';

                if (guidelineId) {
                    url = `/api/prevention/${guidelineId}`;
                    method = 'PUT';
                }

                const res = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    App.showToast(data.message, 'success');
                    const modalEl = document.getElementById('modalPreventionGuideline');
                    bootstrap.Modal.getInstance(modalEl)?.hide();
                    loadPrevention();
                } else {
                    App.showToast(data.error || 'Failed to save guideline.', 'danger');
                }
            } catch (err) {
                App.showToast('Network error: ' + err.message, 'danger');
            }
        });
    }

    async function loadPrevention(filters = currentFilters) {
        try {
            const queryParams = new URLSearchParams();
            for (const [k, v] of Object.entries(filters)) {
                if (v) queryParams.append(k, v);
            }

            const res = await fetch(`/api/prevention?${queryParams.toString()}`);
            const data = await res.json();

            if (res.ok && data.success) {
                preventionCache = data.data;
                renderPreventionGrid();
            }

            // Load summary metadata
            const sumRes = await fetch('/api/prevention/summary');
            const sumData = await sumRes.json();
            if (sumRes.ok && sumData.success) {
                populateCategoryFilter(sumData.data.categories);
                renderRecurringPatterns(sumData.data.recurring_patterns);
            }

        } catch (err) {
            console.error('loadPrevention error:', err);
        }
    }

    function renderPreventionGrid() {
        const container = document.getElementById('preventionGridContainer');
        if (!container) return;

        const currentRole = App.getCurrentRole();
        const canManage = currentRole === 'Admin';

        if (!preventionCache || preventionCache.length === 0) {
            container.innerHTML = `
                <div class="col-12 text-center py-5 text-muted">
                    <i class="bi bi-shield-slash fs-2 d-block mb-2"></i>
                    No prevention guidelines found matching filters.
                </div>
            `;
            return;
        }

        let html = '';
        preventionCache.forEach(g => {
            const actionButtonsHtml = canManage
                ? `<div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-secondary btn-sm" onclick="PreventionModule.openEditModal(${g.id})" title="Edit Guideline">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-sm" onclick="PreventionModule.deleteGuideline(${g.id})" title="Delete Guideline">
                            <i class="bi bi-trash"></i>
                        </button>
                   </div>`
                : `<span class="badge bg-light text-secondary border small">Read-Only</span>`;

            html += `
                <div class="col-lg-6">
                    <div class="saas-card h-100 border-start border-primary border-3">
                        <div class="saas-card-body p-4 d-flex flex-column justify-content-between">
                            <div>
                                <div class="d-flex align-items-center justify-content-between mb-2">
                                    <span class="badge bg-primary-subtle text-primary border border-primary-subtle">${g.module}</span>
                                    <span class="badge bg-light text-secondary border small">${g.category || 'General'}</span>
                                </div>
                                <div class="mb-3">
                                    <span class="fw-bold text-danger small text-uppercase d-block mb-1">Root Cause Analysis</span>
                                    <p class="small text-dark mb-0 bg-light p-2 rounded">${escapeHtml(g.root_cause)}</p>
                                </div>
                                <div class="mb-3">
                                    <span class="fw-bold text-success small text-uppercase d-block mb-1">Prevention Guideline / Best Practice</span>
                                    <p class="small text-dark mb-0 bg-light p-2 rounded border-start border-success border-2">${escapeHtml(g.guideline)}</p>
                                </div>
                            </div>
                            <div class="d-flex align-items-center justify-content-between pt-2 border-top mt-2">
                                <small class="text-muted">${(g.created_at || '').substring(0, 10)}</small>
                                ${actionButtonsHtml}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    function populateCategoryFilter(categories) {
        const select = document.getElementById('preventionFilterCategory');
        if (!select || !categories) return;

        const currentVal = select.value;
        select.innerHTML = '<option value="">All Categories</option>';
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            if (cat === currentVal) opt.selected = true;
            select.appendChild(opt);
        });
    }

    function renderRecurringPatterns(patterns) {
        const container = document.getElementById('preventionRecurringPatternsContainer');
        if (!container) return;

        if (!patterns || patterns.length === 0) {
            container.innerHTML = '<div class="text-muted small">No recurring defect clusters identified yet.</div>';
            return;
        }

        let html = '<ul class="list-group list-group-flush small">';
        patterns.forEach(p => {
            html += `
                <li class="list-group-item d-flex justify-content-between align-items-center px-0">
                    <div>
                        <strong class="text-dark">${p.module}</strong>
                        <span class="text-secondary ms-2">&mdash; ${p.type} issues</span>
                    </div>
                    <span class="badge bg-danger-subtle text-danger border">${p.defect_count} recurring instances</span>
                </li>
            `;
        });
        html += '</ul>';
        container.innerHTML = html;
    }

    function openAddModal() {
        document.getElementById('preventionGuidelineId').value = '';
        document.getElementById('preventionModalTitle').textContent = 'Record Prevention Guideline';
        document.getElementById('preventionFormModule').value = 'Authentication';
        document.getElementById('preventionFormCategory').value = '';
        document.getElementById('preventionFormRootCause').value = '';
        document.getElementById('preventionFormGuideline').value = '';

        const modalEl = document.getElementById('modalPreventionGuideline');
        new bootstrap.Modal(modalEl).show();
    }

    async function openEditModal(id) {
        if (App.getCurrentRole() !== 'Admin') {
            App.showToast('Forbidden: Only Admin can edit prevention guidelines.', 'danger');
            return;
        }

        try {
            const res = await fetch(`/api/prevention/${id}`);
            const data = await res.json();
            if (!res.ok || !data.success) {
                App.showToast('Could not load guideline.', 'danger');
                return;
            }

            const g = data.data;
            document.getElementById('preventionGuidelineId').value = g.id;
            document.getElementById('preventionModalTitle').textContent = 'Edit Prevention Guideline';
            document.getElementById('preventionFormModule').value = g.module;
            document.getElementById('preventionFormCategory').value = g.category;
            document.getElementById('preventionFormRootCause').value = g.root_cause;
            document.getElementById('preventionFormGuideline').value = g.guideline;

            const modalEl = document.getElementById('modalPreventionGuideline');
            new bootstrap.Modal(modalEl).show();
        } catch (err) {
            console.error('openEditModal error:', err);
        }
    }

    async function deleteGuideline(id) {
        if (App.getCurrentRole() !== 'Admin') {
            App.showToast('Forbidden: Only Admin can delete prevention guidelines.', 'danger');
            return;
        }

        if (!confirm('Are you sure you want to delete this prevention guideline?')) return;

        try {
            const res = await fetch(`/api/prevention/${id}`, { method: 'DELETE' });
            const data = await res.json();
            if (res.ok && data.success) {
                App.showToast('Prevention record deleted.', 'success');
                loadPrevention();
            } else {
                App.showToast(data.error || 'Failed to delete record.', 'danger');
            }
        } catch (err) {
            App.showToast('Network error: ' + err.message, 'danger');
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    init();

    return {
        loadPrevention,
        applyRoleUI,
        openAddModal,
        openEditModal,
        deleteGuideline
    };
})();
