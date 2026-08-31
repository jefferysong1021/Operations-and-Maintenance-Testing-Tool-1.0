from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "ops-test-lab"
    assert "time" in data


def test_ready_returns_database_ok():
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
    }


def test_unknown_route_returns_404():
    response = client.get("/not-found")

    assert response.status_code == 404