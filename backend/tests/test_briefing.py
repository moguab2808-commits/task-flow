import json
import sqlite3
from datetime import date, timedelta
from types import SimpleNamespace

import anthropic
import pytest
from fastapi.testclient import TestClient

from app import suggest as suggest_mod
from app.main import app

URL = "/api/tasks/briefing"


def _resp(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
    )


class FakeClient:
    """anthropic.Anthropic 대역. 실제 API 는 부르지 않는다."""

    calls: list[dict] = []
    result = None  # 응답 또는 던질 예외

    def __init__(self, **kwargs):
        self.messages = self

    def create(self, **kwargs):
        FakeClient.calls.append(kwargs)
        if isinstance(FakeClient.result, Exception):
            raise FakeClient.result
        return FakeClient.result


def _api_error(cls, status):
    import httpx2 as httpx

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("err", response=httpx.Response(status, request=req), body=None)


def _answer(top3=(1,), later=(), cheer="힘내세요"):
    return json.dumps(
        {"top3": [{"id": i, "reason": f"{i}번 이유"} for i in top3],
         "later": list(later), "cheer": cheer},
        ensure_ascii=False,
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(suggest_mod.anthropic, "Anthropic", FakeClient)
    FakeClient.calls = []
    FakeClient.result = _resp(_answer())
    with TestClient(app) as c:
        c.post("/api/auth/signup", json={"username": "alice", "password": "password-1"})
        assert c.post(
            "/api/auth/login", json={"username": "alice", "password": "password-1"}
        ).status_code == 200
        yield c


def _make(client, n=3, **kw):
    """할 일 n 개를 만들고 id 목록을 돌려준다."""
    return [
        client.post("/api/tasks", json={"title": f"할 일 {i}", "description": f"비밀 설명 {i}", **kw}).json()["id"]
        for i in range(n)
    ]


def _sent(client_call):
    return json.loads(client_call["messages"][0]["content"])


def test_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        assert c.post(URL).status_code == 401


def test_success_shape(client):
    ids = _make(client, 3)
    FakeClient.result = _resp(_answer(top3=ids[:2], later=ids[2:], cheer="오늘도 화이팅"))
    r = client.post(URL)
    assert r.status_code == 200
    assert r.json() == {
        "top3": [{"id": ids[0], "reason": f"{ids[0]}번 이유"},
                 {"id": ids[1], "reason": f"{ids[1]}번 이유"}],
        "later": [ids[2]],
        "cheer": "오늘도 화이팅",
    }


@pytest.mark.parametrize("wrap", ["{}", "'''{}'''", "```json\n{}\n```"])
def test_fenced_response(client, wrap):
    ids = _make(client, 1)
    FakeClient.result = _resp(wrap.format(_answer(top3=ids)))
    assert client.post(URL).status_code == 200


def test_request_content(client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    a = client.post("/api/tasks", json={"title": "밀린 일", "description": "비밀 설명",
                                         "priority": "HIGH", "due_date": yesterday}).json()["id"]
    done = client.post("/api/tasks", json={"title": "끝난 일"}).json()["id"]
    client.patch(f"/api/tasks/{done}", json={"status": "DONE"})
    prog = client.post("/api/tasks", json={"title": "하는 중"}).json()["id"]
    client.patch(f"/api/tasks/{prog}", json={"status": "IN_PROGRESS"})
    # 다른 사용자의 할 일은 섞이지 않는다.
    with TestClient(app) as other:
        other.post("/api/auth/signup", json={"username": "bob", "password": "password-2"})
        other.post("/api/auth/login", json={"username": "bob", "password": "password-2"})
        other.post("/api/tasks", json={"title": "밥의 일"})
    FakeClient.result = _resp(_answer(top3=[a]))

    assert client.post(URL).status_code == 200
    call = FakeClient.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    sent = _sent(call)
    assert sent["today"] == date.today().isoformat()
    assert {t["id"] for t in sent["tasks"]} == {a, prog}
    first = next(t for t in sent["tasks"] if t["id"] == a)
    assert first == {"id": a, "title": "밀린 일", "priority": "HIGH",
                     "due_date": yesterday, "overdue": True}
    assert all(set(t) == {"id", "title", "priority", "due_date", "overdue"} for t in sent["tasks"])
    assert "비밀 설명" not in call["messages"][0]["content"]
    assert "밥의 일" not in call["messages"][0]["content"]


def test_empty_does_not_call_model(client):
    r = client.post(URL)
    assert r.status_code == 200
    assert r.json() == {"top3": [], "later": [], "cheer": "오늘은 비어 있어요"}
    assert FakeClient.calls == []


def test_only_done_is_empty(client):
    t = client.post("/api/tasks", json={"title": "끝"}).json()["id"]
    client.patch(f"/api/tasks/{t}", json={"status": "DONE"})
    r = client.post(URL)
    assert r.json()["cheer"] == "오늘은 비어 있어요"
    assert FakeClient.calls == []


def test_unknown_ids_are_dropped(client):
    ids = _make(client, 2)
    FakeClient.result = _resp(_answer(top3=[999, ids[0]], later=[888, ids[1], 777]))
    body = client.post(URL).json()
    assert [p["id"] for p in body["top3"]] == [ids[0]]
    assert body["later"] == [ids[1]]


def test_top3_capped_at_three(client):
    ids = _make(client, 5)
    FakeClient.result = _resp(_answer(top3=ids[:4], later=ids[4:]))
    body = client.post(URL).json()
    assert [p["id"] for p in body["top3"]] == ids[:3]
    assert body["later"] == ids[4:]


def test_duplicates_removed(client):
    ids = _make(client, 3)
    FakeClient.result = _resp(_answer(top3=[ids[0], ids[0]], later=[ids[0], ids[1], ids[1]]))
    body = client.post(URL).json()
    assert [p["id"] for p in body["top3"]] == [ids[0]]
    assert body["later"] == [ids[1]]


def test_no_key_is_503(client, monkeypatch):
    _make(client, 1)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    r = client.post(URL)
    assert (r.status_code, r.json()["detail"]) == (503, "AI 기능 꺼짐")
    assert FakeClient.calls == []


@pytest.mark.parametrize(
    "exc,detail",
    [
        (_api_error(anthropic.AuthenticationError, 401), "AI 기능 꺼짐"),
        (_api_error(anthropic.RateLimitError, 429), suggest_mod.BUSY),
        (_api_error(anthropic.InternalServerError, 529), suggest_mod.BUSY),
        (_api_error(anthropic.InternalServerError, 500), suggest_mod.BUSY),
    ],
)
def test_api_errors_are_503(client, exc, detail):
    _make(client, 1)
    FakeClient.result = exc
    r = client.post(URL)
    assert (r.status_code, r.json()["detail"]) == (503, detail)


@pytest.mark.parametrize(
    "text",
    [
        "브리핑을 드리겠습니다",
        "[1, 2]",
        '{"later": [], "cheer": "x"}',
        '{"top3": "x", "later": [], "cheer": "x"}',
        '{"top3": [{"id": 1, "reason": "x"}], "later": "x", "cheer": "x"}',
        '{"top3": [{"id": 1, "reason": "x"}], "later": []}',
        '{"top3": [{"id": 1, "reason": "x"}], "later": [], "cheer": 5}',
        '{"top3": [1], "later": [], "cheer": "x"}',
        '{"top3": [{"id": "1", "reason": "x"}], "later": [], "cheer": "x"}',
        '{"top3": [{"id": 1, "reason": 5}], "later": [], "cheer": "x"}',
        '{"top3": [{"id": 1, "reason": "x"}], "later": ["a"], "cheer": "x"}',
        '{"top3": [], "later": [], "cheer": "x"}',  # 고른 것이 없음
        '{"top3": [{"id": 999, "reason": "x"}], "later": [], "cheer": "x"}',  # 전부 버려짐
    ],
)
def test_bad_format_is_502(client, text):
    _make(client, 1)
    FakeClient.result = _resp(text)
    r = client.post(URL)
    assert r.status_code == 502
    assert r.json()["detail"] == "제안 실패"


@pytest.mark.parametrize("stop", ["max_tokens", "refusal"])
def test_truncated_or_refused_is_502(client, stop):
    ids = _make(client, 1)
    FakeClient.result = _resp(_answer(top3=ids), stop_reason=stop)
    r = client.post(URL)
    assert (r.status_code, r.json()["detail"]) == (502, "제안 실패")


def _rows(path):
    con = sqlite3.connect(path)
    try:
        return con.execute("select * from tasks").fetchall()
    finally:
        con.close()


def test_db_is_never_changed(client, tmp_path):
    ids = _make(client, 2)
    path = str(tmp_path / "t.db")
    before = _rows(path)
    for result in [_resp(_answer(top3=ids)), _resp("not json"),
                   _api_error(anthropic.RateLimitError, 429)]:
        FakeClient.result = result
        client.post(URL)
    assert _rows(path) == before
