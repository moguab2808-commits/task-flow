"""DB 에 깨진 값이 들어 있어도 읽기가 통째로 실패하지 않아야 한다."""

import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import suggest as suggest_mod
from app.main import app


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setenv("TASKFLOW_DB", path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    with TestClient(app) as c:
        c.post("/api/auth/signup", json={"username": "alice", "password": "password-1"})
        assert c.post(
            "/api/auth/login", json={"username": "alice", "password": "password-1"}
        ).status_code == 200
        yield c, path


def _insert(path, title, status="TODO", due_date=None):
    """검증을 거치지 않고 DB 에 직접 넣는다 (손으로 고친 DB · 옛 데이터를 흉내 낸다)."""
    con = sqlite3.connect(path)
    try:
        owner = con.execute("SELECT id FROM users WHERE username = 'alice'").fetchone()[0]
        with con:
            cur = con.execute(
                "INSERT INTO tasks (title, description, status, created_at, updated_at,"
                " owner_id, priority, due_date) VALUES (?, '', ?, 'x', 'x', ?, 'NORMAL', ?)",
                (title, status, owner, due_date),
            )
        return cur.lastrowid
    finally:
        con.close()


@pytest.mark.parametrize("bad", ["abc", "", "2026-02-30", "2026/10/29", "2026-10-29T10:00"])
def test_list_survives_bad_due_date(env, bad):
    client, path = env
    good = _insert(path, "정상")
    broken = _insert(path, "깨진 마감일", due_date=bad)
    r = client.get("/api/tasks")
    assert r.status_code == 200
    by_id = {t["id"]: t for t in r.json()}
    assert set(by_id) == {good, broken}
    assert by_id[broken]["is_overdue"] is False  # 읽을 수 없는 마감일은 기한 초과로 보지 않는다


@pytest.mark.parametrize("bad", ["done", "ARCHIVED", ""])
def test_list_skips_bad_status(env, bad):
    client, path = env
    good = _insert(path, "정상")
    _insert(path, "깨진 상태", status=bad)
    r = client.get("/api/tasks")
    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == [good]


def test_briefing_survives_bad_rows(env, monkeypatch):
    client, path = env

    class FakeClient:
        def __init__(self, **kw):
            self.messages = self

        def create(self, **kw):
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(
                    type="text",
                    text='{"top3": [{"id": %d, "reason": "x"}], "later": [], "cheer": "c"}' % good,
                )],
            )

    monkeypatch.setattr(suggest_mod.anthropic, "Anthropic", FakeClient)
    good = _insert(path, "정상")
    _insert(path, "깨진 마감일", due_date="abc")
    _insert(path, "깨진 상태", status="done")
    r = client.post("/api/tasks/briefing")
    assert r.status_code == 200
    assert r.json()["top3"][0]["id"] == good
