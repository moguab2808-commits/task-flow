import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tasks.db"

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'TODO',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    owner_id INTEGER REFERENCES users(id)
);
"""


def db_path() -> Path:
    return Path(os.environ.get("TASKFLOW_DB", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def init_db() -> None:
    """새 DB 에는 스키마를 만든다. 이미 있는 DB 는 alembic 으로 올린 것이어야 한다."""
    db_path().parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        task_columns = _columns(conn, "tasks")
        if not task_columns:
            with conn:
                conn.executescript(SCHEMA)
        elif "owner_id" not in task_columns:
            raise RuntimeError(
                "DB 가 아직 마이그레이션되지 않았습니다. "
                "백업 후 'alembic upgrade head' 를 먼저 실행해 주세요."
            )
    finally:
        conn.close()
