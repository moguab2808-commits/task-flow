from datetime import datetime

from app.db import connect


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# 모든 쿼리는 owner_id 로 범위를 좁힌다. 다른 사용자의 Task 는 없는 것과 같다.


def list_tasks(owner_id: int) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id ASC", (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_task(owner_id: int, title: str, description: str) -> dict:
    now = _now()
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
                " VALUES (?, ?, 'TODO', ?, ?, ?)",
                (title, description, now, now, owner_id),
            )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_status(owner_id: int, task_id: int, status: str) -> dict | None:
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
                (status, _now(), task_id, owner_id),
            )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_content(
    owner_id: int, task_id: int, title: str, description: str | None
) -> dict | None:
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE tasks SET title = ?, description = COALESCE(?, description),"
                " updated_at = ? WHERE id = ? AND owner_id = ?",
                (title, description, _now(), task_id, owner_id),
            )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def delete_task(owner_id: int, task_id: int) -> bool:
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
            )
        return cur.rowcount > 0
    finally:
        conn.close()
