import pytest

from app import config


def test_empty_secret_refuses_start(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "")
    with pytest.raises(RuntimeError) as e:
        config.session_secret()
    assert "SESSION_SECRET" in str(e.value)


def test_missing_secret_refuses_start(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        config.session_secret()


def test_secret_value_is_returned(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "abc")
    assert config.session_secret() == "abc"
