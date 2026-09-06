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


def test_checks_returns_recent_history():
    client.get("/health")
    client.get("/ready")

    response = client.get("/checks?limit=2")

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["status"] == "ready"
    assert data["items"][1]["status"] == "ok"


def test_dashboard_returns_html():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Ops Test Lab 监控面板" in response.text
    assert "最近 20 条检查记录" in response.text
