from datetime import date, datetime

from app.db import connect

# 수정 요청에서 due_date 를 "보내지 않음"(그대로 둠)과 null(지움)로 구별하는 표시.
UNSET = object()

_PRIORITY_RANK = {"HIGH": 0, "NORMAL": 1, "LOW": 2}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> date:
    """기한 초과의 기준이 되는 "오늘". 서버의 로컬 날짜이며 _now() 와 같은 시계다."""
    return date.today()


def _is_overdue(row: dict, today: date) -> bool:
    """마감일이 있고, 오늘보다 이전이고, 완료가 아니면 기한 초과다. 당일은 아니다 (BR-3)."""
    due = row["due_date"]
    return due is not None and date.fromisoformat(due) < today and row["status"] != "DONE"


def _out(row, today: date) -> dict:
    task = dict(row)
    task["is_overdue"] = _is_overdue(task, today)
    return task


# 모든 쿼리는 owner_id 로 범위를 좁힌다. 다른 사용자의 Task 는 없는 것과 같다.


def list_tasks(owner_id: int) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id ASC", (owner_id,)
        ).fetchall()
        today = _today()
        tasks = [_out(r, today) for r in rows]
        # 기한 초과 → 우선순위(HIGH 먼저) → 가까운 마감일(없으면 뒤) → 만든 순서(ID) (BR-4)
        tasks.sort(
            key=lambda t: (
                not t["is_overdue"],
                _PRIORITY_RANK[t["priority"]],
                t["due_date"] is None,
                t["due_date"] or "",
                t["id"],
            )
        )
        return tasks
    finally:
        conn.close()


def create_task(
    owner_id: int,
    title: str,
    description: str,
    priority: str = "NORMAL",
    due_date: str | None = None,
) -> dict:
    now = _now()
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, description, status, created_at, updated_at,"
                " owner_id, priority, due_date) VALUES (?, ?, 'TODO', ?, ?, ?, ?, ?)",
                (title, description, now, now, owner_id, priority, due_date),
            )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _out(row, _today())
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
        return _out(row, _today())
    finally:
        conn.close()


def update_content(
    owner_id: int,
    task_id: int,
    title: str,
    description: str | None,
    priority: str | None = None,
    due_date: str | None | object = UNSET,
) -> dict | None:
    """priority None / due_date UNSET 은 그대로 둔다. due_date None 은 마감일을 지운다."""
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE tasks SET title = ?, description = COALESCE(?, description),"
                " priority = COALESCE(?, priority),"
                " due_date = CASE WHEN ? THEN ? ELSE due_date END,"
                " updated_at = ? WHERE id = ? AND owner_id = ?",
                (
                    title,
                    description,
                    priority,
                    due_date is not UNSET,
                    None if due_date is UNSET else due_date,
                    _now(),
                    task_id,
                    owner_id,
                ),
            )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _out(row, _today())
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
