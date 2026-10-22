import sqlite3
from datetime import datetime, timedelta, timezone

from app.db import connect

SESSION_TTL = timedelta(minutes=30)  # D-017: 로그인 시점부터 30분, 연장 없음


def now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def create_user(username: str, password_hash: str) -> bool:
    """가입. 이전용 계정처럼 해시가 비어 있는 같은 이름의 행이 있으면 그 행을 넘겨받는다.

    이미 쓰는 이름이면 False.
    """
    conn = connect()
    try:
        with conn:
            adopted = conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ? AND password_hash IS NULL",
                (password_hash, username),
            )
            if adopted.rowcount == 1:
                return True
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, password_hash, _iso(now())),
                )
            except sqlite3.IntegrityError:
                return False
        return True
    finally:
        conn.close()


def find_user_by_username(username: str) -> dict | None:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_session(session_id: str, user_id: int) -> datetime:
    created = now()
    expires = created + SESSION_TTL
    conn = connect()
    try:
        with conn:
            # 만료된 세션 행은 로그인할 때 함께 지운다.
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_iso(created),))
            conn.execute(
                "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (session_id, user_id, _iso(created), _iso(expires)),
            )
        return expires
    finally:
        conn.close()


def delete_session(session_id: str) -> None:
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    finally:
        conn.close()


def find_user_by_session(session_id: str) -> dict | None:
    """만료되지 않은 세션의 사용자. 없거나 만료되었으면 None."""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT u.id, u.username, s.expires_at FROM sessions s"
            " JOIN users u ON u.id = s.user_id WHERE s.id = ?",
            (session_id,),
        ).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= now():
            return None
        return {"id": row["id"], "username": row["username"]}
    finally:
        conn.close()
