import os
import sqlite3
from datetime import datetime, timezone, timedelta
from flask import g, current_app

def get_db(db_path=None):
    """
    Get a database connection. If in Flask request context, store connection in g.
    """
    if db_path is None:
        if current_app:
            db_path = current_app.config.get('DATABASE_PATH')
        else:
            db_path = os.path.join(os.path.dirname(__file__), 'defects.db')

    # In Flask context
    if current_app and hasattr(g, '_database') and getattr(g, '_db_path', None) == db_path:
        return g._database

    # Connect to SQLite
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True) if db_path != ':memory:' else None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    if current_app:
        g._database = conn
        g._db_path = db_path

    return conn

def close_db(e=None):
    """Close db connection stored in g."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        g._database = None

def run_migrations(conn):
    """
    Safely apply schema migrations to preserve existing database records.
    Adds actor_email, actor_role, action, previous_value, new_value, comment to defect_history,
    adds is_deleted, deleted_at, verification_notes to defects, and creates users table.
    """
    cursor = conn.cursor()

    # 1. Ensure users table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # 2. Check defects columns
    cursor.execute("PRAGMA table_info(defects)")
    defect_cols = [row[1] for row in cursor.fetchall()]

    if 'is_deleted' not in defect_cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")
    if 'deleted_at' not in defect_cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN deleted_at TEXT")
    if 'verification_notes' not in defect_cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN verification_notes TEXT")
    if 'verification_assignee' not in defect_cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN verification_assignee TEXT")
    if 'investigation_notes' not in defect_cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN investigation_notes TEXT")
    if 'reopening_reason' not in defect_cols:
        cursor.execute("ALTER TABLE defects ADD COLUMN reopening_reason TEXT")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_defects_deleted ON defects(is_deleted)")

    # 3. Check defect_history columns
    cursor.execute("PRAGMA table_info(defect_history)")
    existing_cols = [row[1] for row in cursor.fetchall()]

    if 'actor_email' not in existing_cols:
        cursor.execute("ALTER TABLE defect_history ADD COLUMN actor_email TEXT")
    if 'actor_role' not in existing_cols:
        cursor.execute("ALTER TABLE defect_history ADD COLUMN actor_role TEXT")
    if 'action' not in existing_cols:
        cursor.execute("ALTER TABLE defect_history ADD COLUMN action TEXT")
    if 'previous_value' not in existing_cols:
        cursor.execute("ALTER TABLE defect_history ADD COLUMN previous_value TEXT")
    if 'new_value' not in existing_cols:
        cursor.execute("ALTER TABLE defect_history ADD COLUMN new_value TEXT")
    if 'comment' not in existing_cols:
        cursor.execute("ALTER TABLE defect_history ADD COLUMN comment TEXT")

    # 4. Seed demo users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        demo_users = [
            ('admin@demo.com', 'Admin User', 'Admin', 'System Administrator', now),
            ('developer@demo.com', 'Demo Developer', 'Developer', 'Software Developer', now),
            ('tester@demo.com', 'Demo Tester', 'Tester', 'QA Test Engineer', now)
        ]
        cursor.executemany("""
            INSERT INTO users (email, name, role, title, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, demo_users)

    conn.commit()

def init_db(db_path, seed_if_empty=True):
    """
    Execute schema.sql to create tables and optionally seed realistic records.
    """
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True) if db_path != ':memory:' else None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    with conn:
        conn.executescript(schema_sql)

    # Run safe non-destructive migrations
    run_migrations(conn)

    if seed_if_empty:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM defects")
        count = cursor.fetchone()[0]
        if count == 0:
            seed_demonstration_data(conn)

    conn.close()

def seed_demonstration_data(conn):
    """
    Seed realistic demonstration data covering all six defect management subprocesses.
    Only called when the database is freshly initialized and empty.
    """
    now = datetime.now(timezone.utc)
    t1 = (now - timedelta(days=12)).strftime('%Y-%m-%d %H:%M:%S')
    t2 = (now - timedelta(days=9)).strftime('%Y-%m-%d %H:%M:%S')
    t3 = (now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    t4 = (now - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')
    t5 = (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    t6 = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
    t7 = (now - timedelta(hours=18)).strftime('%Y-%m-%d %H:%M:%S')
    t8 = now.strftime('%Y-%m-%d %H:%M:%S')

    # 1. Prevention Guidelines
    prevention_records = [
        (
            "Missing validation of expired authentication tokens in authorization header.",
            "Centralize token validation in API Gateway middleware with boundary unit tests for exp and nbf claims.",
            "Authentication",
            "Security & Authorization",
            t1
        ),
        (
            "Double charge vulnerability when user double-clicks checkout button.",
            "Implement idempotent request keys (Idempotency-Key header) and Redis-backed distributed locks on payment capture.",
            "Payments",
            "Concurrency & Idempotency",
            t1
        ),
        (
            "Race condition leading to negative stock counts during flash sales.",
            "Enforce atomic database updates (UPDATE inventory SET stock = stock - qty WHERE stock >= qty) and pessimistic row locks.",
            "Inventory",
            "Data Integrity",
            t2
        ),
        (
            "Unsanitized customer input in cart note rendering reflected XSS.",
            "Apply strict HTML context-aware encoding and enforce strict Content Security Policy (CSP).",
            "Cart & Checkout",
            "Input Validation",
            t3
        ),
        (
            "Notification service cascading failure when downstream SMTP server times out.",
            "Implement circuit breaker pattern and isolate third-party notification calls in asynchronous background queues with exponential backoff.",
            "Notification Service",
            "Resilience & Fault Tolerance",
            t3
        ),
        (
            "API Gateway thread exhaustion due to unbounded request payload sizes.",
            "Enforce strict request payload size limits (max 10MB) and rate-limiting per client IP and authenticated tenant.",
            "API Gateway",
            "Rate Limiting & Boundary Checks",
            t4
        ),
        (
            "Session fixation on login endpoint when session ID was not regenerated.",
            "Regenerate session identifiers upon any authentication state change and set Secure, HttpOnly, and SameSite=Lax flags.",
            "Authentication",
            "Session Management",
            t4
        ),
        (
            "Float precision loss calculating currency conversions and multi-tier tax.",
            "Use fixed-point Decimal types for all monetary arithmetic instead of IEEE-754 floating point numbers.",
            "Payments",
            "Calculation Precision",
            t5
        )
    ]

    with conn:
        conn.executemany("""
            INSERT INTO prevention_guidelines (root_cause, guideline, module, category, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, prevention_records)

    # 2. Defects Seed Data (includes developer@demo.com assignments)
    defects_data = [
        (
            "DEF-101",
            "JWT token expiration bypass when system clock skewed",
            "System fails to reject JWT tokens whose exp timestamp has lapsed by less than 5 minutes due to missing clock skew tolerance validation.",
            "1. Generate JWT with exp = now - 60s.\n2. Dispatch GET /api/v1/user/profile with Bearer token.\n3. Observe HTTP 200 response.",
            "HTTP 401 Unauthorized with token_expired code.",
            "HTTP 200 OK allowing unauthorized access.",
            "Authentication",
            "Security",
            "Critical",
            "P1 – High",
            "Security Audit",
            "QA Staging",
            "RESOLVED",
            "tester@demo.com",
            "developer@demo.com",
            "Centralize token validation in API Gateway middleware with boundary unit tests for exp and nbf claims.",
            "Implemented strict jwt.verify with nbf and zero clock tolerance window.",
            "commit 8f2b1a9c",
            t1, t4, t4, None
        ),
        (
            "DEF-102",
            "Duplicate payment transactions on rapid double-submit",
            "Submitting the payment form twice within 400ms creates two separate capture requests to Stripe gateway.",
            "1. Fill credit card details.\n2. Rapidly double-click 'Pay $149.00'.\n3. Check merchant dashboard.",
            "Single transaction charged; second request blocked or deduplicated.",
            "Two distinct transaction charges recorded on user card.",
            "Payments",
            "Functional",
            "Blocker",
            "P1 – High",
            "Integration Testing",
            "Pre-Production",
            "IN PROGRESS",
            "tester@demo.com",
            "developer@demo.com",
            "Implement idempotent request keys (Idempotency-Key header) and Redis-backed distributed locks on payment capture.",
            "Adding Redis idempotency filter on /api/v1/payments/charge.",
            None,
            t2, t5, None, None
        ),
        (
            "DEF-103",
            "Negative stock allocated when two concurrent orders exceed inventory",
            "When two users purchase the final item simultaneously, both checkouts succeed resulting in stock of -1.",
            "1. Set item stock to 1.\n2. Concurrently submit 2 checkout requests via JMeter.\n3. Inspect inventory DB table.",
            "First transaction succeeds; second receives out of stock error.",
            "Both orders succeed; inventory table shows stock = -1.",
            "Inventory",
            "Database",
            "Critical",
            "P1 – High",
            "System Testing",
            "QA Staging",
            "NEW",
            "tester@demo.com",
            "Elena Backend Dev",
            "Enforce atomic database updates (UPDATE inventory SET stock = stock - qty WHERE stock >= qty) and pessimistic row locks.",
            None,
            None,
            t3, t3, None, None
        ),
        (
            "DEF-104",
            "Cart checkout button unresponsive on iOS Safari viewport",
            "Checkout button rendered under mobile sticky footer due to z-index and safe-area-inset CSS conflict.",
            "1. Open Safari on iPhone 14 Simulator.\n2. Add item to cart.\n3. Attempt to tap 'Proceed to Checkout'.",
            "Checkout button is tappable and navigates to payment.",
            "Button is obscured and untappable.",
            "Cart & Checkout",
            "UI/UX",
            "Minor",
            "P2 – Medium",
            "User Acceptance Testing",
            "Pre-Production",
            "ASSIGNED",
            "tester@demo.com",
            "developer@demo.com",
            None,
            "Carlos assigned to fix viewport safe-area CSS rules.",
            None,
            t4, t5, None, None
        ),
        (
            "DEF-105",
            "Email notification timeout blocks user registration flow",
            "If SendGrid API response exceeds 5 seconds, user registration throws HTTP 504 Gateway Timeout.",
            "1. Trigger registration while simulating 6s SMTP delay.\n2. Submit registration form.",
            "User registered immediately; email dispatched asynchronously.",
            "User registration fails with Gateway Timeout; user row created in dirty state.",
            "Notification Service",
            "Backend/API",
            "Major",
            "P2 – Medium",
            "Integration Testing",
            "QA Staging",
            "CLOSED",
            "tester@demo.com",
            "Sam Developer (Auth Team)",
            "Implement circuit breaker pattern and isolate third-party notification calls in asynchronous background queues with exponential backoff.",
            "Offloaded welcome emails to Celery worker task with 3-minute retry limit.",
            "commit 3d4e7f8a",
            t1, t3, t2, t3
        ),
        (
            "DEF-106",
            "API Gateway memory leak under high-volume chunked transfer",
            "Streaming chunked HTTP payloads causes heap memory growth of 200MB/hour due to unreleased buffer references.",
            "1. Run Apache Bench with chunked payload.\n2. Stream 100k requests over 30 minutes.\n3. Inspect memory usage.",
            "Heap memory stabilizes under 128MB.",
            "Node memory exceeds 1.5GB triggering OOM restart.",
            "API Gateway",
            "Performance",
            "Major",
            "P2 – Medium",
            "System Testing",
            "QA Staging",
            "VERIFIED",
            "tester@demo.com",
            "developer@demo.com",
            "Enforce strict request payload size limits (max 10MB) and rate-limiting per client IP and authenticated tenant.",
            "Fixed stream pipe listener leak and attached cleanup on 'end' event.",
            "commit c7e1904b",
            t2, t6, t5, None
        ),
        (
            "DEF-107",
            "Coupon discount code calculation applies before sales tax roundoff",
            "Percentage discount code calculation produces 1 cent discrepancy against ERP financial ledger.",
            "1. Add item worth $99.99.\n2. Apply coupon SAVE15 (15% off).\n3. Calculate tax at 8.25%.",
            "Final total matches exact ERP accounting ledger ($91.99).",
            "Final total calculates as $92.00 due to early floating-point roundoff.",
            "Payments",
            "Functional",
            "Minor",
            "P3 – Low",
            "Unit Testing",
            "Development",
            "REOPENED",
            "tester@demo.com",
            "developer@demo.com",
            "Use fixed-point Decimal types for all monetary arithmetic instead of IEEE-754 floating point numbers.",
            "Initial fix rounded to 2 decimals too early; reopened to use decimal.ROUND_HALF_UP at final stage.",
            None,
            t3, t7, None, None
        ),
        (
            "DEF-108",
            "Cross-site scripting (XSS) in Cart promotional notes",
            "Order gift note field renders raw HTML tags allowing `<script>` execution in warehouse fulfillment portal.",
            "1. Add item to cart.\n2. Enter `<img src=x onerror=alert(1)>` in Gift Note.\n3. Open admin order details.",
            "Input rendered as escaped literal text string.",
            "Alert popup executes in admin browser context.",
            "Cart & Checkout",
            "Security",
            "Blocker",
            "P1 – High",
            "Code Review",
            "Development",
            "RESOLVED",
            "tester@demo.com",
            "developer@demo.com",
            "Apply strict HTML context-aware encoding and enforce strict Content Security Policy (CSP).",
            "Added DOMPurify sanitization and server-side html.escape() before storing notes.",
            "commit a14b62ff",
            t4, t8, t8, None
        ),
        (
            "DEF-109",
            "Session not invalidated after user password change",
            "Active sessions on other browsers remain valid even after user updates security credentials.",
            "1. Log in on Device A.\n2. Log in on Device B and change password.\n3. Perform authenticated request on Device A.",
            "Device A returns 401 Unauthorized and redirects to login.",
            "Device A continues to perform operations without re-authenticating.",
            "Authentication",
            "Security",
            "Major",
            "P1 – High",
            "Security Audit",
            "Pre-Production",
            "ASSIGNED",
            "tester@demo.com",
            "Sam Developer (Auth Team)",
            "Regenerate session identifiers upon any authentication state change and set Secure, HttpOnly, and SameSite=Lax flags.",
            "Assigned to Sam to implement session version incrementation in DB.",
            None,
            t5, t6, None, None
        ),
        (
            "DEF-110",
            "Product catalog pagination links miss total page count on filtered queries",
            "When filtering by category, next page button is active even when results fit on single page.",
            "1. Filter inventory by category 'Luxury'.\n2. View pagination bar at bottom.\n3. Click Next button.",
            "Next button disabled when count <= page size.",
            "Next button visible; clicking displays empty grid.",
            "Inventory",
            "UI/UX",
            "Trivial",
            "P3 – Low",
            "Unit Testing",
            "Development",
            "NEW",
            "tester@demo.com",
            "Carlos Frontend Dev",
            None,
            None,
            None,
            t6, t6, None, None
        )
    ]

    with conn:
        conn.executemany("""
            INSERT INTO defects (
                defect_code, title, description, steps_to_reproduce,
                expected_behavior, actual_behavior, module, type,
                severity, priority, discovery_phase, environment,
                status, reporter, assignee, prevention_guideline,
                resolution_notes, commit_reference, created_at, updated_at,
                resolved_at, closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, defects_data)

    # 3. Seed Defect History
    cursor = conn.cursor()
    cursor.execute("SELECT id, defect_code, status, reporter, assignee, created_at, updated_at, resolved_at, closed_at FROM defects")
    all_defects = cursor.fetchall()

    history_records = []
    for d in all_defects:
        did = d['id']
        code = d['defect_code']
        st = d['status']
        rep = d['reporter']
        ass = d['assignee']
        c_at = d['created_at']
        u_at = d['updated_at']
        r_at = d['resolved_at']
        cl_at = d['closed_at']

        # Initial creation record
        history_records.append((did, None, 'NEW', rep, f"Defect {code} logged by {rep}", 'tester@demo.com', 'Tester', c_at))

        if st == 'ASSIGNED':
            history_records.append((did, 'NEW', 'ASSIGNED', ass, f"Assigned to {ass} for root-cause investigation", 'admin@demo.com', 'Admin', u_at))
        elif st == 'IN PROGRESS':
            history_records.append((did, 'NEW', 'ASSIGNED', ass, f"Assigned to {ass}", 'admin@demo.com', 'Admin', c_at))
            history_records.append((did, 'ASSIGNED', 'IN PROGRESS', ass, "Active development and code fix started", 'developer@demo.com', 'Developer', u_at))
        elif st == 'RESOLVED':
            history_records.append((did, 'NEW', 'ASSIGNED', ass, f"Assigned to {ass}", 'admin@demo.com', 'Admin', c_at))
            history_records.append((did, 'ASSIGNED', 'IN PROGRESS', ass, "Fix in development", 'developer@demo.com', 'Developer', c_at))
            history_records.append((did, 'IN PROGRESS', 'RESOLVED', ass, "Code fix verified locally and submitted for test verification", 'developer@demo.com', 'Developer', r_at or u_at))
        elif st == 'VERIFIED':
            history_records.append((did, 'NEW', 'ASSIGNED', ass, f"Assigned to {ass}", 'admin@demo.com', 'Admin', c_at))
            history_records.append((did, 'ASSIGNED', 'IN PROGRESS', ass, "Fix in development", 'developer@demo.com', 'Developer', c_at))
            history_records.append((did, 'IN PROGRESS', 'RESOLVED', ass, "Code submitted for QA staging verification", 'developer@demo.com', 'Developer', c_at))
            history_records.append((did, 'RESOLVED', 'VERIFIED', rep, "QA verification passed in staging environment", 'tester@demo.com', 'Tester', u_at))
        elif st == 'CLOSED':
            history_records.append((did, 'NEW', 'ASSIGNED', ass, f"Assigned to {ass}", 'admin@demo.com', 'Admin', c_at))
            history_records.append((did, 'ASSIGNED', 'IN PROGRESS', ass, "Fix in development", 'developer@demo.com', 'Developer', c_at))
            history_records.append((did, 'IN PROGRESS', 'RESOLVED', ass, "Code committed and deployed to production", 'developer@demo.com', 'Developer', r_at or c_at))
            history_records.append((did, 'RESOLVED', 'VERIFIED', rep, "Production smoke test confirmed fix", 'tester@demo.com', 'Tester', cl_at or u_at))
            history_records.append((did, 'VERIFIED', 'CLOSED', rep, "Defect resolution accepted and closed", 'admin@demo.com', 'Admin', cl_at or u_at))
        elif st == 'REOPENED':
            history_records.append((did, 'NEW', 'ASSIGNED', ass, f"Assigned to {ass}", 'admin@demo.com', 'Admin', c_at))
            history_records.append((did, 'ASSIGNED', 'IN PROGRESS', ass, "Initial patch implemented", 'developer@demo.com', 'Developer', c_at))
            history_records.append((did, 'IN PROGRESS', 'RESOLVED', ass, "Patch submitted", 'developer@demo.com', 'Developer', c_at))
            history_records.append((did, 'RESOLVED', 'REOPENED', rep, "Regression identified in edge case; reopening defect", 'tester@demo.com', 'Tester', u_at))

    with conn:
        conn.executemany("""
            INSERT INTO defect_history (defect_id, previous_status, new_status, assignee, notes, actor_email, actor_role, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, history_records)
