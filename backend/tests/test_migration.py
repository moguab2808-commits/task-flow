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


# ---- 0002: priority, due_date (이슈 #21) ----

V020_USER = (1, "migrated@test.com", None, "2026-10-20T00:00:00+00:00")
V020_ROWS = [
    (1, "첫 카드", "설명", "TODO", "2026-01-01T10:00:00", "2026-01-01T10:00:00", 1),
    (2, "둘째", "", "DONE", "2026-01-02T10:00:00", "2026-01-03T11:00:00", 1),
    (5, "id 건너뜀", "x", "IN_PROGRESS", "2026-02-01T10:00:00", "2026-02-02T10:00:00", 2),
]
TASK_BASE = "SELECT id, title, description, status, created_at, updated_at, owner_id FROM tasks ORDER BY id"


@pytest.fixture
def v020_db(tmp_path, monkeypatch):
    """v0.2.0 모양의 DB: owner_id 까지 있고 priority · due_date 가 없다. alembic 은 0001 까지 적용된 상태."""
    path = tmp_path / "v020.db"
    monkeypatch.setenv("TASKFLOW_DB", str(path))
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
            password_hash TEXT, created_at TEXT NOT NULL);
        CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'TODO',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            owner_id INTEGER REFERENCES users(id));
        """
    )
    conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", V020_USER)
    conn.execute("INSERT INTO users VALUES (2, 'other', 'hash', '2026-10-21T00:00:00+00:00')")
    conn.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)", V020_ROWS)
    conn.commit()
    conn.close()
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.stamp(cfg, "0001")
    return path


def test_0002_keeps_every_existing_value_and_adds_defaults(v020_db):
    _upgrade()
    rows = _q(v020_db, TASK_BASE)
    assert [tuple(r.values()) for r in rows] == V020_ROWS
    added = _q(v020_db, "SELECT priority, due_date FROM tasks")
    assert added == [{"priority": "NORMAL", "due_date": None}] * 3


def test_0002_does_not_touch_users_or_sessions(v020_db):
    _upgrade()
    users = _q(v020_db, "SELECT id, username, password_hash, created_at FROM users ORDER BY id")
    assert users[0] == dict(zip(["id", "username", "password_hash", "created_at"], V020_USER))
    assert [u["username"] for u in users] == ["migrated@test.com", "other"]
    assert _q(v020_db, "SELECT COUNT(*) AS n FROM sessions")[0]["n"] == 0


def test_0002_is_safe_to_run_twice(v020_db):
    _upgrade()
    _upgrade()
    assert _q(v020_db, "SELECT COUNT(*) AS n FROM tasks")[0]["n"] == 3


def test_0002_enforces_priority_values_in_storage(v020_db):
    _upgrade()
    conn = sqlite3.connect(v020_db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE tasks SET priority = 'URGENT' WHERE id = 1")
    conn.close()


def test_full_chain_from_pre_auth_db_reaches_new_columns_and_keeps_tasks(old_db):
    _upgrade()
    rows = _q(old_db, "SELECT id, title, description, status, created_at, updated_at FROM tasks ORDER BY id")
    assert [tuple(r.values()) for r in rows] == OLD_ROWS
    assert _q(old_db, "SELECT DISTINCT priority, due_date FROM tasks") == [
        {"priority": "NORMAL", "due_date": None}
    ]


def test_migrated_db_and_fresh_db_have_same_tasks_structure(old_db, tmp_path):
    from app import db

    _upgrade()
    fresh = tmp_path / "fresh.db"
    conn = sqlite3.connect(fresh)
    conn.executescript(db.SCHEMA)
    conn.close()

    def shape(path):
        c = sqlite3.connect(path)
        try:
            return [
                (r[1], r[2], r[3], r[4])  # name, type, notnull, default
                for r in c.execute("PRAGMA table_info(tasks)")
            ]
        finally:
            c.close()

    assert shape(old_db) == shape(fresh)


def test_server_starts_on_v020_db_only_after_upgrade(v020_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass
    _upgrade()
    with TestClient(app) as c:
        assert c.get("/api/tasks").status_code == 401
