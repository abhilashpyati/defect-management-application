# DefectGuard — Web-Based Defect Management Application

A full-stack, enterprise-grade Web-Based Defect Management Application built for the **VII Semester Software Testing Curriculum (Section 1.9)**. The system implements all **SIX** core defect management subprocesses with persistent SQLite database storage, dynamic RESTful APIs, a strict lifecycle state machine, real-time discovery leakage analytics, a prevention knowledge base, a transparent rule-based defect prediction engine, and **Role-Based Access Control (RBAC)** supporting **Admin**, **Developer**, and **Tester** roles in **Demo Mode**.

---

## 1. Role-Based Access Control (RBAC) & Demonstration System

The application features seamless demonstration role switching via a persistent selector in the top navigation bar without logging out.

### Demo Identities
| Role | Email | Display Name | Title | Primary Responsibility |
|---|---|---|---|---|
| **Admin** | `admin@demo.com` | Admin User | System Administrator | Complete system access, assigning developers, deleting defects, closing lifecycle, managing prevention base |
| **Developer** | `developer@demo.com` | Demo Developer | Software Developer | Investigating assigned defects, progressing to `IN PROGRESS`, adding technical notes, submitting code fixes (`RESOLVED`) |
| **Tester** | `tester@demo.com` | Demo Tester | QA Test Engineer | Reporting defects, defining reproduction steps, verifying resolved builds (`VERIFIED`), reopening regressions (`REOPENED`) |

### Role Permissions Matrix

| Capability / Action | Admin | Developer | Tester | Backend Enforcement |
|---|:---:|:---:|:---:|---|
| **View All Defects & History** | Yes (`can_view_all_defects: true`) | No (Assigned only) | No (Reported / Assigned Verification only) | Strict Backend Exact Identity Query Filtering |
| **Record New Defect** | Yes | No (403) | Yes | `POST /api/defects` (`@require_roles('Admin', 'Tester')`) |
| **Assign Developers** | Yes | No (403) | No (Creation is `Unassigned`; 403 on assign) | `POST /api/defects` (Tester creations are `Unassigned`), `PUT /api/defects/<id>`, `PATCH /api/defects/<id>` (Admin only) |
| **Assign QA Verification** | Yes | No (403) | No (403) | `PUT /api/defects/<id>`, `PATCH /api/defects/<id>` (Admin only) |
| **Alter Severity / Priority** | Yes | No (403) | No (403) | Field allowlist validation on `PUT` and `PATCH` |
| **Move `NEW` $\rightarrow$ `ASSIGNED`** | Yes | No (403) | No (403) | State Machine + Role Validator |
| **Move `ASSIGNED` $\rightarrow$ `IN PROGRESS`** | Yes | Yes (Exact Assignee) | No (403) | State Machine + Developer Assignment Check |
| **Move `IN PROGRESS` $\rightarrow$ `RESOLVED`** | Yes | Yes (Exact Assignee) | No (403) | State Machine + Developer Assignment Check |
| **Move `RESOLVED` $\rightarrow$ `VERIFIED`** | Yes | No (403) | Yes (Authorized Tester) | State Machine + Tester Authorization |
| **Move `RESOLVED` $\rightarrow$ `REOPENED`** | Yes | No (403) | Yes (Reason Required) | State Machine + Mandatory `reopening_reason` |
| **Move `REOPENED` $\rightarrow$ `ASSIGNED`** | Yes | No (403) | No (403) | State Machine + Admin Authorization (Only Admin assigns/reassigns) |
| **Move `VERIFIED` $\rightarrow$ `CLOSED`** | Yes | No (403) | No (403) | State Machine + Admin Authorization |
| **Delete Defect (Soft Deletion)** | Yes | No (403) | No (403) | `DELETE /api/defects/<id>` (`@require_roles('Admin')`) |
| **Manage Prevention Base** | Yes | No (403) | No (403) | `POST/PUT/DELETE /api/prevention` (`@require_roles('Admin')`) |
| **Export All Defects (CSV)** | Yes | No (Assigned only) | No (Authorized only) | `/api/export/csv` (Role-scoped export) |
| **View System Analytics** | Yes | No (Assigned only) | No (Authorized only) | `/api/analytics` (Role-isolated dataset) |

---

## 2. Six Core Defect Management Subprocesses

### Subprocess 1: Defect Prevention
- **Root Cause Analysis Records**: Catalogs historical root causes, vulnerability patterns, and architectural flaws.
- **Categorized Prevention Rules**: Grouped by functional module (`Authentication`, `Payments`, `Cart & Checkout`, `Inventory`, `Notification Service`, `API Gateway`) and engineering category (`Security`, `Concurrency & Idempotency`, `Data Integrity`, etc.).
- **Interactive Knowledge Base**: Search, filter, add, edit, and delete prevention records (management restricted to Admin).
- **Recurring Defect Identification**: Automated clustering of repeating failure modes with actionable prevention checklists.

### Subprocess 2: Defect Discovery
- **Phase Mapping**: Tracks discovery across `Unit Testing`, `Integration Testing`, `System Testing`, `User Acceptance Testing`, `Code Review`, and `Security Audit`.
- **Environment Context**: Categorizes defect occurrence in `Development`, `QA Staging`, `Pre-Production`, and `Production`.
- **Curriculum Leakage Formula**:
  $$\text{Defect Leakage (\%)} = \left(\frac{\text{Defects Discovered After Unit Testing}}{\text{Total Defects}}\right) \times 100$$
- **Visual Distribution**: Real-time Chart.js phase and environment leakage breakdowns.

### Subprocess 3: Defect Recording & Reporting
- **Standardized Defect Schema**: Defect ID (`DEF-101`, `DEF-102`...), Title, Description, Steps to Reproduce, Expected vs. Actual Behaviour, Module, Type, Severity, Priority, Discovery Phase, Environment, Reporter, Assignee, and Timestamps.
- **Server-Side Validation**: Rejects empty mandatory fields, non-conforming severity/priority values, or invalid modules.
- **Full Operational Support**: Create, view details modal, edit attributes, full-text search, multi-field filtering, soft deletion with audit preservation, RFC 4180 CSV export, and printable summary sheet.

### Subprocess 4: Defect Classification
Implements 4 orthogonal classification dimensions:
1. **Severity (Impact)**: `Blocker`, `Critical`, `Major`, `Minor`, `Trivial`.
2. **Priority (Urgency)**: `P1 – High`, `P2 – Medium`, `P3 – Low`.
3. **Defect Type**: `Functional`, `UI/UX`, `Backend/API`, `Security`, `Database`, `Performance`.
4. **Functional Module**: `Authentication`, `Payments`, `Cart & Checkout`, `Inventory`, `Notification Service`, `API Gateway`.

### Subprocess 5: Defect Resolution & Lifecycle
- **Strict State Machine**:
  $$\text{NEW} \longrightarrow \text{ASSIGNED} \longrightarrow \text{IN PROGRESS} \longrightarrow \text{RESOLVED} \longrightarrow \text{VERIFIED} \longrightarrow \text{CLOSED}$$
  $$\text{RESOLVED} \longrightarrow \text{REOPENED} \longrightarrow \text{ASSIGNED}$$
- **Prohibited Transitions**: Direct illegal jumps (e.g. `NEW` $\rightarrow$ `CLOSED` or `NEW` $\rightarrow$ `RESOLVED`) are strictly blocked by the backend with HTTP 400.
- **Audit History**: Every state change records previous status, new status, developer assignee, resolution notes, optional git commit reference, actor email, actor role, and an ISO timestamp in `defect_history`.

### Subprocess 6: Defect Prediction & Statistical Analytics
- **Rule-Based Weighted Severity Engine**:
  - Blocker = 3
  - Critical = 3
  - Major = 2
  - Minor = 1
  - Trivial = 0
  $$\text{Module Risk Score} = (3 \times \text{Blocker/Critical}) + (2 \times \text{Major}) + (1 \times \text{Minor})$$
- **Deterministic Transparency**: Rule-based algorithm explicitly adhering to Section 1.9 formula (no black-box machine learning claims).
- **Core Statistical Metrics**: Total defects, Open defects, In Progress, Resolved, Critical/Blocker count, Defect Leakage %, Open-to-Resolved velocity ratio, and Mean Time to Resolve (MTTR).

---

## 3. Technology Stack

- **Backend**: Python 3.11+, Flask 3.1, SQLite3
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons, Chart.js 4.4
- **Testing**: pytest 9.1
- **Deployment**: Gunicorn, Render (`render.yaml`, `Procfile`)

---

## 4. Project Structure

```
defect-management-dashboard/
│
├── app.py                      # Flask application factory, error handlers & blueprints
├── config.py                   # Environment configurations (Dev, Test, Prod)
├── requirements.txt            # Python dependencies
├── Procfile                    # Process definition for Gunicorn
├── render.yaml                 # Infrastructure-as-code for Render deployment
├── .gitignore                  # Git ignore rules
├── README.md                   # System documentation
│
├── database/
│   ├── __init__.py
│   ├── db.py                   # SQLite connection helpers, schema migrations & seeding
│   ├── schema.sql              # DDL table creation and index definitions
│   └── defects.db              # SQLite persistence database file
│
├── services/
│   ├── __init__.py
│   ├── auth_service.py         # RBAC decorators, role permissions & user session logic
│   ├── defect_service.py       # Defect CRUD, auto-ID generation, server validation
│   ├── lifecycle_service.py    # Defect lifecycle state machine & audit logger
│   ├── prevention_service.py   # Root-cause analysis & prevention guidelines
│   └── prediction_service.py   # Rule-based risk scoring & role dashboard metrics
│
├── routes/
│   ├── __init__.py
│   ├── auth_routes.py          # /api/auth/session & /api/auth/switch-role endpoints
│   ├── defect_routes.py        # /api/defects endpoints (RBAC protected)
│   ├── prevention_routes.py    # /api/prevention endpoints (Admin protected)
│   ├── analytics_routes.py     # /api/analytics & /api/health endpoints
│   └── export_routes.py        # /api/export/csv endpoint
│
├── templates/
│   └── index.html              # Single-page SaaS dashboard interface
│
├── static/
│   ├── css/
│   │   └── style.css           # Clean modern SaaS styling & print styles
│   └── js/
│       ├── dashboard.js        # Core app controller, role switching & toasts
│       ├── defects.js          # Defect tracker, tables, modals & lifecycle forms
│       ├── analytics.js        # Chart.js visualizations & role-specific dashboards
│       └── prevention.js       # Prevention knowledge base controller
│
└── tests/
    ├── __init__.py
    ├── conftest.py             # Temporary SQLite database fixtures & test client
    ├── test_defects.py         # TC-01 to TC-09 (Defect CRUD, validation, filters)
    ├── test_lifecycle.py       # TC-10 to TC-13 (State machine, transitions, audit)
    ├── test_prevention.py      # TC-14 to TC-15 (Prevention rules & guidelines)
    ├── test_analytics.py       # TC-16 to TC-22 (Risk scores, leakage, CSV, health)
    └── test_roles.py           # Role switching, RBAC permissions & end-to-end workflow
```

---

## 5. Database Schema & Architecture

The database uses SQLite with foreign keys enforced (`PRAGMA foreign_keys = ON;`). Data integrity is preserved across restarts with automatic, non-destructive schema migrations.

### Tables & Schema:

1. **`users`** (Demo Identities):
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `email`: TEXT UNIQUE NOT NULL
   - `name`: TEXT NOT NULL
   - `role`: TEXT NOT NULL (`Admin`, `Developer`, `Tester`)
   - `title`: TEXT NOT NULL
   - `created_at`: TEXT NOT NULL

2. **`defects`**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `defect_code`: TEXT UNIQUE NOT NULL (`DEF-101`, `DEF-102`...)
   - `title`, `description`, `steps_to_reproduce`, `expected_behavior`, `actual_behavior`: TEXT NOT NULL
   - `module`, `type`, `severity`, `priority`, `discovery_phase`, `environment`: TEXT NOT NULL
   - `status`: TEXT NOT NULL DEFAULT 'NEW'
   - `reporter`: TEXT NOT NULL (Exact identity of defect creator)
   - `assignee`: TEXT NOT NULL (Assigned developer identity)
   - `verification_assignee`: TEXT (Explicitly assigned QA Tester for verification)
   - `prevention_guideline`: TEXT
   - `investigation_notes`: TEXT (Technical root cause findings by Developer)
   - `resolution_notes`: TEXT (Technical solution details by Developer)
   - `commit_reference`: TEXT (Git commit SHA reference by Developer)
   - `verification_notes`: TEXT (QA verification test evidence by Tester)
   - `reopening_reason`: TEXT (Mandatory reproduction rationale for reopenings)
   - `is_deleted`: INTEGER NOT NULL DEFAULT 0 (Soft-deletion flag)
   - `deleted_at`: TEXT (Soft-deletion timestamp)
   - `created_at`, `updated_at`: TEXT NOT NULL
   - `resolved_at`, `closed_at`: TEXT

3. **`prevention_guidelines`**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `root_cause`, `guideline`, `module`, `category`, `created_at`: TEXT NOT NULL

4. **`defect_history`**:
   - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
   - `defect_id`: INTEGER NOT NULL (FK $\rightarrow$ `defects.id`)
   - `action`: TEXT (`CREATED`, `ASSIGNED`, `VERIFICATION_ASSIGNED`, `IN PROGRESS`, `RESOLVED`, `VERIFIED`, `REOPENED`, `CLOSED`, `DELETED`, `FIELD_UPDATE`)
   - `previous_status`, `new_status`: TEXT NOT NULL
   - `previous_value`, `new_value`: TEXT
   - `assignee`, `notes`, `comment`: TEXT
   - `actor_email`, `actor_role`: TEXT NOT NULL (Sourced strictly from authenticated session)
   - `timestamp`: TEXT NOT NULL

### Soft Deletion & Audit History Preservation
Defects utilize soft deletion (`is_deleted = 1, deleted_at = <timestamp>`). Soft-deleted defects are hidden from Developers and Testers across listings, searches, direct retrieval, and CSV exports. **Audit history is permanently preserved** and accessible exclusively to Admin for compliance and traceability.

---

## 6. REST API Endpoints

| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/` | All | Serves web dashboard frontend |
| `GET` | `/api/health` | All | Health check & connection status |
| `GET` | `/api/auth/session` | All | Returns active demo identity, role & permissions |
| `POST` | `/api/auth/switch-role` | All | Switches active demo role (`Admin`, `Developer`, `Tester`) |
| `GET` | `/api/auth/roles` | All | Lists all available demo roles |
| `GET` | `/api/defects` | Role-Scoped | List defects (Developer: assigned only; Tester: reported / verification-assigned only) |
| `POST` | `/api/defects` | Admin, Tester | Create new defect report (Developer returns 403) |
| `GET` | `/api/defects/<id>` | Role-Scoped | Retrieve specific defect with role-filtered transitions (Admin supports `?include_deleted=true`) |
| `PUT` | `/api/defects/<id>` | Role-Aware | Edit defect details with strict field allowlists |
| `PATCH` | `/api/defects/<id>` | Role-Aware | State-machine transition validated against role rules and note separation |
| `DELETE` | `/api/defects/<id>` | Admin Only | Soft-delete defect (Developer and Tester return 403) |
| `GET` | `/api/defects/<id>/history` | Role-Scoped | Audit lifecycle history with actor identity & role |
| `GET` | `/api/prevention` | All | List prevention guidelines |
| `POST` | `/api/prevention` | Admin Only | Create prevention guideline (Dev/Tester return 403) |
| `PUT` | `/api/prevention/<id>` | Admin Only | Update prevention guideline (Dev/Tester return 403) |
| `DELETE` | `/api/prevention/<id>` | Admin Only | Delete prevention guideline (Dev/Tester return 403) |
| `GET` | `/api/prevention/summary` | All | Distribution & recurring problem clusters |
| `GET` | `/api/analytics` | Role-Scoped | Analytics & role-isolated dashboard views |
| `GET` | `/api/export/csv` | Role-Scoped | Download role-authorized RFC 4180 CSV dataset |

---

## 7. Step-by-Step Multi-Role Demonstration Workflow

Follow these steps in the web interface to demonstrate the complete collaborative workflow across all three roles:

1. **Step 1: Switch to Tester**
   - Click the **Role** dropdown in the top navbar and select **Tester**.
   - Notice the top badge displays `tester@demo.com` and the sidebar adapts to QA Tester view.
2. **Step 2: Report a New Defect**
   - Click **Record New Defect** in the sidebar.
   - Enter defect title: `Concurrent Checkout Race Condition in Inventory`.
   - Select Module: `Inventory`, Type: `Functional`, Severity: `Critical`, Priority: `P1 – High`.
   - Fill reproduction steps and expected/actual behaviour. Click **Save & Log Defect**.
   - The defect is logged with status `NEW`.
3. **Step 3: Switch to Admin**
   - Click the **Role** dropdown and select **Admin**.
   - Notice the Overview Dashboard displays system-wide KPIs, critical alerts, and developer workload.
   - Open **Defect Tracker**, locate the newly reported defect, and click the **Update Lifecycle** icon.
   - Transition status from `NEW` to `ASSIGNED`, set Assignee Developer to `developer@demo.com`, and QA Verification Assignee to `tester@demo.com`. Click **Confirm Transition**.
4. **Step 4: Switch to Developer**
   - Click the **Role** dropdown and select **Developer**.
   - Notice the Developer Dashboard displays **Assigned to Me**, priority breakdown, and your assigned task queue.
   - Notice **Record New Defect** is removed from the sidebar.
   - In the assigned queue or Tracker, click **Update Lifecycle**:
     - Select `IN PROGRESS`, enter investigation notes, and confirm.
     - Once fix is coded, click **Update Lifecycle** again: select `RESOLVED`, enter resolution notes and git commit ref (e.g. `commit 8f2b1a9c`), and confirm.
5. **Step 5: Switch Back to Tester**
   - Click the **Role** dropdown and select **Tester**.
   - The Tester Dashboard highlights the **Resolved Defects Awaiting Verification** table.
   - Click **Verify / Reopen** on the resolved defect:
     - Select `REOPENED` without a reason: notice the mandatory reason validation error.
     - Enter reopening reason and confirm transition to `REOPENED`.
     - After developer re-resolves, select `VERIFIED`, enter verification notes, and confirm.
6. **Step 6: Switch to Admin and Close Defect**
   - Click the **Role** dropdown and select **Admin**.
   - Open the verified defect in the tracker, click **Update Lifecycle**, select `CLOSED`, and confirm.
   - Click **View Details** $\rightarrow$ **Lifecycle History & Audit** tab to inspect the complete immutable audit trail showing each transition with timestamp, actor email, and actor role (`Tester`, `Admin`, `Developer`).

---

## 8. Automated Test Suite (pytest)

The test suite validates all 22 required curriculum test cases plus 26 comprehensive role-based, security, visibility, and lifecycle tests:

```bash
python -m pytest -v
```

### Verified Test Results (48 passed in 8.92s):
- `tests/test_defects.py`: 9 Passed (TC-01 through TC-09)
- `tests/test_lifecycle.py`: 4 Passed (TC-10 through TC-13)
- `tests/test_prevention.py`: 2 Passed (TC-14, TC-15)
- `tests/test_analytics.py`: 7 Passed (TC-16 through TC-22)
- `tests/test_roles.py`: 26 Passed (Role switching, permissions, field allowlists, note separation, verification assignment, activity filtering, zero analytics, deleted restrictions, actor validation, defect retrieval actor validation, assignment validation without default identities, workflow)

---

## 9. Installation and Execution Guide

### 1. Create and Activate a Virtual Environment
```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Project Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize the Database (Optional)
The application automatically executes database migrations and populates demonstration records upon startup. To manually initialize:
```bash
python -c "from database.db import init_db; init_db('database/defects.db', seed_if_empty=True)"
```

### 4. Start the Flask Application
```bash
python app.py
```
Or for production WSGI server:
```bash
gunicorn app:app
```

### 5. Access the Web Dashboard
Open your web browser and navigate to:
```
http://localhost:5000
```

### 6. Run the Complete Test Suite
```bash
python -m pytest -v
```
