import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200

def test_health_check():
    # Note: This might return 503 if DB/Redis are not running in the test environment,
    # but the endpoint itself should exist.
    response = client.get("/health")
    assert response.status_code in [200, 503]

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
