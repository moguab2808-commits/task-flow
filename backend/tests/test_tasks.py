import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        yield c


def test_create_with_title_only(client):
    r = client.post("/api/tasks", json={"title": "a"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "a"
    assert body["description"] == ""
    assert body["status"] == "TODO"
    assert isinstance(body["id"], int)
    assert body["created_at"] and body["updated_at"]


def test_create_with_description(client):
    r = client.post("/api/tasks", json={"title": "a", "description": "d"})
    assert r.json()["description"] == "d"


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_blank_title_rejected(client, title):
    assert client.post("/api/tasks", json={"title": title}).status_code == 422
    assert client.get("/api/tasks").json() == []


def test_missing_title_rejected(client):
    assert client.post("/api/tasks", json={"description": "d"}).status_code == 422


def test_list_in_creation_order(client):
    client.post("/api/tasks", json={"title": "a"})
    client.post("/api/tasks", json={"title": "b"})
    assert [t["title"] for t in client.get("/api/tasks").json()] == ["a", "b"]


def test_persists_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        c.post("/api/tasks", json={"title": "keep"})
    with TestClient(app) as c:
        assert [t["title"] for t in c.get("/api/tasks").json()] == ["keep"]


def _make(client, title="a"):
    return client.post("/api/tasks", json={"title": title}).json()


@pytest.mark.parametrize("status", ["IN_PROGRESS", "DONE", "TODO"])
def test_change_status_to_any_value(client, status):
    t = _make(client)
    client.patch(f"/api/tasks/{t['id']}", json={"status": "DONE"})
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": status})
    assert r.status_code == 200
    assert r.json()["status"] == status


def test_change_status_keeps_title_and_description(client):
    t = client.post("/api/tasks", json={"title": "a", "description": "d"}).json()
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": "DONE"}).json()
    assert (r["title"], r["description"], r["created_at"]) == ("a", "d", t["created_at"])


def test_change_status_only_affects_target(client):
    a, b = _make(client, "a"), _make(client, "b")
    client.patch(f"/api/tasks/{a['id']}", json={"status": "DONE"})
    statuses = {t["title"]: t["status"] for t in client.get("/api/tasks").json()}
    assert statuses == {"a": "DONE", "b": "TODO"}


def test_status_persists_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        t = c.post("/api/tasks", json={"title": "a"}).json()
        c.patch(f"/api/tasks/{t['id']}", json={"status": "IN_PROGRESS"})
    with TestClient(app) as c:
        assert c.get("/api/tasks").json()[0]["status"] == "IN_PROGRESS"


def test_invalid_status_rejected(client):
    t = _make(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={"status": "X"}).status_code == 422
    assert client.get("/api/tasks").json()[0]["status"] == "TODO"


def test_status_change_unknown_id_404(client):
    assert client.patch("/api/tasks/999", json={"status": "DONE"}).status_code == 404


def test_status_change_mixed_with_content_rejected(client):
    t = _make(client)
    r = client.patch(f"/api/tasks/{t['id']}", json={"status": "DONE", "title": "b"})
    assert r.status_code == 422


def test_edit_content_keeps_status(client):
    t = _make(client)
    client.patch(f"/api/tasks/{t['id']}", json={"status": "DONE"})
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "b", "description": "d2"})
    assert r.status_code == 200
    body = r.json()
    assert (body["title"], body["description"], body["status"]) == ("b", "d2", "DONE")


def test_edit_can_clear_description(client):
    t = client.post("/api/tasks", json={"title": "a", "description": "d"}).json()
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": "a", "description": ""})
    assert r.json()["description"] == ""


@pytest.mark.parametrize("title", ["", "  "])
def test_edit_blank_title_rejected(client, title):
    t = _make(client)
    r = client.patch(f"/api/tasks/{t['id']}", json={"title": title})
    assert r.status_code == 422
    assert client.get("/api/tasks").json()[0]["title"] == "a"


def test_edit_unknown_id_404(client):
    assert client.patch("/api/tasks/999", json={"title": "b"}).status_code == 404


def test_empty_patch_rejected(client):
    t = _make(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={}).status_code == 422


def test_delete_removes_task_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        a, b = _make(c, "a"), _make(c, "b")
        assert c.delete(f"/api/tasks/{a['id']}").status_code == 204
    with TestClient(app) as c:
        assert [t["title"] for t in c.get("/api/tasks").json()] == ["b"]


def test_delete_unknown_id_404(client):
    t = _make(client)
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 404
