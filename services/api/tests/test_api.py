from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "api"

def test_summary_shape():
    response = client.get("/api/summary")
    assert response.status_code == 200
    assert "clusters" in response.json()
