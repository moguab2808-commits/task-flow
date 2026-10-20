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


def update_status(task_id: int, status: str) -> dict | None:
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), task_id),
            )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_content(task_id: int, title: str, description: str | None) -> dict | None:
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE tasks SET title = ?, description = COALESCE(?, description),"
                " updated_at = ? WHERE id = ?",
                (title, description, _now(), task_id),
            )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def delete_task(task_id: int) -> bool:
    conn = connect()
    try:
        with conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0
    finally:
        conn.close()
