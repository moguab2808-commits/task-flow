"""우선순위 · 마감일 · 기한 초과 · 정렬 (이슈 #21, R-010 ~ R-013). 업무 규칙은 BUSINESS-RULES.md."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import repository
from app.main import app

TODAY = date(2026, 10, 27)
YESTERDAY, TOMORROW = "2026-10-26", "2026-10-28"


def _user(c, name):
    c.post("/api/auth/signup", json={"username": name, "password": "password-1"})
    assert c.post("/api/auth/login", json={"username": name, "password": "password-1"}).status_code == 200


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(repository, "_today", lambda: TODAY)  # 기한 초과 검수용으로 "오늘"을 고정한다.
    with TestClient(app) as c:
        _user(c, "tester")
        yield c


def _make(c, title="a", **extra):
    r = c.post("/api/tasks", json={"title": title, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _get(c, task_id):
    return next(t for t in c.get("/api/tasks").json() if t["id"] == task_id)


# ---- 등록: 우선순위 · 마감일 (R-010, R-011) ----

def test_create_defaults_to_normal_priority_and_no_due_date(client):
    t = _make(client)
    assert (t["priority"], t["due_date"], t["is_overdue"]) == ("NORMAL", None, False)


@pytest.mark.parametrize("priority", ["LOW", "NORMAL", "HIGH"])
def test_create_with_each_priority(client, priority):
    assert _make(client, priority=priority)["priority"] == priority


def test_create_with_due_date_and_it_is_listed(client):
    t = _make(client, due_date="2026-11-30")
    assert _get(client, t["id"])["due_date"] == "2026-11-30"


def test_create_accepts_past_due_date(client):
    assert _make(client, due_date="2020-01-01")["due_date"] == "2020-01-01"


def test_create_with_null_due_date_means_no_due_date(client):
    assert _make(client, due_date=None)["due_date"] is None


@pytest.mark.parametrize("bad", ["URGENT", "high", "normal", "", 1, ["HIGH"]])
def test_create_rejects_priority_outside_three_values(client, bad):
    r = client.post("/api/tasks", json={"title": "a", "priority": bad})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "priority"
    assert client.get("/api/tasks").json() == []


def test_create_rejects_null_priority(client):
    r = client.post("/api/tasks", json={"title": "a", "priority": None})
    assert r.status_code == 422
    assert "우선순위" in r.json()["detail"][0]["msg"]
    assert client.get("/api/tasks").json() == []


@pytest.mark.parametrize(
    "bad",
    ["2026/10/30", "20261030", "2026-1-3", "2026-10-30T00:00:00", "2026-10-30 10:00",
     "2026-02-30", "2026-13-01", "abc", "", " 2026-10-30", 20261030, True],
)
def test_create_rejects_non_date_due_date(client, bad):
    r = client.post("/api/tasks", json={"title": "a", "due_date": bad})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "due_date"
    assert client.get("/api/tasks").json() == []


def test_rejected_request_saves_nothing_from_the_same_request(client):
    r = client.post("/api/tasks", json={"title": "ok", "priority": "HIGH", "due_date": "nope"})
    assert r.status_code == 422
    assert client.get("/api/tasks").json() == []


def test_422_message_is_korean_and_names_the_field(client):
    r = client.post("/api/tasks", json={"title": "a", "due_date": "nope"})
    assert "마감일" in r.json()["detail"][0]["msg"]
    r = client.post("/api/tasks", json={"title": "a", "priority": "URGENT"})
    assert "우선순위" in r.json()["detail"][0]["msg"]


def test_create_still_works_with_old_request_shape(client):
    t = _make(client, description="d")
    assert (t["title"], t["description"], t["status"]) == ("a", "d", "TODO")


# ---- 수정: 보내지 않으면 그대로, due_date null 이면 지움, priority null 은 422 (결정 7 ~ 9) ----

def test_edit_without_new_fields_keeps_priority_and_due_date(client):
    t = _make(client, priority="HIGH", due_date="2026-11-01")
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "b"})
    assert (r.json()["priority"], r.json()["due_date"]) == ("HIGH", "2026-11-01")


def test_edit_changes_priority_only(client):
    t = _make(client, priority="LOW", due_date="2026-11-01")
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "priority": "HIGH"})
    assert (r.json()["priority"], r.json()["due_date"]) == ("HIGH", "2026-11-01")


def test_edit_changes_due_date_to_new_date(client):
    t = _make(client, due_date="2026-11-01")
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "due_date": "2026-12-25"})
    assert r.json()["due_date"] == "2026-12-25"
    assert _get(client, t["id"])["due_date"] == "2026-12-25"


def test_edit_with_null_due_date_clears_it(client):
    t = _make(client, due_date="2026-11-01", priority="HIGH")
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "due_date": None})
    assert r.status_code == 200
    assert (r.json()["due_date"], r.json()["priority"]) == (None, "HIGH")
    assert _get(client, t["id"])["due_date"] is None


def test_edit_can_set_due_date_on_task_without_one(client):
    t = _make(client)
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "due_date": "2026-11-01"})
    assert r.json()["due_date"] == "2026-11-01"


def test_edit_rejects_null_priority_and_keeps_everything(client):
    t = _make(client, priority="HIGH")
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "changed", "priority": None})
    assert r.status_code == 422
    kept = _get(client, t["id"])
    assert (kept["title"], kept["priority"]) == ("a", "HIGH")


@pytest.mark.parametrize("bad", ["URGENT", "", "low", 3])
def test_edit_rejects_priority_outside_three_values(client, bad):
    t = _make(client, priority="LOW")
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "x", "priority": bad})
    assert r.status_code == 422
    kept = _get(client, t["id"])
    assert (kept["title"], kept["priority"]) == ("a", "LOW")


@pytest.mark.parametrize("bad", ["2026-02-30", "10/30", "", 5])
def test_edit_rejects_bad_due_date_and_keeps_everything(client, bad):
    t = _make(client, due_date="2026-11-01")
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "x", "due_date": bad})
    assert r.status_code == 422
    kept = _get(client, t["id"])
    assert (kept["title"], kept["due_date"]) == ("a", "2026-11-01")


def test_edit_accepts_past_due_date(client):
    t = _make(client)
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "due_date": "2000-01-01"})
    assert r.json()["due_date"] == "2000-01-01"


def test_edit_does_not_change_status(client):
    t = _make(client)
    client.patch(f"/api/tasks/{t['id']}", json={"status": "IN_PROGRESS"})
    r = client.patch(
        f"/api/tasks/{t['id']}", json={"title": "b", "priority": "HIGH", "due_date": YESTERDAY}
    )
    assert r.json()["status"] == "IN_PROGRESS"


# ---- 상태 변경: 새 필드는 그대로, 섞인 요청은 거절 (A-10, A-12) ----

def test_status_change_keeps_priority_and_due_date(client):
    t = _make(client, priority="HIGH", due_date="2026-11-01")
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": "DONE"})
    assert (r.json()["priority"], r.json()["due_date"], r.json()["status"]) == ("HIGH", "2026-11-01", "DONE")


@pytest.mark.parametrize("extra", [{"priority": "HIGH"}, {"due_date": "2026-11-01"}, {"due_date": None}])
def test_status_change_mixed_with_new_fields_rejected(client, extra):
    t = _make(client, priority="LOW")
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": "DONE", **extra})
    assert r.status_code == 422
    kept = _get(client, t["id"])
    assert (kept["status"], kept["priority"], kept["due_date"]) == ("TODO", "LOW", None)


def test_empty_patch_still_rejected(client):
    t = _make(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={}).status_code == 422


def test_patch_with_only_new_fields_is_rejected_because_title_is_required(client):
    t = _make(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={"priority": "HIGH"}).status_code == 422


# ---- 기한 초과: 판정표 8행 (BR-3). "오늘" = 2026-10-27 ----

OVERDUE_TABLE = [
    (YESTERDAY, "TODO", True), (YESTERDAY, "IN_PROGRESS", True),
    (YESTERDAY, "DONE", False),
    ("2026-10-27", "TODO", False), ("2026-10-27", "IN_PROGRESS", False),
    ("2026-10-27", "DONE", False),
    (TOMORROW, "TODO", False), (TOMORROW, "DONE", False),
    (None, "TODO", False), (None, "IN_PROGRESS", False), (None, "DONE", False),
]


@pytest.mark.parametrize("due,status,expected", OVERDUE_TABLE)
def test_overdue_judgement_table(client, due, status, expected):
    t = _make(client, due_date=due)
    if status != "TODO":
        client.patch(f"/api/tasks/{t['id']}", json={"status": status})
    assert _get(client, t["id"])["is_overdue"] is expected


def test_overdue_is_in_every_task_response(client):
    t = _make(client, due_date=YESTERDAY)
    assert t["is_overdue"] is True
    edited = client.patch(f"/api/tasks/{t['id']}", json={"title": "a"}).json()
    assert edited["is_overdue"] is True
    done = client.patch(f"/api/tasks/{t['id']}", json={"status": "DONE"}).json()
    assert done["is_overdue"] is False
    back = client.patch(f"/api/tasks/{t['id']}", json={"status": "TODO"}).json()
    assert back["is_overdue"] is True


def test_overdue_follows_edits_of_due_date(client):
    t = _make(client, due_date=YESTERDAY)
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "due_date": TOMORROW})
    assert r.json()["is_overdue"] is False
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "due_date": None})
    assert r.json()["is_overdue"] is False


def test_overdue_is_computed_not_stored_and_follows_today(client, monkeypatch):
    t = _make(client, due_date="2026-10-28")
    assert _get(client, t["id"])["is_overdue"] is False
    monkeypatch.setattr(repository, "_today", lambda: date(2026, 10, 29))
    assert _get(client, t["id"])["is_overdue"] is True


def test_overdue_does_not_change_status(client):
    t = _make(client, due_date="2000-01-01")
    assert _get(client, t["id"])["status"] == "TODO"
    client.patch(f"/api/tasks/{t['id']}", json={"status": "IN_PROGRESS"})
    assert _get(client, t["id"])["status"] == "IN_PROGRESS"


# ---- 정렬: 기한 초과 → 우선순위(HIGH 먼저) → 가까운 마감일(없으면 뒤) → ID (BR-4) ----

def _order(c):
    return [t["title"] for t in c.get("/api/tasks").json()]


def test_sort_overdue_comes_first_even_with_low_priority(client):
    _make(client, "normal-ok", priority="HIGH", due_date=TOMORROW)
    _make(client, "late-low", priority="LOW", due_date=YESTERDAY)
    assert _order(client) == ["late-low", "normal-ok"]


def test_sort_priority_high_normal_low(client):
    _make(client, "low", priority="LOW")
    _make(client, "normal")
    _make(client, "high", priority="HIGH")
    assert _order(client) == ["high", "normal", "low"]


def test_sort_nearer_due_date_first_and_no_due_date_last(client):
    _make(client, "none")
    _make(client, "far", due_date="2026-12-01")
    _make(client, "near", due_date="2026-11-01")
    assert _order(client) == ["near", "far", "none"]


def test_sort_ties_fall_back_to_creation_order(client):
    for name in ("a", "b", "c"):
        _make(client, name, due_date="2026-11-01")
    assert _order(client) == ["a", "b", "c"]


def test_sort_within_overdue_uses_priority_then_due_date_then_id(client):
    _make(client, "late-normal-old", due_date="2026-10-01")
    _make(client, "late-high", priority="HIGH", due_date="2026-10-20")
    _make(client, "late-normal-new", due_date="2026-10-20")
    _make(client, "late-normal-new2", due_date="2026-10-20")
    assert _order(client) == [
        "late-high", "late-normal-old", "late-normal-new", "late-normal-new2",
    ]


def test_sort_done_task_drops_out_of_overdue_group(client):
    a = _make(client, "a", due_date=YESTERDAY)
    _make(client, "b", priority="HIGH")
    assert _order(client) == ["a", "b"]
    client.patch(f"/api/tasks/{a['id']}", json={"status": "DONE"})
    assert _order(client) == ["b", "a"]


def test_sort_is_not_by_status_and_changes_no_values(client):
    a = _make(client, "a", priority="LOW")
    _make(client, "b", priority="HIGH")
    client.patch(f"/api/tasks/{a['id']}", json={"status": "DONE"})
    tasks = client.get("/api/tasks").json()
    assert [t["title"] for t in tasks] == ["b", "a"]
    assert {t["title"]: (t["status"], t["priority"], t["due_date"]) for t in tasks} == {
        "a": ("DONE", "LOW", None), "b": ("TODO", "HIGH", None),
    }


def test_sort_without_new_values_is_creation_order(client):
    for name in ("a", "b", "c"):
        _make(client, name)
    assert _order(client) == ["a", "b", "c"]


# ---- 사용자 분리 (R-009, A-13, A-14) ----

@pytest.fixture
def two_users(client):
    a, b = TestClient(app), TestClient(app)
    _user(a, "alice")
    _user(b, "bob")
    yield a, b
    a.close()
    b.close()


def test_priority_and_due_date_are_not_visible_to_other_user(two_users):
    a, b = two_users
    _make(a, "mine", priority="HIGH", due_date=YESTERDAY)
    assert b.get("/api/tasks").json() == []
    _make(b, "bobs")
    assert [t["title"] for t in a.get("/api/tasks").json()] == ["mine"]


def test_other_users_task_is_404_for_edit_and_stays_unchanged(two_users):
    a, b = two_users
    t = _make(a, "mine", priority="LOW", due_date="2026-11-01")
    r = b.patch(f"/api/tasks/{t['id']}", json={"title": "x", "priority": "HIGH", "due_date": None})
    assert r.status_code == 404
    kept = _get(a, t["id"])
    assert (kept["title"], kept["priority"], kept["due_date"]) == ("mine", "LOW", "2026-11-01")


def test_sort_is_per_user(two_users):
    a, b = two_users
    _make(a, "a-low", priority="LOW")
    _make(b, "b-high", priority="HIGH")
    _make(a, "a-high", priority="HIGH")
    assert [t["title"] for t in a.get("/api/tasks").json()] == ["a-high", "a-low"]
    assert [t["title"] for t in b.get("/api/tasks").json()] == ["b-high"]


def test_login_required_before_validating_new_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as anon:
        assert anon.post("/api/tasks", json={"title": "a", "priority": "BAD"}).status_code == 401
        assert anon.patch("/api/tasks/1", json={"title": "a", "due_date": "BAD"}).status_code == 401


def test_owner_still_not_accepted_from_body(client):
    r = client.post("/api/tasks", json={"title": "a", "priority": "HIGH", "owner_id": 99})
    assert r.status_code == 422


# ---- 응답 형식과 재시작 (A-15, V-11, V-12) ----

def test_response_keeps_existing_fields_and_adds_new_ones(client):
    t = _make(client, "a", description="d")
    assert set(t) == {
        "id", "title", "description", "status", "created_at", "updated_at",
        "priority", "due_date", "is_overdue",
    }
    assert "owner_id" not in t


def test_new_values_persist_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(repository, "_today", lambda: TODAY)
    with TestClient(app) as c:
        _user(c, "u")
        _make(c, "keep", priority="HIGH", due_date="2026-11-01")
    with TestClient(app) as c:
        _user(c, "u")
        kept = c.get("/api/tasks").json()[0]
        assert (kept["priority"], kept["due_date"]) == ("HIGH", "2026-11-01")


def test_delete_still_removes_task_with_new_fields(client):
    t = _make(client, priority="HIGH", due_date=YESTERDAY)
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    assert client.get("/api/tasks").json() == []
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 404
