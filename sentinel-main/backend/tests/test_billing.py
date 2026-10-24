from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_seed():
    response = client.post("/api/v1/billing/seed?days=7")
    assert response.status_code == 201
    data = response.json()
    assert data["records_created"] > 0


def test_get_billing():
    client.post("/api/v1/billing/seed?days=7")
    response = client.get("/api/v1/billing/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0


def test_get_billing_filter():
    client.post("/api/v1/billing/seed?days=7")
    response = client.get("/api/v1/billing/?service=EC2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(r["service"] == "EC2" for r in data)


def test_get_by_id():
    client.post("/api/v1/billing/seed?days=7")
    response = client.get("/api/v1/billing/1")
    assert response.status_code == 200


def test_get_by_id_404():
    response = client.get("/api/v1/billing/999999")
    assert response.status_code == 404


def test_anomalies():
    client.post("/api/v1/billing/seed?days=7")
    response = client.get("/api/v1/billing/anomalies")
    assert response.status_code == 200
    data = response.json()
    for record in data:
        assert "z_score" in record
        assert abs(record["z_score"]) > 2.0


def test_anomaly_threshold():
    client.post("/api/v1/billing/seed?days=30")
    r2 = client.get("/api/v1/billing/anomalies?threshold=2")
    r10 = client.get("/api/v1/billing/anomalies?threshold=10")
    assert r2.status_code == 200
    assert r10.status_code == 200
    assert len(r10.json()) <= len(r2.json())
