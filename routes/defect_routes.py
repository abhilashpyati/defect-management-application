"""
DefectGuard - Defect API Endpoints
Handles Defect CRUD, Lifecycle State Transitions, and Defect History.
Enforces strict Role-Based Access Control, Exact Identity Visibility,
and Field-Level Authorization for both PUT and PATCH.
"""

from flask import Blueprint, request, jsonify
from services.defect_service import (
    create_defect, get_all_defects, get_defect_by_id_or_code,
    update_defect, delete_defect
)
from services.lifecycle_service import (
    transition_defect, get_defect_history, get_allowed_transitions,
    get_allowed_transitions_for_role
)
from services.auth_service import (
    get_current_user, require_roles, validate_field_permissions
)

defect_bp = Blueprint('defects', __name__, url_prefix='/api/defects')

@defect_bp.route('', methods=['GET'])
def list_defects():
    """
    Retrieve all defects with optional filter parameters and strict role-based visibility.
    - Admin: all defects
    - Developer: only assigned defects
    - Tester: only reported or verification-relevant defects
    """
    current_user = get_current_user()
    user_role = current_user.get('role')

    filters = {
        'status': request.args.get('status'),
        'severity': request.args.get('severity'),
        'priority': request.args.get('priority'),
        'module': request.args.get('module'),
        'discovery_phase': request.args.get('discovery_phase'),
        'assignee': request.args.get('assignee'),
        'search': request.args.get('search'),
        'include_deleted': request.args.get('include_deleted')
    }

    defects = get_all_defects(filters, actor=current_user)
    return jsonify({
        'success': True,
        'count': len(defects),
        'active_role': user_role,
        'data': defects
    }), 200

@defect_bp.route('', methods=['POST'])
@require_roles('Admin', 'Tester')
def add_defect():
    """
    Record a new defect.
    Authorized for Admin and Tester. Developers receive HTTP 403.
    """
    current_user = get_current_user()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload in request body.'}), 400

    # In Tester role, reporter is always the current tester demo user and assignee is always Unassigned.
    # Testers cannot assign defects to developers; only Admin can assign defects.
    if current_user.get('role') == 'Tester':
        data['reporter'] = current_user.get('email', 'tester@demo.com')
        data['assignee'] = 'Unassigned'
    elif 'reporter' not in data:
        data['reporter'] = current_user.get('email', 'admin@demo.com')

    try:
        new_defect = create_defect(data, actor=current_user)
        return jsonify({
            'success': True,
            'message': f"Defect {new_defect['defect_code']} successfully created by {current_user.get('name', 'User')} ({current_user.get('role')}).",
            'data': new_defect
        }), 201
    except PermissionError as pe:
        return jsonify({'success': False, 'error': str(pe)}), 403
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Internal server error: {str(e)}"}), 500

@defect_bp.route('/<id_or_code>', methods=['GET'])
def get_defect(id_or_code):
    """
    Retrieve defect by ID or Defect Code with role visibility checks
    and role-filtered allowed transitions.
    Supports ?include_deleted=true strictly for Admin.
    """
    current_user = get_current_user()
    inc_del = str(request.args.get('include_deleted')).lower() == 'true'

    try:
        defect = get_defect_by_id_or_code(id_or_code, actor=current_user, include_deleted=inc_del)
        if not defect:
            return jsonify({'success': False, 'error': f"Defect '{id_or_code}' not found."}), 404

        allowed_transitions = get_allowed_transitions_for_role(
            defect['status'],
            role=current_user.get('role'),
            defect=defect,
            actor=current_user
        )

        return jsonify({
            'success': True,
            'data': defect,
            'allowed_transitions': allowed_transitions,
            'active_role': current_user.get('role')
        }), 200
    except PermissionError as pe:
        return jsonify({'success': False, 'error': str(pe)}), 403

@defect_bp.route('/<id_or_code>', methods=['PUT'])
def update_defect_info(id_or_code):
    """
    Update defect details with strict field-level role authorization checks.
    Rejects unauthorized fields per role allowlist with HTTP 403.
    """
    current_user = get_current_user()
    if not current_user.get('role'):
        return jsonify({'success': False, 'error': 'Forbidden: Authentication required.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload in request body.'}), 400

    # Strict field allowlist validation on PUT
    is_allowed, err_msg = validate_field_permissions(current_user['role'], data.keys())
    if not is_allowed:
        return jsonify({'success': False, 'error': err_msg}), 403

    try:
        updated = update_defect(id_or_code, data, actor=current_user)
        if not updated:
            return jsonify({'success': False, 'error': f"Defect '{id_or_code}' not found."}), 404

        return jsonify({
            'success': True,
            'message': f"Defect {updated['defect_code']} updated successfully by {current_user['role']}.",
            'data': updated
        }), 200
    except PermissionError as pe:
        return jsonify({'success': False, 'error': str(pe)}), 403
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to update defect: {str(e)}"}), 500

@defect_bp.route('/<id_or_code>', methods=['PATCH'])
def patch_defect(id_or_code):
    """
    Partially update defect or trigger lifecycle state transition.
    Enforces state machine, field allowlists, and role-based authorization.
    Rejects unauthorized fields per role allowlist with HTTP 403.
    """
    current_user = get_current_user()
    if not current_user.get('role'):
        return jsonify({'success': False, 'error': 'Forbidden: Authentication required.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload in request body.'}), 400

    # Retrieve existing defect to check authorization and detect modified fields
    try:
        existing = get_defect_by_id_or_code(id_or_code, actor=current_user)
        if not existing:
            return jsonify({'success': False, 'error': f"Defect '{id_or_code}' not found."}), 404
    except PermissionError as pe:
        return jsonify({'success': False, 'error': str(pe)}), 403

    # If assignee or verification_assignee is passed by non-Admin, verify they are not attempting reassignment
    keys_to_validate = set(data.keys())
    if current_user['role'] != 'Admin':
        if 'assignee' in data:
            if str(data['assignee']).strip().lower() != (existing.get('assignee') or '').strip().lower():
                return jsonify({'success': False, 'error': "Forbidden: Only Admin can assign or change defect assignees."}), 403
            keys_to_validate.discard('assignee')
        if 'verification_assignee' in data:
            if str(data.get('verification_assignee') or '').strip().lower() != (existing.get('verification_assignee') or '').strip().lower():
                return jsonify({'success': False, 'error': "Forbidden: Only Admin can assign or change QA verification assignees."}), 403
            keys_to_validate.discard('verification_assignee')

    # Strict field allowlist validation on PATCH for remaining fields
    is_allowed, err_msg = validate_field_permissions(current_user['role'], keys_to_validate)
    if not is_allowed:
        return jsonify({'success': False, 'error': err_msg}), 403

    try:
        if 'status' in data:
            updated = transition_defect(
                id_or_code=id_or_code,
                new_status=data['status'],
                assignee=data.get('assignee'),
                verification_assignee=data.get('verification_assignee'),
                notes=data.get('notes'),
                investigation_notes=data.get('investigation_notes'),
                resolution_notes=data.get('resolution_notes'),
                fix_description=data.get('fix_description'),
                commit_reference=data.get('commit_reference'),
                verification_notes=data.get('verification_notes'),
                reopening_reason=data.get('reopening_reason'),
                actor=current_user
            )
        else:
            updated = update_defect(id_or_code, data, actor=current_user)

        if not updated:
            return jsonify({'success': False, 'error': f"Defect '{id_or_code}' not found."}), 404

        return jsonify({
            'success': True,
            'message': f"Defect {updated['defect_code']} updated successfully by {current_user['role']}.",
            'data': updated
        }), 200
    except PermissionError as pe:
        return jsonify({'success': False, 'error': str(pe)}), 403
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to patch defect: {str(e)}"}), 500

@defect_bp.route('/<id_or_code>', methods=['DELETE'])
@require_roles('Admin')
def remove_defect(id_or_code):
    """
    Delete a defect (Soft deletion).
    Authorized exclusively for Admin. Developer and Tester receive HTTP 403.
    """
    current_user = get_current_user()
    defect = get_defect_by_id_or_code(id_or_code, actor=current_user)
    if not defect:
        return jsonify({'success': False, 'error': f"Defect '{id_or_code}' not found."}), 404

    try:
        deleted = delete_defect(id_or_code, actor=current_user)
        if deleted:
            return jsonify({
                'success': True,
                'message': f"Defect {defect['defect_code']} successfully deleted by Admin."
            }), 200
        return jsonify({'success': False, 'error': 'Failed to delete defect.'}), 500
    except PermissionError as pe:
        return jsonify({'success': False, 'error': str(pe)}), 403

@defect_bp.route('/<id_or_code>/history', methods=['GET'])
def defect_history_endpoint(id_or_code):
    """
    Retrieve defect audit lifecycle history.
    Enforces role visibility: Developer can view history only for assigned defects,
    Tester only for reported or verification-relevant defects.
    """
    current_user = get_current_user()

    try:
        history = get_defect_history(id_or_code, actor=current_user)
        if history is None:
            return jsonify({'success': False, 'error': f"Defect '{id_or_code}' not found."}), 404

        defect = get_defect_by_id_or_code(id_or_code, actor=current_user, include_deleted=True)
        return jsonify({
            'success': True,
            'defect_code': defect['defect_code'] if defect else id_or_code,
            'count': len(history),
            'data': history
        }), 200
    except PermissionError as pe:
        return jsonify({'success': False, 'error': str(pe)}), 403
