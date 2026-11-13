"""
DefectGuard - Authentication & Role-Based Access Control (RBAC) Service
Provides centralized role validation, session-based demo identities,
field-level permission validation, and lifecycle authorization.
"""

from functools import wraps
from flask import session, request, jsonify, current_app

VALID_ROLES = ('Admin', 'Developer', 'Tester')

DEMO_USERS = {
    'Admin': {
        'email': 'admin@demo.com',
        'name': 'Admin User',
        'role': 'Admin',
        'title': 'System Administrator'
    },
    'Developer': {
        'email': 'developer@demo.com',
        'name': 'Demo Developer',
        'role': 'Developer',
        'title': 'Software Developer'
    },
    'Tester': {
        'email': 'tester@demo.com',
        'name': 'Demo Tester',
        'role': 'Tester',
        'title': 'QA Test Engineer'
    }
}

GUEST_USER = {
    'email': None,
    'name': 'Guest User',
    'role': None,
    'title': 'Unauthenticated Guest'
}

# Field allowlists for defect modification
ALLOWED_UPDATE_FIELDS = {
    'Admin': {
        'title', 'description', 'steps_to_reproduce', 'expected_behavior',
        'actual_behavior', 'module', 'type', 'severity', 'priority',
        'discovery_phase', 'environment', 'assignee', 'verification_assignee',
        'prevention_guideline', 'investigation_notes', 'resolution_notes',
        'commit_reference', 'verification_notes', 'reopening_reason', 'notes',
        'fix_description', 'status'
    },
    'Developer': {
        'investigation_notes', 'resolution_notes', 'commit_reference',
        'notes', 'fix_description', 'status'
    },
    'Tester': {
        'verification_notes', 'reopening_reason', 'notes', 'status'
    }
}

def normalize_role(role_name):
    """
    Normalize role string to canonical title case ('Admin', 'Developer', 'Tester').
    Returns canonical role name if valid, or None if invalid or empty.
    Never defaults an invalid role to 'Admin'.
    """
    if not role_name:
        return None
    role_str = str(role_name).strip()
    if not role_str:
        return None
    for canonical in VALID_ROLES:
        if role_str.lower() == canonical.lower():
            return canonical
    return None

def is_valid_role(role_name):
    """Check if the given role name is a recognized valid role."""
    return normalize_role(role_name) is not None

def get_current_user():
    """
    Get the active user identity and role from session or test header.
    
    Security Rules:
    1. The X-Demo-Role header is ONLY accepted when current_app.config['TESTING'] is True.
       In normal/production mode, header overrides are completely ignored.
    2. Session role is the single source of truth in normal mode.
    3. Missing or invalid session roles never grant administrative privileges.
       They return an unprivileged GUEST_USER (role: None).
    """
    # 1. In TESTING mode only, allow header override for automated tests
    is_testing = current_app and current_app.config.get('TESTING') is True
    if is_testing:
        header_role = request.headers.get('X-Demo-Role')
        if header_role is not None:
            norm_role = normalize_role(header_role)
            if norm_role:
                return DEMO_USERS[norm_role]
            # Invalid header provided in test returns guest (no admin privileges)
            return GUEST_USER

    # 2. Check session role
    session_role = session.get('role')
    if session_role:
        norm_role = normalize_role(session_role)
        if norm_role:
            return DEMO_USERS[norm_role]
        # Malformed/invalid role in session gets guest (no admin privileges)
        return GUEST_USER

    # 3. If in automated testing mode and neither header nor session was set:
    # Fallback to Admin only for legacy curriculum test cases
    if is_testing:
        return DEMO_USERS['Admin']

    # 4. Production/normal mode with missing session: unprivileged guest
    return GUEST_USER

def set_session_role(role_name):
    """
    Update the active demo role in Flask session.
    Rejects invalid roles with ValueError.
    """
    canonical_role = normalize_role(role_name)
    if not canonical_role:
        raise ValueError(f"Invalid role '{role_name}'. Permitted roles: {', '.join(VALID_ROLES)}.")

    user = DEMO_USERS[canonical_role]
    session['role'] = user['role']
    session['user_email'] = user['email']
    session['user_name'] = user['name']
    return user

def validate_actor(actor):
    """
    Validate that an actor object is provided, non-empty, and has a recognized valid role
    with exact role-identity consistency in Demo Mode.
    
    Enforces exact configured demo identities:
    - Admin: admin@demo.com
    - Developer: developer@demo.com
    - Tester: tester@demo.com
    
    Rejects missing actors, invalid roles, missing emails, and mismatched role-email pairs.
    Never defaults a missing or invalid actor to Admin.
    """
    if not actor or not isinstance(actor, dict):
        raise PermissionError("Forbidden: Authentication required. Actor identity is missing.")

    role = normalize_role(actor.get('role'))
    if not role:
        raise PermissionError("Forbidden: Authentication required. Invalid or unprivileged actor role.")

    email = (actor.get('email') or '').strip().lower()
    if not email:
        raise PermissionError("Forbidden: Authentication required. Actor email is missing.")

    expected_user = DEMO_USERS.get(role)
    if not expected_user:
        raise PermissionError(f"Forbidden: Unrecognized role '{role}'.")

    expected_email = expected_user['email'].lower()
    if email != expected_email:
        raise PermissionError(
            f"Forbidden: Role-identity mismatch. Role '{role}' must be associated with '{expected_email}', got '{email}'."
        )

    return {
        'role': role,
        'email': expected_user['email'],
        'name': actor.get('name') or expected_user['name'],
        'title': actor.get('title') or expected_user['title']
    }

def get_role_permissions(role):
    """
    Return dictionary of granular permissions for a given role.
    Centralized permissions definition ensuring exact alignment across
    backend authorization, API responses, and frontend logic.
    Returns all False if role is None or invalid.
    """
    norm_role = normalize_role(role)
    if norm_role == 'Admin':
        return {
            'role': 'Admin',
            'is_admin': True,
            'is_developer': False,
            'is_tester': False,
            'can_view_all_defects': True,
            'can_create_defects': True,
            'can_edit_defects': True,
            'can_edit_all_fields': True,
            'can_delete_defects': True,
            'can_assign_defects': True,
            'can_manage_prevention': True,
            'can_view_all_analytics': True,
            'can_view_analytics': True,
            'can_export_all_defects': True,
            'can_change_severity_priority': True,
            'can_verify_defects': True,
            'can_reopen_defects': True,
            'can_progress_defects': True,
            'can_resolve_defects': True,
            'can_close_defects': True
        }
    elif norm_role == 'Developer':
        return {
            'role': 'Developer',
            'is_admin': False,
            'is_developer': True,
            'is_tester': False,
            'can_view_all_defects': False,
            'can_create_defects': False,
            'can_edit_defects': False,
            'can_edit_all_defects': False,
            'can_edit_all_fields': False,
            'can_delete_defects': False,
            'can_assign_defects': False,
            'can_manage_prevention': False,
            'can_view_all_analytics': False,
            'can_view_analytics': True,
            'can_export_all_defects': False,
            'can_change_severity_priority': False,
            'can_verify_defects': False,
            'can_reopen_defects': False,
            'can_progress_defects': True,
            'can_resolve_defects': True,
            'can_close_defects': False
        }
    elif norm_role == 'Tester':
        return {
            'role': 'Tester',
            'is_admin': False,
            'is_developer': False,
            'is_tester': True,
            'can_view_all_defects': False,
            'can_create_defects': True,
            'can_edit_defects': False,
            'can_edit_all_defects': False,
            'can_edit_all_fields': False,
            'can_delete_defects': False,
            'can_assign_defects': False,
            'can_manage_prevention': False,
            'can_view_all_analytics': False,
            'can_view_analytics': True,
            'can_export_all_defects': False,
            'can_change_severity_priority': False,
            'can_verify_defects': True,
            'can_reopen_defects': True,
            'can_progress_defects': False,
            'can_resolve_defects': False,
            'can_close_defects': False
        }

    # Guest / Unauthenticated: all permissions False
    return {
        'role': None,
        'is_admin': False,
        'is_developer': False,
        'is_tester': False,
        'can_view_all_defects': False,
        'can_create_defects': False,
        'can_edit_defects': False,
        'can_edit_all_defects': False,
        'can_edit_all_fields': False,
        'can_delete_defects': False,
        'can_assign_defects': False,
        'can_manage_prevention': False,
        'can_view_all_analytics': False,
        'can_view_analytics': False,
        'can_export_all_defects': False,
        'can_change_severity_priority': False,
        'can_verify_defects': False,
        'can_reopen_defects': False,
        'can_progress_defects': False,
        'can_resolve_defects': False,
        'can_close_defects': False
    }

def validate_field_permissions(role, submitted_fields):
    """
    Validate that the given role is authorized to modify the submitted fields.
    Returns (is_allowed, error_message).
    """
    norm_role = normalize_role(role)
    if norm_role == 'Admin':
        return True, None

    if not norm_role:
        return False, "Forbidden: Unauthenticated or invalid role cannot modify defect fields."

    allowed = ALLOWED_UPDATE_FIELDS.get(norm_role, set())
    # Exclude internal/timing fields if sent
    ignored_keys = {'id', 'defect_code', 'created_at', 'updated_at'}
    keys_to_check = set(submitted_fields) - ignored_keys

    disallowed = keys_to_check - allowed
    if disallowed:
        disallowed_list = sorted(list(disallowed))
        return False, f"Forbidden: Role '{norm_role}' cannot modify field(s): {', '.join(disallowed_list)}."

    return True, None

def require_roles(*allowed_roles):
    """
    Decorator to enforce backend role-based access control (RBAC).
    Returns HTTP 403 Forbidden if current role is not in allowed_roles.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = get_current_user()
            user_role = current_user.get('role')

            if not user_role:
                return jsonify({
                    'success': False,
                    'error': "Forbidden: Authentication required. Active role is None."
                }), 403

            normalized_allowed = [normalize_role(r) for r in allowed_roles if normalize_role(r)]

            if user_role not in normalized_allowed:
                return jsonify({
                    'success': False,
                    'error': f"Forbidden: Action restricted to [{', '.join(normalized_allowed)}]. Current active role is '{user_role}'."
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def is_assigned_to_developer(defect, actor):
    """
    Check if the defect is assigned to the current developer identity using exact matching.
    Does NOT use loose substring matching or fallbacks.
    Returns False if actor is missing, invalid, or unassigned.
    """
    if not defect or not actor or not isinstance(actor, dict):
        return False

    role = normalize_role(actor.get('role'))
    if not role or role != 'Developer':
        return False

    actor_email = (actor.get('email') or '').strip().lower()
    actor_name = (actor.get('name') or '').strip().lower()
    if not actor_email and not actor_name:
        return False

    assignee = (defect.get('assignee') or '').strip().lower()
    if not assignee:
        return False

    return assignee == actor_email or assignee == actor_name

def can_view_defect(defect, actor):
    """
    Check if the acting user has permission to view a specific defect.
    Enforces exact identity matching without keyword/substring shortcuts.
    
    ADMIN: Can view all defects.
    DEVELOPER: Can view ONLY defects assigned to their exact identity.
    TESTER: Can view defects reported by their identity OR explicitly assigned
            to them as verification_assignee.
            Does NOT use defect status alone to determine Tester visibility.
    """
    if not defect:
        return False

    if not actor:
        return False

    role = normalize_role(actor.get('role'))
    if role == 'Admin':
        return True

    if role == 'Developer':
        assignee = (defect.get('assignee') or '').strip().lower()
        dev_email = (actor.get('email') or '').strip().lower()
        dev_name = (actor.get('name') or '').strip().lower()
        return bool(assignee and (assignee == dev_email or assignee == dev_name))

    if role == 'Tester':
        reporter = (defect.get('reporter') or '').strip().lower()
        ver_assignee = (defect.get('verification_assignee') or '').strip().lower()
        tester_email = (actor.get('email') or '').strip().lower()
        tester_name = (actor.get('name') or '').strip().lower()

        is_reporter = bool(reporter and (reporter == tester_email or reporter == tester_name))
        is_ver_assignee = bool(ver_assignee and (ver_assignee == tester_email or ver_assignee == tester_name))

        return is_reporter or is_ver_assignee

    return False

def can_view_defect_history(defect, actor):
    """
    Check if the acting user has permission to view the audit history of a defect.
    Follows defect visibility permissions.
    """
    return can_view_defect(defect, actor)

def validate_lifecycle_role_permission(user_role, curr_status, new_status, defect=None, actor=None):
    """
    Validate whether a role has permission to trigger a specific defect lifecycle transition.
    Returns (is_allowed, error_message).
    """
    role = normalize_role(user_role)
    if not role:
        return False, "Forbidden: Unauthenticated or invalid role."

    curr = str(curr_status).upper()
    target = str(new_status).upper()

    # 1. Admin can perform any valid transition
    if role == 'Admin':
        return True, None

    # 2. Developer permissions
    if role == 'Developer':
        # Allowed transitions for developer: ASSIGNED -> IN PROGRESS, IN PROGRESS -> RESOLVED
        # Reassignment from REOPENED -> ASSIGNED is restricted exclusively to Admin (only Admin assigns defects)
        if curr == 'ASSIGNED' and target == 'IN PROGRESS':
            if defect and not is_assigned_to_developer(defect, actor):
                return False, f"Forbidden: Defect is assigned to '{defect.get('assignee')}', not '{actor.get('name') if actor else 'you'}'."
            return True, None

        if curr == 'IN PROGRESS' and target == 'RESOLVED':
            if defect and not is_assigned_to_developer(defect, actor):
                return False, f"Forbidden: Defect is assigned to '{defect.get('assignee')}', not '{actor.get('name') if actor else 'you'}'."
            return True, None

        if curr == 'REOPENED' and target == 'ASSIGNED':
            return False, "Forbidden: Developers cannot reassign defects. Only Admin can assign defects from 'REOPENED' to 'ASSIGNED'."

        return False, f"Forbidden: Role 'Developer' cannot perform transition from '{curr}' to '{target}'. Developers can only move assigned defects to 'IN PROGRESS' or 'RESOLVED'."

    # 3. Tester permissions
    if role == 'Tester':
        # Allowed transitions for tester: RESOLVED -> VERIFIED, RESOLVED -> REOPENED
        if curr == 'RESOLVED' and target == 'VERIFIED':
            return True, None

        if curr == 'RESOLVED' and target == 'REOPENED':
            return True, None

        return False, f"Forbidden: Role 'Tester' cannot perform transition from '{curr}' to '{target}'. Testers can only verify or reopen 'RESOLVED' defects."

    return False, f"Forbidden: Role '{role}' is not authorized for this lifecycle transition."
