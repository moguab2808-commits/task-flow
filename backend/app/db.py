import os

import psycopg
from psycopg.rows import dict_row

import app.config  # noqa: F401  backend/.env 를 환경 변수로 읽어 둔다.

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
    owner_id INTEGER REFERENCES users(id),
    priority TEXT NOT NULL DEFAULT 'NORMAL' CHECK (priority IN ('LOW', 'NORMAL', 'HIGH')),
    due_date TEXT
);
"""


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL 이 비어 있습니다. backend/.env 에 값을 설정해 주세요.")
    return url


def connect() -> psycopg.Connection:
    # prepare_threshold=None: Supabase pooler(6543, transaction 모드)는 prepared statement 를 지원하지 않는다.
    return psycopg.connect(
        database_url(), row_factory=dict_row, autocommit=True, prepare_threshold=None
    )


def _columns(conn: psycopg.Connection, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    return [r["column_name"] for r in rows]


def init_db() -> None:
    """테이블은 backend/supabase/schema.sql 이 만든다. 여기서는 필요한 열이 있는지만 확인한다."""
    conn = connect()
    try:
        task_columns = _columns(conn, "tasks")
        if not {"owner_id", "priority", "due_date"} <= set(task_columns):
            raise RuntimeError(
                "DB 에 tasks 테이블이 없거나 열이 모자랍니다. "
                "backend/supabase/schema.sql 을 먼저 적용해 주세요."
            )
    finally:
        conn.close()
