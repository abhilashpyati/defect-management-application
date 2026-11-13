import os
import pytest
from app import create_app
from database.db import init_db

@pytest.fixture
def app(tmp_path):
    """
    Create a test application instance pointing to an isolated temporary SQLite database.
    """
    db_file = tmp_path / "test_defects.db"
    db_path = str(db_file)

    test_config = {
        'TESTING': True,
        'DEBUG': False,
        'DATABASE_PATH': db_path,
        'SECRET_KEY': 'test-secret-key-123'
    }

    app_instance = create_app(config_name='testing', config_override=test_config)

    with app_instance.app_context():
        init_db(db_path, seed_if_empty=True)

    yield app_instance

@pytest.fixture
def client(app):
    """
    Test client for HTTP request dispatch.
    """
    return app.test_client()

@pytest.fixture
def sample_defect_payload():
    """
    A valid defect payload for testing creation.
    """
    return {
        "title": "Payment gateway timeout on 3D Secure verification",
        "description": "When 3DS card verification takes > 30s, transaction is marked failed but card is billed.",
        "steps_to_reproduce": "1. Initiate payment.\n2. Delay 3DS OTP submission by 35s.\n3. Observe gateway status.",
        "expected_behavior": "Transaction aborts cleanly with no debit.",
        "actual_behavior": "Card debited and user order state is aborted.",
        "module": "Payments",
        "type": "Backend/API",
        "severity": "Critical",
        "priority": "P1 – High",
        "discovery_phase": "Integration Testing",
        "environment": "QA Staging",
        "reporter": "Alice Senior QA",
        "assignee": "Bob Dev Lead",
        "prevention_guideline": "Implement two-phase commit verification with card acquirer."
    }
