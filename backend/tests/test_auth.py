from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth_repository, db
from app.main import app

PW = "password-1"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    with TestClient(app) as c:
        yield c


def _signup(c, name="alice", pw=PW):
    return c.post("/api/auth/signup", json={"username": name, "password": pw})


def _login(c, name="alice", pw=PW):
    return c.post("/api/auth/login", json={"username": name, "password": pw})


def test_signup_returns_only_username(client):
    r = _signup(client)
    assert r.status_code == 201
    assert r.json() == {"username": "alice"}


def test_signup_does_not_log_in(client):
    _signup(client)
    assert client.get("/api/auth/me").status_code == 401


def test_password_stored_as_hash_only(client):
    _signup(client)
    conn = db.connect()
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    conn.close()
    assert stored and PW not in stored


def test_duplicate_username_rejected_case_insensitive(client):
    assert _signup(client, "Alice").status_code == 201
    r = _signup(client, " alice ")
    assert r.status_code == 409
    assert "이미" in r.json()["detail"]


@pytest.mark.parametrize("name", ["", "   ", "a" * 51])
def test_signup_bad_username_rejected(client, name):
    assert _signup(client, name).status_code == 422


@pytest.mark.parametrize("pw", ["", "short"])
def test_signup_bad_password_rejected_and_not_echoed(client, pw):
    r = _signup(client, pw=pw)
    assert r.status_code == 422
    if pw:
        assert pw not in r.text


def test_username_with_at_sign_allowed(client):
    assert _signup(client, "me@example.com").status_code == 201


def test_login_sets_httponly_cookie(client):
    _signup(client)
    r = _login(client)
    assert r.status_code == 200
    assert r.json() == {"username": "alice"}
    cookie = r.headers["set-cookie"].lower()
    assert "taskflow_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=1800" in cookie
    assert PW not in r.text


def test_login_failure_is_same_for_wrong_password_and_unknown_user(client):
    _signup(client)
    a = _login(client, pw="wrong-password")
    b = _login(client, name="nobody")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    assert "set-cookie" not in a.headers


def test_login_empty_input_rejected(client):
    assert _login(client, name="", pw="x").status_code == 422
    assert _login(client, name="alice", pw="").status_code == 422


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401
    _signup(client)
    _login(client)
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json() == {"username": "alice"}


def test_tampered_cookie_is_unauthorized(client):
    _signup(client)
    _login(client)
    value = client.cookies.get("taskflow_session")
    client.cookies.clear()
    client.cookies.set("taskflow_session", value[:-1] + ("0" if value[-1] != "0" else "1"))
    assert client.get("/api/auth/me").status_code == 401


def test_logout_deletes_session_and_cookie(client):
    _signup(client)
    _login(client)
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert "taskflow_session" in r.headers["set-cookie"]
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    conn.close()
    assert client.get("/api/auth/me").status_code == 401


def test_logout_when_logged_out_is_ok(client):
    assert client.post("/api/auth/logout").status_code == 204


def test_session_expires_30_minutes_after_login_without_extension(client, monkeypatch):
    _signup(client)
    start = auth_repository.now()
    monkeypatch.setattr(auth_repository, "now", lambda: start)
    _login(client)
    monkeypatch.setattr(auth_repository, "now", lambda: start + timedelta(minutes=29))
    assert client.get("/api/auth/me").status_code == 200  # 쓰는 중이어도 연장하지 않는다
    monkeypatch.setattr(auth_repository, "now", lambda: start + timedelta(minutes=31))
    assert client.get("/api/auth/me").status_code == 401


def test_expired_sessions_are_purged_on_next_login(client, monkeypatch):
    _signup(client)
    start = auth_repository.now()
    monkeypatch.setattr(auth_repository, "now", lambda: start)
    _login(client)
    monkeypatch.setattr(auth_repository, "now", lambda: start + timedelta(minutes=31))
    _login(client)
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    conn.close()


def test_same_user_can_log_in_twice(client):
    _signup(client)
    _login(client)
    _login(client)
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    conn.close()


# --- 이전용 계정 (D-016) ---------------------------------------------------


@pytest.fixture
def migrated(client):
    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES ('migrated@test.com', NULL, 'now')"
        )
    user_id = conn.execute("SELECT id FROM users").fetchone()[0]
    conn.close()
    return user_id


def test_migrated_account_cannot_log_in_before_signup(client, migrated):
    for pw in ("", PW, "None"):
        r = client.post("/api/auth/login", json={"username": "migrated@test.com", "password": pw or "x"})
        assert r.status_code == 401


def test_signup_adopts_migrated_account(client, migrated):
    r = _signup(client, "migrated@test.com")
    assert r.status_code == 201
    assert r.json() == {"username": "migrated@test.com"}
    conn = db.connect()
    rows = conn.execute("SELECT id, password_hash FROM users").fetchall()
    conn.close()
    assert len(rows) == 1 and rows[0]["id"] == migrated and rows[0]["password_hash"]
    assert _login(client, "migrated@test.com").status_code == 200


def test_migrated_account_cannot_be_adopted_twice(client, migrated):
    assert _signup(client, "migrated@test.com").status_code == 201
    assert _signup(client, "migrated@test.com", pw="another-pass").status_code == 409


def test_empty_secret_refuses_server_start(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("SESSION_SECRET", "")
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass


def test_cors_allows_credentials_only_for_known_origins(client):
    ok = client.options(
        "/api/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert ok.headers["access-control-allow-credentials"] == "true"
    bad = client.options(
        "/api/auth/login",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in bad.headers
