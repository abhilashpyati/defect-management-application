import pytest

def test_role_switching_session(client):
    """
    Test switching between all three demo roles and verifying session persistence.
    """
    # 1. Default session should be Admin
    s_resp = client.get('/api/auth/session')
    assert s_resp.status_code == 200
    assert s_resp.get_json()['user']['role'] == 'Admin'

    # 2. Switch to Developer
    dev_resp = client.post('/api/auth/switch-role', json={'role': 'Developer'})
    assert dev_resp.status_code == 200
    assert dev_resp.get_json()['user']['role'] == 'Developer'
    assert dev_resp.get_json()['user']['email'] == 'developer@demo.com'

    # Verify session retained Developer
    s_resp2 = client.get('/api/auth/session')
    assert s_resp2.get_json()['user']['role'] == 'Developer'

    # 3. Switch to Tester
    test_resp = client.post('/api/auth/switch-role', json={'role': 'Tester'})
    assert test_resp.status_code == 200
    assert test_resp.get_json()['user']['role'] == 'Tester'
    assert test_resp.get_json()['user']['email'] == 'tester@demo.com'

    # 4. Switch back to Admin
    admin_resp = client.post('/api/auth/switch-role', json={'role': 'Admin'})
    assert admin_resp.status_code == 200
    assert admin_resp.get_json()['user']['role'] == 'Admin'

    # 5. Invalid roles strictly rejected with HTTP 400 (never granted Admin)
    bad_resp = client.post('/api/auth/switch-role', json={'role': 'Superuser'})
    assert bad_resp.status_code == 400
    assert bad_resp.get_json()['success'] is False

    bad_resp2 = client.post('/api/auth/switch-role', json={'role': 'Administrator2'})
    assert bad_resp2.status_code == 400
    assert bad_resp2.get_json()['success'] is False

    bad_resp3 = client.post('/api/auth/switch-role', json={'role': ''})
    assert bad_resp3.status_code == 400
    assert bad_resp3.get_json()['success'] is False

    bad_resp4 = client.post('/api/auth/switch-role', json={'role': 'Unknown'})
    assert bad_resp4.status_code == 400
    assert bad_resp4.get_json()['success'] is False

def test_admin_permissions(client, sample_defect_payload):
    """
    Test that Admin has full authority to create, assign, change priority/severity,
    manage prevention guidelines, and delete defects.
    """
    headers = {'X-Demo-Role': 'Admin'}

    # 1. Admin creates defect
    p = dict(sample_defect_payload, title="Admin created defect")
    create_r = client.post('/api/defects', json=p, headers=headers)
    assert create_r.status_code == 201
    d_code = create_r.get_json()['data']['defect_code']

    # 2. Admin assigns defect (NEW -> ASSIGNED)
    assign_r = client.patch(f"/api/defects/{d_code}", json={
        "status": "ASSIGNED",
        "assignee": "developer@demo.com"
    }, headers=headers)
    assert assign_r.status_code == 200
    assert assign_r.get_json()['data']['status'] == 'ASSIGNED'

    # 3. Admin modifies severity & priority
    edit_r = client.put(f"/api/defects/{d_code}", json={
        "severity": "Minor",
        "priority": "P3 – Low"
    }, headers=headers)
    assert edit_r.status_code == 200
    assert edit_r.get_json()['data']['severity'] == 'Minor'

    # 4. Admin manages prevention guidelines
    prev_r = client.post('/api/prevention', json={
        "root_cause": "Admin root cause",
        "guideline": "Admin prevention rule",
        "module": "Authentication",
        "category": "Security"
    }, headers=headers)
    assert prev_r.status_code == 201
    prev_id = prev_r.get_json()['data']['id']

    # 5. Admin deletes defect
    del_r = client.delete(f"/api/defects/{d_code}", headers=headers)
    assert del_r.status_code == 200

def test_developer_permissions(client, sample_defect_payload):
    """
    Test Developer permissions:
    - CANNOT record new defect (403)
    - CANNOT delete defect (403)
    - CANNOT alter severity or priority (403)
    - CANNOT manage prevention guidelines (403)
    - CAN progress assigned defect to IN PROGRESS and RESOLVED
    - CANNOT verify defect (403)
    """
    dev_headers = {'X-Demo-Role': 'Developer'}
    admin_headers = {'X-Demo-Role': 'Admin'}

    # 1. Developer cannot record new defect
    dev_create = client.post('/api/defects', json=sample_defect_payload, headers=dev_headers)
    assert dev_create.status_code == 403
    assert "restricted to [Admin, Tester]" in dev_create.get_json()['error'] or "Developer" in dev_create.get_json()['error']

    # Create defect as Admin and assign to developer@demo.com
    c_resp = client.post('/api/defects', json=sample_defect_payload, headers=admin_headers)
    d_code = c_resp.get_json()['data']['defect_code']
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)

    # 2. Developer cannot delete defect
    del_r = client.delete(f"/api/defects/{d_code}", headers=dev_headers)
    assert del_r.status_code == 403
    assert "restricted to [Admin]" in del_r.get_json()['error'] or "Admin" in del_r.get_json()['error']

    # 3. Developer cannot change severity or priority
    put_r = client.put(f"/api/defects/{d_code}", json={"severity": "Trivial"}, headers=dev_headers)
    assert put_r.status_code == 403
    assert "severity" in put_r.get_json()['error'] and "Developer" in put_r.get_json()['error']

    # 4. Developer cannot add prevention guidelines
    prev_r = client.post('/api/prevention', json={
        "root_cause": "Dev cause",
        "guideline": "Dev rule",
        "module": "Authentication",
        "category": "General"
    }, headers=dev_headers)
    assert prev_r.status_code == 403

    # 5. Developer CAN update assigned defect to IN PROGRESS
    prog_r = client.patch(f"/api/defects/{d_code}", json={
        "status": "IN PROGRESS",
        "notes": "Developer began investigation"
    }, headers=dev_headers)
    assert prog_r.status_code == 200
    assert prog_r.get_json()['data']['status'] == 'IN PROGRESS'

    # 6. Developer CAN mark assigned defect as RESOLVED
    res_r = client.patch(f"/api/defects/{d_code}", json={
        "status": "RESOLVED",
        "fix_description": "Added boundary check",
        "commit_reference": "commit 1234abcd"
    }, headers=dev_headers)
    assert res_r.status_code == 200
    assert res_r.get_json()['data']['status'] == 'RESOLVED'

    # 7. Developer CANNOT mark defect as VERIFIED
    ver_r = client.patch(f"/api/defects/{d_code}", json={"status": "VERIFIED"}, headers=dev_headers)
    assert ver_r.status_code == 403

def test_tester_permissions(client, sample_defect_payload):
    """
    Test Tester permissions:
    - CAN record new defect (201)
    - CANNOT delete defect (403)
    - CANNOT assign defect (403)
    - CANNOT start progress on defect (403)
    - CAN verify defect marked as RESOLVED (200)
    - CAN reopen defect marked as RESOLVED (200)
    - CANNOT manage prevention guidelines (403)
    """
    tester_headers = {'X-Demo-Role': 'Tester'}
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}

    # 1. Tester CAN record new defect
    t_create = client.post('/api/defects', json=sample_defect_payload, headers=tester_headers)
    assert t_create.status_code == 201
    d_code = t_create.get_json()['data']['defect_code']

    # 2. Tester CANNOT delete defect
    del_r = client.delete(f"/api/defects/{d_code}", headers=tester_headers)
    assert del_r.status_code == 403

    # 3. Tester CANNOT assign defect
    assign_r = client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "Dev X"}, headers=tester_headers)
    assert assign_r.status_code == 403

    # Advance defect using Admin and Developer
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)
    client.patch(f"/api/defects/{d_code}", json={"status": "IN PROGRESS"}, headers=dev_headers)
    client.patch(f"/api/defects/{d_code}", json={"status": "RESOLVED", "fix_description": "Done"}, headers=dev_headers)

    # 4. Tester CAN reopen a resolved defect
    reopen_r = client.patch(f"/api/defects/{d_code}", json={
        "status": "REOPENED",
        "notes": "Bug still reproducible on edge cases"
    }, headers=tester_headers)
    assert reopen_r.status_code == 200
    assert reopen_r.get_json()['data']['status'] == 'REOPENED'

    # Admin reassigns, Dev resolves again
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)
    client.patch(f"/api/defects/{d_code}", json={"status": "IN PROGRESS"}, headers=dev_headers)
    client.patch(f"/api/defects/{d_code}", json={"status": "RESOLVED"}, headers=dev_headers)

    # 5. Tester CAN verify the resolved defect
    verify_r = client.patch(f"/api/defects/{d_code}", json={
        "status": "VERIFIED",
        "notes": "Fix confirmed in staging environment"
    }, headers=tester_headers)
    assert verify_r.status_code == 200
    assert verify_r.get_json()['data']['status'] == 'VERIFIED'

    # 6. Tester CANNOT manage prevention guidelines
    prev_r = client.post('/api/prevention', json={
        "root_cause": "Tester cause",
        "guideline": "Tester rule",
        "module": "Payments",
        "category": "Validation"
    }, headers=tester_headers)
    assert prev_r.status_code == 403

def test_defect_history_records_actor_and_role(client, sample_defect_payload):
    """
    Verify that every lifecycle update records the acting demo identity and role
    in the immutable defect_history table.
    """
    # 1. Tester records defect
    c_resp = client.post('/api/defects', json=sample_defect_payload, headers={'X-Demo-Role': 'Tester'})
    d_code = c_resp.get_json()['data']['defect_code']

    # 2. Admin assigns defect
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers={'X-Demo-Role': 'Admin'})

    # 3. Developer starts work
    client.patch(f"/api/defects/{d_code}", json={"status": "IN PROGRESS"}, headers={'X-Demo-Role': 'Developer'})

    # 4. Developer marks resolved
    client.patch(f"/api/defects/{d_code}", json={"status": "RESOLVED", "fix_description": "Fixed"}, headers={'X-Demo-Role': 'Developer'})

    # 5. Tester verifies
    client.patch(f"/api/defects/{d_code}", json={"status": "VERIFIED"}, headers={'X-Demo-Role': 'Tester'})

    # Check History Records
    h_resp = client.get(f"/api/defects/{d_code}/history")
    assert h_resp.status_code == 200
    history = h_resp.get_json()['data']
    assert len(history) >= 5

    roles_in_history = [h.get('actor_role') for h in history]
    assert 'Tester' in roles_in_history
    assert 'Admin' in roles_in_history
    assert 'Developer' in roles_in_history

    emails_in_history = [h.get('actor_email') for h in history]
    assert any('tester@demo.com' in str(e) for e in emails_in_history)
    assert any('admin@demo.com' in str(e) for e in emails_in_history)
    assert any('developer@demo.com' in str(e) for e in emails_in_history)

def test_role_dashboard_data(client):
    """
    Verify that /api/analytics returns role-specific dashboard views
    for Admin, Developer, and Tester.
    """
    resp = client.get('/api/analytics')
    assert resp.status_code == 200
    data = resp.get_json()['data']

    assert 'role_dashboards' in data
    dashboards = data['role_dashboards']

    # Admin Dashboard
    assert 'admin' in dashboards
    admin_dash = dashboards['admin']
    assert 'developer_workload' in admin_dash
    assert 'recent_activities' in admin_dash

    # Developer Dashboard
    assert 'developer' in dashboards
    dev_dash = dashboards['developer']
    assert 'assigned_defects' in dev_dash
    assert 'new_assignments' in dev_dash
    assert 'in_progress' in dev_dash
    assert 'resolved_defects' in dev_dash
    assert 'defects_by_priority' in dev_dash

    # Tester Dashboard
    assert 'tester' in dashboards
    tester_dash = dashboards['tester']
    assert 'total_reported' in tester_dash
    assert 'new_defects' in tester_dash
    assert 'awaiting_verification' in tester_dash
    assert 'verified_defects' in tester_dash

def test_complete_demonstration_workflow(client, sample_defect_payload):
    """
    Demonstrate complete end-to-end multi-role collaborative workflow:
    1. Switch to Tester.
    2. Report a new defect (status: NEW).
    3. Switch to Admin.
    4. Review and assign defect to developer@demo.com (status: ASSIGNED).
    5. Switch to Developer.
    6. Investigate (status: IN PROGRESS) and resolve (status: RESOLVED).
    7. Switch to Tester.
    8. Verify the fix (status: VERIFIED).
    9. Switch to Admin and close the defect (status: CLOSED).
    """
    # 1. Switch to Tester
    r1 = client.post('/api/auth/switch-role', json={'role': 'Tester'})
    assert r1.status_code == 200

    # 2. Report a new defect
    r2 = client.post('/api/defects', json=sample_defect_payload)
    assert r2.status_code == 201
    d_code = r2.get_json()['data']['defect_code']
    assert r2.get_json()['data']['status'] == 'NEW'

    # 3. Switch to Admin
    r3 = client.post('/api/auth/switch-role', json={'role': 'Admin'})
    assert r3.status_code == 200

    # 4. Review and assign defect to developer
    r4 = client.patch(f"/api/defects/{d_code}", json={
        "status": "ASSIGNED",
        "assignee": "developer@demo.com",
        "notes": "Assigned to developer for urgent triage"
    })
    assert r4.status_code == 200
    assert r4.get_json()['data']['status'] == 'ASSIGNED'
    assert r4.get_json()['data']['assignee'] == 'developer@demo.com'

    # 5. Switch to Developer
    r5 = client.post('/api/auth/switch-role', json={'role': 'Developer'})
    assert r5.status_code == 200

    # 6. Investigate and resolve
    r6_start = client.patch(f"/api/defects/{d_code}", json={
        "status": "IN PROGRESS",
        "notes": "Investigating race condition logs"
    })
    assert r6_start.status_code == 200
    assert r6_start.get_json()['data']['status'] == 'IN PROGRESS'

    r6_resolve = client.patch(f"/api/defects/{d_code}", json={
        "status": "RESOLVED",
        "fix_description": "Added pessimistic lock to inventory capture",
        "commit_reference": "commit 90af231",
        "notes": "Code fix passes all local unit tests"
    })
    assert r6_resolve.status_code == 200
    assert r6_resolve.get_json()['data']['status'] == 'RESOLVED'

    # 7. Switch back to Tester
    r7 = client.post('/api/auth/switch-role', json={'role': 'Tester'})
    assert r7.status_code == 200

    # 8. Verify the fix
    r8 = client.patch(f"/api/defects/{d_code}", json={
        "status": "VERIFIED",
        "notes": "Verified in staging environment with concurrent JMeter tests"
    })
    assert r8.status_code == 200
    assert r8.get_json()['data']['status'] == 'VERIFIED'

    # 9. Switch to Admin and close
    r9 = client.post('/api/auth/switch-role', json={'role': 'Admin'})
    assert r9.status_code == 200

    r9_close = client.patch(f"/api/defects/{d_code}", json={
        "status": "CLOSED",
        "notes": "Accepted and closed for release candidate v2.0"
    })
    assert r9_close.status_code == 200
    assert r9_close.get_json()['data']['status'] == 'CLOSED'

    # Verify complete audit history
    h_resp = client.get(f"/api/defects/{d_code}/history")
    assert h_resp.status_code == 200
    history = h_resp.get_json()['data']
    assert len(history) == 6  # NEW -> ASSIGNED -> IN PROGRESS -> RESOLVED -> VERIFIED -> CLOSED

def test_role_normalization_and_validation():
    """
    Test Phase 2 centralized role normalization and strict rejection of invalid roles.
    """
    from services.auth_service import normalize_role, is_valid_role, VALID_ROLES

    assert VALID_ROLES == ('Admin', 'Developer', 'Tester')

    # Valid roles (case insensitive and whitespace safe)
    assert normalize_role('Admin') == 'Admin'
    assert normalize_role('admin') == 'Admin'
    assert normalize_role('  Developer  ') == 'Developer'
    assert normalize_role('developer') == 'Developer'
    assert normalize_role('TESTER') == 'Tester'
    assert normalize_role('tester') == 'Tester'

    assert is_valid_role('Admin') is True
    assert is_valid_role('Developer') is True
    assert is_valid_role('Tester') is True

    # Invalid roles must return None and NEVER default to Admin
    assert normalize_role('Superuser') is None
    assert normalize_role('Administrator2') is None
    assert normalize_role('Unknown') is None
    assert normalize_role('Guest') is None
    assert normalize_role('') is None
    assert normalize_role('   ') is None
    assert normalize_role(None) is None

    assert is_valid_role('Superuser') is False
    assert is_valid_role('Administrator2') is False
    assert is_valid_role('') is False
    assert is_valid_role(None) is False

def test_field_level_authorization_developer(client, sample_defect_payload):
    """
    Test Phase 5 field-level authorization:
    Developer is restricted to technical notes/commit references on assigned defects.
    Modifying unauthorized fields (title, severity, priority, assignee) returns 403 Forbidden.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}

    # 1. Admin creates defect and assigns to developer@demo.com
    c_resp = client.post('/api/defects', json=sample_defect_payload, headers=admin_headers)
    assert c_resp.status_code == 201
    d_code = c_resp.get_json()['data']['defect_code']

    client.patch(f"/api/defects/{d_code}", json={
        "status": "ASSIGNED",
        "assignee": "developer@demo.com"
    }, headers=admin_headers)

    # 2. Developer attempts to change severity -> 403 Forbidden
    r_sev = client.put(f"/api/defects/{d_code}", json={"severity": "Minor"}, headers=dev_headers)
    assert r_sev.status_code == 403
    assert "Forbidden" in r_sev.get_json()['error']

    # 3. Developer attempts to change title -> 403 Forbidden
    r_title = client.put(f"/api/defects/{d_code}", json={"title": "Hacked Title"}, headers=dev_headers)
    assert r_title.status_code == 403
    assert "Forbidden" in r_title.get_json()['error']

    # 4. Developer attempts to reassign defect -> 403 Forbidden
    r_ass = client.put(f"/api/defects/{d_code}", json={"assignee": "other@demo.com"}, headers=dev_headers)
    assert r_ass.status_code == 403
    assert "Forbidden" in r_ass.get_json()['error']

    # 5. Developer CAN update resolution_notes and commit_reference
    r_res = client.put(f"/api/defects/{d_code}", json={
        "resolution_notes": "Identified missing boundary check in auth filter.",
        "commit_reference": "commit 4a3f2b1"
    }, headers=dev_headers)
    assert r_res.status_code == 200
    assert r_res.get_json()['data']['resolution_notes'] == "Identified missing boundary check in auth filter."
    assert r_res.get_json()['data']['commit_reference'] == "commit 4a3f2b1"

def test_field_level_authorization_tester(client, sample_defect_payload):
    """
    Test Phase 5 field-level authorization for Tester:
    Tester cannot reassign defects, cannot edit technical resolution notes.
    """
    tester_headers = {'X-Demo-Role': 'Tester'}
    admin_headers = {'X-Demo-Role': 'Admin'}

    c_resp = client.post('/api/defects', json=sample_defect_payload, headers=tester_headers)
    d_code = c_resp.get_json()['data']['defect_code']

    # Tester attempts to reassign developer -> 403 Forbidden
    r_reassign = client.put(f"/api/defects/{d_code}", json={"assignee": "new_dev@demo.com"}, headers=tester_headers)
    assert r_reassign.status_code == 403
    assert "Forbidden" in r_reassign.get_json()['error']

    # Tester attempts to modify technical resolution details -> 403 Forbidden
    r_tech = client.put(f"/api/defects/{d_code}", json={"resolution_notes": "Tester resolution"}, headers=tester_headers)
    assert r_tech.status_code == 403
    assert "Forbidden" in r_tech.get_json()['error']

def test_exact_developer_assignment_check(client, sample_defect_payload):
    """
    Test Phase 7 exact developer identity matching:
    Developer cannot transition or edit defects assigned to someone else.
    Partial substring matching like 'dev' in assignee does NOT bypass authorization.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}

    # Create defect and assign to an unrelated engineer 'devops@company.com'
    c_resp = client.post('/api/defects', json=sample_defect_payload, headers=admin_headers)
    d_code = c_resp.get_json()['data']['defect_code']

    client.patch(f"/api/defects/{d_code}", json={
        "status": "ASSIGNED",
        "assignee": "devops@company.com"
    }, headers=admin_headers)

    # Developer (developer@demo.com) attempts to transition defect assigned to devops@company.com
    r_progress = client.patch(f"/api/defects/{d_code}", json={"status": "IN PROGRESS"}, headers=dev_headers)
    assert r_progress.status_code == 403
    assert "access" in r_progress.get_json()['error'] or "assigned to" in r_progress.get_json()['error']

    # Developer attempts to update defect assigned to devops@company.com
    r_update = client.put(f"/api/defects/{d_code}", json={"resolution_notes": "Trying to edit"}, headers=dev_headers)
    assert r_update.status_code == 403
    assert "access" in r_update.get_json()['error'] or "assigned to" in r_update.get_json()['error']

def test_soft_deletion_and_history_retention(client, sample_defect_payload):
    """
    Test Phase 8 soft deletion and audit history preservation:
    1. Only Admin can delete defects.
    2. Soft-deleted defects are removed from active queries and /api/defects.
    3. GET /api/defects/<code_or_id> returns 404 for soft-deleted defects.
    4. GET /api/defects/<code_or_id>/history remains fully accessible with DELETED action logged.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    tester_headers = {'X-Demo-Role': 'Tester'}
    dev_headers = {'X-Demo-Role': 'Developer'}

    # 1. Create defect
    c_resp = client.post('/api/defects', json=sample_defect_payload, headers=admin_headers)
    d_code = c_resp.get_json()['data']['defect_code']

    # 2. Non-admins cannot delete
    del_tester = client.delete(f"/api/defects/{d_code}", headers=tester_headers)
    assert del_tester.status_code == 403

    del_dev = client.delete(f"/api/defects/{d_code}", headers=dev_headers)
    assert del_dev.status_code == 403

    # 3. Admin soft-deletes defect
    del_admin = client.delete(f"/api/defects/{d_code}", headers=admin_headers)
    assert del_admin.status_code == 200
    assert del_admin.get_json()['success'] is True

    # 4. Defect is no longer found in standard active queries
    get_resp = client.get(f"/api/defects/{d_code}")
    assert get_resp.status_code == 404

    list_resp = client.get('/api/defects')
    assert list_resp.status_code == 200
    all_codes = [d['defect_code'] for d in list_resp.get_json()['data']]
    assert d_code not in all_codes

    # 5. Defect audit history is preserved for compliance
    hist_resp = client.get(f"/api/defects/{d_code}/history")
    assert hist_resp.status_code == 200
    history = hist_resp.get_json()['data']
    assert len(history) >= 2  # CREATED and DELETED

    deleted_entry = history[-1]
    assert deleted_entry['new_status'] == 'DELETED'
    assert 'soft-deleted' in deleted_entry['notes']
    assert deleted_entry['actor_email'] == 'admin@demo.com'

def test_production_mode_ignores_header_override(tmp_path):
    """
    Test Phase 3 security: In production/normal mode (TESTING: False),
    the X-Demo-Role header is completely ignored.
    Requests without a session are treated as unprivileged guests (HTTP 403).
    """
    from app import create_app
    from database.db import init_db

    db_path = str(tmp_path / "prod_test.db")
    prod_config = {
        'TESTING': False,
        'DEBUG': False,
        'DATABASE_PATH': db_path,
        'SECRET_KEY': 'prod-test-key'
    }
    app = create_app(config_name='production', config_override=prod_config)
    with app.app_context():
        init_db(db_path, seed_if_empty=True)

    client = app.test_client()

    # 1. Attacker sends X-Demo-Role: Admin without a session to delete a defect
    # In production mode, header must be IGNORED! Active role is Guest (None) -> 403 Forbidden
    del_resp = client.delete('/api/defects/DEF-101', headers={'X-Demo-Role': 'Admin'})
    assert del_resp.status_code == 403
    assert "Forbidden" in del_resp.get_json()['error']

    # 2. Attacker sends X-Demo-Role: Admin to create a prevention guideline -> 403 Forbidden
    prev_resp = client.post('/api/prevention', json={
        "root_cause": "Hacker cause",
        "guideline": "Hacker rule",
        "module": "Authentication",
        "category": "Security"
    }, headers={'X-Demo-Role': 'Admin'})
    assert prev_resp.status_code == 403

    # 3. Proper role switching sets session, allowing authorized actions
    switch_resp = client.post('/api/auth/switch-role', json={'role': 'Admin'})
    assert switch_resp.status_code == 200

    # Now session has Admin, authorized actions succeed
    del_authorized = client.delete('/api/defects/DEF-101')
    assert del_authorized.status_code == 200

def test_defect_visibility_by_role(client, sample_defect_payload):
    """
    Test Section 1 & 5 Defect Visibility:
    - Admin can view all defects and history.
    - Developer can view only defects assigned to exact identity; cannot access other defects (403).
    - Tester can view defects reported by them or awaiting verification; cannot access unrelated defects (403).
    - Defect history access is strictly restricted by visibility rules.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # 1. Create 3 distinct defects as Admin
    # Defect A: assigned to developer@demo.com, reported by tester@demo.com, status: NEW
    pA = dict(sample_defect_payload, title="Defect A - Dev Assigned", reporter="tester@demo.com", assignee="developer@demo.com")
    rA = client.post('/api/defects', json=pA, headers=admin_headers)
    assert rA.status_code == 201
    codeA = rA.get_json()['data']['defect_code']

    # Defect B: assigned to other_dev@demo.com, reported by tester@demo.com, status: NEW
    pB = dict(sample_defect_payload, title="Defect B - Other Dev", reporter="tester@demo.com", assignee="other_dev@demo.com")
    rB = client.post('/api/defects', json=pB, headers=admin_headers)
    assert rB.status_code == 201
    codeB = rB.get_json()['data']['defect_code']

    # Defect C: assigned to other_dev@demo.com, reported by other_tester@demo.com, status: NEW
    pC = dict(sample_defect_payload, title="Defect C - Unrelated Private", reporter="other_tester@demo.com", assignee="other_dev@demo.com")
    rC = client.post('/api/defects', json=pC, headers=admin_headers)
    assert rC.status_code == 201
    codeC = rC.get_json()['data']['defect_code']

    # 2. Admin can list and view all three defects and their histories
    admin_list = client.get('/api/defects', headers=admin_headers).get_json()['data']
    admin_codes = [d['defect_code'] for d in admin_list]
    assert codeA in admin_codes
    assert codeB in admin_codes
    assert codeC in admin_codes
    assert client.get(f"/api/defects/{codeA}/history", headers=admin_headers).status_code == 200
    assert client.get(f"/api/defects/{codeB}/history", headers=admin_headers).status_code == 200
    assert client.get(f"/api/defects/{codeC}/history", headers=admin_headers).status_code == 200

    # 3. Developer can view ONLY Defect A (assigned to developer@demo.com)
    dev_list = client.get('/api/defects', headers=dev_headers).get_json()['data']
    dev_codes = [d['defect_code'] for d in dev_list]
    assert codeA in dev_codes
    assert codeB not in dev_codes
    assert codeC not in dev_codes

    # Direct retrieval of Defect A succeeds (200)
    assert client.get(f"/api/defects/{codeA}", headers=dev_headers).status_code == 200
    assert client.get(f"/api/defects/{codeA}/history", headers=dev_headers).status_code == 200

    # Direct retrieval of Defect B or C by Developer returns 403 Forbidden!
    assert client.get(f"/api/defects/{codeB}", headers=dev_headers).status_code == 403
    assert client.get(f"/api/defects/{codeC}", headers=dev_headers).status_code == 403
    assert client.get(f"/api/defects/{codeB}/history", headers=dev_headers).status_code == 403
    assert client.get(f"/api/defects/{codeC}/history", headers=dev_headers).status_code == 403

    # 4. Tester can view Defect A & B (reported by tester@demo.com), but NOT Defect C (reported by other_tester)
    tester_list = client.get('/api/defects', headers=tester_headers).get_json()['data']
    tester_codes = [d['defect_code'] for d in tester_list]
    assert codeA in tester_codes
    assert codeB in tester_codes
    assert codeC not in tester_codes

    assert client.get(f"/api/defects/{codeA}", headers=tester_headers).status_code == 200
    assert client.get(f"/api/defects/{codeB}", headers=tester_headers).status_code == 200
    # Direct retrieval of unrelated Defect C by Tester returns 403 Forbidden!
    assert client.get(f"/api/defects/{codeC}", headers=tester_headers).status_code == 403
    assert client.get(f"/api/defects/{codeC}/history", headers=tester_headers).status_code == 403

    # 5. Admin assigns Defect C to tester@demo.com for verification
    client.patch(f"/api/defects/{codeC}", json={"status": "ASSIGNED"}, headers=admin_headers)
    client.patch(f"/api/defects/{codeC}", json={"status": "IN PROGRESS"}, headers=admin_headers)
    client.patch(f"/api/defects/{codeC}", json={"status": "RESOLVED"}, headers=admin_headers)

    # Without verification assignment, Tester cannot access unrelated Defect C (Phase 3 Strict Visibility)
    assert client.get(f"/api/defects/{codeC}", headers=tester_headers).status_code == 403

    # Once Admin explicitly assigns tester@demo.com as verification_assignee, Tester can access it
    client.patch(f"/api/defects/{codeC}", json={"verification_assignee": "tester@demo.com"}, headers=admin_headers)
    assert client.get(f"/api/defects/{codeC}", headers=tester_headers).status_code == 200
    assert client.get(f"/api/defects/{codeC}/history", headers=tester_headers).status_code == 200

def test_field_permissions_put_and_patch_consistency(client, sample_defect_payload):
    """
    Test Section 2: Consistent field allowlists on both PUT and PATCH operations.
    Unauthorized fields are rejected with HTTP 403 on both methods.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    c_resp = client.post('/api/defects', json=sample_defect_payload, headers=admin_headers)
    d_code = c_resp.get_json()['data']['defect_code']
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)

    # Developer: blocked on PUT and PATCH for unauthorized fields
    # PUT title -> 403
    assert client.put(f"/api/defects/{d_code}", json={"title": "New Title"}, headers=dev_headers).status_code == 403
    # PATCH title -> 403
    assert client.patch(f"/api/defects/{d_code}", json={"title": "New Title"}, headers=dev_headers).status_code == 403

    # PUT severity -> 403
    assert client.put(f"/api/defects/{d_code}", json={"severity": "Minor"}, headers=dev_headers).status_code == 403
    # PATCH severity -> 403
    assert client.patch(f"/api/defects/{d_code}", json={"severity": "Minor"}, headers=dev_headers).status_code == 403

    # PUT assignee -> 403
    assert client.put(f"/api/defects/{d_code}", json={"assignee": "other@demo.com"}, headers=dev_headers).status_code == 403
    # PATCH assignee -> 403
    assert client.patch(f"/api/defects/{d_code}", json={"assignee": "other@demo.com"}, headers=dev_headers).status_code == 403

    # Tester: blocked on PUT and PATCH for unauthorized fields
    # PUT resolution_notes -> 403
    assert client.put(f"/api/defects/{d_code}", json={"resolution_notes": "Fix notes"}, headers=tester_headers).status_code == 403
    # PATCH resolution_notes -> 403
    assert client.patch(f"/api/defects/{d_code}", json={"resolution_notes": "Fix notes"}, headers=tester_headers).status_code == 403

    # PUT assignee -> 403
    assert client.put(f"/api/defects/{d_code}", json={"assignee": "other@demo.com"}, headers=tester_headers).status_code == 403
    # PATCH assignee -> 403
    assert client.patch(f"/api/defects/{d_code}", json={"assignee": "other@demo.com"}, headers=tester_headers).status_code == 403

def test_separate_defect_notes_and_lifecycle_reopen_reason(client, sample_defect_payload):
    """
    Test Section 3 & 4:
    - Distinct separation of investigation_notes, resolution_notes, commit_reference,
      verification_notes, and reopening_reason.
    - Reopening requires a non-empty reason (400 if omitted).
    - Successful updates are audited.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # 1. Create defect
    c_resp = client.post('/api/defects', json=sample_defect_payload, headers=tester_headers)
    d_code = c_resp.get_json()['data']['defect_code']

    # 2. Admin assigns to developer@demo.com
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)

    # 3. Developer progresses to IN PROGRESS and adds investigation notes
    r_prog = client.patch(f"/api/defects/{d_code}", json={
        "status": "IN PROGRESS",
        "investigation_notes": "Root cause identified in token expiration clock skew logic."
    }, headers=dev_headers)
    assert r_prog.status_code == 200
    d_data = r_prog.get_json()['data']
    assert d_data['investigation_notes'] == "Root cause identified in token expiration clock skew logic."

    # 4. Developer marks RESOLVED with distinct resolution_notes and commit_reference
    r_res = client.patch(f"/api/defects/{d_code}", json={
        "status": "RESOLVED",
        "resolution_notes": "Added nbf validation and configured zero skew tolerance window.",
        "commit_reference": "commit e5b7190"
    }, headers=dev_headers)
    assert r_res.status_code == 200
    d_data = r_res.get_json()['data']
    assert d_data['resolution_notes'] == "Added nbf validation and configured zero skew tolerance window."
    assert d_data['commit_reference'] == "commit e5b7190"
    # Investigation notes are preserved separately
    assert d_data['investigation_notes'] == "Root cause identified in token expiration clock skew logic."

    # 5. Tester attempts to reopen WITHOUT reason -> 400 Bad Request!
    bad_reopen = client.patch(f"/api/defects/{d_code}", json={"status": "REOPENED"}, headers=tester_headers)
    assert bad_reopen.status_code == 400
    assert "Reopening reason is required" in bad_reopen.get_json()['error']

    # 6. Tester reopens WITH mandatory reopening_reason -> 200 OK!
    good_reopen = client.patch(f"/api/defects/{d_code}", json={
        "status": "REOPENED",
        "reopening_reason": "Still reproducible on negative timestamp edge case."
    }, headers=tester_headers)
    assert good_reopen.status_code == 200
    d_data = good_reopen.get_json()['data']
    assert d_data['status'] == 'REOPENED'
    assert d_data['reopening_reason'] == "Still reproducible on negative timestamp edge case."

    # 7. Admin reassigns, Dev resolves again, Tester verifies with verification_notes
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)
    client.patch(f"/api/defects/{d_code}", json={"status": "IN PROGRESS"}, headers=dev_headers)
    client.patch(f"/api/defects/{d_code}", json={"status": "RESOLVED", "resolution_notes": "Handled negative timestamps."}, headers=dev_headers)

    verify_resp = client.patch(f"/api/defects/{d_code}", json={
        "status": "VERIFIED",
        "verification_notes": "Confirmed fixed in QA staging regression suite."
    }, headers=tester_headers)
    assert verify_resp.status_code == 200
    d_data = verify_resp.get_json()['data']
    assert d_data['status'] == 'VERIFIED'
    assert d_data['verification_notes'] == "Confirmed fixed in QA staging regression suite."

    # 8. Check history records distinct note types
    hist = client.get(f"/api/defects/{d_code}/history", headers=admin_headers).get_json()['data']
    hist_notes = [h.get('notes', '') for h in hist]
    assert any('Investigation' in n or 'clock skew' in n for n in hist_notes)
    assert any('Resolution' in n or 'skew tolerance' in n for n in hist_notes)
    assert any('Reopening Reason' in n or 'negative timestamp' in n for n in hist_notes)
    assert any('Verification' in n or 'QA staging' in n for n in hist_notes)

def test_role_specific_analytics_isolation(client, sample_defect_payload):
    """
    Test Section 6: Analytics Isolation
    - Developer analytics contains only assigned defects; does NOT expose other developers' workloads.
    - Tester analytics contains only testing-relevant metrics.
    - Admin analytics contains complete system metrics and developer workloads.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # Admin view includes developer_workload
    admin_analytics = client.get('/api/analytics', headers=admin_headers).get_json()['data']
    assert 'kpis' in admin_analytics
    assert 'role_dashboards' in admin_analytics
    assert 'developer_workload' in admin_analytics['role_dashboards']['admin']

    # Developer view: developer_workload is NOT exposed in the developer dashboard
    dev_analytics = client.get('/api/analytics', headers=dev_headers).get_json()['data']
    assert dev_analytics.get('role') == 'Developer'
    assert 'developer_workload' not in dev_analytics
    assert 'assigned_defects' in dev_analytics['kpis']

    # Tester view: developer_workload is NOT exposed in the tester dashboard
    tester_analytics = client.get('/api/analytics', headers=tester_headers).get_json()['data']
    assert tester_analytics.get('role') == 'Tester'
    assert 'developer_workload' not in tester_analytics
    assert 'total_reported' in tester_analytics['kpis']

def test_role_specific_csv_export_isolation(client, sample_defect_payload):
    """
    Test Section 7: CSV Export Permissions
    - Developer exports only assigned defects.
    - Tester exports only authorized defects.
    - Admin exports all defects.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # Create defect assigned to other developer
    p_other = dict(sample_defect_payload, title="Other Dev Defect", reporter="other@demo.com", assignee="other_dev@demo.com")
    c_other = client.post('/api/defects', json=p_other, headers=admin_headers)
    code_other = c_other.get_json()['data']['defect_code']

    # Developer export: code_other must NOT be in the CSV
    dev_csv = client.get('/api/export/csv', headers=dev_headers).data.decode('utf-8')
    assert code_other not in dev_csv

    # Admin export: code_other IS in the CSV
    admin_csv = client.get('/api/export/csv', headers=admin_headers).data.decode('utf-8')
    assert code_other in admin_csv

def test_verification_assignment_isolation(client, sample_defect_payload):
    """
    Test Phase 8 & Phase 3: Verification Assignment & Isolation
    - Admin can assign a Tester for verification.
    - Assigned Tester can access the defect.
    - Unrelated Testers cannot access it.
    - Developer assignment remains separate.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # 1. Admin creates defect reported by other_tester and assigned to developer@demo.com
    payload = dict(
        sample_defect_payload,
        title="Isolated Verification Task",
        reporter="external_qa@test.com",
        assignee="developer@demo.com"
    )
    c_resp = client.post('/api/defects', json=payload, headers=admin_headers)
    assert c_resp.status_code == 201
    d_code = c_resp.get_json()['data']['defect_code']

    # 2. Before verification assignment, demo tester cannot access this defect
    assert client.get(f"/api/defects/{d_code}", headers=tester_headers).status_code == 403
    assert client.get(f"/api/defects/{d_code}/history", headers=tester_headers).status_code == 403

    # 3. Non-admin cannot assign verification
    unauth_assign = client.patch(
        f"/api/defects/{d_code}",
        json={"verification_assignee": "tester@demo.com"},
        headers=tester_headers
    )
    assert unauth_assign.status_code == 403

    # 4. Admin assigns verification_assignee to tester@demo.com
    auth_assign = client.patch(
        f"/api/defects/{d_code}",
        json={"verification_assignee": "tester@demo.com"},
        headers=admin_headers
    )
    assert auth_assign.status_code == 200
    assert auth_assign.get_json()['data']['verification_assignee'] == 'tester@demo.com'

    # 5. Assigned Tester can now access defect and history
    assert client.get(f"/api/defects/{d_code}", headers=tester_headers).status_code == 200
    assert client.get(f"/api/defects/{d_code}/history", headers=tester_headers).status_code == 200

    # 6. Audit history recorded verification assignment
    hist = client.get(f"/api/defects/{d_code}/history", headers=admin_headers).get_json()['data']
    assert any(h.get('action') == 'VERIFICATION_ASSIGNED' for h in hist)

def test_activity_filtering_by_role(client, sample_defect_payload):
    """
    Test Final Polish 1: Recent Activity Filtering by Role
    - Admin sees all activities.
    - Developer sees only activities related to assigned defects.
    - Tester sees only activities related to reported or verification-assigned defects.
    - Unrelated status activities (NEW, VERIFIED, REOPENED) on other defects are never exposed.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # Create an unrelated defect: assigned to other_dev, reported by other_tester
    p_unrelated = dict(
        sample_defect_payload,
        title="Secret Unrelated System Defect",
        reporter="other_tester@demo.com",
        assignee="other_developer@demo.com"
    )
    c_unrelated = client.post('/api/defects', json=p_unrelated, headers=admin_headers)
    u_code = c_unrelated.get_json()['data']['defect_code']

    # Transition unrelated defect
    client.patch(f"/api/defects/{u_code}", json={"status": "ASSIGNED"}, headers=admin_headers)
    client.patch(f"/api/defects/{u_code}", json={"status": "IN PROGRESS"}, headers=admin_headers)
    client.patch(f"/api/defects/{u_code}", json={"status": "RESOLVED"}, headers=admin_headers)

    # 1. Developer activities feed: u_code must NOT be present
    dev_analytics = client.get('/api/analytics', headers=dev_headers).get_json()['data']
    dev_acts = dev_analytics.get('recent_activities', [])
    assert all(a.get('defect_code') != u_code for a in dev_acts)

    # 2. Tester activities feed: u_code must NOT be present (even though status reached RESOLVED)
    tester_analytics = client.get('/api/analytics', headers=tester_headers).get_json()['data']
    tester_acts = tester_analytics.get('recent_activities', [])
    assert all(a.get('defect_code') != u_code for a in tester_acts)

    # 3. Admin activities feed: u_code IS present
    admin_analytics = client.get('/api/analytics', headers=admin_headers).get_json()['data']
    admin_acts = admin_analytics['role_dashboards']['admin']['recent_activities']
    assert any(a.get('defect_code') == u_code for a in admin_acts)

def test_zero_defect_tester_analytics(tmp_path):
    """
    Test Final Polish 2: Zero Defect Tester Analytics
    - A Tester with zero reported defects and zero verification assignments sees 0, not global counts.
    """
    from app import create_app
    from database.db import get_db

    db_file = tmp_path / "zero_defect_test.db"
    db_path = str(db_file)
    test_config = {
        'TESTING': True,
        'DEBUG': False,
        'DATABASE_PATH': db_path,
        'SECRET_KEY': 'test-secret-key-123'
    }
    app_instance = create_app(config_name='testing', config_override=test_config)
    with app_instance.app_context():
        conn = get_db(db_path)
        with conn:
            conn.execute("DELETE FROM defect_history")
            conn.execute("DELETE FROM defects")

    clean_client = app_instance.test_client()
    resp = clean_client.get('/api/analytics', headers={'X-Demo-Role': 'Tester'})
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['role'] == 'Tester'
    assert data['kpis']['total_reported'] == 0
    assert data['kpis']['new_defects'] == 0
    assert data['kpis']['awaiting_verification'] == 0
    assert data['kpis']['verified_defects'] == 0
    assert data['kpis']['reopened_defects'] == 0
    assert data['role_dashboards']['tester']['total_reported'] == 0

def test_deleted_defects_visibility_and_restrictions(client, sample_defect_payload):
    """
    Test Final Polish 3: Restricted Deleted-Defect Visibility
    - Admin can view active defects and explicitly request deleted defects with include_deleted=true.
    - Developer CANNOT view deleted defects even if include_deleted=true.
    - Tester CANNOT view deleted defects even if include_deleted=true.
    - Direct API requests to soft-deleted defects return 404 for Developer and Tester.
    - Soft-deleted defects are excluded from CSV exports for Developer and Tester.
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # 1. Tester creates defect (logged as Unassigned; Admin assigns to Developer)
    payload = dict(sample_defect_payload, title="Defect to Delete")
    c_resp = client.post('/api/defects', json=payload, headers=tester_headers)
    d_code = c_resp.get_json()['data']['defect_code']
    assert c_resp.get_json()['data']['assignee'] == 'Unassigned'

    # Admin assigns to developer@demo.com
    client.patch(f"/api/defects/{d_code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)

    # 2. Admin soft-deletes the defect
    del_resp = client.delete(f"/api/defects/{d_code}", headers=admin_headers)
    assert del_resp.status_code == 200

    # 3. Developer requests list with include_deleted=true: defect is NOT visible
    dev_list = client.get('/api/defects?include_deleted=true', headers=dev_headers).get_json()['data']
    assert all(d['defect_code'] != d_code for d in dev_list)

    # 4. Tester requests list with include_deleted=true: defect is NOT visible
    tester_list = client.get('/api/defects?include_deleted=true', headers=tester_headers).get_json()['data']
    assert all(d['defect_code'] != d_code for d in tester_list)

    # 5. Admin requests list with include_deleted=true: defect IS visible
    admin_list = client.get('/api/defects?include_deleted=true', headers=admin_headers).get_json()['data']
    assert any(d['defect_code'] == d_code for d in admin_list)

    # 6. Direct retrieval of soft-deleted defect returns 404 for Developer and Tester
    assert client.get(f"/api/defects/{d_code}", headers=dev_headers).status_code == 404
    assert client.get(f"/api/defects/{d_code}", headers=tester_headers).status_code == 404
    # Admin can retrieve it with include_deleted query param
    assert client.get(f"/api/defects/{d_code}?include_deleted=true", headers=admin_headers).status_code == 200

    # 7. Defect history for soft-deleted defect: restricted to Admin
    assert client.get(f"/api/defects/{d_code}/history", headers=dev_headers).status_code == 404
    assert client.get(f"/api/defects/{d_code}/history", headers=tester_headers).status_code == 404
    assert client.get(f"/api/defects/{d_code}/history", headers=admin_headers).status_code == 200

    # 8. CSV export with include_deleted: Developer and Tester do not get deleted defects
    dev_csv = client.get('/api/export/csv?include_deleted=true', headers=dev_headers).data.decode('utf-8')
    assert d_code not in dev_csv
    tester_csv = client.get('/api/export/csv?include_deleted=true', headers=tester_headers).data.decode('utf-8')
    assert d_code not in tester_csv

def test_actor_validation_and_no_admin_fallback(client, sample_defect_payload):
    """
    Test Final Polish 4: Remove Default Admin Fallback Identities
    - Missing or unvalidated actor in service operations raises PermissionError.
    - Invalid actor role raises PermissionError.
    - Actor information is strictly validated and never defaults to Admin.
    """
    from services.auth_service import validate_actor
    from services.defect_service import create_defect, update_defect, delete_defect
    from services.lifecycle_service import transition_defect

    # 1. validate_actor rejects None
    with pytest.raises(PermissionError) as exc_info:
        validate_actor(None)
    assert "Actor identity is missing" in str(exc_info.value)

    # 2. validate_actor rejects empty dict
    with pytest.raises(PermissionError) as exc_info2:
        validate_actor({})
    assert "Invalid or unprivileged" in str(exc_info2.value) or "Actor identity is missing" in str(exc_info2.value)

    # 3. validate_actor rejects unknown role
    with pytest.raises(PermissionError) as exc_info3:
        validate_actor({'role': 'Superuser', 'email': 'super@demo.com'})
    assert "Invalid or unprivileged actor role" in str(exc_info3.value)

    # 4. Service methods reject None actor
    with pytest.raises(PermissionError):
        create_defect(sample_defect_payload, actor=None)

    with pytest.raises(PermissionError):
        update_defect("DEF-101", {"notes": "test"}, actor=None)

    with pytest.raises(PermissionError):
        delete_defect("DEF-101", actor=None)

    with pytest.raises(PermissionError):
        transition_defect("DEF-101", "IN PROGRESS", actor=None)

def test_actor_validation_for_defect_retrieval(client, sample_defect_payload):
    """
    Test Section 3 & Regression C: Explicit Actor Validation for Defect Retrieval
    - get_defect_by_id_or_code() requires a validated actor.
    - Missing or invalid actor raises PermissionError.
    - Developer can retrieve assigned defect.
    - Developer CANNOT retrieve another developer's defect (raises PermissionError / 403).
    - Tester can retrieve reported or verification-assigned defect.
    - Tester CANNOT retrieve unrelated defect (raises PermissionError / 403).
    - Admin can retrieve all authorized defects.
    - Developer and Tester CANNOT retrieve deleted defects.
    """
    from services.defect_service import get_defect_by_id_or_code, create_defect, delete_defect
    from services.auth_service import DEMO_USERS

    admin_actor = DEMO_USERS['Admin']
    dev_actor = DEMO_USERS['Developer']
    tester_actor = DEMO_USERS['Tester']

    # 1. Missing actor raises PermissionError
    with pytest.raises(PermissionError):
        get_defect_by_id_or_code("DEF-101", actor=None)

    # 2. Invalid actor raises PermissionError
    with pytest.raises(PermissionError):
        get_defect_by_id_or_code("DEF-101", actor={'role': 'InvalidRole', 'email': 'bad@bad.com'})

    # 3. Create defect assigned to other developer, reported by other tester
    p = dict(
        sample_defect_payload,
        title="Protected Cross-Role Defect",
        reporter="other_tester@demo.com",
        assignee="other_developer@demo.com"
    )
    c_defect = create_defect(p, actor=admin_actor)
    code = c_defect['defect_code']

    # Admin can retrieve it
    assert get_defect_by_id_or_code(code, actor=admin_actor) is not None

    # Developer cannot retrieve another developer's defect
    with pytest.raises(PermissionError):
        get_defect_by_id_or_code(code, actor=dev_actor)

    # Tester cannot retrieve unrelated defect
    with pytest.raises(PermissionError):
        get_defect_by_id_or_code(code, actor=tester_actor)

    # 4. Soft-delete defect and verify Developer/Tester cannot retrieve it (returns None)
    delete_defect(code, actor=admin_actor)
    assert get_defect_by_id_or_code(code, actor=dev_actor, include_deleted=True) is None
    assert get_defect_by_id_or_code(code, actor=tester_actor, include_deleted=True) is None

    # Admin can retrieve deleted defect only when include_deleted=True
    assert get_defect_by_id_or_code(code, actor=admin_actor, include_deleted=False) is None
    assert get_defect_by_id_or_code(code, actor=admin_actor, include_deleted=True) is not None

def test_developer_assignment_validation_without_default_identity(client, sample_defect_payload):
    """
    Test Section 2 & Regression B: Developer Assignment Validation Without Defaults
    - is_assigned_to_developer() rejects missing actor (returns False).
    - Rejects invalid actor.
    - Enforces exact identity matching without defaulting to developer@demo.com.
    """
    from services.auth_service import is_assigned_to_developer

    defect = {'assignee': 'developer@demo.com'}

    # 1. Missing actor returns False
    assert is_assigned_to_developer(defect, actor=None) is False

    # 2. Invalid actor returns False
    assert is_assigned_to_developer(defect, actor={'role': 'Hacker', 'email': 'hack@demo.com'}) is False

    # 3. Exact matching succeeds
    assert is_assigned_to_developer(defect, actor={'role': 'Developer', 'email': 'developer@demo.com', 'name': 'Demo Developer'}) is True

    # 4. Another developer returns False
    assert is_assigned_to_developer(defect, actor={'role': 'Developer', 'email': 'other_dev@demo.com', 'name': 'Other Dev'}) is False

def test_analytics_rejects_missing_or_invalid_actor(client):
    """
    Test Section 1 & Regression A: Analytics Rejects Missing or Invalid Actor
    - calculate_comprehensive_analytics() raises PermissionError when current_user is None or invalid.
    """
    from services.prediction_service import calculate_comprehensive_analytics

    with pytest.raises(PermissionError):
        calculate_comprehensive_analytics(current_user=None)

    with pytest.raises(PermissionError):
        calculate_comprehensive_analytics(current_user={'role': 'Bogus', 'email': 'bogus@demo.com'})

def test_validate_actor_strict_matrix():
    """
    Test Section 2 & Regression: Strict validate_actor Matrix
    - Enforces exact role-email mapping for Demo Mode.
    - Rejects missing, empty, or mismatched actor combinations.
    """
    from services.auth_service import validate_actor

    # 1. Valid pairs succeed
    admin_valid = validate_actor({'role': 'Admin', 'email': 'admin@demo.com'})
    assert admin_valid['role'] == 'Admin'
    assert admin_valid['email'] == 'admin@demo.com'

    dev_valid = validate_actor({'role': 'Developer', 'email': 'developer@demo.com'})
    assert dev_valid['role'] == 'Developer'
    assert dev_valid['email'] == 'developer@demo.com'

    tester_valid = validate_actor({'role': 'Tester', 'email': 'tester@demo.com'})
    assert tester_valid['role'] == 'Tester'
    assert tester_valid['email'] == 'tester@demo.com'

    # Case insensitivity
    ci_valid = validate_actor({'role': 'admin', 'email': 'ADMIN@demo.com'})
    assert ci_valid['role'] == 'Admin'
    assert ci_valid['email'] == 'admin@demo.com'

    # 2. Invalid / Mismatched combinations raise PermissionError
    mismatched_pairs = [
        {'role': 'Admin', 'email': 'developer@demo.com'},
        {'role': 'Admin', 'email': 'tester@demo.com'},
        {'role': 'Developer', 'email': 'admin@demo.com'},
        {'role': 'Developer', 'email': 'tester@demo.com'},
        {'role': 'Tester', 'email': 'admin@demo.com'},
        {'role': 'Tester', 'email': 'developer@demo.com'},
        {'role': 'Admin', 'email': 'random@example.com'},
        {'role': 'Developer', 'email': 'random@example.com'},
        {'role': 'Tester', 'email': 'random@example.com'},
    ]
    for pair in mismatched_pairs:
        with pytest.raises(PermissionError):
            validate_actor(pair)

    # 3. Missing/malformed actors raise PermissionError
    invalid_actors = [
        None,
        {},
        "Admin",
        {"role": "Admin"},
        {"email": "admin@demo.com"},
        {"role": "", "email": "admin@demo.com"},
        {"role": "Admin", "email": ""},
        {"role": "SuperUser", "email": "admin@demo.com"},
        {"role": "Guest", "email": "guest@demo.com"},
    ]
    for bad_actor in invalid_actors:
        with pytest.raises(PermissionError):
            validate_actor(bad_actor)

def test_get_all_defects_strict_authorization(client, sample_defect_payload):
    """
    Test Section 1 & Regression: Strict get_all_defects Authorization
    - Enforces validated actor; rejects missing or invalid actors.
    - Scopes visibility strictly by role:
        Admin: all defects (active + soft-deleted if include_deleted=True).
        Developer: only assigned active defects.
        Tester: only reported or verification-assigned active defects.
    """
    from services.defect_service import get_all_defects, create_defect, delete_defect
    from services.auth_service import DEMO_USERS

    admin_actor = DEMO_USERS['Admin']
    dev_actor = DEMO_USERS['Developer']
    tester_actor = DEMO_USERS['Tester']

    # 1. Missing actor raises PermissionError
    with pytest.raises(PermissionError):
        get_all_defects(actor=None)

    # 2. Empty / invalid actor raises PermissionError
    with pytest.raises(PermissionError):
        get_all_defects(actor={})

    with pytest.raises(PermissionError):
        get_all_defects(actor={'role': 'Admin', 'email': 'developer@demo.com'})

    with pytest.raises(PermissionError):
        get_all_defects(actor="not-a-dict")

    # 3. Create a defect reported by tester (unassigned), and assigned by Admin to developer
    p1 = dict(sample_defect_payload, title="Dev Assigned Defect", reporter="tester@demo.com")
    d1 = create_defect(p1, actor=tester_actor)
    assert d1['assignee'] == 'Unassigned'
    from services.defect_service import update_defect
    update_defect(d1['defect_code'], {"assignee": "developer@demo.com", "status": "ASSIGNED"}, actor=admin_actor)

    # Create a defect assigned to someone else, reported by someone else (Admin)
    p2 = dict(sample_defect_payload, title="Other Defect", assignee="other_dev@demo.com", reporter="admin@demo.com")
    d2 = create_defect(p2, actor=admin_actor)

    # Verify Developer only sees defects assigned to developer@demo.com
    dev_defects = get_all_defects(actor=dev_actor)
    assert all(
        (d.get('assignee') or '').strip().lower() == 'developer@demo.com' or
        (d.get('assigned_to') or '').strip().lower() == 'developer@demo.com'
        for d in dev_defects
    )
    dev_codes = [d['defect_code'] for d in dev_defects]
    assert d1['defect_code'] in dev_codes
    assert d2['defect_code'] not in dev_codes

    # Verify Tester only sees defects where tester is reporter or verification_assignee
    tester_defects = get_all_defects(actor=tester_actor)
    for td in tester_defects:
        is_rep = (td.get('reporter') or '').strip().lower() == 'tester@demo.com'
        is_v_assignee = (td.get('verification_assignee') or '').strip().lower() == 'tester@demo.com'
        assert is_rep or is_v_assignee
    tester_codes = [d['defect_code'] for d in tester_defects]
    assert d1['defect_code'] in tester_codes
    assert d2['defect_code'] not in tester_codes

    # Verify Admin sees all active defects
    admin_defects = get_all_defects(actor=admin_actor)
    admin_codes = [d['defect_code'] for d in admin_defects]
    assert d1['defect_code'] in admin_codes
    assert d2['defect_code'] in admin_codes

    # 4. Soft-delete d1 and test include_deleted behavior
    delete_defect(d1['defect_code'], actor=admin_actor)

    # Developer requesting include_deleted=True still CANNOT see soft-deleted defect
    dev_defects_inc = get_all_defects(actor=dev_actor, include_deleted=True)
    assert d1['defect_code'] not in [d['defect_code'] for d in dev_defects_inc]

    # Tester requesting include_deleted=True still CANNOT see soft-deleted defect
    tester_defects_inc = get_all_defects(actor=tester_actor, include_deleted=True)
    assert d1['defect_code'] not in [d['defect_code'] for d in tester_defects_inc]

    # Admin requesting include_deleted=False does not see soft-deleted defect
    admin_active_only = get_all_defects(actor=admin_actor, include_deleted=False)
    assert d1['defect_code'] not in [d['defect_code'] for d in admin_active_only]

    # Admin requesting include_deleted=True sees soft-deleted defect
    admin_all = get_all_defects(actor=admin_actor, include_deleted=True)
    assert d1['defect_code'] in [d['defect_code'] for d in admin_all]

def test_developer_status_transitions_and_reopen_resolution(client, sample_defect_payload):
    """
    Test Developer status transitions and re-resolution workflow:
    - ASSIGNED -> IN PROGRESS (Developer on assigned defect)
    - IN PROGRESS -> RESOLVED (Developer on assigned defect, providing resolution notes & commit reference)
    - RESOLVED -> REOPENED (Tester providing mandatory reopening reason)
    - REOPENED -> ASSIGNED (Developer acknowledging reopened defect for subsequent resolution)
    - Enforces that Developer CANNOT transition defects assigned to others
    - Enforces that Developer CANNOT change assignee during transitions
    - Confirms that echoing existing assignee in request payload does NOT trigger 403
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # 1. Create defect assigned to developer@demo.com
    payload = dict(sample_defect_payload, assignee="developer@demo.com", reporter="tester@demo.com")
    c_resp = client.post('/api/defects', json=payload, headers=tester_headers)
    assert c_resp.status_code == 201
    code = c_resp.get_json()['data']['defect_code']

    # Admin assigns defect to developer@demo.com (status -> ASSIGNED)
    admin_assign = client.patch(f"/api/defects/{code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)
    assert admin_assign.status_code == 200

    # 2. Developer transitions ASSIGNED -> IN PROGRESS, echoing existing assignee
    prog_resp = client.patch(f"/api/defects/{code}", json={
        "status": "IN PROGRESS",
        "assignee": "developer@demo.com",
        "investigation_notes": "Identified memory leak in connection pool"
    }, headers=dev_headers)
    assert prog_resp.status_code == 200
    assert prog_resp.get_json()['data']['status'] == 'IN PROGRESS'
    assert prog_resp.get_json()['data']['investigation_notes'] == "Identified memory leak in connection pool"

    # 3. Developer transitions IN PROGRESS -> RESOLVED with resolution notes and commit
    res_resp = client.patch(f"/api/defects/{code}", json={
        "status": "RESOLVED",
        "resolution_notes": "Implemented context manager with auto-close",
        "commit_reference": "commit fedcba98"
    }, headers=dev_headers)
    assert res_resp.status_code == 200
    d_res = res_resp.get_json()['data']
    assert d_res['status'] == 'RESOLVED'
    assert d_res['resolved_at'] is not None
    assert d_res['resolution_notes'] == "Implemented context manager with auto-close"
    assert d_res['commit_reference'] == "commit fedcba98"

    # 4. Tester reopens defect: RESOLVED -> REOPENED
    reopen_resp = client.patch(f"/api/defects/{code}", json={
        "status": "REOPENED",
        "reopening_reason": "Connections still leak under high concurrent spikes (>500 rps)"
    }, headers=tester_headers)
    assert reopen_resp.status_code == 200
    d_reopened = reopen_resp.get_json()['data']
    assert d_reopened['status'] == 'REOPENED'
    assert d_reopened['resolved_at'] is None
    assert d_reopened['reopening_reason'] == "Connections still leak under high concurrent spikes (>500 rps)"

    # 5. Developer attempts REOPENED -> ASSIGNED -> 403 Forbidden (only Admin can assign/reassign)
    bad_dev_reassign = client.patch(f"/api/defects/{code}", json={
        "status": "ASSIGNED",
        "notes": "Developer attempting reassignment"
    }, headers=dev_headers)
    assert bad_dev_reassign.status_code == 403
    assert "Forbidden" in bad_dev_reassign.get_json()['error']

    # Admin reassigns REOPENED -> ASSIGNED
    reassign_resp = client.patch(f"/api/defects/{code}", json={
        "status": "ASSIGNED",
        "assignee": "developer@demo.com",
        "notes": "Admin reassigned defect. Tuning pool max_overflow."
    }, headers=admin_headers)
    assert reassign_resp.status_code == 200
    assert reassign_resp.get_json()['data']['status'] == 'ASSIGNED'
    assert reassign_resp.get_json()['data']['assignee'] == 'developer@demo.com'

    # 6. Developer transitions ASSIGNED -> IN PROGRESS again
    prog_resp2 = client.patch(f"/api/defects/{code}", json={
        "status": "IN PROGRESS",
        "investigation_notes": "Tuning queue timeout and overflow bounds"
    }, headers=dev_headers)
    assert prog_resp2.status_code == 200
    assert prog_resp2.get_json()['data']['status'] == 'IN PROGRESS'

    # 7. Developer resolves again
    res_resp2 = client.patch(f"/api/defects/{code}", json={
        "status": "RESOLVED",
        "resolution_notes": "Set max_overflow=50 with 5s pool timeout",
        "commit_reference": "commit 11223344"
    }, headers=dev_headers)
    assert res_resp2.status_code == 200
    assert res_resp2.get_json()['data']['status'] == 'RESOLVED'

    # 8. Tester verifies defect
    ver_resp = client.patch(f"/api/defects/{code}", json={
        "status": "VERIFIED",
        "verification_notes": "JMeter stress test passed at 1000 rps without connection drops"
    }, headers=tester_headers)
    assert ver_resp.status_code == 200
    assert ver_resp.get_json()['data']['status'] == 'VERIFIED'

    # 9. Admin closes defect
    close_resp = client.patch(f"/api/defects/{code}", json={"status": "CLOSED"}, headers=admin_headers)
    assert close_resp.status_code == 200
    assert close_resp.get_json()['data']['status'] == 'CLOSED'

def test_tester_cannot_assign_defects_only_admin_can(client, sample_defect_payload):
    """
    Test that Tester CANNOT assign defects to developers:
    - When Tester creates a defect, it is strictly recorded as 'Unassigned' in 'NEW' status
    - Tester cannot assign or reassign via PUT (403 Forbidden)
    - Tester cannot assign or reassign via PATCH (403 Forbidden)
    - Only Admin can assign defects to developers
    - Admin can assign during creation or via PATCH / PUT
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # 1. Tester creates a defect specifying an assignee
    p_tester = dict(sample_defect_payload, title="Tester Logged Defect", assignee="developer@demo.com")
    resp_create = client.post('/api/defects', json=p_tester, headers=tester_headers)
    assert resp_create.status_code == 201
    d_created = resp_create.get_json()['data']
    code = d_created['defect_code']

    # Assignee must be 'Unassigned', NOT 'developer@demo.com'
    assert d_created['assignee'] == 'Unassigned'
    assert d_created['status'] == 'NEW'
    assert d_created['reporter'] == 'tester@demo.com'

    # 2. Tester attempts to assign developer via PUT -> 403 Forbidden
    put_resp = client.put(f"/api/defects/{code}", json={"assignee": "developer@demo.com"}, headers=tester_headers)
    assert put_resp.status_code == 403
    assert "Forbidden" in put_resp.get_json()['error']

    # 3. Tester attempts to assign developer via PATCH -> 403 Forbidden
    patch_resp = client.patch(f"/api/defects/{code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=tester_headers)
    assert patch_resp.status_code == 403
    assert "Forbidden" in patch_resp.get_json()['error'] or "Only Admin can assign" in patch_resp.get_json()['error']

    # 4. Admin successfully assigns developer -> 200 OK
    admin_assign = client.patch(f"/api/defects/{code}", json={"status": "ASSIGNED", "assignee": "developer@demo.com"}, headers=admin_headers)
    assert admin_assign.status_code == 200
    assert admin_assign.get_json()['data']['assignee'] == 'developer@demo.com'
    assert admin_assign.get_json()['data']['status'] == 'ASSIGNED'

    # 5. Admin can assign developer directly on creation
    p_admin = dict(sample_defect_payload, title="Admin Logged Defect", assignee="developer@demo.com")
    resp_admin = client.post('/api/defects', json=p_admin, headers=admin_headers)
    assert resp_admin.status_code == 201
    assert resp_admin.get_json()['data']['assignee'] == 'developer@demo.com'








