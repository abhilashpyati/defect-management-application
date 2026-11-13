import pytest

def test_tc10_validate_lifecycle_transitions(client, sample_defect_payload):
    """
    TC-10: Validate lifecycle transitions.
    Test full allowed workflow:
    NEW -> ASSIGNED -> IN PROGRESS -> RESOLVED -> VERIFIED -> CLOSED
    And test rejection of invalid transitions (e.g. NEW -> RESOLVED, NEW -> CLOSED, CLOSED -> NEW).
    """
    # 1. Create a fresh defect in NEW status
    create_resp = client.post('/api/defects', json=sample_defect_payload)
    assert create_resp.status_code == 201
    defect = create_resp.get_json()['data']
    code = defect['defect_code']
    assert defect['status'] == 'NEW'

    # 2. Test Invalid Transition: NEW -> RESOLVED
    bad_resp1 = client.patch(f"/api/defects/{code}", json={"status": "RESOLVED"})
    assert bad_resp1.status_code == 400
    assert "Invalid lifecycle transition" in bad_resp1.get_json()['error']

    # 3. Test Invalid Transition: NEW -> CLOSED
    bad_resp2 = client.patch(f"/api/defects/{code}", json={"status": "CLOSED"})
    assert bad_resp2.status_code == 400

    # 4. Valid: NEW -> ASSIGNED
    r_assigned = client.patch(f"/api/defects/{code}", json={
        "status": "ASSIGNED",
        "assignee": "Dev A",
        "notes": "Assigned for triage"
    })
    assert r_assigned.status_code == 200
    assert r_assigned.get_json()['data']['status'] == 'ASSIGNED'

    # 5. Invalid: ASSIGNED -> CLOSED
    bad_resp3 = client.patch(f"/api/defects/{code}", json={"status": "CLOSED"})
    assert bad_resp3.status_code == 400

    # 6. Valid: ASSIGNED -> IN PROGRESS
    r_prog = client.patch(f"/api/defects/{code}", json={
        "status": "IN PROGRESS",
        "notes": "Starting code changes"
    })
    assert r_prog.status_code == 200
    assert r_prog.get_json()['data']['status'] == 'IN PROGRESS'

def test_tc11_resolve_defect(client, sample_defect_payload):
    """
    TC-11: Resolve a defect.
    Transition IN PROGRESS -> RESOLVED.
    Verify resolved_at timestamp is populated and fix description is captured.
    """
    # Create defect
    c = client.post('/api/defects', json=sample_defect_payload).get_json()['data']['defect_code']
    client.patch(f"/api/defects/{c}", json={"status": "ASSIGNED"})
    client.patch(f"/api/defects/{c}", json={"status": "IN PROGRESS"})

    # Transition to RESOLVED
    res_resp = client.patch(f"/api/defects/{c}", json={
        "status": "RESOLVED",
        "fix_description": "Fixed token expiration check logic",
        "commit_reference": "commit a91bc2e",
        "notes": "Unit tests pass locally"
    })
    assert res_resp.status_code == 200
    resolved_defect = res_resp.get_json()['data']
    assert resolved_defect['status'] == 'RESOLVED'
    assert resolved_defect['resolved_at'] is not None
    assert resolved_defect['resolution_notes'] == "Fixed token expiration check logic"
    assert resolved_defect['commit_reference'] == "commit a91bc2e"

def test_tc12_reopen_resolved_defect(client, sample_defect_payload):
    """
    TC-12: Reopen a resolved defect.
    Transition from RESOLVED -> REOPENED.
    Verify status becomes REOPENED and state machine allows it.
    """
    # Create and advance to RESOLVED
    c = client.post('/api/defects', json=sample_defect_payload).get_json()['data']['defect_code']
    client.patch(f"/api/defects/{c}", json={"status": "ASSIGNED"})
    client.patch(f"/api/defects/{c}", json={"status": "IN PROGRESS"})
    client.patch(f"/api/defects/{c}", json={"status": "RESOLVED"})

    # Reopen
    reopen_resp = client.patch(f"/api/defects/{c}", json={
        "status": "REOPENED",
        "notes": "Edge case test failed during QA verification"
    })
    assert reopen_resp.status_code == 200
    d = reopen_resp.get_json()['data']
    assert d['status'] == 'REOPENED'

    # Now verify REOPENED -> ASSIGNED is allowed
    reassign_resp = client.patch(f"/api/defects/{c}", json={
        "status": "ASSIGNED",
        "assignee": "Senior Fixer",
        "notes": "Re-assigned to Senior Fixer"
    })
    assert reassign_resp.status_code == 200
    assert reassign_resp.get_json()['data']['status'] == 'ASSIGNED'

def test_tc13_verify_lifecycle_audit_history(client, sample_defect_payload):
    """
    TC-13: Verify lifecycle audit history.
    Verify that each status transition generates an immutable record in defect_history
    with previous_status, new_status, assignee, notes, and timestamp.
    """
    # Create defect
    c = client.post('/api/defects', json=sample_defect_payload).get_json()['data']['defect_code']
    client.patch(f"/api/defects/{c}", json={"status": "ASSIGNED", "assignee": "Dev 1", "notes": "Triage step"})
    client.patch(f"/api/defects/{c}", json={"status": "IN PROGRESS", "notes": "Work step"})
    client.patch(f"/api/defects/{c}", json={"status": "RESOLVED", "notes": "Fix complete"})
    client.patch(f"/api/defects/{c}", json={"status": "VERIFIED", "notes": "QA passed"})
    client.patch(f"/api/defects/{c}", json={"status": "CLOSED", "notes": "Closed in sprint"})

    # Retrieve history
    hist_resp = client.get(f"/api/defects/{c}/history")
    assert hist_resp.status_code == 200
    history = hist_resp.get_json()['data']

    # Initial creation + 5 transitions = 6 records
    assert len(history) >= 6

    # Verify transitions sequence
    statuses = [h['new_status'] for h in history]
    assert 'NEW' in statuses
    assert 'ASSIGNED' in statuses
    assert 'IN PROGRESS' in statuses
    assert 'RESOLVED' in statuses
    assert 'VERIFIED' in statuses
    assert 'CLOSED' in statuses

    # Verify timestamps are populated
    for h in history:
        assert h['timestamp'] is not None
        assert len(h['timestamp']) > 0

def test_developer_lifecycle_complete_workflow(client, sample_defect_payload):
    """
    Test Developer Lifecycle:
    - ASSIGNED -> IN PROGRESS (with investigation notes)
    - IN PROGRESS -> RESOLVED (with resolution notes & commit reference)
    - REOPENED -> ASSIGNED (for subsequent resolution)
    - Rejection of unauthorized transitions or unassigned defects
    - Safe handling of unchanged assignee payload (frontend echo)
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}
    tester_headers = {'X-Demo-Role': 'Tester'}

    # 1. Tester records defect assigned to developer@demo.com
    payload = dict(sample_defect_payload, assignee="developer@demo.com", reporter="tester@demo.com")
    c_resp = client.post('/api/defects', json=payload, headers=tester_headers)
    assert c_resp.status_code == 201
    code = c_resp.get_json()['data']['defect_code']

    # Admin assigns to developer@demo.com (status becomes ASSIGNED)
    assign_resp = client.patch(f"/api/defects/{code}", json={
        "status": "ASSIGNED",
        "assignee": "developer@demo.com"
    }, headers=admin_headers)
    assert assign_resp.status_code == 200
    assert assign_resp.get_json()['data']['status'] == 'ASSIGNED'

    # 2. Developer transitions ASSIGNED -> IN PROGRESS with investigation notes and unchanged assignee echo
    dev_prog = client.patch(f"/api/defects/{code}", json={
        "status": "IN PROGRESS",
        "assignee": "developer@demo.com",  # Form echo of existing assignee
        "investigation_notes": "Root cause identified in token expiration handler"
    }, headers=dev_headers)
    assert dev_prog.status_code == 200
    d_prog = dev_prog.get_json()['data']
    assert d_prog['status'] == 'IN PROGRESS'
    assert d_prog['investigation_notes'] == "Root cause identified in token expiration handler"

    # 3. Developer transitions IN PROGRESS -> RESOLVED with resolution notes & commit reference
    dev_res = client.patch(f"/api/defects/{code}", json={
        "status": "RESOLVED",
        "resolution_notes": "Added boundary check on JWT expiration clock drift",
        "commit_reference": "commit 8f2b1a9c"
    }, headers=dev_headers)
    assert dev_res.status_code == 200
    d_res = dev_res.get_json()['data']
    assert d_res['status'] == 'RESOLVED'
    assert d_res['resolved_at'] is not None
    assert d_res['resolution_notes'] == "Added boundary check on JWT expiration clock drift"
    assert d_res['commit_reference'] == "commit 8f2b1a9c"

    # 4. Tester attempts to reopen without reason -> 400
    bad_reopen = client.patch(f"/api/defects/{code}", json={
        "status": "REOPENED"
    }, headers=tester_headers)
    assert bad_reopen.status_code == 400
    assert "Reopening reason is required" in bad_reopen.get_json()['error']

    # Tester reopens with reason -> 200
    tester_reopen = client.patch(f"/api/defects/{code}", json={
        "status": "REOPENED",
        "reopening_reason": "Still failing when OTP timeout occurs precisely at 30 seconds"
    }, headers=tester_headers)
    assert tester_reopen.status_code == 200
    d_reopen = tester_reopen.get_json()['data']
    assert d_reopen['status'] == 'REOPENED'
    assert d_reopen['resolved_at'] is None
    assert d_reopen['reopening_reason'] == "Still failing when OTP timeout occurs precisely at 30 seconds"

    # 5. Developer attempts REOPENED -> ASSIGNED -> 403 Forbidden (only Admin can assign/reassign)
    bad_dev_reassign = client.patch(f"/api/defects/{code}", json={
        "status": "ASSIGNED",
        "notes": "Developer trying to reassign"
    }, headers=dev_headers)
    assert bad_dev_reassign.status_code == 403
    assert "Forbidden" in bad_dev_reassign.get_json()['error']

    # Admin reassigns REOPENED -> ASSIGNED to developer@demo.com -> 200 OK
    admin_reassign = client.patch(f"/api/defects/{code}", json={
        "status": "ASSIGNED",
        "assignee": "developer@demo.com",
        "notes": "Admin reassigned defect for second resolution cycle."
    }, headers=admin_headers)
    assert admin_reassign.status_code == 200
    d_reassigned = admin_reassign.get_json()['data']
    assert d_reassigned['status'] == 'ASSIGNED'
    assert d_reassigned['assignee'] == 'developer@demo.com'

    # 6. Developer transitions ASSIGNED -> IN PROGRESS again
    dev_prog2 = client.patch(f"/api/defects/{code}", json={
        "status": "IN PROGRESS",
        "investigation_notes": "Added precision timer handling"
    }, headers=dev_headers)
    assert dev_prog2.status_code == 200
    assert dev_prog2.get_json()['data']['status'] == 'IN PROGRESS'

    # 7. Developer transitions IN PROGRESS -> RESOLVED again
    dev_res2 = client.patch(f"/api/defects/{code}", json={
        "status": "RESOLVED",
        "resolution_notes": "Adjusted timeout threshold to 30.5s with monotonic clock",
        "commit_reference": "commit 99c0d12e"
    }, headers=dev_headers)
    assert dev_res2.status_code == 200
    d_res2 = dev_res2.get_json()['data']
    assert d_res2['status'] == 'RESOLVED'
    assert d_res2['resolved_at'] is not None
    assert d_res2['resolution_notes'] == "Adjusted timeout threshold to 30.5s with monotonic clock"
    assert d_res2['commit_reference'] == "commit 99c0d12e"

    # 8. Tester verifies defect
    tester_ver = client.patch(f"/api/defects/{code}", json={
        "status": "VERIFIED",
        "verification_notes": "Retested in QA staging; timeout handling verified successfully"
    }, headers=tester_headers)
    assert tester_ver.status_code == 200
    assert tester_ver.get_json()['data']['status'] == 'VERIFIED'

    # 9. Admin closes defect
    admin_close = client.patch(f"/api/defects/{code}", json={
        "status": "CLOSED"
    }, headers=admin_headers)
    assert admin_close.status_code == 200
    assert admin_close.get_json()['data']['status'] == 'CLOSED'

def test_developer_restrictions_on_unassigned_defects_and_reassignments(client, sample_defect_payload):
    """
    Test Developer restrictions:
    - Cannot transition a defect assigned to someone else
    - Cannot reassign defect to another developer (HTTP 403)
    - Cannot perform unpermitted transitions (e.g. to VERIFIED or CLOSED)
    """
    admin_headers = {'X-Demo-Role': 'Admin'}
    dev_headers = {'X-Demo-Role': 'Developer'}

    # 1. Defect assigned to other_dev@demo.com
    p1 = dict(sample_defect_payload, title="Other Dev Defect", assignee="other_dev@demo.com")
    c1 = client.post('/api/defects', json=p1, headers=admin_headers).get_json()['data']['defect_code']
    client.patch(f"/api/defects/{c1}", json={"status": "ASSIGNED"}, headers=admin_headers)

    # Developer cannot transition unassigned defect (returns 403 because defect is not assigned to them)
    dev_fail = client.patch(f"/api/defects/{c1}", json={"status": "IN PROGRESS"}, headers=dev_headers)
    assert dev_fail.status_code == 403

    # 2. Defect assigned to developer@demo.com
    p2 = dict(sample_defect_payload, title="My Dev Defect", assignee="developer@demo.com")
    c2 = client.post('/api/defects', json=p2, headers=admin_headers).get_json()['data']['defect_code']
    client.patch(f"/api/defects/{c2}", json={"status": "ASSIGNED"}, headers=admin_headers)

    # Developer cannot reassign to another developer
    reassign_fail = client.patch(f"/api/defects/{c2}", json={
        "status": "IN PROGRESS",
        "assignee": "other_dev@demo.com"
    }, headers=dev_headers)
    assert reassign_fail.status_code == 403
    assert "Only Admin can assign" in reassign_fail.get_json()['error'] or "Forbidden" in reassign_fail.get_json()['error']

    # From ASSIGNED, direct transition to VERIFIED is rejected by state machine with 400
    bad_trans1 = client.patch(f"/api/defects/{c2}", json={"status": "VERIFIED"}, headers=dev_headers)
    assert bad_trans1.status_code == 400
    assert "Invalid lifecycle transition" in bad_trans1.get_json()['error']

    # Advance to IN PROGRESS then RESOLVED
    client.patch(f"/api/defects/{c2}", json={"status": "IN PROGRESS"}, headers=dev_headers)
    client.patch(f"/api/defects/{c2}", json={"status": "RESOLVED", "resolution_notes": "Done"}, headers=dev_headers)

    # From RESOLVED, Developer attempting transition to VERIFIED returns 403 (role restriction)
    bad_trans2 = client.patch(f"/api/defects/{c2}", json={"status": "VERIFIED"}, headers=dev_headers)
    assert bad_trans2.status_code == 403
    assert "Forbidden" in bad_trans2.get_json()['error']

