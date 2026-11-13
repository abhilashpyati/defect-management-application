import json
import pytest

def test_tc01_record_new_defect(client, sample_defect_payload):
    """
    TC-01: Record a new defect.
    Verify that posting a valid defect payload creates a record and returns HTTP 201.
    """
    response = client.post('/api/defects', json=sample_defect_payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data
    defect = data['data']
    assert defect['title'] == sample_defect_payload['title']
    assert defect['status'] == 'NEW'
    assert defect['defect_code'].startswith('DEF-')
    assert defect['module'] == 'Payments'

def test_tc02_generate_unique_defect_ids(client, sample_defect_payload):
    """
    TC-02: Generate unique defect IDs.
    Record multiple defects in succession and verify codes increment monotonically and uniquely.
    """
    p1 = dict(sample_defect_payload, title="Defect Number One")
    p2 = dict(sample_defect_payload, title="Defect Number Two")

    r1 = client.post('/api/defects', json=p1)
    r2 = client.post('/api/defects', json=p2)

    assert r1.status_code == 201
    assert r2.status_code == 201

    d1 = r1.get_json()['data']
    d2 = r2.get_json()['data']

    assert d1['defect_code'] != d2['defect_code']
    num1 = int(d1['defect_code'].split('-')[1])
    num2 = int(d2['defect_code'].split('-')[1])
    assert num2 == num1 + 1

def test_tc03_retrieve_all_defects(client):
    """
    TC-03: Retrieve all defects.
    Verify GET /api/defects returns a list of defects with HTTP 200.
    """
    response = client.get('/api/defects')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert isinstance(data['data'], list)
    assert data['count'] >= 10  # Demonstration records seeded

def test_tc04_retrieve_specific_defect(client):
    """
    TC-04: Retrieve a specific defect.
    Verify retrieval by both database integer ID and defect_code (e.g. DEF-101).
    """
    # By code
    resp_code = client.get('/api/defects/DEF-101')
    assert resp_code.status_code == 200
    d_code = resp_code.get_json()['data']
    assert d_code['defect_code'] == 'DEF-101'

    # By ID
    resp_id = client.get(f"/api/defects/{d_code['id']}")
    assert resp_id.status_code == 200
    d_id = resp_id.get_json()['data']
    assert d_id['id'] == d_code['id']

    # Non-existent
    resp_404 = client.get('/api/defects/DEF-999999')
    assert resp_404.status_code == 404

def test_tc05_update_defect_details(client):
    """
    TC-05: Update defect details.
    Verify that updating defect attributes via PUT /api/defects/<id> persists.
    """
    updated_payload = {
        "title": "JWT token expiration bypass - Patched Title",
        "description": "Updated vulnerability description after thorough team triage.",
        "module": "Authentication",
        "severity": "Major",
        "priority": "P2 – Medium",
        "assignee": "Alex Security Dev"
    }

    response = client.put('/api/defects/DEF-101', json=updated_payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['data']['title'] == "JWT token expiration bypass - Patched Title"
    assert data['data']['severity'] == "Major"
    assert data['data']['assignee'] == "Alex Security Dev"

def test_tc06_validate_mandatory_fields(client, sample_defect_payload):
    """
    TC-06: Validate mandatory fields.
    Verify that omitting any mandatory field results in HTTP 400 Bad Request.
    """
    mandatory_keys = [
        'title', 'description', 'steps_to_reproduce', 'expected_behavior',
        'actual_behavior', 'module', 'type', 'severity', 'priority',
        'discovery_phase', 'environment', 'reporter', 'assignee'
    ]

    for key in mandatory_keys:
        bad_payload = dict(sample_defect_payload)
        bad_payload[key] = ""  # empty value
        resp = client.post('/api/defects', json=bad_payload)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False
        assert f"'{key}'" in data['error']

def test_tc07_reject_invalid_severity_and_priority(client, sample_defect_payload):
    """
    TC-07: Reject invalid severity and priority values.
    Verify rejection of non-conforming severity/priority values.
    """
    # Invalid severity
    bad_sev = dict(sample_defect_payload, severity="Catastrophic")
    resp_sev = client.post('/api/defects', json=bad_sev)
    assert resp_sev.status_code == 400
    assert "Invalid severity" in resp_sev.get_json()['error']

    # Invalid priority
    bad_prio = dict(sample_defect_payload, priority="P0 - Immediately")
    resp_prio = client.post('/api/defects', json=bad_prio)
    assert resp_prio.status_code == 400
    assert "Invalid priority" in resp_prio.get_json()['error']

def test_tc08_apply_defect_filters(client):
    """
    TC-08: Apply defect filters.
    Verify filtering by status, severity, module, and search keywords.
    """
    # Filter by status
    r_status = client.get('/api/defects?status=RESOLVED')
    assert r_status.status_code == 200
    defects_resolved = r_status.get_json()['data']
    assert all(d['status'] == 'RESOLVED' for d in defects_resolved)

    # Filter by module
    r_mod = client.get('/api/defects?module=Authentication')
    assert r_mod.status_code == 200
    defects_auth = r_mod.get_json()['data']
    assert all(d['module'] == 'Authentication' for d in defects_auth)

    # Filter by search
    r_search = client.get('/api/defects?search=token')
    assert r_search.status_code == 200
    defects_search = r_search.get_json()['data']
    assert len(defects_search) >= 1

def test_tc09_assign_defect_to_developer(client):
    """
    TC-09: Assign a defect to a developer.
    Verify assignee update updates the defect and records an audit trail.
    """
    assign_payload = {
        "assignee": "Sarah Senior Lead Developer"
    }
    resp = client.patch('/api/defects/DEF-103', json=assign_payload)
    assert resp.status_code == 200
    d = resp.get_json()['data']
    assert d['assignee'] == "Sarah Senior Lead Developer"

    # Check history
    hist_resp = client.get('/api/defects/DEF-103/history')
    assert hist_resp.status_code == 200
    history = hist_resp.get_json()['data']
    assert any("Sarah Senior Lead Developer" in h.get('notes', '') or h.get('assignee') == "Sarah Senior Lead Developer" for h in history)
