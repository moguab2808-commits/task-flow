from fastapi.testclient import TestClient

from app.main import app


def test_health_paths():
    # 수명 이벤트를 켜지 않아 DB 에 닿지 않는다.
    client = TestClient(app)
    for path in ("/health", "/api/health"):
        r = client.get(path)
        assert (r.status_code, r.json()) == (200, {"status": "ok"})
