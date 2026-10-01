from fastapi.testclient import TestClient

from newsflow.app import app


def test_health_endpoint_reports_service_identity() -> None:
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"service": "newsflow-api", "status": "ok"}
