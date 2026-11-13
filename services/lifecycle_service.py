"""
DefectGuard - Defect Lifecycle Service
Enforces strict finite-state machine transitions (Curriculum 1.9),
centralized role authorization checks, distinct notes separation,
and audit history tracking.
"""

from datetime import datetime, timezone
from database.db import get_db
from services.defect_service import get_defect_by_id_or_code, row_to_dict
from services.auth_service import (
    validate_lifecycle_role_permission, normalize_role,
    can_view_defect, can_view_defect_history, validate_actor
)

ALLOWED_TRANSITIONS = {
    'NEW': ['ASSIGNED'],
    'ASSIGNED': ['IN PROGRESS'],
    'IN PROGRESS': ['RESOLVED'],
    'RESOLVED': ['VERIFIED', 'REOPENED'],
    'VERIFIED': ['CLOSED'],
    'REOPENED': ['ASSIGNED'],
    'CLOSED': []
}

def get_allowed_transitions(current_status):
    """Return list of valid next statuses for the current status (unconstrained)."""
    return ALLOWED_TRANSITIONS.get(str(current_status).upper(), [])

def get_allowed_transitions_for_role(current_status, role='Admin', defect=None, actor=None):
    """
    Return list of valid next statuses filtered by role permissions.
    """
    base_allowed = get_allowed_transitions(current_status)
    norm_role = normalize_role(role)
    if norm_role == 'Admin':
        return base_allowed

    filtered = []
    for target in base_allowed:
        is_allowed, _ = validate_lifecycle_role_permission(norm_role, current_status, target, defect, actor)
        if is_allowed:
            filtered.append(target)
    return filtered

def transition_defect(id_or_code, new_status, assignee=None, verification_assignee=None, notes=None,
                      investigation_notes=None, resolution_notes=None,
                      fix_description=None, commit_reference=None,
                      verification_notes=None, reopening_reason=None, actor=None):
    """
    Perform defect lifecycle transition and record immutable audit history.
    Enforces valid transitions according to curriculum Section 1.9 and role authorization.
    Centralizes all transition rules, reason requirements, and distinct note updates.
    Requires explicitly validated actor; never defaults missing actor to Admin.
    """
    valid_actor = validate_actor(actor)
    actor_email = valid_actor['email']
    actor_role = valid_actor['role']

    defect = get_defect_by_id_or_code(id_or_code, actor=valid_actor)
    if not defect:
        raise KeyError(f"Defect '{id_or_code}' not found.")

    # 1. Defect visibility authorization check
    if not can_view_defect(defect, valid_actor):
        raise PermissionError(
            f"Forbidden: Role '{actor_role}' is not authorized to access defect '{defect['defect_code']}'."
        )

    curr_status = defect['status'].upper()
    target_status = str(new_status).strip().upper()

    # 2. State machine integrity check
    allowed = get_allowed_transitions(curr_status)
    if target_status not in allowed:
        raise ValueError(
            f"Invalid lifecycle transition from '{curr_status}' to '{target_status}'. "
            f"Allowed transitions for '{curr_status}': {allowed if allowed else 'None (terminal state)'}."
        )

    # 3. Role permission check (centralized)
    is_allowed, err_msg = validate_lifecycle_role_permission(actor_role, curr_status, target_status, defect, actor)
    if not is_allowed:
        raise PermissionError(err_msg)

    # 4. Reopening mandatory reason validation
    final_reopening_reason = None
    if target_status == 'REOPENED':
        reason = reopening_reason or notes
        if not reason or not str(reason).strip():
            raise ValueError("Reopening reason is required to reopen a resolved defect.")
        final_reopening_reason = str(reason).strip()

    # 5. Extract distinct notes according to target transition
    final_investigation_notes = None
    if target_status == 'IN PROGRESS':
        inv = investigation_notes or notes
        if inv and str(inv).strip():
            final_investigation_notes = str(inv).strip()

    final_resolution_notes = None
    final_commit_ref = None
    if target_status == 'RESOLVED':
        res = resolution_notes or fix_description or notes
        if res and str(res).strip():
            final_resolution_notes = str(res).strip()
        if commit_reference and str(commit_reference).strip():
            final_commit_ref = str(commit_reference).strip()

    final_verification_notes = None
    if target_status == 'VERIFIED':
        ver = verification_notes or notes
        if ver and str(ver).strip():
            final_verification_notes = str(ver).strip()

    conn = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Non-Admin roles cannot change assignee or verification_assignee
    if actor_role != 'Admin':
        if assignee and str(assignee).strip().lower() != (defect['assignee'] or '').strip().lower():
            raise PermissionError(f"Forbidden: Role '{actor_role}' cannot assign defects. Only Admin can assign defects.")
        if verification_assignee and str(verification_assignee).strip().lower() != (defect.get('verification_assignee') or '').strip().lower():
            raise PermissionError(f"Forbidden: Role '{actor_role}' cannot assign verification responsibilities. Only Admin can assign verification assignees.")

    final_assignee = assignee.strip() if (assignee and str(assignee).strip()) else defect['assignee']
    final_ver_assignee = verification_assignee.strip() if (verification_assignee and str(verification_assignee).strip()) else defect.get('verification_assignee')

    # Build human-readable audit notes
    combined_notes = []
    if final_reopening_reason:
        combined_notes.append(f"Reopening Reason: {final_reopening_reason}")
    if final_verification_notes:
        combined_notes.append(f"Verification: {final_verification_notes}")
    if final_resolution_notes:
        combined_notes.append(f"Resolution: {final_resolution_notes}")
    if final_commit_ref:
        combined_notes.append(f"Commit: {final_commit_ref}")
    if final_investigation_notes:
        combined_notes.append(f"Investigation: {final_investigation_notes}")
    if notes and not combined_notes:
        combined_notes.append(str(notes).strip())

    notes_text = " | ".join(combined_notes) if combined_notes else f"Transitioned status to {target_status}"

    resolved_at = defect['resolved_at']
    closed_at = defect['closed_at']

    if target_status == 'RESOLVED':
        resolved_at = now
    elif target_status == 'CLOSED':
        closed_at = now
    elif target_status in ('REOPENED', 'ASSIGNED', 'IN PROGRESS'):
        if target_status == 'REOPENED':
            resolved_at = None

    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE defects
            SET status = ?,
                assignee = ?,
                verification_assignee = ?,
                investigation_notes = COALESCE(?, investigation_notes),
                resolution_notes = COALESCE(?, resolution_notes),
                commit_reference = COALESCE(?, commit_reference),
                verification_notes = COALESCE(?, verification_notes),
                reopening_reason = COALESCE(?, reopening_reason),
                updated_at = ?,
                resolved_at = ?,
                closed_at = ?
            WHERE id = ?
        """, (
            target_status,
            final_assignee,
            final_ver_assignee,
            final_investigation_notes,
            final_resolution_notes,
            final_commit_ref,
            final_verification_notes,
            final_reopening_reason,
            now,
            resolved_at,
            closed_at,
            defect['id']
        ))

        action_name = target_status
        cursor.execute("""
            INSERT INTO defect_history (
                defect_id, action, previous_status, new_status, previous_value, new_value,
                assignee, notes, comment, actor_email, actor_role, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            defect['id'],
            action_name,
            curr_status,
            target_status,
            curr_status,
            target_status,
            final_assignee,
            notes_text,
            notes_text,
            actor_email,
            actor_role,
            now
        ))

    return get_defect_by_id_or_code(defect['id'], actor=valid_actor)

def get_defect_history(id_or_code, actor=None):
    """
    Retrieve audit history log for a defect.
    Preserves and returns history for active defects.
    For soft-deleted defects, history is strictly restricted to Admin.
    Developers and Testers cannot access history for soft-deleted defects.
    """
    actor_role = normalize_role(actor.get('role')) if actor else None
    allow_deleted = bool(actor_role == 'Admin')

    defect = get_defect_by_id_or_code(id_or_code, actor=actor, include_deleted=allow_deleted)
    if not defect:
        return None

    if actor and not can_view_defect_history(defect, actor):
        raise PermissionError(
            f"Forbidden: Role '{actor.get('role')}' is not authorized to access defect history for '{defect['defect_code']}'."
        )

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM defect_history
        WHERE defect_id = ?
        ORDER BY id ASC
    """, (defect['id'],))

    rows = cursor.fetchall()
    return [row_to_dict(r) for r in rows]
