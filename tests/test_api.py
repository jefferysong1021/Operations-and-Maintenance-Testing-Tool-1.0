from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

import app as app_module
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


def test_ready_returns_503_when_database_fails():
    with patch.object(
        app_module,
        "get_db_connection",
        side_effect=SQLAlchemyError("simulated database failure"),
    ):
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "error",
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


def test_checks_rejects_invalid_limit():
    assert client.get("/checks?limit=0").status_code == 422
    assert client.get("/checks?limit=101").status_code == 422


def test_dashboard_returns_html():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Ops Test Lab 监控面板" in response.text
    assert "最近 20 条检查记录" in response.text
    assert "最近告警" in response.text


def test_alerts_returns_json():
    response = client.get("/alerts?limit=10")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data["count"], int)
    assert data["count"] <= 10
    assert isinstance(data["items"], list)


def test_alerts_rejects_invalid_limit():
    assert client.get("/alerts?limit=0").status_code == 422
    assert client.get("/alerts?limit=101").status_code == 422


def test_summary_returns_current_monitor_status():
    response = client.get("/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["current_status"] in {"healthy", "unhealthy", "unknown"}
    assert "checked_at" in data
    assert isinstance(data["failed_targets"], list)
    assert isinstance(data["recent_alert_count"], int)
