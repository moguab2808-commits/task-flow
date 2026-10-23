import sqlite3

import pytest

from app import db


def _cols(path, table):
    conn = sqlite3.connect(path)
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def test_fresh_db_has_auth_tables_and_owner_id(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    monkeypatch.setenv("TASKFLOW_DB", str(path))
    db.init_db()
    assert _cols(path, "users") == ["id", "username", "password_hash", "created_at"]
    assert _cols(path, "sessions") == ["id", "user_id", "created_at", "expires_at"]
    assert "owner_id" in _cols(path, "tasks")


def test_username_is_unique(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    db.init_db()
    conn = db.connect()
    conn.execute("INSERT INTO users (username, created_at) VALUES ('a', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (username, created_at) VALUES ('a', 'now')")
    conn.close()


def test_init_is_repeatable(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    db.init_db()
    db.init_db()


def test_unmigrated_db_refuses_start(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,"
        " description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'TODO',"
        " created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("TASKFLOW_DB", str(path))
    with pytest.raises(RuntimeError) as e:
        db.init_db()
    assert "alembic" in str(e.value)
    assert "owner_id" not in _cols(path, "tasks")
