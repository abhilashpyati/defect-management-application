"""
DefectGuard - Authentication & Role Switching Routes
Provides session retrieval, secure demo role switching, and role listing.
"""

from flask import Blueprint, request, jsonify, session
from services.auth_service import (
    get_current_user, set_session_role, get_role_permissions,
    DEMO_USERS, normalize_role, VALID_ROLES
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/session', methods=['GET'])
def get_session():
    """
    Return currently active demo user, role, and permissions.
    If session is uninitialized on initial browser dashboard visit,
    initializes the demonstration session to Admin.
    """
    # Initialize demo session to Admin on first dashboard entry if not yet set
    if 'role' not in session:
        set_session_role('Admin')

    user = get_current_user()
    permissions = get_role_permissions(user.get('role'))

    available_roles = [
        {
            'role': u['role'],
            'email': u['email'],
            'name': u['name'],
            'title': u['title']
        }
        for u in DEMO_USERS.values()
    ]

    return jsonify({
        'success': True,
        'user': user,
        'permissions': permissions,
        'available_roles': available_roles,
        'demo_mode': True
    }), 200

@auth_bp.route('/switch-role', methods=['POST'])
def switch_role():
    """
    Switch active demo role for demonstration purposes.
    Accepts JSON body: { "role": "Developer" } or { "email": "developer@demo.com" }.
    Rejects invalid roles (e.g. Superuser, Administrator2, malformed values) with HTTP 400.
    """
    data = request.get_json(silent=True) or {}
    target_role = data.get('role')

    # If email was provided instead of role name
    if not target_role and data.get('email'):
        email = str(data.get('email')).strip().lower()
        for r, u in DEMO_USERS.items():
            if u['email'].lower() == email:
                target_role = r
                break

    if not target_role:
        return jsonify({
            'success': False,
            'error': f"Role must be specified. Valid roles: {', '.join(VALID_ROLES)}."
        }), 400

    canonical_role = normalize_role(target_role)
    if not canonical_role:
        return jsonify({
            'success': False,
            'error': f"Invalid role '{target_role}'. Valid roles: {', '.join(VALID_ROLES)}."
        }), 400

    try:
        user = set_session_role(canonical_role)
        permissions = get_role_permissions(user['role'])

        return jsonify({
            'success': True,
            'message': f"Switched active demo role to '{user['role']}' ({user['email']}).",
            'user': user,
            'permissions': permissions
        }), 200
    except ValueError as ve:
        return jsonify({
            'success': False,
            'error': str(ve)
        }), 400

@auth_bp.route('/roles', methods=['GET'])
def list_roles():
    """List all available demo roles (Admin, Developer, Tester)."""
    return jsonify({
        'success': True,
        'roles': list(DEMO_USERS.values())
    }), 200
