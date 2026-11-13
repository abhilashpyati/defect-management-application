from flask import Blueprint, request, jsonify
from services.prevention_service import (
    get_all_prevention_guidelines, get_prevention_guideline_by_id,
    add_prevention_guideline, update_prevention_guideline,
    delete_prevention_guideline, get_prevention_knowledge_summary
)
from services.auth_service import require_roles

prevention_bp = Blueprint('prevention', __name__, url_prefix='/api/prevention')

@prevention_bp.route('', methods=['GET'])
def list_prevention():
    """Retrieve prevention records with optional filters (All roles)."""
    filters = {
        'module': request.args.get('module'),
        'category': request.args.get('category'),
        'search': request.args.get('search')
    }
    guidelines = get_all_prevention_guidelines(filters)
    return jsonify({
        'success': True,
        'count': len(guidelines),
        'data': guidelines
    }), 200

@prevention_bp.route('', methods=['POST'])
@require_roles('Admin')
def create_prevention():
    """Add a new prevention guideline (Admin only)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    try:
        new_record = add_prevention_guideline(data)
        return jsonify({
            'success': True,
            'message': 'Prevention guideline recorded successfully by Admin.',
            'data': new_record
        }), 201
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Internal server error: {str(e)}"}), 500

@prevention_bp.route('/<int:guideline_id>', methods=['GET'])
def get_prevention(guideline_id):
    """Retrieve specific prevention guideline (All roles)."""
    record = get_prevention_guideline_by_id(guideline_id)
    if not record:
        return jsonify({'success': False, 'error': f"Prevention record '{guideline_id}' not found."}), 404
    return jsonify({'success': True, 'data': record}), 200

@prevention_bp.route('/<int:guideline_id>', methods=['PUT'])
@require_roles('Admin')
def edit_prevention(guideline_id):
    """Update a prevention guideline (Admin only)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    try:
        updated = update_prevention_guideline(guideline_id, data)
        if not updated:
            return jsonify({'success': False, 'error': f"Prevention record '{guideline_id}' not found."}), 404
        return jsonify({
            'success': True,
            'message': 'Prevention guideline updated successfully by Admin.',
            'data': updated
        }), 200
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to update prevention record: {str(e)}"}), 500

@prevention_bp.route('/<int:guideline_id>', methods=['DELETE'])
@require_roles('Admin')
def remove_prevention(guideline_id):
    """Delete a prevention guideline (Admin only)."""
    deleted = delete_prevention_guideline(guideline_id)
    if not deleted:
        return jsonify({'success': False, 'error': f"Prevention record '{guideline_id}' not found."}), 404
    return jsonify({
        'success': True,
        'message': f"Prevention record '{guideline_id}' successfully deleted by Admin."
    }), 200

@prevention_bp.route('/summary', methods=['GET'])
def prevention_summary():
    """Retrieve knowledge base summary and recurring problem patterns."""
    summary = get_prevention_knowledge_summary()
    return jsonify({'success': True, 'data': summary}), 200
