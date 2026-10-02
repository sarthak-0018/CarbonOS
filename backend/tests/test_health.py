from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_is_live_without_database_access():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "carbonos-api"}
