"""
DefectGuard - Defect Management Service
Implements CRUD, domain validation, auto-incrementing defect IDs,
field-level role permissions, soft deletion, role-based visibility, and audit logging.
"""

import re
from datetime import datetime, timezone
from database.db import get_db
from services.auth_service import (
    validate_field_permissions, is_assigned_to_developer, normalize_role,
    can_view_defect, validate_actor
)

SEVERITIES = ['Blocker', 'Critical', 'Major', 'Minor', 'Trivial']
PRIORITIES = ['P1 – High', 'P2 – Medium', 'P3 – Low']
TYPES = ['Functional', 'UI/UX', 'Backend/API', 'Security', 'Database', 'Performance']
MODULES = ['Authentication', 'Payments', 'Cart & Checkout', 'Inventory', 'Notification Service', 'API Gateway']
DISCOVERY_PHASES = ['Unit Testing', 'Integration Testing', 'System Testing', 'User Acceptance Testing', 'Code Review', 'Security Audit']
ENVIRONMENTS = ['Development', 'QA Staging', 'Pre-Production', 'Production']
STATUSES = ['NEW', 'ASSIGNED', 'IN PROGRESS', 'RESOLVED', 'VERIFIED', 'CLOSED', 'REOPENED']

MANDATORY_FIELDS = [
    'title', 'description', 'steps_to_reproduce', 'expected_behavior',
    'actual_behavior', 'module', 'type', 'severity', 'priority',
    'discovery_phase', 'environment', 'reporter', 'assignee'
]

def normalize_priority(val):
    """Normalize priority value to canonical 'P1 – High', 'P2 – Medium', 'P3 – Low'."""
    if not val:
        return val
    val_str = str(val).strip()
    for p in PRIORITIES:
        if val_str == p or val_str == p.replace('–', '-'):
            return p
        if val_str.upper().startswith(p[:2]):
            return p
    return val_str

def row_to_dict(row):
    """Convert an sqlite3.Row object to a standard python dict."""
    if row is None:
        return None
    return dict(row)

def generate_next_defect_code(conn):
    """
    Generate auto-incrementing Defect ID (e.g. DEF-101, DEF-102, ...).
    """
    cursor = conn.cursor()
    cursor.execute("SELECT defect_code FROM defects")
    rows = cursor.fetchall()

    max_num = 100  # Default base so first is DEF-101
    pattern = re.compile(r'DEF-(\d+)', re.IGNORECASE)

    for r in rows:
        match = pattern.match(r['defect_code'])
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    return f"DEF-{max_num + 1}"

def validate_defect_data(data, is_update=False):
    """
    Validate defect data for mandatory fields and domain rules.
    Returns (is_valid, error_message, cleaned_data).
    """
    cleaned = dict(data)

    if not is_update:
        for field in MANDATORY_FIELDS:
            val = cleaned.get(field)
            if val is None or str(val).strip() == '':
                return False, f"Mandatory field '{field}' is required and cannot be empty.", None

    if 'severity' in cleaned:
        sev = str(cleaned['severity']).strip()
        matching_sev = next((s for s in SEVERITIES if s.lower() == sev.lower()), None)
        if not matching_sev:
            return False, f"Invalid severity '{sev}'. Must be one of: {', '.join(SEVERITIES)}.", None
        cleaned['severity'] = matching_sev

    if 'priority' in cleaned:
        prio = normalize_priority(cleaned['priority'])
        if prio not in PRIORITIES:
            return False, f"Invalid priority '{cleaned['priority']}'. Must be one of: {', '.join(PRIORITIES)}.", None
        cleaned['priority'] = prio

    if 'module' in cleaned:
        mod = str(cleaned['module']).strip()
        matching_mod = next((m for m in MODULES if m.lower() == mod.lower()), None)
        if not matching_mod:
            return False, f"Invalid module '{mod}'. Must be one of: {', '.join(MODULES)}.", None
        cleaned['module'] = matching_mod

    if 'type' in cleaned:
        t = str(cleaned['type']).strip()
        matching_t = next((typ for typ in TYPES if typ.lower() == t.lower()), None)
        if not matching_t:
            return False, f"Invalid type '{t}'. Must be one of: {', '.join(TYPES)}.", None
        cleaned['type'] = matching_t

    if 'discovery_phase' in cleaned:
        dp = str(cleaned['discovery_phase']).strip()
        matching_dp = next((ph for ph in DISCOVERY_PHASES if ph.lower() == dp.lower()), None)
        if not matching_dp:
            return False, f"Invalid discovery phase '{dp}'. Must be one of: {', '.join(DISCOVERY_PHASES)}.", None
        cleaned['discovery_phase'] = matching_dp

    if 'environment' in cleaned:
        env = str(cleaned['environment']).strip()
        matching_env = next((e for e in ENVIRONMENTS if e.lower() == env.lower()), None)
        if not matching_env:
            return False, f"Invalid environment '{env}'. Must be one of: {', '.join(ENVIRONMENTS)}.", None
        cleaned['environment'] = matching_env

    return True, None, cleaned

def create_defect(data, actor=None):
    """
    Create a new defect record with auto-generated code and initial audit entry.
    Authorized for Admin and Tester. Developer receives PermissionError.
    Requires explicitly validated actor; never defaults missing actor to Admin.
    """
    valid_actor = validate_actor(actor)
    actor_email = valid_actor['email']
    actor_role = valid_actor['role']

    if actor_role == 'Developer':
        raise PermissionError("Developers cannot record new defects.")

    is_valid, err, cleaned = validate_defect_data(data, is_update=False)
    if not is_valid:
        raise ValueError(err)

    conn = get_db()
    defect_code = cleaned.get('defect_code') or generate_next_defect_code(conn)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    status = cleaned.get('status', 'NEW')
    if status not in STATUSES:
        status = 'NEW'

    # Only Admin can assign defects to developers.
    # Testers report defects in NEW status without assignment (assignee is strictly 'Unassigned').
    if actor_role == 'Tester':
        cleaned['assignee'] = 'Unassigned'
        status = 'NEW'
    else:
        if not cleaned.get('assignee') or cleaned['assignee'].strip() == '':
            cleaned['assignee'] = 'Unassigned'

    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO defects (
                defect_code, title, description, steps_to_reproduce,
                expected_behavior, actual_behavior, module, type,
                severity, priority, discovery_phase, environment,
                status, reporter, assignee, verification_assignee, prevention_guideline,
                investigation_notes, resolution_notes, commit_reference,
                verification_notes, reopening_reason,
                is_deleted, deleted_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
        """, (
            defect_code,
            cleaned['title'].strip(),
            cleaned['description'].strip(),
            cleaned['steps_to_reproduce'].strip(),
            cleaned['expected_behavior'].strip(),
            cleaned['actual_behavior'].strip(),
            cleaned['module'],
            cleaned['type'],
            cleaned['severity'],
            cleaned['priority'],
            cleaned['discovery_phase'],
            cleaned['environment'],
            status,
            cleaned['reporter'].strip(),
            cleaned['assignee'].strip(),
            cleaned.get('verification_assignee', '').strip() if cleaned.get('verification_assignee') else None,
            cleaned.get('prevention_guideline', '').strip() if cleaned.get('prevention_guideline') else None,
            cleaned.get('investigation_notes', '').strip() if cleaned.get('investigation_notes') else None,
            cleaned.get('resolution_notes', '').strip() if cleaned.get('resolution_notes') else None,
            cleaned.get('commit_reference', '').strip() if cleaned.get('commit_reference') else None,
            cleaned.get('verification_notes', '').strip() if cleaned.get('verification_notes') else None,
            cleaned.get('reopening_reason', '').strip() if cleaned.get('reopening_reason') else None,
            now,
            now
        ))
        defect_id = cursor.lastrowid

        # Insert initial audit log with actor identity, role, and action
        cursor.execute("""
            INSERT INTO defect_history (
                defect_id, action, previous_status, new_status, previous_value, new_value,
                assignee, notes, comment, actor_email, actor_role, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            defect_id,
            'CREATED',
            None,
            status,
            None,
            status,
            cleaned['reporter'].strip(),
            f"Defect {defect_code} created by {cleaned['reporter'].strip()} ({actor_role})",
            f"Defect {defect_code} created by {cleaned['reporter'].strip()} ({actor_role})",
            actor_email,
            actor_role,
            now
        ))

    return get_defect_by_id_or_code(defect_id, actor=valid_actor)

def _get_defect_raw_internal(id_or_code, include_deleted=True):
    """
    Explicit internal administrative helper for service operations.
    Bypasses actor checks strictly for safe internal ID lookups.
    Should never be exposed directly to route handlers or clients.
    """
    conn = get_db()
    cursor = conn.cursor()
    del_clause = "" if include_deleted else " AND is_deleted = 0"
    if isinstance(id_or_code, int) or (isinstance(id_or_code, str) and id_or_code.isdigit()):
        cursor.execute(f"SELECT * FROM defects WHERE id = ?{del_clause}", (int(id_or_code),))
    else:
        cursor.execute(f"SELECT * FROM defects WHERE UPPER(defect_code) = UPPER(?){del_clause}", (str(id_or_code).strip(),))
    row = cursor.fetchone()
    return row_to_dict(row)

def get_defect_by_id_or_code(id_or_code, actor=None, include_deleted=False):
    """
    Retrieve defect by integer ID or defect_code (e.g. DEF-101).
    Requires a valid actor. Enforces role visibility:
    - Developer only views assigned defects.
    - Tester only views reported or verification-assigned defects.
    - Excludes soft-deleted defects unless include_deleted=True and actor is Admin.
    - Developers and Testers can NEVER view soft-deleted defects.
    Rejects missing or invalid actor information with PermissionError.
    """
    valid_actor = validate_actor(actor)
    actor_role = valid_actor['role']
    allow_deleted = bool(include_deleted and actor_role == 'Admin')

    defect = _get_defect_raw_internal(id_or_code, include_deleted=allow_deleted)
    if not defect:
        return None

    # Enforce role visibility
    if not can_view_defect(defect, valid_actor):
        raise PermissionError(
            f"Forbidden: Defect '{defect['defect_code']}' is not accessible by role '{actor_role}'."
        )

    return defect

def get_all_defects(filters=None, include_deleted=False, actor=None):
    """
    Retrieve all defects with optional filtering, search, and strict role visibility.
    Requires an explicitly validated actor via validate_actor().
    - ADMIN: Can view all defects. If explicitly requested, can view deleted defects.
    - DEVELOPER: Can view ONLY active defects assigned to their exact identity. Never deleted.
    - TESTER: Can view ONLY active defects reported or assigned for verification. Never deleted.
    Rejects missing or invalid actor information with PermissionError.
    """
    valid_actor = validate_actor(actor)
    actor_role = valid_actor['role']
    actor_email = valid_actor['email'].strip().lower()
    actor_name = valid_actor['name'].strip().lower()

    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM defects WHERE 1=1"
    params = []

    inc_del = (include_deleted or (filters and str(filters.get('include_deleted')).lower() == 'true')) and (actor_role == 'Admin')
    if not inc_del:
        query += " AND is_deleted = 0"

    # Enforce backend role-based visibility
    if actor_role == 'Developer':
        query += " AND (LOWER(assignee) = ? OR LOWER(assignee) = ?)"
        params.extend([actor_email, actor_name])
    elif actor_role == 'Tester':
        query += " AND ((LOWER(reporter) = ? OR LOWER(reporter) = ?) OR (LOWER(verification_assignee) = ? OR LOWER(verification_assignee) = ?))"
        params.extend([actor_email, actor_name, actor_email, actor_name])
    elif actor_role != 'Admin':
        return []

    if filters:
        if filters.get('status'):
            query += " AND UPPER(status) = UPPER(?)"
            params.append(filters['status'].strip())

        if filters.get('severity'):
            query += " AND UPPER(severity) = UPPER(?)"
            params.append(filters['severity'].strip())

        if filters.get('priority'):
            norm_prio = normalize_priority(filters['priority'])
            query += " AND (priority = ? OR priority = ?)"
            params.append(norm_prio)
            params.append(norm_prio.replace('–', '-'))

        if filters.get('module'):
            query += " AND UPPER(module) = UPPER(?)"
            params.append(filters['module'].strip())

        if filters.get('discovery_phase'):
            query += " AND UPPER(discovery_phase) = UPPER(?)"
            params.append(filters['discovery_phase'].strip())

        if filters.get('assignee'):
            query += " AND LOWER(assignee) LIKE LOWER(?)"
            params.append(f"%{filters['assignee'].strip()}%")

        if filters.get('search'):
            s = f"%{filters['search'].strip()}%"
            query += """ AND (
                defect_code LIKE ? OR
                title LIKE ? OR
                description LIKE ? OR
                reporter LIKE ? OR
                assignee LIKE ? OR
                module LIKE ?
            )"""
            params.extend([s, s, s, s, s, s])

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [row_to_dict(r) for r in rows]

def update_defect(id_or_code, data, actor=None):
    """
    Update defect information with strict field-level role authorization checks.
    Rejects unauthorized fields per role allowlists.
    Requires explicitly validated actor; never defaults missing actor to Admin.
    """
    valid_actor = validate_actor(actor)
    actor_email = valid_actor['email']
    actor_role = valid_actor['role']

    existing = get_defect_by_id_or_code(id_or_code, actor=valid_actor)
    if not existing:
        return None

    # 1. Defect visibility check
    if not can_view_defect(existing, valid_actor):
        raise PermissionError(
            f"Forbidden: Defect '{existing['defect_code']}' is not accessible by role '{actor_role}'."
        )

    # 2. Field-level permission validation (rejects unauthorized fields)
    is_allowed, err_msg = validate_field_permissions(actor_role, data.keys())
    if not is_allowed:
        raise PermissionError(err_msg)

    # 3. Developer-specific checks: must be assigned developer
    if actor_role == 'Developer':
        if not is_assigned_to_developer(existing, actor):
            raise PermissionError(
                f"Forbidden: Defect is assigned to '{existing.get('assignee')}', not '{actor.get('name') if actor else 'you'}'."
            )

    # 4. Tester-specific checks: cannot reassign developer or verification assignee
    if actor_role == 'Tester':
        if 'assignee' in data and data['assignee'] != existing['assignee']:
            raise PermissionError("Forbidden: Testers cannot assign defects to developers. Only Admin can assign defects.")
        if 'verification_assignee' in data and data['verification_assignee'] != existing.get('verification_assignee'):
            raise PermissionError("Forbidden: Testers cannot assign verification responsibilities. Only Admin can assign verification assignees.")

    # 5. Only Admin can assign/reassign defects or verification assignees
    if 'assignee' in data and data['assignee'] != existing['assignee']:
        if actor_role != 'Admin':
            raise PermissionError(f"Forbidden: Role '{actor_role}' cannot assign defects. Only Admin can assign defects.")

    if 'verification_assignee' in data and data['verification_assignee'] != existing.get('verification_assignee'):
        if actor_role != 'Admin':
            raise PermissionError(f"Forbidden: Role '{actor_role}' cannot assign verification responsibilities. Only Admin can assign verification assignees.")

    is_valid, err, cleaned = validate_defect_data(data, is_update=True)
    if not is_valid:
        raise ValueError(err)

    # Map aliases to separate distinct notes columns
    if 'fix_description' in cleaned and 'resolution_notes' not in cleaned:
        cleaned['resolution_notes'] = cleaned['fix_description']
    if 'notes' in cleaned:
        if actor_role == 'Developer' and 'investigation_notes' not in cleaned:
            cleaned['investigation_notes'] = cleaned['notes']
        elif actor_role == 'Tester' and 'verification_notes' not in cleaned:
            cleaned['verification_notes'] = cleaned['notes']

    conn = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    fields = [
        'title', 'description', 'steps_to_reproduce', 'expected_behavior',
        'actual_behavior', 'module', 'type', 'severity', 'priority',
        'discovery_phase', 'environment', 'assignee', 'verification_assignee',
        'prevention_guideline', 'investigation_notes', 'resolution_notes',
        'commit_reference', 'verification_notes', 'reopening_reason'
    ]

    set_clauses = ["updated_at = ?"]
    params = [now]
    modified_fields = []

    for f in fields:
        if f in cleaned:
            set_clauses.append(f"{f} = ?")
            val = cleaned[f]
            params.append(val.strip() if isinstance(val, str) else val)
            modified_fields.append(f)

    params.append(existing['id'])

    with conn:
        cursor = conn.cursor()
        sql = f"UPDATE defects SET {', '.join(set_clauses)} WHERE id = ?"
        cursor.execute(sql, params)

        # Audit logging for field updates
        if 'assignee' in cleaned and cleaned['assignee'].strip() != existing['assignee']:
            cursor.execute("""
                INSERT INTO defect_history (
                    defect_id, action, previous_status, new_status, previous_value, new_value,
                    assignee, notes, comment, actor_email, actor_role, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                existing['id'],
                'ASSIGNED',
                existing['status'],
                existing['status'],
                existing['assignee'],
                cleaned['assignee'].strip(),
                cleaned['assignee'].strip(),
                f"Assignee changed from '{existing['assignee']}' to '{cleaned['assignee'].strip()}' by {actor_email} ({actor_role})",
                f"Assignee changed from '{existing['assignee']}' to '{cleaned['assignee'].strip()}' by {actor_email} ({actor_role})",
                actor_email,
                actor_role,
                now
            ))
        elif 'verification_assignee' in cleaned and cleaned['verification_assignee'] != existing.get('verification_assignee'):
            prev_ver = existing.get('verification_assignee') or 'Unassigned'
            new_ver = (cleaned['verification_assignee'] or '').strip()
            cursor.execute("""
                INSERT INTO defect_history (
                    defect_id, action, previous_status, new_status, previous_value, new_value,
                    assignee, notes, comment, actor_email, actor_role, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                existing['id'],
                'VERIFICATION_ASSIGNED',
                existing['status'],
                existing['status'],
                prev_ver,
                new_ver,
                existing['assignee'],
                f"Verification assignee changed from '{prev_ver}' to '{new_ver}' by {actor_email} ({actor_role})",
                f"Verification assignee changed from '{prev_ver}' to '{new_ver}' by {actor_email} ({actor_role})",
                actor_email,
                actor_role,
                now
            ))
        elif 'investigation_notes' in cleaned and cleaned['investigation_notes']:
            cursor.execute("""
                INSERT INTO defect_history (
                    defect_id, action, previous_status, new_status, previous_value, new_value,
                    assignee, notes, comment, actor_email, actor_role, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                existing['id'],
                'INVESTIGATION',
                existing['status'],
                existing['status'],
                None,
                cleaned['investigation_notes'],
                existing['assignee'],
                f"Investigation notes added: {cleaned['investigation_notes']}",
                cleaned['investigation_notes'],
                actor_email,
                actor_role,
                now
            ))
        elif modified_fields:
            fields_str = ', '.join(modified_fields)
            cursor.execute("""
                INSERT INTO defect_history (
                    defect_id, action, previous_status, new_status, previous_value, new_value,
                    assignee, notes, comment, actor_email, actor_role, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                existing['id'],
                'FIELD_UPDATE',
                existing['status'],
                existing['status'],
                None,
                fields_str,
                existing['assignee'],
                f"Updated fields [{fields_str}] by {actor_email} ({actor_role})",
                f"Updated fields [{fields_str}] by {actor_email} ({actor_role})",
                actor_email,
                actor_role,
                now
            ))

    return get_defect_by_id_or_code(existing['id'], actor=valid_actor)

def delete_defect(id_or_code, actor=None):
    """
    Soft-delete a defect and record audit history. Restricted to Admin.
    Preserves defect audit history for verification and compliance.
    Requires explicitly validated actor; never defaults missing actor to Admin.
    """
    valid_actor = validate_actor(actor)
    actor_email = valid_actor['email']
    actor_role = valid_actor['role']
    if actor_role != 'Admin':
        raise PermissionError(f"Forbidden: Only Admin can delete defects. Active role is '{actor_role}'.")

    existing = get_defect_by_id_or_code(id_or_code, actor=valid_actor)
    if not existing:
        return False

    conn = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    with conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE defects SET is_deleted = 1, deleted_at = ? WHERE id = ?", (now, existing['id']))

        # Record soft deletion in defect_history
        cursor.execute("""
            INSERT INTO defect_history (
                defect_id, action, previous_status, new_status, previous_value, new_value,
                assignee, notes, comment, actor_email, actor_role, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            existing['id'],
            'DELETED',
            existing['status'],
            'DELETED',
            existing['status'],
            'DELETED',
            existing['assignee'],
            f"Defect {existing['defect_code']} soft-deleted by {actor_email} ({actor_role})",
            f"Defect {existing['defect_code']} soft-deleted by {actor_email} ({actor_role})",
            actor_email,
            actor_role,
            now
        ))

    return True
