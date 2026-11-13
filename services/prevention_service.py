from datetime import datetime, timezone
from database.db import get_db
from services.defect_service import row_to_dict, MODULES

PREVENTION_CATEGORIES = [
    'Security & Authorization',
    'Concurrency & Idempotency',
    'Data Integrity',
    'Input Validation',
    'Resilience & Fault Tolerance',
    'Rate Limiting & Boundary Checks',
    'Session Management',
    'Calculation Precision',
    'UI & Viewport Standards',
    'Performance & Caching'
]

def get_all_prevention_guidelines(filters=None):
    """
    Retrieve prevention guidelines with optional filters for module, category, search.
    """
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM prevention_guidelines WHERE 1=1"
    params = []

    if filters:
        if filters.get('module'):
            query += " AND UPPER(module) = UPPER(?)"
            params.append(filters['module'].strip())

        if filters.get('category'):
            query += " AND UPPER(category) = UPPER(?)"
            params.append(filters['category'].strip())

        if filters.get('search'):
            s = f"%{filters['search'].strip()}%"
            query += """ AND (
                root_cause LIKE ? OR
                guideline LIKE ? OR
                module LIKE ? OR
                category LIKE ?
            )"""
            params.extend([s, s, s, s])

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [row_to_dict(r) for r in rows]

def get_prevention_guideline_by_id(guideline_id):
    """Retrieve guideline by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prevention_guidelines WHERE id = ?", (int(guideline_id),))
    row = cursor.fetchone()
    return row_to_dict(row)

def add_prevention_guideline(data):
    """
    Add a new root cause analysis and prevention guideline record.
    """
    root_cause = data.get('root_cause', '').strip()
    guideline = data.get('guideline', '').strip()
    module = data.get('module', '').strip()
    category = data.get('category', '').strip()

    if not root_cause:
        raise ValueError("Root cause description is required.")
    if not guideline:
        raise ValueError("Prevention guideline is required.")
    if not module:
        raise ValueError("Functional module is required.")
    if not category:
        category = "General Practice"

    # Match module case-insensitively
    matching_mod = next((m for m in MODULES if m.lower() == module.lower()), module)

    conn = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prevention_guidelines (root_cause, guideline, module, category, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (root_cause, guideline, matching_mod, category, now))
        new_id = cursor.lastrowid

    return get_prevention_guideline_by_id(new_id)

def update_prevention_guideline(guideline_id, data):
    """Update existing prevention guideline."""
    existing = get_prevention_guideline_by_id(guideline_id)
    if not existing:
        return None

    root_cause = data.get('root_cause', existing['root_cause']).strip()
    guideline = data.get('guideline', existing['guideline']).strip()
    module = data.get('module', existing['module']).strip()
    category = data.get('category', existing['category']).strip()

    if not root_cause or not guideline or not module:
        raise ValueError("Root cause, guideline, and module cannot be empty.")

    conn = get_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE prevention_guidelines
            SET root_cause = ?, guideline = ?, module = ?, category = ?
            WHERE id = ?
        """, (root_cause, guideline, module, category, int(guideline_id)))

    return get_prevention_guideline_by_id(guideline_id)

def delete_prevention_guideline(guideline_id):
    """Delete prevention guideline."""
    existing = get_prevention_guideline_by_id(guideline_id)
    if not existing:
        return False

    conn = get_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM prevention_guidelines WHERE id = ?", (int(guideline_id),))

    return True

def get_prevention_knowledge_summary():
    """
    Summarize root cause patterns and recurring problems across modules.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT module, COUNT(*) as count
        FROM prevention_guidelines
        GROUP BY module
        ORDER BY count DESC
    """)
    module_counts = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM prevention_guidelines
        GROUP BY category
        ORDER BY count DESC
    """)
    category_counts = [dict(r) for r in cursor.fetchall()]

    # Recurring defect patterns linked to prevention
    cursor.execute("""
        SELECT d.module, d.type, COUNT(*) as defect_count
        FROM defects d
        GROUP BY d.module, d.type
        HAVING COUNT(*) > 1
        ORDER BY defect_count DESC
    """)
    recurring_patterns = [dict(r) for r in cursor.fetchall()]

    return {
        "module_guideline_distribution": module_counts,
        "category_distribution": category_counts,
        "recurring_patterns": recurring_patterns,
        "categories": PREVENTION_CATEGORIES
    }
