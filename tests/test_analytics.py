import csv
import io
import pytest
from app import create_app
from database.db import init_db

def test_tc16_calculate_module_risk_scores(client):
    """
    TC-16: Calculate module risk scores.
    Verify the curriculum formula:
    Module Risk Score = (3 × Blocker/Critical) + (2 × Major) + (1 × Minor) + (0 × Trivial)
    """
    resp = client.get('/api/analytics')
    assert resp.status_code == 200
    data = resp.get_json()['data']

    prediction = data['prediction']
    assert prediction['is_rule_based'] is True
    ranking = prediction['module_risk_ranking']
    assert len(ranking) > 0

    # Verify score formula calculation for each ranked module
    for mod in ranking:
        high_impact = mod['blocker_critical_count']
        major = mod['major_count']
        minor = mod['minor_count']
        expected_score = (3 * high_impact) + (2 * major) + (1 * minor)
        assert mod['risk_score'] == expected_score

    # Verify descending ordering
    scores = [m['risk_score'] for m in ranking]
    assert scores == sorted(scores, reverse=True)

def test_tc17_calculate_severity_statistics(client):
    """
    TC-17: Calculate severity statistics.
    Verify severity counts match total records in database.
    """
    resp = client.get('/api/analytics')
    assert resp.status_code == 200
    data = resp.get_json()['data']

    sev_dist = data['severity_distribution']
    total_sev_count = sum(sev_dist.values())
    assert total_sev_count == data['kpis']['total_defects']
    assert 'Blocker' in sev_dist
    assert 'Critical' in sev_dist
    assert 'Major' in sev_dist
    assert 'Minor' in sev_dist
    assert 'Trivial' in sev_dist

def test_tc18_calculate_discovery_phase_statistics(client):
    """
    TC-18: Calculate discovery phase statistics.
    Verify phase distribution and Defect Leakage Percentage formula:
    (Defects discovered after Unit Testing / Total Defects) * 100
    """
    resp = client.get('/api/analytics')
    assert resp.status_code == 200
    data = resp.get_json()['data']

    phase_dist = data['phase_distribution']
    total_defects = data['kpis']['total_defects']

    unit_count = phase_dist.get('Unit Testing', 0)
    post_unit_count = total_defects - unit_count

    expected_leakage = round((post_unit_count / total_defects) * 100, 2) if total_defects > 0 else 0.0
    assert data['kpis']['defect_leakage_percentage'] == expected_leakage

def test_tc19_export_valid_csv(client):
    """
    TC-19: Export valid CSV.
    Verify GET /api/export/csv returns valid CSV mime-type, headers, and rows.
    """
    response = client.get('/api/export/csv')
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("Content-Type", "")
    assert "attachment; filename=defects_export.csv" in response.headers.get("Content-Disposition", "")

    csv_text = response.data.decode('utf-8')
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # Header verification
    assert len(rows) >= 2  # Header + at least 1 record
    header = rows[0]
    assert 'Defect ID' in header
    assert 'Title' in header
    assert 'Functional Module' in header
    assert 'Severity' in header
    assert 'Priority' in header
    assert 'Discovery Phase' in header
    assert 'Status' in header

def test_tc20_verify_database_persistence_after_restart(tmp_path, sample_defect_payload):
    """
    TC-20: Verify database persistence after application restart.
    Create a defect in an app instance, shutdown app, re-create app using same DB file,
    verify defect still exists and was not overwritten or lost.
    """
    db_file = tmp_path / "persistence_test.db"
    db_path = str(db_file)

    config_override = {
        'TESTING': True,
        'DATABASE_PATH': db_path
    }

    # 1. Start First App Instance
    app1 = create_app(config_name='testing', config_override=config_override)
    with app1.app_context():
        init_db(db_path, seed_if_empty=True)

    client1 = app1.test_client()
    create_resp = client1.post('/api/defects', json=sample_defect_payload)
    assert create_resp.status_code == 201
    defect_code = create_resp.get_json()['data']['defect_code']

    # 2. Simulate Application Restart (Instantiate fresh app instance with same DB)
    app2 = create_app(config_name='testing', config_override=config_override)
    client2 = app2.test_client()

    retrieve_resp = client2.get(f"/api/defects/{defect_code}")
    assert retrieve_resp.status_code == 200
    retrieved = retrieve_resp.get_json()['data']
    assert retrieved['defect_code'] == defect_code
    assert retrieved['title'] == sample_defect_payload['title']

def test_tc21_verify_api_health_endpoint(client):
    """
    TC-21: Verify API health endpoint.
    GET /api/health should return status 'healthy' and database 'connected'.
    """
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['database'] == 'connected'
    assert 'counts' in data
    assert data['counts']['total_defects'] >= 10

def test_tc22_verify_dashboard_loads_successfully(client):
    """
    TC-22: Verify dashboard loads successfully.
    GET / should return HTTP 200 and serve HTML containing the core dashboard layout.
    """
    response = client.get('/')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert '<!DOCTYPE html>' in html
    assert 'DefectGuard' in html
    assert 'Overview Dashboard' in html
    assert 'Defect Tracker' in html
