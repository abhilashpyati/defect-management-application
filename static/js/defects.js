/**
 * DefectGuard - Defects Module
 * Handles Defect Recording, Reporting, Tracking, Filters, Pagination & Role-Aware Lifecycle Transitions
 */

const DefectsModule = (function () {
    let defectsCache = [];
    let currentFilters = {};
    let currentPage = 1;
    const pageSize = 8;
    let pendingDeleteId = null;

    function init() {
        setupFilterListeners();
        setupFormListeners();
    }

    function setupFilterListeners() {
        const searchInput = document.getElementById('trackerSearchInput');
        const filterStatus = document.getElementById('trackerFilterStatus');
        const filterSeverity = document.getElementById('trackerFilterSeverity');
        const filterPriority = document.getElementById('trackerFilterPriority');
        const filterModule = document.getElementById('trackerFilterModule');
        const resetBtn = document.getElementById('trackerResetFiltersBtn');

        let debounceTimer;
        searchInput?.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                applyFilters();
            }, 300);
        });

        filterStatus?.addEventListener('change', applyFilters);
        filterSeverity?.addEventListener('change', applyFilters);
        filterPriority?.addEventListener('change', applyFilters);
        filterModule?.addEventListener('change', applyFilters);

        resetBtn?.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            if (filterStatus) filterStatus.value = '';
            if (filterSeverity) filterSeverity.value = '';
            if (filterPriority) filterPriority.value = '';
            if (filterModule) filterModule.value = '';
            currentFilters = {};
            currentPage = 1;
            loadDefects();
        });
    }

    function applyFilters() {
        currentFilters = {
            search: document.getElementById('trackerSearchInput')?.value.trim() || '',
            status: document.getElementById('trackerFilterStatus')?.value || '',
            severity: document.getElementById('trackerFilterSeverity')?.value || '',
            priority: document.getElementById('trackerFilterPriority')?.value || '',
            module: document.getElementById('trackerFilterModule')?.value || ''
        };
        currentPage = 1;
        loadDefects(currentFilters);
    }

    function filterAssignedToMe() {
        const user = App.getCurrentUser();
        const searchInput = document.getElementById('trackerSearchInput');
        if (searchInput) searchInput.value = user.email;
        currentFilters = { search: user.email };
        currentPage = 1;
        loadDefects(currentFilters);
    }

    function setupFormListeners() {
        // 1. Record New Defect Form
        const newForm = document.getElementById('newDefectForm');
        newForm?.addEventListener('submit', async (e) => {
            e.preventDefault();

            const currentRole = App.getCurrentRole();
            if (currentRole === 'Developer') {
                App.showToast('Forbidden: Developers cannot record new defects. Switch to Tester or Admin.', 'danger', 'Permission Denied');
                return;
            }

            const currentUser = App.getCurrentUser();
            const assigneeVal = currentRole === 'Tester' ? 'Unassigned' : (document.getElementById('defectAssignee')?.value.trim() || 'Unassigned');
            const payload = {
                title: document.getElementById('defectTitle')?.value.trim(),
                module: document.getElementById('defectModule')?.value,
                type: document.getElementById('defectType')?.value,
                severity: document.getElementById('defectSeverity')?.value,
                priority: document.getElementById('defectPriority')?.value,
                discovery_phase: document.getElementById('defectPhase')?.value,
                environment: document.getElementById('defectEnvironment')?.value,
                reporter: document.getElementById('defectReporter')?.value.trim() || currentUser.email,
                assignee: assigneeVal,
                description: document.getElementById('defectDescription')?.value.trim(),
                steps_to_reproduce: document.getElementById('defectSteps')?.value.trim(),
                expected_behavior: document.getElementById('defectExpected')?.value.trim(),
                actual_behavior: document.getElementById('defectActual')?.value.trim(),
                prevention_guideline: document.getElementById('defectPrevention')?.value.trim() || null
            };

            // Basic client validation (assignee is not required for Tester)
            for (const [key, val] of Object.entries(payload)) {
                if (key !== 'prevention_guideline' && key !== 'assignee' && (!val || val === '')) {
                    App.showToast(`Please fill out required field: ${key.replace('_', ' ')}`, 'warning', 'Validation Error');
                    return;
                }
            }

            try {
                const res = await fetch('/api/defects', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    App.showToast(`Defect ${data.data.defect_code} created successfully!`, 'success', 'Created');
                    newForm.reset();
                    App.navigateTo('tracker');
                    App.refreshAllData();
                } else {
                    App.showToast(data.error || 'Failed to record defect.', 'danger', 'Submission Error');
                }
            } catch (err) {
                App.showToast('Network error while saving defect: ' + err.message, 'danger', 'Error');
            }
        });

        // 2. Lifecycle Transition Form
        const lifecycleForm = document.getElementById('lifecycleTransitionForm');
        lifecycleForm?.addEventListener('submit', async (e) => {
            e.preventDefault();

            const defectId = document.getElementById('lifecycleDefectId')?.value;
            const newStatus = document.getElementById('lifecycleNextStatus')?.value;
            const assignee = document.getElementById('lifecycleAssignee')?.value.trim();
            const verAssignee = document.getElementById('lifecycleVerificationAssignee')?.value.trim();
            const notes = document.getElementById('lifecycleNotes')?.value.trim();
            const commitRef = document.getElementById('lifecycleCommit')?.value.trim();

            if (!defectId || !newStatus) return;

            const payload = {
                status: newStatus
            };
            const currentRole = App.getCurrentRole();
            if (currentRole === 'Admin') {
                if (assignee) payload.assignee = assignee;
                if (verAssignee) payload.verification_assignee = verAssignee;
            }
            if (newStatus === 'REOPENED' && !notes) {
                App.showToast('Reopening reason is mandatory to reopen a resolved defect.', 'warning', 'Validation Error');
                return;
            }
            if (notes) {
                if (newStatus === 'IN PROGRESS') payload.investigation_notes = notes;
                else if (newStatus === 'RESOLVED') payload.resolution_notes = notes;
                else if (newStatus === 'VERIFIED') payload.verification_notes = notes;
                else if (newStatus === 'REOPENED') payload.reopening_reason = notes;
                payload.notes = notes;
            }
            if (commitRef && (newStatus === 'RESOLVED' || newStatus === 'IN PROGRESS')) {
                payload.commit_reference = commitRef;
            }

            try {
                const res = await fetch(`/api/defects/${defectId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    App.showToast(`Defect transitioned to ${newStatus}`, 'success', 'Lifecycle Updated');
                    const modalEl = document.getElementById('modalLifecycleTransition');
                    bootstrap.Modal.getInstance(modalEl)?.hide();
                    App.refreshAllData();
                } else {
                    App.showToast(data.error || 'Failed to update lifecycle.', 'danger', 'Transition Error');
                }
            } catch (err) {
                App.showToast('Network error: ' + err.message, 'danger', 'Error');
            }
        });

        // 3. Edit Defect Form
        const editForm = document.getElementById('editDefectForm');
        editForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const defectId = document.getElementById('editDefectId')?.value;
            if (!defectId) return;

            const payload = {
                title: document.getElementById('editDefectTitle')?.value.trim(),
                module: document.getElementById('editDefectModule')?.value,
                severity: document.getElementById('editDefectSeverity')?.value,
                priority: document.getElementById('editDefectPriority')?.value,
                assignee: document.getElementById('editDefectAssignee')?.value.trim(),
                verification_assignee: document.getElementById('editDefectVerificationAssignee')?.value.trim() || undefined,
                description: document.getElementById('editDefectDescription')?.value.trim(),
                steps_to_reproduce: document.getElementById('editDefectSteps')?.value.trim(),
                expected_behavior: document.getElementById('editDefectExpected')?.value.trim(),
                actual_behavior: document.getElementById('editDefectActual')?.value.trim()
            };

            try {
                const res = await fetch(`/api/defects/${defectId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    App.showToast(`Defect ${data.data.defect_code} updated successfully.`, 'success', 'Updated');
                    const modalEl = document.getElementById('modalEditDefect');
                    bootstrap.Modal.getInstance(modalEl)?.hide();
                    App.refreshAllData();
                } else {
                    App.showToast(data.error || 'Failed to update defect.', 'danger', 'Error');
                }
            } catch (err) {
                App.showToast('Network error: ' + err.message, 'danger', 'Error');
            }
        });

        // 4. Confirm Delete Submit
        document.getElementById('confirmDeleteSubmitBtn')?.addEventListener('click', async () => {
            if (!pendingDeleteId) return;

            try {
                const res = await fetch(`/api/defects/${pendingDeleteId}`, { method: 'DELETE' });
                const data = await res.json();
                if (res.ok && data.success) {
                    App.showToast('Defect permanently deleted.', 'success', 'Deleted');
                    const modalEl = document.getElementById('modalConfirmDelete');
                    bootstrap.Modal.getInstance(modalEl)?.hide();
                    pendingDeleteId = null;
                    App.refreshAllData();
                } else {
                    App.showToast(data.error || 'Failed to delete defect.', 'danger', 'Error');
                }
            } catch (err) {
                App.showToast('Network error: ' + err.message, 'danger', 'Error');
            }
        });
    }

    async function loadDefects(filters = currentFilters) {
        try {
            const queryParams = new URLSearchParams();
            for (const [key, val] of Object.entries(filters)) {
                if (val) queryParams.append(key, val);
            }

            const res = await fetch(`/api/defects?${queryParams.toString()}`);
            const data = await res.json();

            if (res.ok && data.success) {
                defectsCache = data.data;
                renderTrackerTable();
            }
        } catch (err) {
            console.error('Error fetching defects:', err);
        }
    }

    function renderTrackerTable() {
        const tbody = document.getElementById('trackerTableBody');
        const countBadge = document.getElementById('trackerCountBadge');
        const paginationInfo = document.getElementById('trackerPaginationInfo');
        const paginationControls = document.getElementById('trackerPaginationControls');

        if (!tbody) return;

        const currentRole = App.getCurrentRole();

        if (countBadge) countBadge.textContent = `${defectsCache.length} records`;

        if (!defectsCache || defectsCache.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center py-5 text-muted"><i class="bi bi-inbox fs-2 d-block mb-2"></i>No defects found matching current filters.</td></tr>`;
            if (paginationInfo) paginationInfo.textContent = 'Showing 0 of 0 defects';
            if (paginationControls) paginationControls.innerHTML = '';
            return;
        }

        const totalPages = Math.ceil(defectsCache.length / pageSize) || 1;
        if (currentPage > totalPages) currentPage = totalPages;

        const startIndex = (currentPage - 1) * pageSize;
        const pageItems = defectsCache.slice(startIndex, startIndex + pageSize);

        let rowsHtml = '';
        pageItems.forEach(d => {
            const canDelete = currentRole === 'Admin';
            const deleteBtnHtml = canDelete
                ? `<button class="btn btn-outline-danger" title="Delete Defect (Admin Only)" onclick="DefectsModule.confirmDelete('${d.id}', '${d.defect_code}')"><i class="bi bi-trash"></i></button>`
                : `<button class="btn btn-outline-secondary disabled opacity-25" title="Only Admin can delete defects" disabled><i class="bi bi-trash"></i></button>`;

            const canEdit = currentRole === 'Admin';
            const editBtnHtml = canEdit
                ? `<button class="btn btn-outline-secondary" title="Edit Defect (Admin Only)" onclick="DefectsModule.openEditModal('${d.id}')"><i class="bi bi-pencil"></i></button>`
                : `<button class="btn btn-outline-secondary disabled opacity-25" title="Only Admin can edit core defect details" disabled><i class="bi bi-pencil"></i></button>`;

            rowsHtml += `
                <tr>
                    <td><span class="defect-code-badge">${d.defect_code}</span></td>
                    <td class="defect-title-cell" title="${escapeHtml(d.title)}">${escapeHtml(d.title)}</td>
                    <td><span class="badge bg-light text-dark border">${d.module}</span></td>
                    <td>${getSeverityBadgeHtml(d.severity)}</td>
                    <td>${getPriorityBadgeHtml(d.priority)}</td>
                    <td><small class="text-secondary">${escapeHtml(d.assignee)}</small></td>
                    <td>${getStatusBadgeHtml(d.status)}</td>
                    <td><small class="text-muted">${(d.created_at || '').substring(0, 10)}</small></td>
                    <td class="text-end">
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-secondary" title="View Details & History" onclick="DefectsModule.viewDefectDetails('${d.id}')">
                                <i class="bi bi-eye"></i>
                            </button>
                            <button class="btn btn-outline-primary" title="Update Lifecycle (${currentRole})" onclick="DefectsModule.openLifecycleModal('${d.id}')">
                                <i class="bi bi-arrow-repeat"></i>
                            </button>
                            ${editBtnHtml}
                            ${deleteBtnHtml}
                        </div>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = rowsHtml;

        // Pagination rendering
        if (paginationInfo) {
            paginationInfo.textContent = `Showing ${startIndex + 1} to ${Math.min(startIndex + pageSize, defectsCache.length)} of ${defectsCache.length} defects`;
        }

        if (paginationControls) {
            let pgHtml = `
                <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                    <button class="page-link" onclick="DefectsModule.changePage(${currentPage - 1})">Previous</button>
                </li>
            `;
            for (let i = 1; i <= totalPages; i++) {
                pgHtml += `
                    <li class="page-item ${i === currentPage ? 'active' : ''}">
                        <button class="page-link" onclick="DefectsModule.changePage(${i})">${i}</button>
                    </li>
                `;
            }
            pgHtml += `
                <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                    <button class="page-link" onclick="DefectsModule.changePage(${currentPage + 1})">Next</button>
                </li>
            `;
            paginationControls.innerHTML = pgHtml;
        }
    }

    function changePage(page) {
        currentPage = page;
        renderTrackerTable();
    }

    async function viewDefectDetails(idOrCode) {
        try {
            const res = await fetch(`/api/defects/${idOrCode}`);
            const data = await res.json();
            if (!res.ok || !data.success) {
                App.showToast('Failed to load defect details.', 'danger');
                return;
            }

            const d = data.data;

            // Load audit history
            const histRes = await fetch(`/api/defects/${idOrCode}/history`);
            const histData = await histRes.json();
            const history = (histRes.ok && histData.success) ? histData.data : [];

            // Populate Modal
            document.getElementById('modalDefectCodeBadge').textContent = d.defect_code;
            document.getElementById('modalDefectTitle').textContent = d.title;

            document.getElementById('modalDetailStatus').outerHTML = getStatusBadgeHtml(d.status, 'modalDetailStatus');
            document.getElementById('modalDetailSeverity').outerHTML = getSeverityBadgeHtml(d.severity, 'modalDetailSeverity');
            document.getElementById('modalDetailPriority').outerHTML = getPriorityBadgeHtml(d.priority, 'modalDetailPriority');
            document.getElementById('modalDetailModule').textContent = d.module;

            document.getElementById('modalDetailType').textContent = d.type;
            document.getElementById('modalDetailPhase').textContent = d.discovery_phase;
            document.getElementById('modalDetailEnvironment').textContent = d.environment;
            document.getElementById('modalDetailAssignee').textContent = d.assignee;
            const modalVerAssignee = document.getElementById('modalDetailVerificationAssignee');
            if (modalVerAssignee) modalVerAssignee.textContent = d.verification_assignee || 'Unassigned';

            document.getElementById('modalDetailDescription').textContent = d.description;
            document.getElementById('modalDetailReporter').textContent = d.reporter;
            document.getElementById('modalDetailCreated').textContent = d.created_at;
            document.getElementById('modalDetailResolved').textContent = d.resolved_at || 'Not resolved';
            document.getElementById('modalDetailCommit').textContent = d.commit_reference || 'None';

            // Distinct lifecycle notes
            const invEl = document.getElementById('modalDetailInvestigation');
            if (invEl) invEl.textContent = d.investigation_notes || 'None recorded';

            const resEl = document.getElementById('modalDetailResolution');
            if (resEl) resEl.textContent = d.resolution_notes || 'None recorded';

            const verEl = document.getElementById('modalDetailVerification');
            if (verEl) verEl.textContent = d.verification_notes || 'None recorded';

            const reopenEl = document.getElementById('modalDetailReopeningReason');
            if (reopenEl) reopenEl.textContent = d.reopening_reason || 'None (no reopening recorded)';

            document.getElementById('modalDetailSteps').textContent = d.steps_to_reproduce;
            document.getElementById('modalDetailExpected').textContent = d.expected_behavior;
            document.getElementById('modalDetailActual').textContent = d.actual_behavior;
            document.getElementById('modalDetailPrevention').textContent = d.prevention_guideline || 'None specified';

            // Populate Timeline
            const timelineContainer = document.getElementById('modalHistoryTimeline');
            if (timelineContainer) {
                if (history.length === 0) {
                    timelineContainer.innerHTML = '<div class="text-muted small">No history recorded.</div>';
                } else {
                    let timelineHtml = '';
                    history.forEach(h => {
                        const actorRoleBadge = h.actor_role
                            ? `<span class="badge ${h.actor_role === 'Admin' ? 'bg-danger-subtle text-danger' : h.actor_role === 'Developer' ? 'bg-primary-subtle text-primary' : 'bg-success-subtle text-success'} border ms-1">${h.actor_role}</span>`
                            : '';

                        timelineHtml += `
                            <div class="timeline-item">
                                <div class="timeline-point"></div>
                                <div class="timeline-content">
                                    <div class="timeline-header">
                                        <div>
                                            <span class="badge bg-secondary me-1">${h.previous_status || 'INITIAL'}</span>
                                            <i class="bi bi-arrow-right text-muted mx-1"></i>
                                            <span class="badge bg-primary">${h.new_status}</span>
                                            ${actorRoleBadge}
                                        </div>
                                        <span class="timeline-time">${h.timestamp}</span>
                                    </div>
                                    <div class="small text-secondary mb-1">Actor: <strong>${escapeHtml(h.actor_email || h.assignee || 'System')}</strong></div>
                                    <div class="small text-dark">${escapeHtml(h.notes || 'Status updated')}</div>
                                </div>
                            </div>
                        `;
                    });
                    timelineContainer.innerHTML = timelineHtml;
                }
            }

            // Bind modal action buttons
            const editBtn = document.getElementById('modalViewEditBtn');
            const transBtn = document.getElementById('modalViewTransitionBtn');

            if (editBtn) editBtn.onclick = () => {
                bootstrap.Modal.getInstance(document.getElementById('modalViewDefect'))?.hide();
                openEditModal(d.id);
            };

            if (transBtn) transBtn.onclick = () => {
                bootstrap.Modal.getInstance(document.getElementById('modalViewDefect'))?.hide();
                openLifecycleModal(d.id);
            };

            document.getElementById('tab-overview-btn')?.click();

            const modalEl = document.getElementById('modalViewDefect');
            new bootstrap.Modal(modalEl).show();

        } catch (err) {
            console.error('viewDefectDetails error:', err);
            App.showToast('Error loading defect modal.', 'danger');
        }
    }

    async function openLifecycleModal(idOrCode) {
        try {
            const currentRole = App.getCurrentRole();
            const res = await fetch(`/api/defects/${idOrCode}`);
            const data = await res.json();
            if (!res.ok || !data.success) {
                App.showToast('Could not load defect for lifecycle update.', 'danger');
                return;
            }

            const d = data.data;
            const allowed = data.allowed_transitions || [];

            document.getElementById('lifecycleDefectId').value = d.id;
            document.getElementById('lifecycleModalSubtitle').textContent = `Defect ${d.defect_code}: ${d.title}`;

            const actingLabel = document.getElementById('lifecycleActingRoleLabel');
            if (actingLabel) actingLabel.textContent = currentRole;

            const currStatusContainer = document.getElementById('lifecycleCurrentStatusBadge');
            if (currStatusContainer) {
                currStatusContainer.outerHTML = getStatusBadgeHtml(d.status, 'lifecycleCurrentStatusBadge');
            }

            // Configure fields by role
            const assigneeContainer = document.getElementById('lifecycleAssigneeContainer');
            const verAssigneeContainer = document.getElementById('lifecycleVerificationAssigneeContainer');
            const commitContainer = document.getElementById('lifecycleCommitContainer');
            const notesLabel = document.getElementById('lifecycleNotesLabel');

            if (assigneeContainer) {
                // Only Admin can assign/reassign developers
                assigneeContainer.style.display = currentRole === 'Admin' ? 'block' : 'none';
            }

            if (verAssigneeContainer) {
                // Only Admin can assign QA verification assignees
                verAssigneeContainer.style.display = currentRole === 'Admin' ? 'block' : 'none';
            }

            if (commitContainer) {
                // Developer and Admin provide commit references; not applicable for Tester
                commitContainer.style.display = (currentRole === 'Developer' || currentRole === 'Admin') ? 'block' : 'none';
            }

            if (notesLabel) {
                notesLabel.textContent = currentRole === 'Developer' ? 'Technical Resolution Notes / Fix Rationale' :
                                         currentRole === 'Tester' ? 'QA Verification Comments / Reopen Rationale' :
                                         'Administrative Lifecycle Notes';
            }

            const nextSelect = document.getElementById('lifecycleNextStatus');
            const submitBtn = document.getElementById('lifecycleSubmitBtn');
            const helpText = document.getElementById('lifecycleAllowedHelp');

            if (nextSelect) {
                nextSelect.innerHTML = '';
                if (allowed.length === 0) {
                    let reason = `No authorized transitions available for '${currentRole}' from status '${d.status}'.`;
                    if (d.status === 'NEW' && currentRole === 'Developer') {
                        reason = "Defect is in 'NEW' status. An Admin must assign it to a developer before work can begin.";
                    } else if (d.status === 'NEW' && currentRole === 'Tester') {
                        reason = "Defect is awaiting Admin assignment.";
                    } else if (d.status === 'ASSIGNED' && currentRole === 'Tester') {
                        reason = "Defect is assigned to development. Only Developer/Admin can start progress.";
                    } else if (d.status === 'IN PROGRESS' && currentRole === 'Tester') {
                        reason = "Defect is currently being fixed by developer. Awaiting RESOLVED state for QA verification.";
                    } else if (d.status === 'RESOLVED' && currentRole === 'Developer') {
                        reason = "Fix submitted. Awaiting QA Tester verification.";
                    } else if (d.status === 'REOPENED' && currentRole === 'Developer') {
                        reason = "Defect is in 'REOPENED' status. An Admin must review and reassign it before development work can resume.";
                    } else if (d.status === 'REOPENED' && currentRole === 'Tester') {
                        reason = "Defect is in 'REOPENED' status. Awaiting Admin review and developer reassignment.";
                    } else if (d.status === 'CLOSED') {
                        reason = "Defect is in terminal CLOSED state.";
                    }

                    nextSelect.innerHTML = `<option value="" disabled selected>${reason}</option>`;
                    if (submitBtn) submitBtn.disabled = true;
                    if (helpText) helpText.textContent = reason;
                } else {
                    if (submitBtn) submitBtn.disabled = false;
                    allowed.forEach((status, idx) => {
                        const opt = document.createElement('option');
                        opt.value = status;
                        opt.textContent = `${status} (Authorized for ${currentRole})`;
                        if (idx === 0) opt.selected = true;
                        nextSelect.appendChild(opt);
                    });
                    if (helpText) helpText.textContent = `Authorized next status options for role '${currentRole}' from '${d.status}'.`;

                    function updateDynamicNotesLabel(target) {
                        if (!notesLabel) return;
                        const notesInput = document.getElementById('lifecycleNotes');
                        if (target === 'IN PROGRESS') {
                            notesLabel.textContent = 'Investigation Notes / Technical Findings';
                            if (notesInput) notesInput.placeholder = 'Record root cause analysis, stack trace investigation, or affected code components...';
                        } else if (target === 'RESOLVED') {
                            notesLabel.textContent = 'Resolution Notes / Fix Details';
                            if (notesInput) notesInput.placeholder = 'Describe technical solution, patches applied, and boundary conditions handled...';
                        } else if (target === 'ASSIGNED') {
                            notesLabel.textContent = 'Assignment / Triage Notes';
                            if (notesInput) notesInput.placeholder = 'Notes on developer assignment or acknowledging reopened defect...';
                        } else if (target === 'REOPENED') {
                            notesLabel.innerHTML = 'Reopening Reason <span class="text-danger">* (Mandatory)</span>';
                            if (notesInput) notesInput.placeholder = 'Specify exact reproduction scenario where the fix failed or edge case encountered...';
                        } else if (target === 'VERIFIED') {
                            notesLabel.textContent = 'QA Verification Notes / Test Evidence';
                            if (notesInput) notesInput.placeholder = 'Confirm test environment, test cases executed, and verification results...';
                        } else {
                            notesLabel.textContent = 'Lifecycle Transition Notes';
                            if (notesInput) notesInput.placeholder = 'Notes on status transition...';
                        }
                    }

                    nextSelect.onchange = (e) => updateDynamicNotesLabel(e.target.value);
                    if (allowed.length > 0) updateDynamicNotesLabel(allowed[0]);
                }
            }

            document.getElementById('lifecycleAssignee').value = d.assignee || '';
            const verAssigneeInput = document.getElementById('lifecycleVerificationAssignee');
            if (verAssigneeInput) verAssigneeInput.value = d.verification_assignee || '';
            document.getElementById('lifecycleNotes').value = '';
            document.getElementById('lifecycleCommit').value = d.commit_reference || '';

            const modalEl = document.getElementById('modalLifecycleTransition');
            new bootstrap.Modal(modalEl).show();
        } catch (err) {
            console.error('openLifecycleModal error:', err);
            App.showToast('Failed to open lifecycle modal.', 'danger');
        }
    }

    async function openEditModal(idOrCode) {
        try {
            const currentRole = App.getCurrentRole();
            const res = await fetch(`/api/defects/${idOrCode}`);
            const data = await res.json();
            if (!res.ok || !data.success) {
                App.showToast('Could not load defect details for edit.', 'danger');
                return;
            }

            const d = data.data;
            document.getElementById('editDefectId').value = d.id;
            document.getElementById('editDefectTitle').value = d.title;
            document.getElementById('editDefectModule').value = d.module;
            document.getElementById('editDefectSeverity').value = d.severity;
            document.getElementById('editDefectPriority').value = d.priority;
            document.getElementById('editDefectAssignee').value = d.assignee;
            const verAssInput = document.getElementById('editDefectVerificationAssignee');
            if (verAssInput) verAssInput.value = d.verification_assignee || '';
            document.getElementById('editDefectDescription').value = d.description;
            document.getElementById('editDefectSteps').value = d.steps_to_reproduce;
            document.getElementById('editDefectExpected').value = d.expected_behavior;
            document.getElementById('editDefectActual').value = d.actual_behavior;

            // Role-based restrictions on fields
            const sevSelect = document.getElementById('editDefectSeverity');
            const prioSelect = document.getElementById('editDefectPriority');
            const assInput = document.getElementById('editDefectAssignee');
            const verAssEl = document.getElementById('editDefectVerificationAssignee');
            const sevHelp = document.getElementById('editSeverityHelp');
            const assHelp = document.getElementById('editAssigneeHelp');
            const verAssHelp = document.getElementById('editVerAssigneeHelp');

            if (currentRole === 'Developer') {
                sevSelect.disabled = true;
                prioSelect.disabled = true;
                assInput.disabled = true;
                if (verAssEl) verAssEl.disabled = true;
                if (sevHelp) sevHelp.textContent = "Locked: Developer cannot alter severity/priority.";
                if (assHelp) assHelp.textContent = "Locked: Developer cannot reassign.";
                if (verAssHelp) verAssHelp.textContent = "Locked: Developer cannot assign verification.";
            } else if (currentRole === 'Tester') {
                sevSelect.disabled = true;
                prioSelect.disabled = true;
                assInput.disabled = true;
                if (verAssEl) verAssEl.disabled = true;
                if (sevHelp) sevHelp.textContent = "Locked: Tester cannot alter severity/priority after submission.";
                if (assHelp) assHelp.textContent = "Locked: Tester cannot reassign developer.";
                if (verAssHelp) verAssHelp.textContent = "Locked: Only Admin can assign QA verification.";
            } else {
                sevSelect.disabled = false;
                prioSelect.disabled = false;
                assInput.disabled = false;
                if (verAssEl) verAssEl.disabled = false;
                if (sevHelp) sevHelp.textContent = "";
                if (assHelp) assHelp.textContent = "";
                if (verAssHelp) verAssHelp.textContent = "";
            }

            const modalEl = document.getElementById('modalEditDefect');
            new bootstrap.Modal(modalEl).show();
        } catch (err) {
            console.error('openEditModal error:', err);
        }
    }

    function confirmDelete(id, defectCode) {
        if (App.getCurrentRole() !== 'Admin') {
            App.showToast('Forbidden: Only Admin can delete defects.', 'danger');
            return;
        }
        pendingDeleteId = id;
        const msgEl = document.getElementById('deleteConfirmMessage');
        if (msgEl) msgEl.textContent = `Are you sure you want to soft-delete defect ${defectCode}? Active listings will hide it while audit history is permanently preserved.`;
        const modalEl = document.getElementById('modalConfirmDelete');
        new bootstrap.Modal(modalEl).show();
    }

    function exportFilteredCSV() {
        const queryParams = new URLSearchParams();
        for (const [key, val] of Object.entries(currentFilters)) {
            if (val) queryParams.append(key, val);
        }
        window.location.href = `/api/export/csv?${queryParams.toString()}`;
    }

    // Badge styling helpers
    function getStatusBadgeHtml(status, elementId = '') {
        const s = (status || '').toUpperCase();
        let cls = 'badge-status-new';
        let icon = 'bi-circle';

        if (s === 'ASSIGNED') { cls = 'badge-status-assigned'; icon = 'bi-person-check'; }
        else if (s === 'IN PROGRESS') { cls = 'badge-status-in-progress'; icon = 'bi-gear'; }
        else if (s === 'RESOLVED') { cls = 'badge-status-resolved'; icon = 'bi-check2'; }
        else if (s === 'VERIFIED') { cls = 'badge-status-verified'; icon = 'bi-patch-check'; }
        else if (s === 'CLOSED') { cls = 'badge-status-closed'; icon = 'bi-lock'; }
        else if (s === 'REOPENED') { cls = 'badge-status-reopened'; icon = 'bi-arrow-counterclockwise'; }

        const idAttr = elementId ? `id="${elementId}"` : '';
        return `<span ${idAttr} class="badge-status ${cls}"><i class="bi ${icon}"></i> ${s}</span>`;
    }

    function getSeverityBadgeHtml(sev, elementId = '') {
        const s = (sev || '').toLowerCase();
        let cls = 'badge-sev-trivial';
        if (s === 'blocker') cls = 'badge-sev-blocker';
        else if (s === 'critical') cls = 'badge-sev-critical';
        else if (s === 'major') cls = 'badge-sev-major';
        else if (s === 'minor') cls = 'badge-sev-minor';

        const idAttr = elementId ? `id="${elementId}"` : '';
        return `<span ${idAttr} class="badge-severity ${cls}">${sev}</span>`;
    }

    function getPriorityBadgeHtml(prio, elementId = '') {
        const p = (prio || '').toUpperCase();
        let cls = 'badge-prio-low';
        if (p.includes('P1') || p.includes('HIGH')) cls = 'badge-prio-high';
        else if (p.includes('P2') || p.includes('MEDIUM')) cls = 'badge-prio-medium';

        const idAttr = elementId ? `id="${elementId}"` : '';
        return `<span ${idAttr} class="badge-prio ${cls}">${prio}</span>`;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function applyRoleUI(role) {
        const assInput = document.getElementById('defectAssignee');
        const assLabel = document.getElementById('defectAssigneeLabel');
        const assStar = document.getElementById('defectAssigneeRequiredStar');
        const assHelp = document.getElementById('defectAssigneeHelp');

        if (assInput) {
            if (role === 'Tester') {
                assInput.disabled = true;
                assInput.value = 'Unassigned';
                assInput.placeholder = 'Unassigned (Only Admin can assign)';
                if (assStar) assStar.style.display = 'none';
                if (assHelp) assHelp.textContent = 'Locked: Only Admin can assign defects to developers. Defects reported by Tester are logged as Unassigned.';
            } else {
                assInput.disabled = false;
                assInput.value = '';
                assInput.placeholder = 'developer@demo.com or Dev Name';
                if (assStar) assStar.style.display = 'inline';
                if (assHelp) assHelp.textContent = 'Admin can assign a developer on creation, or leave blank to assign later.';
            }
        }
    }

    init();

    return {
        loadDefects,
        changePage,
        viewDefectDetails,
        openLifecycleModal,
        openEditModal,
        confirmDelete,
        exportFilteredCSV,
        filterAssignedToMe,
        getStatusBadgeHtml,
        getSeverityBadgeHtml,
        getPriorityBadgeHtml,
        applyRoleUI
    };
})();
