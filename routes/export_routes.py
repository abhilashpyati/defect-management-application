"""
DefectGuard - CSV Export Routes
Exports defects matching active filters with strict role-based visibility enforcement.
Admin exports all matching records; Developer exports only assigned records;
Tester exports only reported or verification-relevant records.
"""

import csv
import io
from flask import Blueprint, request, Response
from services.defect_service import get_all_defects
from services.auth_service import get_current_user

export_bp = Blueprint('export', __name__, url_prefix='/api/export')

@export_bp.route('/csv', methods=['GET'])
def export_defects_csv():
    """
    Export defects dataset as CSV file with filtering support and backend role enforcement.
    """
    current_user = get_current_user()

    filters = {
        'status': request.args.get('status'),
        'severity': request.args.get('severity'),
        'priority': request.args.get('priority'),
        'module': request.args.get('module'),
        'discovery_phase': request.args.get('discovery_phase'),
        'assignee': request.args.get('assignee'),
        'search': request.args.get('search')
    }

    # Strict backend visibility enforcement on CSV export
    defects = get_all_defects(filters, actor=current_user)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header Row
    headers = [
        'Defect ID',
        'Title',
        'Description',
        'Steps to Reproduce',
        'Expected Behaviour',
        'Actual Behaviour',
        'Functional Module',
        'Classification Type',
        'Severity',
        'Priority',
        'Discovery Phase',
        'Testing Environment',
        'Status',
        'Reporter',
        'Assignee',
        'Verification Assignee',
        'Prevention Guideline',
        'Investigation Notes',
        'Resolution Notes',
        'Commit Reference',
        'Verification Notes',
        'Reopening Reason',
        'Created Date',
        'Updated Date',
        'Resolved Date',
        'Closed Date'
    ]
    writer.writerow(headers)

    for d in defects:
        writer.writerow([
            d.get('defect_code', ''),
            d.get('title', ''),
            d.get('description', ''),
            d.get('steps_to_reproduce', ''),
            d.get('expected_behavior', ''),
            d.get('actual_behavior', ''),
            d.get('module', ''),
            d.get('type', ''),
            d.get('severity', ''),
            d.get('priority', ''),
            d.get('discovery_phase', ''),
            d.get('environment', ''),
            d.get('status', ''),
            d.get('reporter', ''),
            d.get('assignee', ''),
            d.get('verification_assignee', '') or '',
            d.get('prevention_guideline', '') or '',
            d.get('investigation_notes', '') or '',
            d.get('resolution_notes', '') or '',
            d.get('commit_reference', '') or '',
            d.get('verification_notes', '') or '',
            d.get('reopening_reason', '') or '',
            d.get('created_at', ''),
            d.get('updated_at', ''),
            d.get('resolved_at', '') or '',
            d.get('closed_at', '') or ''
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=defects_export.csv",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )
