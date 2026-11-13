/**
 * DefectGuard - Statistical Analytics & Role-Based Dashboard Controller
 * Subprocess 2 (Discovery & Leakage), Subprocess 6 (Prediction) & Role Views
 */

const AnalyticsModule = (function () {
    let charts = {};

    async function loadAnalytics() {
        try {
            const res = await fetch('/api/analytics');
            const result = await res.json();
            if (!res.ok || !result.success) {
                console.error('Failed to fetch analytics:', result);
                return;
            }

            const data = result.data;
            const currentRole = App.getCurrentRole();

            // Render shared activity log
            updateSharedActivityLog(data.role_dashboards?.admin?.recent_activities || []);

            // Render specific role view
            if (currentRole === 'Admin') {
                updateAdminDashboard(data);
            } else if (currentRole === 'Developer') {
                updateDeveloperDashboard(data.role_dashboards?.developer);
            } else if (currentRole === 'Tester') {
                updateTesterDashboard(data.role_dashboards?.tester, data);
            }

            // Always update discovery & prediction underlying data
            updateDiscoveryView(data);
            updatePredictionView(data.prediction, data.kpis);
            updateReportsSummary(data);

        } catch (err) {
            console.error('loadAnalytics error:', err);
        }
    }

    function updateAdminDashboard(data) {
        const kpis = data.kpis || {};
        setText('kpiTotalDefects', kpis.total_defects);
        setText('kpiOpenDefects', kpis.open_defects);
        setText('kpiInProgress', kpis.in_progress);
        setText('kpiResolvedDefects', kpis.resolved_defects);
        setText('kpiCriticalDefects', kpis.critical_blocker_defects);
        setText('kpiLeakagePercentage', `${kpis.defect_leakage_percentage}%`);
        setText('kpiOpenResolvedRatio', kpis.open_to_resolved_ratio_display);
        setText('kpiMTTR', kpis.mttr_display);

        // Dashboard high-risk alert banner
        const alertBox = document.getElementById('dashboardAlertsContainer');
        const alertMsg = document.getElementById('dashboardAlertMessage');
        if (alertBox && alertMsg) {
            if (kpis.critical_blocker_defects > 0 || kpis.high_risk_modules_count > 0) {
                alertBox.classList.remove('d-none');
                alertMsg.textContent = `${kpis.critical_blocker_defects} Critical/Blocker defect(s) and ${kpis.high_risk_modules_count} high-risk functional module(s) require regression verification.`;
            } else {
                alertBox.classList.add('d-none');
            }
        }

        // 1. Severity Doughnut Chart
        const sevData = data.severity_distribution || {};
        const sevLabels = ['Blocker', 'Critical', 'Major', 'Minor', 'Trivial'];
        const sevValues = sevLabels.map(l => sevData[l] || 0);
        renderChart('chartSeverity', {
            type: 'doughnut',
            data: {
                labels: sevLabels,
                datasets: [{
                    data: sevValues,
                    backgroundColor: ['#dc2626', '#ef4444', '#f59e0b', '#3b82f6', '#94a3b8'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });

        // 2. Status Bar Chart
        const statData = data.status_distribution || {};
        const statLabels = ['NEW', 'ASSIGNED', 'IN PROGRESS', 'RESOLVED', 'VERIFIED', 'CLOSED', 'REOPENED'];
        const statValues = statLabels.map(l => statData[l] || 0);
        renderChart('chartStatus', {
            type: 'bar',
            data: {
                labels: ['New', 'Assigned', 'In Prog', 'Resolved', 'Verified', 'Closed', 'Reopened'],
                datasets: [{
                    label: 'Defects',
                    data: statValues,
                    backgroundColor: ['#0284c7', '#d97706', '#6366f1', '#10b981', '#059669', '#64748b', '#e11d48'],
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1, precision: 0 } },
                    x: { ticks: { font: { size: 10 } } }
                }
            }
        });

        // 3. Developer Workload Table
        const workloadTbody = document.getElementById('adminWorkloadTableBody');
        const workload = data.role_dashboards?.admin?.developer_workload || [];
        if (workloadTbody) {
            if (workload.length === 0) {
                workloadTbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">No developer assignments recorded.</td></tr>';
            } else {
                let wHtml = '';
                workload.slice(0, 5).forEach(w => {
                    wHtml += `
                        <tr>
                            <td class="fw-bold">${escapeHtml(w.assignee)}</td>
                            <td><span class="badge bg-secondary">${w.count}</span></td>
                            <td><span class="badge bg-warning text-dark">${w.open_count}</span></td>
                            <td><span class="badge bg-success">${w.resolved_count}</span></td>
                        </tr>
                    `;
                });
                workloadTbody.innerHTML = wHtml;
            }
        }
    }

    function updateDeveloperDashboard(devData) {
        if (!devData) return;

        setText('devKpiAssigned', devData.assigned_defects);
        setText('devKpiNew', devData.new_assignments);
        setText('devKpiInProgress', devData.in_progress);
        setText('devKpiResolved', devData.resolved_defects);

        // Developer Priority Chart
        const prioCounts = devData.defects_by_priority || {};
        renderChart('chartDevPriority', {
            type: 'doughnut',
            data: {
                labels: ['P1 – High', 'P2 – Medium', 'P3 – Low'],
                datasets: [{
                    data: [prioCounts['P1 – High'] || 0, prioCounts['P2 – Medium'] || 0, prioCounts['P3 – Low'] || 0],
                    backgroundColor: ['#dc2626', '#f59e0b', '#10b981'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });

        // Developer Tasks Queue Table
        const tbody = document.getElementById('devAssignedTableBody');
        const queue = devData.assigned_defects_list || [];
        if (tbody) {
            if (queue.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted">No defects currently assigned to you.</td></tr>';
            } else {
                let html = '';
                queue.forEach(d => {
                    let quickAction = '';
                    if (d.status === 'ASSIGNED') {
                        quickAction = `<button class="btn btn-sm btn-outline-primary py-0" onclick="DefectsModule.openLifecycleModal('${d.id}')"><i class="bi bi-play"></i> Start Progress</button>`;
                    } else if (d.status === 'IN PROGRESS') {
                        quickAction = `<button class="btn btn-sm btn-success py-0" onclick="DefectsModule.openLifecycleModal('${d.id}')"><i class="bi bi-check"></i> Mark Resolved</button>`;
                    } else if (d.status === 'REOPENED') {
                        quickAction = `<button class="btn btn-sm btn-outline-warning py-0" onclick="DefectsModule.viewDefectDetails('${d.id}')"><i class="bi bi-hourglass-split"></i> Awaiting Admin Reassignment</button>`;
                    } else {
                        quickAction = `<button class="btn btn-sm btn-outline-secondary py-0" onclick="DefectsModule.viewDefectDetails('${d.id}')"><i class="bi bi-eye"></i> View</button>`;
                    }

                    html += `
                        <tr>
                            <td><span class="defect-code-badge">${d.defect_code}</span></td>
                            <td class="defect-title-cell" title="${escapeHtml(d.title)}">${escapeHtml(d.title)}</td>
                            <td>${DefectsModule.getPriorityBadgeHtml(d.priority)}</td>
                            <td>${DefectsModule.getStatusBadgeHtml(d.status)}</td>
                            <td class="text-end">${quickAction}</td>
                        </tr>
                    `;
                });
                tbody.innerHTML = html;
            }
        }
    }

    function updateTesterDashboard(testerData, fullData) {
        if (!testerData) return;

        setText('testerKpiReported', testerData.total_reported);
        setText('testerKpiNew', testerData.new_defects);
        setText('testerKpiAwaiting', testerData.awaiting_verification);
        setText('testerKpiVerified', testerData.verified_defects);

        // Tester Verification Queue (defects in RESOLVED status)
        const tbody = document.getElementById('testerVerificationTableBody');
        if (tbody) {
            // Fetch resolved defects
            fetch('/api/defects?status=RESOLVED')
                .then(r => r.json())
                .then(res => {
                    if (res.ok && res.data && res.data.length > 0) {
                        let html = '';
                        res.data.forEach(d => {
                            html += `
                                <tr>
                                    <td><span class="defect-code-badge">${d.defect_code}</span></td>
                                    <td class="defect-title-cell" title="${escapeHtml(d.title)}">${escapeHtml(d.title)}</td>
                                    <td><span class="badge bg-light text-dark border">${d.module}</span></td>
                                    <td><small class="text-secondary">${escapeHtml(d.assignee)}</small></td>
                                    <td><small class="text-success">${escapeHtml(d.resolution_notes || 'Fix completed')}</small></td>
                                    <td><code class="small">${escapeHtml(d.commit_reference || 'N/A')}</code></td>
                                    <td class="text-end">
                                        <button class="btn btn-sm btn-primary py-0" onclick="DefectsModule.openLifecycleModal('${d.id}')">
                                            <i class="bi bi-patch-check"></i> Verify / Reopen
                                        </button>
                                    </td>
                                </tr>
                            `;
                        });
                        tbody.innerHTML = html;
                    } else {
                        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-check2-circle text-success fs-3 d-block mb-1"></i>No defects currently awaiting verification.</td></tr>';
                    }
                })
                .catch(err => {
                    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3 text-muted">Unable to load verification queue.</td></tr>';
                });
        }
    }

    function updateSharedActivityLog(activities) {
        const tbody = document.getElementById('sharedActivityTableBody');
        if (!tbody) return;

        if (!activities || activities.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">No recent activities recorded.</td></tr>';
            return;
        }

        let html = '';
        activities.forEach(a => {
            const roleBadge = a.actor_role
                ? `<span class="badge ${a.actor_role === 'Admin' ? 'bg-danger-subtle text-danger' : a.actor_role === 'Developer' ? 'bg-primary-subtle text-primary' : 'bg-success-subtle text-success'} border">${a.actor_role}</span>`
                : '<span class="badge bg-light text-secondary border">System</span>';

            html += `
                <tr>
                    <td><small class="text-muted">${(a.timestamp || '').substring(11, 19)}</small></td>
                    <td><span class="defect-code-badge">${a.defect_code}</span></td>
                    <td>
                        <span class="badge bg-secondary me-1">${a.previous_status || 'INITIAL'}</span>
                        <i class="bi bi-arrow-right text-muted mx-1"></i>
                        <span class="badge bg-primary">${a.new_status}</span>
                    </td>
                    <td><small class="fw-bold">${escapeHtml(a.actor_email || a.assignee || 'User')}</small></td>
                    <td>${roleBadge}</td>
                    <td class="text-truncate" style="max-width: 250px;"><small>${escapeHtml(a.notes || 'Status updated')}</small></td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    }

    function updateDiscoveryView(data) {
        const kpis = data.kpis || {};
        setText('discoveryLeakageRate', `${kpis.defect_leakage_percentage}%`);

        const total = kpis.total_defects || 0;
        const phaseData = data.phase_distribution || {};
        const unitDefects = phaseData['Unit Testing'] || 0;
        const postUnit = total - unitDefects;

        setText('discoveryLeakageSummary', `${postUnit} of ${total} defects detected after Unit Testing`);

        // Discovery Phase Chart
        const phaseLabels = Object.keys(phaseData);
        const phaseValues = Object.values(phaseData);
        renderChart('chartDiscoveryPhase', {
            type: 'bar',
            data: {
                labels: phaseLabels,
                datasets: [{
                    label: 'Defects Discovered',
                    data: phaseValues,
                    backgroundColor: '#2563eb',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } },
                    x: { ticks: { font: { size: 10 } } }
                }
            }
        });

        // Environment Chart
        const envData = data.environment_distribution || {};
        const envLabels = Object.keys(envData);
        const envValues = Object.values(envData);
        renderChart('chartDiscoveryEnvironment', {
            type: 'bar',
            data: {
                labels: envLabels,
                datasets: [{
                    label: 'Environment Count',
                    data: envValues,
                    backgroundColor: '#10b981',
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } }
                }
            }
        });

        // Discovery Phase Table
        const tbody = document.getElementById('discoveryPhaseTableBody');
        if (tbody) {
            let html = '';
            for (const [phase, count] of Object.entries(phaseData)) {
                const pct = total > 0 ? ((count / total) * 100).toFixed(1) : '0.0';
                const isLeakage = phase !== 'Unit Testing';
                const leakageBadge = isLeakage
                    ? '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">Post-Unit Leakage</span>'
                    : '<span class="badge bg-success-subtle text-success border border-success-subtle">Base Phase (Internal)</span>';

                html += `
                    <tr>
                        <td class="fw-bold">${phase}</td>
                        <td>${getPhaseType(phase)}</td>
                        <td><span class="badge bg-light text-dark border px-2">${count}</span></td>
                        <td>${pct}%</td>
                        <td>${leakageBadge}</td>
                    </tr>
                `;
            }
            tbody.innerHTML = html;
        }
    }

    function updatePredictionView(prediction, kpis) {
        if (!prediction) return;

        const highest = prediction.highest_risk_module;
        if (highest) {
            setText('predHighestRiskModule', highest.module);
            const scoreBadge = document.getElementById('predHighestRiskScore');
            if (scoreBadge) {
                scoreBadge.textContent = `Risk Score: ${highest.risk_score} (${highest.risk_level})`;
                scoreBadge.className = `badge bg-${highest.badge_class} mt-1 fs-6`;
            }
        }

        // Module Risk Ranking Table
        const tbody = document.getElementById('predictionRankingTableBody');
        if (tbody && prediction.module_risk_ranking) {
            let html = '';
            prediction.module_risk_ranking.forEach((r, idx) => {
                html += `
                    <tr>
                        <td class="fw-bold text-muted">#${idx + 1}</td>
                        <td class="fw-bold text-dark">${r.module}</td>
                        <td><span class="fs-6 fw-bold text-primary">${r.risk_score}</span></td>
                        <td><span class="badge bg-${r.badge_class}">${r.risk_level}</span></td>
                        <td><span class="badge bg-danger-subtle text-danger border">${r.blocker_critical_count}</span></td>
                        <td><span class="badge bg-warning-subtle text-warning-emphasis border">${r.major_count}</span></td>
                        <td><span class="badge bg-info-subtle text-info-emphasis border">${r.minor_count}</span></td>
                        <td class="fw-bold">${r.defect_count}</td>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                <div class="progress flex-grow-1" style="height: 6px;">
                                    <div class="progress-bar bg-primary" style="width: ${r.concentration_percentage}%"></div>
                                </div>
                                <small class="text-secondary" style="min-width: 40px;">${r.concentration_percentage}%</small>
                            </div>
                        </td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        }

        // High-Risk Automated Alerts
        const alertsContainer = document.getElementById('predictionAlertsContainer');
        if (alertsContainer) {
            const alerts = prediction.high_risk_alerts || [];
            if (alerts.length === 0) {
                alertsContainer.innerHTML = '<div class="alert alert-success mb-0 small"><i class="bi bi-check-circle me-1"></i> No modules currently exceed critical risk thresholds.</div>';
            } else {
                let aHtml = '';
                alerts.forEach(a => {
                    aHtml += `
                        <div class="alert alert-danger d-flex align-items-start gap-2 mb-2 p-2">
                            <i class="bi bi-exclamation-octagon-fill text-danger fs-5 mt-1"></i>
                            <div>
                                <strong class="d-block">${a.module} (Risk Score: ${a.risk_score} - ${a.risk_level})</strong>
                                <span class="small">${a.alert_message}</span>
                            </div>
                        </div>
                    `;
                });
                alertsContainer.innerHTML = aHtml;
            }
        }

        // Recommended Regression Testing Focus Areas
        const recContainer = document.getElementById('predictionRecommendationsContainer');
        if (recContainer && prediction.recommendations) {
            let rHtml = '<div class="row g-3">';
            prediction.recommendations.forEach(rec => {
                let testList = '';
                rec.focus_areas.forEach(t => {
                    testList += `<li class="small mb-1"><i class="bi bi-arrow-right-short text-primary"></i> ${t}</li>`;
                });

                rHtml += `
                    <div class="col-md-4">
                        <div class="border rounded p-3 h-100 bg-light">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6 class="fw-bold mb-0 text-primary">${rec.module}</h6>
                                <span class="badge bg-secondary">Score: ${rec.risk_score}</span>
                            </div>
                            <ul class="list-unstyled mb-0">
                                ${testList}
                            </ul>
                        </div>
                    </div>
                `;
            });
            rHtml += '</div>';
            recContainer.innerHTML = rHtml;
        }
    }

    function updateReportsSummary(data) {
        const kpis = data.kpis || {};
        setText('repPrintTotal', kpis.total_defects || 0);
        setText('repPrintOpen', kpis.open_defects || 0);
        setText('repPrintResolved', kpis.resolved_defects || 0);
        setText('repPrintLeakage', `${kpis.defect_leakage_percentage || 0}%`);

        const tbody = document.getElementById('reportPrintTableBody');
        const ranking = (data.prediction && data.prediction.module_risk_ranking) || [];
        if (tbody) {
            let html = '';
            ranking.forEach(r => {
                html += `
                    <tr>
                        <td class="fw-bold">${r.module}</td>
                        <td class="fw-bold">${r.risk_score}</td>
                        <td>${r.risk_level}</td>
                        <td>${r.blocker_critical_count}</td>
                        <td>${r.major_count}</td>
                        <td>${r.minor_count}</td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        }
    }

    function renderChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (charts[canvasId]) {
            charts[canvasId].destroy();
        }

        const ctx = canvas.getContext('2d');
        charts[canvasId] = new Chart(ctx, config);
    }

    function getPhaseType(phase) {
        if (phase === 'Unit Testing' || phase === 'Code Review') return 'Pre-Integration / Static';
        if (phase === 'Integration Testing' || phase === 'System Testing') return 'Functional Test Cycle';
        if (phase === 'User Acceptance Testing') return 'Release Acceptance';
        return 'Specialized Audit';
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text !== undefined && text !== null ? text : '-';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    return {
        loadAnalytics
    };
})();
