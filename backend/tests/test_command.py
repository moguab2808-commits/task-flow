import json
import sqlite3
from datetime import date, timedelta
from types import SimpleNamespace

import anthropic
import pytest
from fastapi.testclient import TestClient

from app import suggest as suggest_mod
from app.command import ASK_FALLBACK
from app.main import app

URL = "/api/tasks/command"
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


def _act(kind, id=None, title=None, priority=None, due_date=None):
    return {"kind": kind, "id": id, "title": title, "priority": priority, "due_date": due_date}


def _answer(actions, ask=None):
    return json.dumps({"actions": actions, "ask": ask}, ensure_ascii=False)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(suggest_mod.anthropic, "Anthropic", FakeClient)
    FakeClient.calls = []
    FakeClient.result = _resp(_answer([_act("add", title="x")]))
    with TestClient(app) as c:
        c.post("/api/auth/signup", json={"username": "alice", "password": "password-1"})
        assert c.post(
            "/api/auth/login", json={"username": "alice", "password": "password-1"}
        ).status_code == 200
        yield c


def _make(client, n=2, **kw):
    return [
        client.post("/api/tasks", json={"title": f"할 일 {i}", "description": f"비밀 설명 {i}", **kw}).json()["id"]
        for i in range(n)
    ]


def _post(client, text="내일까지 보고서 쓰기"):
    return client.post(URL, json={"text": text})


# ---- 입력 ----

def test_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        assert c.post(URL, json={"text": "안녕"}).status_code == 401


def test_in_openapi(client):
    assert URL in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("text", ["", " ", "   \n\t "])
def test_empty_text_is_422_with_reason(client, text):
    r = _post(client, text)
    assert r.status_code == 422
    assert "시킬 내용을 입력해 주세요." in r.json()["detail"][0]["msg"]
    assert FakeClient.calls == []


def test_too_long_text_is_422_with_reason(client):
    r = _post(client, "가" * 201)
    assert r.status_code == 422
    assert "200자 이하" in r.json()["detail"][0]["msg"]
    assert FakeClient.calls == []


@pytest.mark.parametrize("n", [1, 200])
def test_length_boundaries_pass(client, n):
    assert _post(client, "가" * n).status_code == 200


def test_surrounding_spaces_do_not_count(client):
    assert _post(client, " " + "가" * 200 + " ").status_code == 200
    assert json.loads(FakeClient.calls[0]["messages"][0]["content"])["text"] == "가" * 200


@pytest.mark.parametrize("body", [{}, {"text": None}, {"text": 5}, {"text": "a", "extra": 1}])
def test_bad_body_is_422(client, body):
    assert client.post(URL, json=body).status_code == 422
    assert FakeClient.calls == []


# ---- 모델에 보내는 것 ----

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

    assert _post(client, "밀린 일 끝냈어").status_code == 200
    call = FakeClient.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    assert "삭제 동작은 없다" in call["system"]
    sent = json.loads(call["messages"][0]["content"])
    assert sent["today"] == TODAY.isoformat()
    assert sent["text"] == "밀린 일 끝냈어"
    assert sent["tasks"] == [{"id": a, "title": "밀린 일", "priority": "HIGH",
                              "due_date": yesterday, "overdue": True}]
    content = call["messages"][0]["content"]
    assert "비밀 설명" not in content
    assert "밥의 일" not in content
    assert "끝난 일" not in content


def test_no_tasks_still_calls_model(client):
    FakeClient.result = _resp(_answer([_act("add", title="우유 사기")]))
    r = _post(client, "우유 사기 추가해줘")
    assert r.status_code == 200
    assert len(FakeClient.calls) == 1
    assert json.loads(FakeClient.calls[0]["messages"][0]["content"])["tasks"] == []


# ---- 정상 응답 ----

def test_success_shape(client):
    a, b = _make(client, 2)
    FakeClient.result = _resp(_answer([
        _act("add", title="보고서 쓰기", priority="HIGH", due_date=_d(1)),
        _act("due", id=a, due_date=_d(3)),
        _act("done", id=b),
    ]))
    r = _post(client)
    assert r.status_code == 200
    assert r.json() == {
        "actions": [
            _act("add", title="보고서 쓰기", priority="HIGH", due_date=_d(1)),
            _act("due", id=a, due_date=_d(3)),
            _act("done", id=b),
        ],
        "ask": None,
    }


@pytest.mark.parametrize("wrap", ["{}", "'''{}'''", "```json\n{}\n```"])
def test_fenced_response(client, wrap):
    FakeClient.result = _resp(wrap.format(_answer([_act("add", title="x")])))
    assert _post(client).status_code == 200


def test_add_priority_defaults_to_normal(client):
    FakeClient.result = _resp(json.dumps({"actions": [{"kind": "add", "title": "x"}], "ask": None}))
    assert _post(client).json()["actions"] == [_act("add", title="x", priority="NORMAL")]


def test_add_title_is_stripped_and_extra_fields_ignored(client):
    ids = _make(client, 1)
    FakeClient.result = _resp(json.dumps({"actions": [
        {"kind": "add", "id": ids[0], "title": "  우유  ", "priority": None, "due_date": None, "x": 1},
        {"kind": "done", "id": ids[0], "title": "무시", "priority": "HIGH", "due_date": _d(1)},
    ], "ask": None}))
    assert _post(client).json()["actions"] == [
        _act("add", title="우유", priority="NORMAL"),
        _act("done", id=ids[0]),
    ]


def test_actions_exist_so_ask_is_null(client):
    ids = _make(client, 1)
    FakeClient.result = _resp(_answer([_act("done", id=ids[0])], ask="뭘 말씀하신 거죠?"))
    assert _post(client).json()["ask"] is None


def test_same_done_twice_is_kept_once(client):
    ids = _make(client, 1)
    FakeClient.result = _resp(_answer([_act("done", id=ids[0]), _act("done", id=ids[0])]))
    assert _post(client).json()["actions"] == [_act("done", id=ids[0])]


# ---- 버림 ----

def test_unknown_ids_are_dropped(client):
    ids = _make(client, 1)
    FakeClient.result = _resp(_answer([
        _act("done", id=999),
        _act("due", id=888, due_date=_d(1)),
        _act("done", id=ids[0]),
    ]))
    assert _post(client).json()["actions"] == [_act("done", id=ids[0])]


@pytest.mark.parametrize("bad_id", ["1", True, None, 1.5])
def test_non_int_ids_are_dropped(client, bad_id):
    ids = _make(client, 1)
    FakeClient.result = _resp(json.dumps({"actions": [
        {"kind": "done", "id": bad_id},
        {"kind": "done", "id": ids[0]},
    ], "ask": None}))
    assert _post(client).json()["actions"] == [_act("done", id=ids[0])]


def test_done_task_id_is_unknown(client):
    t = _make(client, 1)[0]
    client.patch(f"/api/tasks/{t}", json={"status": "DONE"})
    FakeClient.result = _resp(_answer([_act("done", id=t)]))
    r = _post(client).json()
    assert r["actions"] == [] and r["ask"] == ASK_FALLBACK


def test_other_users_id_is_dropped(client):
    with TestClient(app) as other:
        other.post("/api/auth/signup", json={"username": "bob", "password": "password-2"})
        other.post("/api/auth/login", json={"username": "bob", "password": "password-2"})
        bobs = other.post("/api/tasks", json={"title": "밥의 일"}).json()["id"]
    FakeClient.result = _resp(_answer([_act("done", id=bobs)]))
    assert _post(client).json()["actions"] == []


@pytest.mark.parametrize("kind", ["delete", "remove", "", None, 5, "ADD"])
def test_other_kinds_are_dropped(client, kind):
    ids = _make(client, 1)
    FakeClient.result = _resp(json.dumps({"actions": [
        {"kind": kind, "id": ids[0], "title": "x"},
        {"kind": "done", "id": ids[0]},
    ], "ask": None}))
    assert _post(client).json()["actions"] == [_act("done", id=ids[0])]


@pytest.mark.parametrize("bad", ["내일", "2026-02-30", "2026/10/30", "", 5, "2026-1-5"])
def test_due_with_bad_date_is_dropped(client, bad):
    a, b = _make(client, 2)
    FakeClient.result = _resp(json.dumps({"actions": [
        {"kind": "due", "id": a, "due_date": bad},
        {"kind": "done", "id": b},
    ], "ask": None}))
    assert _post(client).json()["actions"] == [_act("done", id=b)]


def test_due_without_date_is_dropped(client):
    a = _make(client, 1)[0]
    FakeClient.result = _resp(_answer([_act("due", id=a, due_date=None)]))
    assert _post(client).json()["actions"] == []


@pytest.mark.parametrize("bad", ["내일", "2026-02-30", 5])
def test_add_with_bad_date_keeps_card_without_date(client, bad):
    FakeClient.result = _resp(json.dumps({"actions": [
        {"kind": "add", "title": "우유", "priority": "LOW", "due_date": bad},
    ], "ask": None}))
    assert _post(client).json()["actions"] == [_act("add", title="우유", priority="LOW")]


def test_past_date_is_allowed(client):
    a = _make(client, 1)[0]
    past = _d(-30)
    FakeClient.result = _resp(_answer([_act("due", id=a, due_date=past)]))
    assert _post(client).json()["actions"] == [_act("due", id=a, due_date=past)]


@pytest.mark.parametrize("title", [None, "", "   ", 5])
def test_add_without_title_is_dropped(client, title):
    FakeClient.result = _resp(json.dumps({"actions": [{"kind": "add", "title": title}], "ask": None}))
    assert _post(client).json()["actions"] == []


@pytest.mark.parametrize("priority", ["URGENT", "high", 3, ""])
def test_add_with_bad_priority_is_dropped(client, priority):
    FakeClient.result = _resp(json.dumps({"actions": [
        {"kind": "add", "title": "x", "priority": priority},
        {"kind": "add", "title": "y"},
    ], "ask": None}))
    assert _post(client).json()["actions"] == [_act("add", title="y", priority="NORMAL")]


# ---- 남는 action 이 없으면 ask ----

def test_nothing_left_uses_model_ask(client):
    FakeClient.result = _resp(_answer([], ask="어떤 일을 말씀하시는 건가요?"))
    assert _post(client).json() == {"actions": [], "ask": "어떤 일을 말씀하시는 건가요?"}


@pytest.mark.parametrize("ask", [None, "", "   "])
def test_nothing_left_without_ask_uses_fallback(client, ask):
    FakeClient.result = _resp(_answer([], ask=ask))
    assert _post(client).json() == {"actions": [], "ask": ASK_FALLBACK}


def test_everything_dropped_becomes_ask(client):
    FakeClient.result = _resp(_answer([_act("done", id=999), _act("delete", id=1)]))
    assert _post(client).json() == {"actions": [], "ask": ASK_FALLBACK}


# ---- 502 · 503 ----

def test_no_key_is_503(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    r = _post(client)
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
    FakeClient.result = exc
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (503, detail)


def test_api_4xx_is_502(client):
    FakeClient.result = _api_error(anthropic.BadRequestError, 400)
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (502, "제안 실패")


@pytest.mark.parametrize(
    "text",
    [
        "알겠습니다",
        "[1, 2]",
        '{"ask": null}',  # actions 없음
        '{"actions": "x", "ask": null}',
        '{"actions": {}, "ask": null}',
        '{"actions": [], "ask": 5}',
        '{"actions": [], "ask": []}',
        '{"actions": [1], "ask": null}',
        '{"actions": ["done"], "ask": null}',
    ],
)
def test_bad_answers_are_502(client, text):
    FakeClient.result = _resp(text)
    r = _post(client)
    assert r.status_code == 502
    assert r.json()["detail"] == "제안 실패"


@pytest.mark.parametrize("stop", ["max_tokens", "refusal"])
def test_truncated_or_refused_is_502(client, stop):
    FakeClient.result = _resp(_answer([_act("add", title="x")]), stop_reason=stop)
    r = _post(client)
    assert (r.status_code, r.json()["detail"]) == (502, "제안 실패")


# ---- 저장하지 않는다 ----

def _rows(path):
    con = sqlite3.connect(path)
    try:
        return con.execute("select * from tasks").fetchall()
    finally:
        con.close()


def test_db_is_never_changed(client, tmp_path):
    a, b = _make(client, 2)
    path = str(tmp_path / "t.db")
    before = _rows(path)
    for result in [
        _resp(_answer([_act("add", title="새 카드"), _act("done", id=a), _act("due", id=b, due_date=_d(2))])),
        _resp(_answer([], ask="뭐라고요?")),
        _resp("not json"),
        _api_error(anthropic.RateLimitError, 429),
    ]:
        FakeClient.result = result
        _post(client)
    assert _rows(path) == before
    assert len(client.get("/api/tasks").json()) == 2
