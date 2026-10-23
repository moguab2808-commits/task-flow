from app import security


def test_hash_differs_each_time_and_hides_plaintext():
    a, b = security.hash_password("password1"), security.hash_password("password1")
    assert a != b
    assert "password1" not in a


def test_verify_password():
    h = security.hash_password("password1")
    assert security.verify_password("password1", h)
    assert not security.verify_password("password2", h)


def test_no_hash_never_verifies():
    assert not security.verify_password("", None)
    assert not security.verify_password("x", "")


def test_garbage_hash_fails_closed():
    assert not security.verify_password("x", "not-a-hash")


def test_cookie_roundtrip():
    sid = security.new_session_id()
    assert security.read_session_cookie(security.sign_session_id(sid)) == sid


def test_tampered_cookie_rejected():
    sid = security.new_session_id()
    value = security.sign_session_id(sid)
    assert security.read_session_cookie(value[:-1] + ("0" if value[-1] != "0" else "1")) is None
    assert security.read_session_cookie("other." + value.split(".", 1)[1]) is None
    assert security.read_session_cookie(sid) is None
    assert security.read_session_cookie(None) is None


def test_cookie_signed_with_other_secret_rejected(monkeypatch):
    sid = security.new_session_id()
    value = security.sign_session_id(sid)
    monkeypatch.setenv("SESSION_SECRET", "different")
    assert security.read_session_cookie(value) is None
