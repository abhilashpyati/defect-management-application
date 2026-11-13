-- Defect Management Application Database Schema
-- SQLite3 DDL

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS defects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defect_code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    steps_to_reproduce TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    actual_behavior TEXT NOT NULL,
    module TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    priority TEXT NOT NULL,
    discovery_phase TEXT NOT NULL,
    environment TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NEW',
    reporter TEXT NOT NULL,
    assignee TEXT NOT NULL,
    verification_assignee TEXT,
    prevention_guideline TEXT,
    investigation_notes TEXT,
    resolution_notes TEXT,
    commit_reference TEXT,
    verification_notes TEXT,
    reopening_reason TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS prevention_guidelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_cause TEXT NOT NULL,
    guideline TEXT NOT NULL,
    module TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS defect_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defect_id INTEGER NOT NULL,
    action TEXT,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    assignee TEXT,
    notes TEXT,
    comment TEXT,
    actor_email TEXT,
    actor_role TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (defect_id) REFERENCES defects(id)
);

CREATE INDEX IF NOT EXISTS idx_defects_status ON defects(status);
CREATE INDEX IF NOT EXISTS idx_defects_module ON defects(module);
CREATE INDEX IF NOT EXISTS idx_defects_severity ON defects(severity);
CREATE INDEX IF NOT EXISTS idx_defects_phase ON defects(discovery_phase);
CREATE INDEX IF NOT EXISTS idx_history_defect ON defect_history(defect_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
