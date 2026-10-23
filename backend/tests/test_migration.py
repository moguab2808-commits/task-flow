import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parent.parent

OLD_ROWS = [
    (1, "첫 카드", "설명", "TODO", "2026-01-01T10:00:00", "2026-01-01T10:00:00"),
    (2, "둘째", "", "DONE", "2026-01-02T10:00:00", "2026-01-03T11:00:00"),
    (5, "id 건너뜀", "x", "IN_PROGRESS", "2026-02-01T10:00:00", "2026-02-02T10:00:00"),
]


@pytest.fixture
def old_db(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,"
        " description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'TODO',"
        " created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)", OLD_ROWS)
    conn.commit()
    conn.close()
    monkeypatch.setenv("TASKFLOW_DB", str(path))
    return path


def _upgrade():
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(cfg, "head")


def _q(path, sql):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def test_upgrade_keeps_every_task_unchanged_and_assigns_migrated_owner(old_db):
    _upgrade()
    rows = _q(old_db, "SELECT id, title, description, status, created_at, updated_at FROM tasks ORDER BY id")
    assert [tuple(r.values()) for r in rows] == OLD_ROWS
    migrated = _q(old_db, "SELECT id FROM users WHERE username = 'migrated@test.com'")[0]["id"]
    owners = _q(old_db, "SELECT DISTINCT owner_id FROM tasks")
    assert owners == [{"owner_id": migrated}]


def test_upgrade_creates_only_migrated_user_without_hash_and_no_sessions(old_db):
    _upgrade()
    users = _q(old_db, "SELECT username, password_hash FROM users")
    assert users == [{"username": "migrated@test.com", "password_hash": None}]
    assert _q(old_db, "SELECT COUNT(*) AS n FROM sessions")[0]["n"] == 0


def test_upgrade_is_safe_to_run_twice(old_db):
    _upgrade()
    _upgrade()
    assert _q(old_db, "SELECT COUNT(*) AS n FROM users")[0]["n"] == 1
    assert _q(old_db, "SELECT COUNT(*) AS n FROM tasks")[0]["n"] == 3


def test_server_starts_on_migrated_db_and_adopter_gets_old_tasks(old_db):
    from fastapi.testclient import TestClient

    from app.main import app

    _upgrade()
    with TestClient(app) as c:
        assert c.get("/api/tasks").status_code == 401
        login = c.post("/api/auth/login", json={"username": "migrated@test.com", "password": "password-1"})
        assert login.status_code == 401
        other = TestClient(app)
        other.post("/api/auth/signup", json={"username": "other", "password": "password-1"})
        other.post("/api/auth/login", json={"username": "other", "password": "password-1"})
        assert other.get("/api/tasks").json() == []
        c.post("/api/auth/signup", json={"username": "migrated@test.com", "password": "password-1"})
        c.post("/api/auth/login", json={"username": "migrated@test.com", "password": "password-1"})
        assert [t["id"] for t in c.get("/api/tasks").json()] == [1, 2, 5]
        other.close()
