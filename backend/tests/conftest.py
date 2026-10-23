import pytest


@pytest.fixture(autouse=True)
def _session_secret(monkeypatch):
    # 테스트용 임시 값. 실제 backend/.env 의 값을 쓰지 않는다.
    monkeypatch.setenv("SESSION_SECRET", "test-secret-not-real")
