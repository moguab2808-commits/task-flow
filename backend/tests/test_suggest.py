import sqlite3
from datetime import date
from types import SimpleNamespace

import anthropic
import pytest
from fastapi.testclient import TestClient

from app import suggest as suggest_mod
from app.main import app

URL = "/api/tasks/suggest"
BODY = {"title": "보고서 제출", "description": "내일까지"}
GOOD = '{"priority": "HIGH", "due_date": "2026-10-29", "reason": "내일 마감"}'


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
        FakeClient.init_kwargs = kwargs
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


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(suggest_mod.anthropic, "Anthropic", FakeClient)
    FakeClient.calls = []
    FakeClient.result = _resp(GOOD)
    with TestClient(app) as c:
        c.post("/api/auth/signup", json={"username": "alice", "password": "password-1"})
        assert c.post(
            "/api/auth/login", json={"username": "alice", "password": "password-1"}
        ).status_code == 200
        yield c


def test_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        assert c.post(URL, json=BODY).status_code == 401
        assert c.post(URL, json={"title": ""}).status_code == 401  # 401 이 검증보다 먼저


def test_success(client):
    r = client.post(URL, json=BODY)
    assert r.status_code == 200
    assert r.json() == {"priority": "HIGH", "due_date": "2026-10-29", "reason": "내일 마감"}


@pytest.mark.parametrize("wrap", ["{}", "'''{}'''", "```json\n{}\n```", "  '''\n{}\n'''  "])
def test_fenced_response_is_unwrapped(client, wrap):
    FakeClient.result = _resp(wrap.format(GOOD))
    assert client.post(URL, json=BODY).status_code == 200


def test_due_date_null_and_default_priority(client):
    FakeClient.result = _resp('{"due_date": null, "reason": "급하지 않음"}')
    r = client.post(URL, json=BODY)
    assert r.json() == {"priority": "NORMAL", "due_date": None, "reason": "급하지 않음"}


def test_request_shape(client):
    client.post(URL, json=BODY)
    call = FakeClient.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    user = call["messages"][0]["content"]
    assert date.today().isoformat() in user
    assert "보고서 제출" in user and "내일까지" in user
    assert FakeClient.init_kwargs["api_key"] == "fake-key-for-test"


def test_input_validation(client):
    assert client.post(URL, json={"title": "  "}).status_code == 422
    assert client.post(URL, json={"description": "x"}).status_code == 422
    assert FakeClient.calls == []


def test_no_key_is_503(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    r = client.post(URL, json=BODY)
    assert r.status_code == 503
    assert r.json()["detail"] == "AI 기능 꺼짐"
    assert FakeClient.calls == []


@pytest.mark.parametrize(
    "exc,status,detail",
    [
        (_api_error(anthropic.AuthenticationError, 401), 503, "AI 기능 꺼짐"),
        (_api_error(anthropic.RateLimitError, 429), 503, suggest_mod.BUSY),
        (_api_error(anthropic.InternalServerError, 529), 503, suggest_mod.BUSY),
        (_api_error(anthropic.InternalServerError, 500), 503, suggest_mod.BUSY),
    ],
)
def test_api_errors(client, exc, status, detail):
    FakeClient.result = exc
    r = client.post(URL, json=BODY)
    assert (r.status_code, r.json()["detail"]) == (status, detail)


@pytest.mark.parametrize(
    "result",
    [
        _resp("제안을 드리겠습니다"),  # JSON 아님
        _resp("[1, 2]"),  # 객체 아님
        _resp('{"priority": "URGENT", "due_date": null, "reason": "x"}'),  # 허용 밖
        _resp('{"priority": "low", "due_date": null, "reason": "x"}'),  # 대소문자
        _resp('{"priority": "HIGH", "due_date": "내일", "reason": "x"}'),
        _resp('{"priority": "HIGH", "due_date": "2026-02-30", "reason": "x"}'),
        _resp('{"priority": "HIGH", "due_date": null, "reason": 1}'),
        _resp('{"priority": "HIGH", "due_', stop_reason="max_tokens"),  # 잘린 답
        _resp(GOOD, stop_reason="max_tokens"),
        _resp("", stop_reason="refusal"),
    ],
)
def test_bad_answers_are_502(client, result):
    FakeClient.result = result
    r = client.post(URL, json=BODY)
    assert r.status_code == 502
    assert r.json()["detail"] == "제안 실패"


def _rows(path):
    con = sqlite3.connect(path)
    try:
        return con.execute("select * from tasks").fetchall()
    finally:
        con.close()


def test_db_is_never_changed(client, tmp_path):
    client.post("/api/tasks", json={"title": "기존"})
    db_path = str(tmp_path / "t.db")
    before = _rows(db_path)
    for result in [
        _resp(GOOD),
        _resp("not json"),
        _api_error(anthropic.RateLimitError, 429),
    ]:
        FakeClient.result = result
        client.post(URL, json=BODY)
    assert _rows(db_path) == before
    assert len(client.get("/api/tasks").json()) == 1


# ---- 할 일 후보 제안 (POST /api/tasks/suggest-options) ----

OPT_URL = "/api/tasks/suggest-options"


def _item(**kw):
    base = {"title": "발표 자료 초안", "description": "슬라이드 구성", "priority": "HIGH",
            "due_date": "2026-10-29"}
    base.update(kw)
    return base


def _items_json(n=4, **kw):
    import json

    return json.dumps({"items": [_item(**kw) for _ in range(n)]}, ensure_ascii=False)


def test_options_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        assert c.post(OPT_URL, json={"title": "발표"}).status_code == 401
        assert c.post(OPT_URL, json={"title": ""}).status_code == 401


def test_options_success(client):
    FakeClient.result = _resp(_items_json(4))
    r = client.post(OPT_URL, json={"title": "금요일 발표 준비"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 4
    assert items[0] == _item()


@pytest.mark.parametrize("wrap", ["{}", "'''{}'''", "```json\n{}\n```"])
def test_options_fenced(client, wrap):
    FakeClient.result = _resp(wrap.format(_items_json(3)))
    assert client.post(OPT_URL, json={"title": "발표"}).status_code == 200


def test_options_request_shape(client):
    FakeClient.result = _resp(_items_json(3))
    client.post(OPT_URL, json={"title": "금요일 발표 준비"})
    call = FakeClient.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    user = call["messages"][0]["content"]
    assert "금요일 발표 준비" in user and date.today().isoformat() in user
    assert "할 일 개수: 4개" in user or "할 일 개수: 3개" in user or "할 일 개수: 5개" in user


def test_options_count_is_random_between_3_and_5(client):
    FakeClient.result = _resp(_items_json(4))
    for _ in range(60):
        client.post(OPT_URL, json={"title": "발표"})
    counts = {
        int(c["messages"][0]["content"].split("할 일 개수: ")[1].split("개")[0])
        for c in FakeClient.calls
    }
    assert counts == {3, 4, 5}


def test_options_input_validation(client):
    assert client.post(OPT_URL, json={"title": "  "}).status_code == 422
    assert client.post(OPT_URL, json={"title": "a", "description": "x"}).status_code == 422
    assert FakeClient.calls == []


def test_options_no_key_and_busy(client, monkeypatch):
    FakeClient.result = _api_error(anthropic.RateLimitError, 429)
    r = client.post(OPT_URL, json={"title": "발표"})
    assert (r.status_code, r.json()["detail"]) == (503, suggest_mod.BUSY)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    r = client.post(OPT_URL, json={"title": "발표"})
    assert (r.status_code, r.json()["detail"]) == (503, "AI 기능 꺼짐")


@pytest.mark.parametrize(
    "result",
    [
        _resp("할 일을 만들어 드릴게요"),
        _resp('{"items": "x"}'),
        _resp("[1, 2, 3]"),
        _resp(_items_json(2)),  # 너무 적음
        _resp(_items_json(6)),  # 너무 많음
        _resp(_items_json(4, title="  ")),
        _resp(_items_json(4, priority="URGENT")),
        _resp(_items_json(4, due_date="내일")),
        _resp(_items_json(4, description=5)),
        _resp('{"items": [1, 2, 3]}'),
        _resp(_items_json(4), stop_reason="max_tokens"),
        _resp("", stop_reason="refusal"),
    ],
)
def test_options_bad_answers_are_502(client, result):
    FakeClient.result = result
    r = client.post(OPT_URL, json={"title": "발표"})
    assert r.status_code == 502
    assert r.json()["detail"] == "제안 실패"


def test_options_db_is_never_changed(client, tmp_path):
    client.post("/api/tasks", json={"title": "기존"})
    db_path = str(tmp_path / "t.db")
    before = _rows(db_path)
    for result in [_resp(_items_json(4)), _resp("not json"), _api_error(anthropic.RateLimitError, 429)]:
        FakeClient.result = result
        client.post(OPT_URL, json={"title": "발표"})
    assert _rows(db_path) == before
