import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


def _user(c, name):
    c.post("/api/auth/signup", json={"username": name, "password": "password-1"})
    assert c.post("/api/auth/login", json={"username": name, "password": "password-1"}).status_code == 200


@pytest.fixture
def anon(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def two_users(anon):
    """같은 서버를 쓰는 서로 다른 브라우저 둘 (쿠키 보관함이 따로)."""
    a = TestClient(app)
    b = TestClient(app)
    _user(a, "alice")
    _user(b, "bob")
    yield a, b
    a.close()
    b.close()


CALLS = [
    ("get", "/api/tasks", None),
    ("post", "/api/tasks", {"title": "a"}),
    ("patch", "/api/tasks/1", {"title": "b"}),
    ("patch", "/api/tasks/1", {"status": "DONE"}),
    ("delete", "/api/tasks/1", None),
]


@pytest.mark.parametrize("method,path,body", CALLS)
def test_task_api_requires_login(anon, method, path, body):
    r = getattr(anon, method)(path, **({"json": body} if body is not None else {}))
    assert r.status_code == 401


def test_login_check_comes_before_input_validation(anon):
    assert anon.post("/api/tasks", json={"title": ""}).status_code == 401
    assert anon.patch("/api/tasks/1", json={}).status_code == 401


def test_each_user_sees_only_own_tasks(two_users):
    a, b = two_users
    a.post("/api/tasks", json={"title": "alice-task"})
    b.post("/api/tasks", json={"title": "bob-task"})
    assert [t["title"] for t in a.get("/api/tasks").json()] == ["alice-task"]
    assert [t["title"] for t in b.get("/api/tasks").json()] == ["bob-task"]


def test_other_users_task_is_404_for_edit_status_delete(two_users):
    a, b = two_users
    t = a.post("/api/tasks", json={"title": "mine"}).json()
    url = f"/api/tasks/{t['id']}"
    missing = b.delete("/api/tasks/9999")
    for r in (
        b.patch(url, json={"title": "hacked"}),
        b.patch(url, json={"status": "DONE"}),
        b.delete(url),
    ):
        assert r.status_code == 404
        assert r.json() == missing.json()
    untouched = a.get("/api/tasks").json()[0]
    assert (untouched["title"], untouched["status"]) == ("mine", "TODO")


def test_owner_is_set_by_server_not_body(two_users):
    a, b = two_users
    r = a.post("/api/tasks", json={"title": "x", "owner_id": 2})
    assert r.status_code == 422
    assert a.get("/api/tasks").json() == []
    assert "owner_id" not in a.post("/api/tasks", json={"title": "x"}).json()


def test_owner_cannot_be_changed_by_patch(two_users):
    a, b = two_users
    t = a.post("/api/tasks", json={"title": "x"}).json()
    assert a.patch(f"/api/tasks/{t['id']}", json={"title": "x", "owner_id": 2}).status_code == 422


def test_tasks_stored_with_owner_id(two_users):
    a, _ = two_users
    a.post("/api/tasks", json={"title": "x"})
    conn = db.connect()
    owner = conn.execute("SELECT owner_id FROM tasks").fetchone()[0]
    name = conn.execute("SELECT username FROM users WHERE id = ?", (owner,)).fetchone()[0]
    conn.close()
    assert name == "alice"


def test_logged_out_user_loses_access(two_users):
    a, _ = two_users
    a.post("/api/tasks", json={"title": "x"})
    a.post("/api/auth/logout")
    assert a.get("/api/tasks").status_code == 401


def test_migrated_tasks_visible_only_to_adopter(anon):
    conn = db.connect()
    with conn:
        conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES ('migrated@test.com', NULL, 'n')")
        owner = conn.execute("SELECT id FROM users").fetchone()[0]
        conn.execute(
            "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
            " VALUES ('old', '', 'TODO', 'n', 'n', ?)",
            (owner,),
        )
    conn.close()
    other = TestClient(app)
    _user(other, "other")
    assert other.get("/api/tasks").json() == []
    assert other.patch("/api/tasks/1", json={"status": "DONE"}).status_code == 404
    adopter = TestClient(app)
    _user(adopter, "migrated@test.com")
    assert [t["title"] for t in adopter.get("/api/tasks").json()] == ["old"]
    other.close()
    adopter.close()
