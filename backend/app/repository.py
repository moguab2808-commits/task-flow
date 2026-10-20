from datetime import datetime

from app.db import connect


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def list_tasks() -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_task(title: str, description: str) -> dict:
    now = _now()
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, description, status, created_at, updated_at)"
                " VALUES (?, ?, 'TODO', ?, ?)",
                (title, description, now, now),
            )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()
