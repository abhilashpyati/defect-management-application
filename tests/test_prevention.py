import pytest

def test_tc14_add_prevention_guidelines(client):
    """
    TC-14: Add prevention guidelines.
    Verify creating a new root cause analysis record and prevention guideline (Subprocess 1).
    """
    payload = {
        "root_cause": "Race condition on inventory checkout when two threads read same stock value.",
        "guideline": "Use SELECT FOR UPDATE or atomic decrement query to enforce database-level synchronization.",
        "module": "Inventory",
        "category": "Concurrency & Idempotency"
    }

    response = client.post('/api/prevention', json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data['success'] is True
    record = data['data']
    assert record['module'] == "Inventory"
    assert "atomic decrement" in record['guideline']
    assert record['category'] == "Concurrency & Idempotency"
    assert record['created_at'] is not None

def test_tc15_retrieve_prevention_guidelines(client):
    """
    TC-15: Retrieve prevention guidelines.
    Verify listing, searching, filtering, and summary endpoints for prevention records.
    """
    # 1. Retrieve all
    response = client.get('/api/prevention')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert isinstance(data['data'], list)
    assert data['count'] >= 5  # Initial demonstration records

    # 2. Filter by module
    resp_mod = client.get('/api/prevention?module=Payments')
    assert resp_mod.status_code == 200
    mod_items = resp_mod.get_json()['data']
    assert all(item['module'] == 'Payments' for item in mod_items)

    # 3. Filter by search keyword
    resp_search = client.get('/api/prevention?search=token')
    assert resp_search.status_code == 200
    search_items = resp_search.get_json()['data']
    assert len(search_items) >= 1

    # 4. Knowledge summary
    resp_summary = client.get('/api/prevention/summary')
    assert resp_summary.status_code == 200
    sum_data = resp_summary.get_json()['data']
    assert 'categories' in sum_data
    assert 'module_guideline_distribution' in sum_data
