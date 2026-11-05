from fastapi.testclient import TestClient
from app.main import app

def test_liveness_endpoint_does_not_require_backing_services():
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root_endpoint_exposes_api_docs_location():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
