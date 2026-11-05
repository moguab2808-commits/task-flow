"""GET /api/tasks 의 검색(q)과 우선순위 필터(priority). DB 를 쓰지 않는 단위 테스트다.

실제 PostgreSQL 에서의 ILIKE · ESCAPE 결과는 여기서 확인하지 않는다.
"""

import pytest
from fastapi.testclient import TestClient

from app import repository
from app.deps import get_current_user
from app.main import app

BACKSLASH = "\\"


class FakeConn:
    def __init__(self):
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return []

    def close(self):
        pass


@pytest.fixture
def conn(monkeypatch):
    c = FakeConn()
    monkeypatch.setattr(repository, "connect", lambda: c)
    return c


def test_no_condition_is_same_sql_as_before(conn):
    repository.list_tasks(7)
    assert conn.sql == "SELECT * FROM tasks WHERE owner_id = %s ORDER BY id ASC"
    assert conn.params == [7]


def test_q_uses_ilike_escape_and_placeholders(conn):
    repository.list_tasks(7, q="회의")
    escape = f"ESCAPE '{BACKSLASH}'"
    assert f"title ILIKE %s {escape}" in conn.sql
    assert f"description ILIKE %s {escape}" in conn.sql
    assert "회의" not in conn.sql
    assert conn.params == [7, "%회의%", "%회의%"]


def test_priority_filter_with_q_and_owner(conn):
    repository.list_tasks(7, q="회의", priority="NORMAL")
    assert conn.sql.startswith("SELECT * FROM tasks WHERE owner_id = %s AND (")
    assert "AND priority = %s" in conn.sql
    assert "NORMAL" not in conn.sql
    assert conn.params == [7, "%회의%", "%회의%", "NORMAL"]


@pytest.mark.parametrize(
    "q, expected",
    [
        ("%", "%" + BACKSLASH + "%%"),
        ("100%", "%100" + BACKSLASH + "%%"),
        ("a_b", "%a" + BACKSLASH + "_b%"),
        ("a" + BACKSLASH + "b", "%a" + BACKSLASH * 2 + "b%"),
    ],
)
def test_like_pattern_escapes_wildcards(q, expected):
    assert repository._like_pattern(q) == expected


@pytest.fixture
def api(monkeypatch):
    seen = {}

    def fake(*args):
        seen["args"] = args
        return []

    monkeypatch.setattr(repository, "list_tasks", fake)
    app.dependency_overrides[get_current_user] = lambda: {"id": 7, "username": "u"}
    yield TestClient(app), seen  # 수명 이벤트를 켜지 않아 DB 에 닿지 않는다
    app.dependency_overrides.clear()


def test_invalid_priority_is_422(api):
    client, seen = api
    r = client.get("/api/tasks", params={"priority": "URGENT"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["query", "priority"]
    assert "args" not in seen


def test_query_params_reach_repository(api):
    client, seen = api
    r = client.get("/api/tasks", params={"q": "회의", "priority": "HIGH"})
    assert r.status_code == 200
    assert seen["args"] == (7, "회의", "HIGH")


def test_no_params_reach_repository_as_none(api):
    client, seen = api
    assert client.get("/api/tasks").status_code == 200
    assert seen["args"] == (7, None, None)
