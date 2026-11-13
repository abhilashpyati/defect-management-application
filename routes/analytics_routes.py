from datetime import datetime, timezone
from flask import Blueprint, jsonify
from services.prediction_service import calculate_comprehensive_analytics
from services.auth_service import get_current_user
from database.db import get_db

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api')

@analytics_bp.route('/analytics', methods=['GET'])
def get_analytics():
    """Retrieve statistical analytics, defect prediction, discovery metrics, and role dashboard data."""
    try:
        current_user = get_current_user()
        analytics = calculate_comprehensive_analytics(current_user=current_user)
        return jsonify({
            'success': True,
            'active_role': current_user['role'],
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            'data': analytics
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': f"Analytics computation failed: {str(e)}"}), 500

@analytics_bp.route('/health', methods=['GET'])
def health_check():
    """System health check endpoint."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM defects")
        defect_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM prevention_guidelines")
        prevention_count = cursor.fetchone()[0]

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            'database': 'connected',
            'counts': {
                'total_defects': defect_count,
                'prevention_guidelines': prevention_count
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'error',
            'error': str(e)
        }), 500
