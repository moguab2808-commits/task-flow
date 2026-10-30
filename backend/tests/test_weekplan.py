import json
import sqlite3
from datetime import date, timedelta
from types import SimpleNamespace

import anthropic
import pytest
from fastapi.testclient import TestClient

from app import suggest as suggest_mod
from app.main import app

URL = "/api/tasks/weekplan"
TODAY = date.today()


def _d(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


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


def _answer(days, note="마감이 가까운 일을 앞에 두었어요."):
    return json.dumps(
        {"days": [{"date": d, "ids": list(ids)} for d, ids in days], "note": note},
        ensure_ascii=False,
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(suggest_mod.anthropic, "Anthropic", FakeClient)
    FakeClient.calls = []
    FakeClient.result = _resp(_answer([(_d(0), [1])]))
    with TestClient(app) as c:
        c.post("/api/auth/signup", json={"username": "alice", "password": "password-1"})
        assert c.post(
            "/api/auth/login", json={"username": "alice", "password": "password-1"}
        ).status_code == 200
        yield c


def _make(client, n=3, **kw):
    return [
        client.post("/api/tasks", json={"title": f"할 일 {i}", "description": f"비밀 설명 {i}", **kw}).json()["id"]
        for i in range(n)
    ]


def test_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        assert c.post(URL).status_code == 401


def test_in_openapi(client):
    assert URL in client.get("/openapi.json").json()["paths"]


def test_success_shape(client):
    ids = _make(client, 3)
    FakeClient.result = _resp(_answer([(_d(0), ids[:2]), (_d(3), ids[2:])], note="한 줄"))
    r = client.post(URL)
    assert r.status_code == 200
    assert r.json() == {
        "days": [{"date": _d(0), "ids": ids[:2]}, {"date": _d(3), "ids": ids[2:]}],
        "note": "한 줄",
    }


@pytest.mark.parametrize("wrap", ["{}", "'''{}'''", "```json\n{}\n```"])
def test_fenced_response(client, wrap):
    ids = _make(client, 1)
    FakeClient.result = _resp(wrap.format(_answer([(_d(0), ids)])))
    assert client.post(URL).status_code == 200


def test_request_content(client):
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    a = client.post("/api/tasks", json={"title": "밀린 일", "description": "비밀 설명",
                                         "priority": "HIGH", "due_date": yesterday}).json()["id"]
    done = client.post("/api/tasks", json={"title": "끝난 일"}).json()["id"]
    client.patch(f"/api/tasks/{done}", json={"status": "DONE"})
    with TestClient(app) as other:
        other.post("/api/auth/signup", json={"username": "bob", "password": "password-2"})
        other.post("/api/auth/login", json={"username": "bob", "password": "password-2"})
        other.post("/api/tasks", json={"title": "밥의 일"})
    FakeClient.result = _resp(_answer([(_d(0), [a])]))

    assert client.post(URL).status_code == 200
    call = FakeClient.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    assert "7일" in call["system"]
    sent = json.loads(call["messages"][0]["content"])
    assert sent["today"] == TODAY.isoformat()
    assert sent["tasks"] == [{"id": a, "title": "밀린 일", "priority": "HIGH",
                              "due_date": yesterday, "overdue": True}]
    assert "비밀 설명" not in call["messages"][0]["content"]
    assert "밥의 일" not in call["messages"][0]["content"]


def test_task_without_due_date_is_in_the_table(client):
    with_due = client.post("/api/tasks", json={"title": "마감 있음", "due_date": _d(2)}).json()["id"]
    no_due = client.post("/api/tasks", json={"title": "마감 없음"}).json()["id"]
    FakeClient.result = _resp(_answer([(_d(1), [with_due]), (_d(4), [no_due])]))
    body = client.post(URL).json()
    sent = json.loads(FakeClient.calls[0]["messages"][0]["content"])
    assert next(t for t in sent["tasks"] if t["id"] == no_due)["due_date"] is None
    assert no_due in [i for day in body["days"] for i in day["ids"]]


def test_empty_does_not_call_model(client):
    r = client.post(URL)
    assert r.status_code == 200
    assert r.json() == {"days": [], "note": "오늘은 비어 있어요"}
    assert FakeClient.calls == []


def test_only_done_is_empty(client):
    t = client.post("/api/tasks", json={"title": "끝"}).json()["id"]
    client.patch(f"/api/tasks/{t}", json={"status": "DONE"})
    assert client.post(URL).json()["note"] == "오늘은 비어 있어요"
    assert FakeClient.calls == []


def test_dates_outside_seven_days_are_dropped(client):
    ids = _make(client, 4)
    FakeClient.result = _resp(_answer([
        (_d(-1), [ids[0]]),   # 어제
        (_d(0), [ids[1]]),    # 오늘 (경계)
        (_d(6), [ids[2]]),    # 오늘+6 (경계)
        (_d(7), [ids[3]]),    # 오늘+7
    ]))
    days = client.post(URL).json()["days"]
    assert [(d["date"], d["ids"]) for d in days] == [(_d(0), [ids[1]]), (_d(6), [ids[2]])]


@pytest.mark.parametrize("bad", ["내일", "2026-02-30", "2026/10/30", "", None, 5])
def test_bad_dates_are_dropped(client, bad):
    ids = _make(client, 2)
    FakeClient.result = _resp(json.dumps({
        "days": [{"date": bad, "ids": [ids[0]]}, {"date": _d(1), "ids": [ids[1]]}],
        "note": "x",
    }))
    days = client.post(URL).json()["days"]
    assert days == [{"date": _d(1), "ids": [ids[1]]}]


def test_unknown_ids_are_dropped(client):
    ids = _make(client, 2)
    FakeClient.result = _resp(_answer([(_d(0), [999, ids[0]]), (_d(1), [888]), (_d(2), [ids[1], "x", True])]))
    days = client.post(URL).json()["days"]
    assert days == [{"date": _d(0), "ids": [ids[0]]}, {"date": _d(2), "ids": [ids[1]]}]


def test_id_only_on_first_day(client):
    ids = _make(client, 2)
    FakeClient.result = _resp(_answer([(_d(1), [ids[0], ids[0]]), (_d(3), [ids[0], ids[1]])]))
    days = client.post(URL).json()["days"]
    assert days == [{"date": _d(1), "ids": [ids[0]]}, {"date": _d(3), "ids": [ids[1]]}]


def test_same_date_merged_and_sorted(client):
    ids = _make(client, 3)
    FakeClient.result = _resp(_answer([(_d(4), [ids[0]]), (_d(1), [ids[1]]), (_d(4), [ids[2]])]))
    days = client.post(URL).json()["days"]
    assert days == [{"date": _d(1), "ids": [ids[1]]}, {"date": _d(4), "ids": [ids[0], ids[2]]}]


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
        "계획을 드리겠습니다",
        "[1, 2]",
        '{"note": "x"}',
        '{"days": "x", "note": "x"}',
        '{"days": [{"date": "%s", "ids": [1]}]}' % _d(0),  # note 없음
        '{"days": [{"date": "%s", "ids": [1]}], "note": 5}' % _d(0),
        '{"days": [1], "note": "x"}',
        '{"days": [{"date": "%s", "ids": "x"}], "note": "x"}' % _d(0),
        '{"days": [], "note": "x"}',  # 남는 게 없음
        '{"days": [{"date": "%s", "ids": [999]}], "note": "x"}' % _d(0),  # 전부 모르는 id
        '{"days": [{"date": "%s", "ids": [1]}], "note": "x"}' % _d(9),  # 전부 7일 밖
    ],
)
def test_bad_answers_are_502(client, text):
    _make(client, 1)
    FakeClient.result = _resp(text)
    r = client.post(URL)
    assert r.status_code == 502
    assert r.json()["detail"] == "제안 실패"


@pytest.mark.parametrize("stop", ["max_tokens", "refusal"])
def test_truncated_or_refused_is_502(client, stop):
    ids = _make(client, 1)
    FakeClient.result = _resp(_answer([(_d(0), ids)]), stop_reason=stop)
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
    for result in [_resp(_answer([(_d(0), ids)])), _resp("not json"),
                   _api_error(anthropic.RateLimitError, 429)]:
        FakeClient.result = result
        client.post(URL)
    assert _rows(path) == before
