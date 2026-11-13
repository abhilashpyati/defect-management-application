/**
 * DefectGuard - Core Application Dashboard Controller
 * Supports Role Switching (Admin, Developer, Tester) in Demo Mode
 */

const App = (function () {
    const views = {
        'dashboard': {
            title: 'Overview Dashboard',
            subtitle: 'Real-Time Defect Lifecycle & Role-Based Workspace'
        },
        'tracker': {
            title: 'Defect Tracker',
            subtitle: 'Repository Search, Filters & Lifecycle State Machine'
        },
        'report': {
            title: 'Record New Defect',
            subtitle: 'Subprocess 3: Mandatory Validated Defect Logging'
        },
        'discovery': {
            title: 'Discovery Analytics',
            subtitle: 'Subprocess 2: Phase Distribution & Defect Leakage Analysis'
        },
        'prevention': {
            title: 'Prevention Knowledge Base',
            subtitle: 'Subprocess 1: Root Cause Analysis & Lessons Learned'
        },
        'prediction': {
            title: 'Defect Prediction Engine',
            subtitle: 'Subprocess 6: Rule-Based Module Risk Scoring (Curriculum 1.9)'
        },
        'reports': {
            title: 'Reports & Export',
            subtitle: 'RFC 4180 CSV Data Export & Printable Management Summary'
        }
    };

    let currentView = 'dashboard';
    let currentUser = {
        role: 'Admin',
        email: 'admin@demo.com',
        name: 'Admin User',
        title: 'System Administrator'
    };
    let currentPermissions = {};

    async function init() {
        setupNavigation();
        setupRoleSwitcher();
        setupGlobalEvents();

        // 1. Fetch active session user and role
        await fetchSession();

        // 2. Initial Data Load
        refreshAllData();
    }

    async function fetchSession() {
        try {
            const res = await fetch('/api/auth/session');
            const data = await res.json();
            if (res.ok && data.success) {
                currentUser = data.user;
                currentPermissions = data.permissions;
                applyRoleUI();
            }
        } catch (err) {
            console.error('fetchSession error:', err);
        }
    }

    function setupRoleSwitcher() {
        const roleSelect = document.getElementById('roleSelector');
        roleSelect?.addEventListener('change', async (e) => {
            const targetRole = e.target.value;
            await switchRole(targetRole);
        });
    }

    async function switchRole(newRole) {
        try {
            const res = await fetch('/api/auth/switch-role', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role: newRole })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                currentUser = data.user;
                currentPermissions = data.permissions;
                applyRoleUI();
                showToast(`Switched active demo role to ${currentUser.role} (${currentUser.email})`, 'success', 'Role Updated');
                refreshAllData();
            } else {
                showToast(data.error || 'Failed to switch role.', 'danger');
            }
        } catch (err) {
            showToast('Network error while switching role: ' + err.message, 'danger');
        }
    }

    function applyRoleUI() {
        const role = currentUser.role;

        // 1. Update Selector and Badges
        const selector = document.getElementById('roleSelector');
        if (selector && selector.value !== role) selector.value = role;

        const idBadge = document.getElementById('currentRoleIdentityBadge');
        if (idBadge) {
            idBadge.textContent = `${currentUser.email}`;
            idBadge.className = `badge font-monospace small ${role === 'Admin' ? 'bg-danger-subtle text-danger border border-danger-subtle' : role === 'Developer' ? 'bg-primary-subtle text-primary border border-primary-subtle' : 'bg-success-subtle text-success border border-success-subtle'}`;
        }

        const sidebarTitle = document.getElementById('sidebarRoleTitle');
        if (sidebarTitle) sidebarTitle.textContent = `Role: ${role}`;

        // 2. Dynamic Sidebar Navigation Visibility
        document.querySelectorAll('.sidebar-nav-item').forEach(item => {
            const allowed = item.getAttribute('data-role-perm');
            if (allowed) {
                const allowedRoles = allowed.split(',').map(r => r.trim());
                if (!allowedRoles.includes(role)) {
                    item.classList.add('d-none');
                } else {
                    item.classList.remove('d-none');
                }
            }
        });

        // 3. Topbar Quick New Defect Button Visibility
        const topbarNewDefectBtn = document.getElementById('topbarNewDefectBtn');
        if (topbarNewDefectBtn) {
            if (role === 'Developer') {
                topbarNewDefectBtn.classList.add('d-none');
            } else {
                topbarNewDefectBtn.classList.remove('d-none');
            }
        }

        // 4. Tracker "Report New Defect" button
        const trackerReportBtn = document.getElementById('trackerReportNewBtn');
        if (trackerReportBtn) {
            if (role === 'Developer') {
                trackerReportBtn.classList.add('d-none');
            } else {
                trackerReportBtn.classList.remove('d-none');
            }
        }

        // 5. If Developer is on 'report' or 'prevention' view, redirect to dashboard
        if ((role === 'Developer' && (currentView === 'report' || currentView === 'prevention')) ||
            (role === 'Tester' && currentView === 'prediction')) {
            // Keep on current view or dashboard
            if (currentView === 'report') navigateTo('dashboard');
        }

        // 6. Toggle Role Dashboard View Containers
        const adminView = document.getElementById('adminDashboardView');
        const devView = document.getElementById('developerDashboardView');
        const testerView = document.getElementById('testerDashboardView');

        if (adminView) adminView.classList.toggle('d-none', role !== 'Admin');
        if (devView) devView.classList.toggle('d-none', role !== 'Developer');
        if (testerView) testerView.classList.toggle('d-none', role !== 'Tester');

        // Update nav titles
        const navDash = document.getElementById('navDashboardLabel');
        if (navDash) {
            navDash.textContent = role === 'Admin' ? 'Overview Dashboard' :
                                  role === 'Developer' ? 'Developer Dashboard' : 'QA Tester Dashboard';
        }

        // Adjust Prevention Base add buttons and defect forms
        if (typeof PreventionModule !== 'undefined') {
            PreventionModule.applyRoleUI(role);
        }
        if (typeof DefectsModule !== 'undefined' && DefectsModule.applyRoleUI) {
            DefectsModule.applyRoleUI(role);
        }
    }

    function setupNavigation() {
        const navItems = document.querySelectorAll('.sidebar-nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const targetView = item.getAttribute('data-view');
                if (targetView) {
                    navigateTo(targetView);
                }
            });
        });

        document.getElementById('topbarRefreshBtn')?.addEventListener('click', () => {
            refreshAllData();
            showToast('Application metrics refreshed successfully.', 'info', 'Refreshed');
        });

        document.getElementById('topbarNewDefectBtn')?.addEventListener('click', () => {
            navigateTo('report');
        });
    }

    function navigateTo(viewName) {
        if (!views[viewName]) return;

        currentView = viewName;

        document.querySelectorAll('.sidebar-nav-item').forEach(el => {
            el.classList.toggle('active', el.getAttribute('data-view') === viewName);
        });

        document.querySelectorAll('.view-section').forEach(sec => {
            sec.classList.remove('active-view');
        });

        const activeSec = document.getElementById(`view-${viewName}`);
        if (activeSec) {
            activeSec.classList.add('active-view');
        }

        const titleEl = document.getElementById('currentViewTitle');
        const subtitleEl = document.getElementById('currentViewSubtitle');
        if (titleEl) {
            if (viewName === 'dashboard') {
                titleEl.textContent = currentUser.role === 'Admin' ? 'Admin Overview Dashboard' :
                                      currentUser.role === 'Developer' ? 'Developer Workspace Dashboard' : 'QA Tester Dashboard';
            } else {
                titleEl.textContent = views[viewName].title;
            }
        }
        if (subtitleEl) subtitleEl.textContent = views[viewName].subtitle;

        if (viewName === 'reports') {
            const printDate = document.getElementById('reportPrintDate');
            if (printDate) printDate.textContent = new Date().toLocaleString();
        }
    }

    function refreshAllData() {
        if (typeof AnalyticsModule !== 'undefined') {
            AnalyticsModule.loadAnalytics();
        }
        if (typeof DefectsModule !== 'undefined') {
            DefectsModule.loadDefects();
        }
        if (typeof PreventionModule !== 'undefined') {
            PreventionModule.loadPrevention();
        }
    }

    function setupGlobalEvents() {}

    function showToast(message, type = 'info', title = '') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const bgClass = type === 'success' ? 'bg-success text-white' :
                        type === 'danger' || type === 'error' ? 'bg-danger text-white' :
                        type === 'warning' ? 'bg-warning text-dark' : 'bg-primary text-white';

        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center ${bgClass} border-0 shadow" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        ${title ? `<strong>${title}:</strong> ` : ''}${message}
                    </div>
                    <button type="button" class="btn-close ${type !== 'warning' ? 'btn-close-white' : ''} me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', toastHtml);
        const toastElement = document.getElementById(toastId);
        if (toastElement && window.bootstrap) {
            const bsToast = new bootstrap.Toast(toastElement, { delay: 4000 });
            bsToast.show();
            toastElement.addEventListener('hidden.bs.toast', () => {
                toastElement.remove();
            });
        }
    }

    return {
        init,
        navigateTo,
        refreshAllData,
        showToast,
        switchRole,
        getCurrentUser: () => currentUser,
        getCurrentRole: () => currentUser.role,
        getPermissions: () => currentPermissions,
        getCurrentView: () => currentView
    };
})();
