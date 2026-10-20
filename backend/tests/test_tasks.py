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
