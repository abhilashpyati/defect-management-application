from datetime import datetime
from database.db import get_db
from services.defect_service import MODULES, SEVERITIES, PRIORITIES, DISCOVERY_PHASES, ENVIRONMENTS
from services.auth_service import normalize_role, can_view_defect, validate_actor

SEVERITY_WEIGHTS = {
    'Blocker': 3,
    'Critical': 3,
    'Major': 2,
    'Minor': 1,
    'Trivial': 0
}

MODULE_TEST_RECOMMENDATIONS = {
    'Authentication': [
        "Conduct automated boundary security tests for JWT expiration (exp) and not-before (nbf) claims.",
        "Execute cross-device session termination integration tests upon credential resets.",
        "Verify RBAC permission matrix across all authenticated route decorators."
    ],
    'Payments': [
        "Execute high-concurrency automated tests targeting idempotent checkout (Idempotency-Key headers).",
        "Verify IEEE-754 precision compliance using fixed-point Decimal arithmetic for multi-currency taxes.",
        "Perform fault-injection tests simulating gateway timeout and retry deduplication."
    ],
    'Cart & Checkout': [
        "Run automated DOMPurify and context-aware XSS fuzzing on promotional notes and custom inputs.",
        "Perform multi-device mobile viewport regression tests (iOS Safari safe-area insets).",
        "Test abandoned cart expiration and cart session TTL edge cases."
    ],
    'Inventory': [
        "Execute JMeter concurrent load tests verifying pessimistic/atomic stock decrements.",
        "Verify zero and negative quantity boundary checks across catalog pagination filters.",
        "Conduct warehouse fulfillment database transaction rollback tests."
    ],
    'Notification Service': [
        "Simulate third-party SMTP/SMS API degradation to ensure non-blocking Celery dispatch.",
        "Validate circuit breaker trip thresholds and exponential backoff retry policies.",
        "Verify message queue dead-letter routing under sustained throughput."
    ],
    'API Gateway': [
        "Conduct memory profile benchmarks under chunked streaming HTTP transfer payloads.",
        "Verify IP and tenant-level rate-limiting under distributed denial-of-service simulations.",
        "Audit payload size constraint filters (enforcing strict 10MB limits)."
    ]
}

def calculate_comprehensive_analytics(current_user=None):
    """
    Compute real-time statistical analytics, rule-based defect prediction,
    and role-specific dashboard views for Admin, Developer, and Tester.
    All calculations are derived dynamically from actual database records.
    Requires an explicitly validated current_user. Rejects missing or invalid users.
    """
    valid_user = validate_actor(current_user)
    actor_role = valid_user['role']
    actor_email = valid_user['email']
    actor_name = valid_user['name']
    conn = get_db()
    cursor = conn.cursor()

    # 1. Total active defects (excluding soft-deleted)
    cursor.execute("SELECT COUNT(*) FROM defects WHERE is_deleted = 0")
    total_defects = cursor.fetchone()[0]

    # 2. Open defects (NEW, ASSIGNED, IN PROGRESS, REOPENED)
    cursor.execute("""
        SELECT COUNT(*) FROM defects
        WHERE is_deleted = 0 AND UPPER(status) IN ('NEW', 'ASSIGNED', 'IN PROGRESS', 'REOPENED')
    """)
    open_defects = cursor.fetchone()[0]

    # 3. Resolved defects (RESOLVED, VERIFIED, CLOSED)
    cursor.execute("""
        SELECT COUNT(*) FROM defects
        WHERE is_deleted = 0 AND UPPER(status) IN ('RESOLVED', 'VERIFIED', 'CLOSED')
    """)
    resolved_defects = cursor.fetchone()[0]

    # Status Breakdown
    cursor.execute("SELECT status, COUNT(*) as count FROM defects WHERE is_deleted = 0 GROUP BY status")
    status_counts = {r['status']: r['count'] for r in cursor.fetchall()}

    # 4. Defects by Severity
    cursor.execute("SELECT severity, COUNT(*) as count FROM defects WHERE is_deleted = 0 GROUP BY severity")
    raw_severity = {r['severity']: r['count'] for r in cursor.fetchall()}
    defects_by_severity = {s: raw_severity.get(s, 0) for s in SEVERITIES}

    # 5. Defects by Priority
    cursor.execute("SELECT priority, COUNT(*) as count FROM defects WHERE is_deleted = 0 GROUP BY priority")
    raw_priority = {r['priority']: r['count'] for r in cursor.fetchall()}
    defects_by_priority = {}
    for p in PRIORITIES:
        c = raw_priority.get(p, 0) + raw_priority.get(p.replace('–', '-'), 0)
        defects_by_priority[p] = c

    # 6. Defects by Module
    cursor.execute("SELECT module, COUNT(*) as count FROM defects WHERE is_deleted = 0 GROUP BY module")
    raw_module = {r['module']: r['count'] for r in cursor.fetchall()}
    defects_by_module = {m: raw_module.get(m, 0) for m in MODULES}

    # 7. Defects by Discovery Phase
    cursor.execute("SELECT discovery_phase, COUNT(*) as count FROM defects WHERE is_deleted = 0 GROUP BY discovery_phase")
    raw_phase = {r['discovery_phase']: r['count'] for r in cursor.fetchall()}
    defects_by_phase = {dp: raw_phase.get(dp, 0) for dp in DISCOVERY_PHASES}

    # Defects by Environment
    cursor.execute("SELECT environment, COUNT(*) as count FROM defects WHERE is_deleted = 0 GROUP BY environment")
    raw_env = {r['environment']: r['count'] for r in cursor.fetchall()}
    defects_by_env = {e: raw_env.get(e, 0) for e in ENVIRONMENTS}

    # 8. Defect Leakage Percentage
    cursor.execute("""
        SELECT COUNT(*) FROM defects
        WHERE is_deleted = 0 AND UPPER(discovery_phase) != 'UNIT TESTING'
    """)
    defects_after_unit = cursor.fetchone()[0]
    defect_leakage_percentage = round((defects_after_unit / total_defects) * 100, 2) if total_defects > 0 else 0.0

    # 9. Open-to-Resolved Ratio
    if resolved_defects == 0:
        open_to_resolved_ratio = float(open_defects)
        open_to_resolved_ratio_display = f"{open_defects} : 0"
    else:
        ratio_val = round(open_defects / resolved_defects, 2)
        open_to_resolved_ratio = ratio_val
        open_to_resolved_ratio_display = f"{ratio_val} : 1"

    # 10. Mean Time to Resolve (MTTR)
    cursor.execute("""
        SELECT created_at, resolved_at FROM defects
        WHERE is_deleted = 0 AND resolved_at IS NOT NULL AND resolved_at != ''
    """)
    resolved_times = cursor.fetchall()

    mttr_hours = 0.0
    mttr_days = 0.0
    mttr_display = "N/A"

    if resolved_times:
        total_seconds = 0.0
        valid_resolutions = 0
        for r in resolved_times:
            try:
                c_dt = datetime.strptime(r['created_at'], '%Y-%m-%d %H:%M:%S')
                r_dt = datetime.strptime(r['resolved_at'], '%Y-%m-%d %H:%M:%S')
                diff_sec = max(0.0, (r_dt - c_dt).total_seconds())
                total_seconds += diff_sec
                valid_resolutions += 1
            except Exception:
                continue

        if valid_resolutions > 0:
            avg_seconds = total_seconds / valid_resolutions
            mttr_hours = round(avg_seconds / 3600.0, 1)
            mttr_days = round(avg_seconds / 86400.0, 2)
            if mttr_hours >= 48:
                mttr_display = f"{mttr_days} days"
            else:
                mttr_display = f"{mttr_hours} hrs"

    # -------------------------------------------------------------
    # SUBPROCESS 6: RULE-BASED DEFECT PREDICTION & RISK SCORING
    # -------------------------------------------------------------
    cursor.execute("""
        SELECT module, severity, COUNT(*) as count
        FROM defects
        WHERE is_deleted = 0
        GROUP BY module, severity
    """)
    mod_sev_rows = cursor.fetchall()

    module_breakdown = {m: {'Blocker': 0, 'Critical': 0, 'Major': 0, 'Minor': 0, 'Trivial': 0, 'Total': 0} for m in MODULES}
    for r in mod_sev_rows:
        mod = r['module']
        sev = r['severity']
        cnt = r['count']
        if mod in module_breakdown and sev in module_breakdown[mod]:
            module_breakdown[mod][sev] = cnt
            module_breakdown[mod]['Total'] += cnt

    module_risk_ranking = []
    high_risk_alerts = []

    for mod, counts in module_breakdown.items():
        high_impact = counts['Blocker'] + counts['Critical']
        risk_score = (3 * high_impact) + (2 * counts['Major']) + (1 * counts['Minor'])

        defect_count = counts['Total']
        concentration_pct = round((defect_count / total_defects) * 100, 1) if total_defects > 0 else 0.0

        if risk_score >= 8:
            risk_level = "CRITICAL"
            badge_class = "danger"
        elif risk_score >= 4:
            risk_level = "HIGH"
            badge_class = "warning"
        elif risk_score >= 2:
            risk_level = "MODERATE"
            badge_class = "primary"
        else:
            risk_level = "LOW"
            badge_class = "success"

        module_entry = {
            'module': mod,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'badge_class': badge_class,
            'defect_count': defect_count,
            'concentration_percentage': concentration_pct,
            'blocker_critical_count': high_impact,
            'major_count': counts['Major'],
            'minor_count': counts['Minor'],
            'trivial_count': counts['Trivial'],
            'recommended_tests': MODULE_TEST_RECOMMENDATIONS.get(mod, [])
        }
        module_risk_ranking.append(module_entry)

        if high_impact >= 1 or risk_score >= 5:
            high_risk_alerts.append({
                'module': mod,
                'risk_score': risk_score,
                'risk_level': risk_level,
                'alert_message': f"Module '{mod}' exhibits elevated defect severity (Score: {risk_score}, Blocker/Critical: {high_impact}). Urgent regression test coverage required."
            })

    module_risk_ranking.sort(key=lambda x: (x['risk_score'], x['defect_count']), reverse=True)
    highest_risk_module = module_risk_ranking[0] if module_risk_ranking else None

    top_recommendations = []
    for item in module_risk_ranking[:3]:
        top_recommendations.append({
            'module': item['module'],
            'risk_score': item['risk_score'],
            'risk_level': item['risk_level'],
            'focus_areas': item['recommended_tests']
        })

    # -------------------------------------------------------------
    # ROLE-SPECIFIC DASHBOARD ANALYTICS (Admin, Developer, Tester)
    # -------------------------------------------------------------
    # 1. Developer Workload (Admin view)
    cursor.execute("""
        SELECT assignee, COUNT(*) as count,
               SUM(CASE WHEN UPPER(status) IN ('NEW', 'ASSIGNED', 'IN PROGRESS', 'REOPENED') THEN 1 ELSE 0 END) as open_count,
               SUM(CASE WHEN UPPER(status) IN ('RESOLVED', 'VERIFIED', 'CLOSED') THEN 1 ELSE 0 END) as resolved_count
        FROM defects
        WHERE is_deleted = 0
        GROUP BY assignee
        ORDER BY count DESC
    """)
    developer_workload = [dict(r) for r in cursor.fetchall()]

    # 2. System Activities (Filtered using centralized defect visibility)
    cursor.execute("""
        SELECT dh.id, dh.defect_id, d.defect_code, d.title, d.assignee as defect_assignee,
               d.reporter as defect_reporter, d.verification_assignee as defect_verification_assignee,
               dh.previous_status, dh.new_status, dh.assignee, dh.notes, dh.actor_email, dh.actor_role, dh.timestamp
        FROM defect_history dh
        JOIN defects d ON dh.defect_id = d.id
        WHERE d.is_deleted = 0
        ORDER BY dh.id DESC
        LIMIT 50
    """)
    all_raw_activities = [dict(r) for r in cursor.fetchall()]

    from services.auth_service import can_view_defect
    def filter_activities_for_actor(raw_list, actor):
        if not actor or normalize_role(actor.get('role')) == 'Admin':
            return raw_list
        visible_acts = []
        for a in raw_list:
            mock_defect = {
                'id': a['defect_id'],
                'defect_code': a['defect_code'],
                'assignee': a['defect_assignee'],
                'reporter': a['defect_reporter'],
                'verification_assignee': a['defect_verification_assignee'],
                'status': a['new_status']
            }
            if can_view_defect(mock_defect, actor):
                visible_acts.append(a)
        return visible_acts

    # Global activities for Admin view
    recent_activities = all_raw_activities[:10]

    # 3. Developer View Metrics (Exact Identity Matching)
    dev_email = actor_email
    dev_name = actor_name
    cursor.execute("""
        SELECT * FROM defects
        WHERE is_deleted = 0 AND (LOWER(assignee) = LOWER(?) OR LOWER(assignee) = LOWER(?))
        ORDER BY id DESC
    """, (dev_email, dev_name))
    dev_assigned_rows = [dict(r) for r in cursor.fetchall()]

    dev_total_assigned = len(dev_assigned_rows)
    dev_new_assigned = len([d for d in dev_assigned_rows if d['status'] == 'ASSIGNED'])
    dev_in_progress = len([d for d in dev_assigned_rows if d['status'] == 'IN PROGRESS'])
    dev_resolved = len([d for d in dev_assigned_rows if d['status'] in ('RESOLVED', 'VERIFIED', 'CLOSED')])

    dev_prio_counts = {
        'P1 – High': len([d for d in dev_assigned_rows if 'P1' in d['priority'] or 'HIGH' in d['priority'].upper()]),
        'P2 – Medium': len([d for d in dev_assigned_rows if 'P2' in d['priority'] or 'MEDIUM' in d['priority'].upper()]),
        'P3 – Low': len([d for d in dev_assigned_rows if 'P3' in d['priority'] or 'LOW' in d['priority'].upper()])
    }

    dev_recent_updates = filter_activities_for_actor(all_raw_activities, {'role': 'Developer', 'email': dev_email, 'name': dev_name})[:6]

    # 4. Tester View Metrics (Exact Identity Matching on Reporter or Verification Assignee)
    tester_email = actor_email
    tester_name = actor_name
    cursor.execute("""
        SELECT * FROM defects
        WHERE is_deleted = 0 AND (
            LOWER(reporter) = LOWER(?) OR LOWER(reporter) = LOWER(?) OR
            LOWER(verification_assignee) = LOWER(?) OR LOWER(verification_assignee) = LOWER(?)
        )
        ORDER BY id DESC
    """, (tester_email, tester_name, tester_email, tester_name))
    tester_authorized_rows = [dict(r) for r in cursor.fetchall()]

    tester_reported_count = len([d for d in tester_authorized_rows if (d.get('reporter') or '').lower() in (tester_email.lower(), tester_name.lower())])
    awaiting_verification_rows = [d for d in tester_authorized_rows if (d.get('status') or '').upper() == 'RESOLVED']

    tester_new_defects = len([d for d in tester_authorized_rows if (d.get('status') or '').upper() == 'NEW'])
    tester_awaiting_verification = len(awaiting_verification_rows)
    tester_verified = len([d for d in tester_authorized_rows if (d.get('status') or '').upper() == 'VERIFIED'])
    tester_reopened = len([d for d in tester_authorized_rows if (d.get('status') or '').upper() == 'REOPENED'])
    tester_recent_activities = filter_activities_for_actor(all_raw_activities, {'role': 'Tester', 'email': tester_email, 'name': tester_name})[:6]

    # If Developer requests analytics, strictly restrict payload to assigned defect statistics
    if actor_role == 'Developer':
        return {
            'role': 'Developer',
            'kpis': {
                'assigned_defects': dev_total_assigned,
                'in_progress': dev_in_progress,
                'resolved_defects': dev_resolved
            },
            'role_dashboards': {
                'developer': {
                    'assigned_defects': dev_total_assigned,
                    'new_assignments': dev_new_assigned,
                    'in_progress': dev_in_progress,
                    'resolved_defects': dev_resolved,
                    'defects_by_priority': dev_prio_counts,
                    'recent_updates': dev_recent_updates,
                    'assigned_defects_list': dev_assigned_rows[:8]
                }
            },
            'recent_activities': dev_recent_updates
        }

    # If Tester requests analytics, strictly restrict payload to testing metrics
    if actor_role == 'Tester':
        return {
            'role': 'Tester',
            'kpis': {
                'total_reported': tester_reported_count,
                'new_defects': tester_new_defects,
                'awaiting_verification': tester_awaiting_verification,
                'verified_defects': tester_verified,
                'reopened_defects': tester_reopened
            },
            'role_dashboards': {
                'tester': {
                    'total_reported': tester_reported_count,
                    'new_defects': tester_new_defects,
                    'awaiting_verification': tester_awaiting_verification,
                    'verified_defects': tester_verified,
                    'reopened_defects': tester_reopened,
                    'recent_activities': tester_recent_activities,
                    'awaiting_verification_list': awaiting_verification_rows[:8]
                }
            },
            'recent_activities': tester_recent_activities
        }

    # Admin (or full test runner context): complete system-wide analytics
    return {
        'kpis': {
            'total_defects': total_defects,
            'open_defects': open_defects,
            'in_progress': status_counts.get('IN PROGRESS', 0),
            'resolved_defects': resolved_defects,
            'critical_blocker_defects': defects_by_severity.get('Blocker', 0) + defects_by_severity.get('Critical', 0),
            'high_risk_modules_count': len([m for m in module_risk_ranking if m['risk_score'] >= 4]),
            'defect_leakage_percentage': defect_leakage_percentage,
            'open_to_resolved_ratio': open_to_resolved_ratio,
            'open_to_resolved_ratio_display': open_to_resolved_ratio_display,
            'mttr_hours': mttr_hours,
            'mttr_days': mttr_days,
            'mttr_display': mttr_display
        },
        'status_distribution': status_counts,
        'severity_distribution': defects_by_severity,
        'priority_distribution': defects_by_priority,
        'module_distribution': defects_by_module,
        'phase_distribution': defects_by_phase,
        'environment_distribution': defects_by_env,
        'prediction': {
            'algorithm': 'Rule-Based Weighted Severity Scoring Model (Section 1.9 Formula)',
            'is_rule_based': True,
            'formula_description': 'Risk Score = (3 × Blocker/Critical) + (2 × Major) + (1 × Minor)',
            'highest_risk_module': highest_risk_module,
            'module_risk_ranking': module_risk_ranking,
            'high_risk_alerts': high_risk_alerts,
            'recommendations': top_recommendations
        },
        'role_dashboards': {
            'admin': {
                'total_defects': total_defects,
                'open_defects': open_defects,
                'resolved_defects': resolved_defects,
                'critical_defects': defects_by_severity.get('Blocker', 0) + defects_by_severity.get('Critical', 0),
                'defects_by_severity': defects_by_severity,
                'defects_by_status': status_counts,
                'developer_workload': developer_workload,
                'recent_activities': recent_activities
            },
            'developer': {
                'assigned_defects': dev_total_assigned,
                'new_assignments': dev_new_assigned,
                'in_progress': dev_in_progress,
                'resolved_defects': dev_resolved,
                'defects_by_priority': dev_prio_counts,
                'recent_updates': dev_recent_updates,
                'assigned_defects_list': dev_assigned_rows[:8]
            },
            'tester': {
                'total_reported': tester_reported_count,
                'new_defects': tester_new_defects,
                'awaiting_verification': tester_awaiting_verification,
                'verified_defects': tester_verified,
                'reopened_defects': tester_reopened,
                'recent_activities': tester_recent_activities,
                'awaiting_verification_list': awaiting_verification_rows[:8]
            }
        }
    }
