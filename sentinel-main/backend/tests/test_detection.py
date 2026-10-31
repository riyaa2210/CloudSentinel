from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Fixed base time so tests are deterministic and independent of wall clock.
BASE_TS = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _batch(service, costs, *, region="us-east-1", account="111111111111", start=BASE_TS):
    records = [
        {
            "service": service,
            "cost": c,
            "timestamp": (start + timedelta(hours=i)).isoformat(),
            "region": region,
            "account_id": account,
        }
        for i, c in enumerate(costs)
    ]
    return {"records": records}


# Tight, non-varying history: std == 0 -> "insufficient", never flagged, and
# crucially no ZeroDivisionError.
def test_constant_costs_no_anomalies_and_no_division_error():
    assert client.post("/api/v1/billing/batch", json=_batch("EC2", [10.0] * 20)).status_code == 201
    r = client.get("/api/v1/billing/anomalies?min_observations=5&window=10&threshold=2")
    assert r.status_code == 200
    assert r.json() == []


# Too few prior points to form a baseline -> "insufficient_data", not flagged.
def test_insufficient_history_not_flagged():
    assert client.post("/api/v1/billing/batch", json=_batch("EC2", [10.0, 11.0, 12.0])).status_code == 201
    r = client.get("/api/v1/billing/anomalies?min_observations=5&window=10&threshold=2")
    assert r.status_code == 200
    assert r.json() == []


# A genuine spike is flagged, enriched with the baseline that produced it,
# persisted as an event, and the candidate never contaminated its own baseline.
def test_spike_detected_enriched_and_persisted():
    normal = [10.0, 10.01] * 7  # 14 near-constant observations
    costs = normal + [100.0]    # clear spike as the last observation
    assert client.post("/api/v1/billing/batch", json=_batch("EC2", costs)).status_code == 201

    r = client.get("/api/v1/billing/anomalies?min_observations=5&window=20&threshold=2")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1  # only the spike, no noise from the near-constant history

    spike = data[0]
    assert spike["service"] == "EC2"
    assert spike["cost"] == 100.0
    assert spike["z_score"] > 2.0
    assert spike["severity"] == "high"
    assert 9.0 < spike["baseline_mean"] < 11.0  # baseline is the normal history
    assert spike["detection_reason"]
    assert spike["anomaly_event_id"] is not None

    # Persisted and visible in the event history.
    events = client.get("/api/v1/anomaly-events/").json()
    assert len(events) == 1
    assert events[0]["status"] == "open"
    assert events[0]["severity"] == "high"


# Normal, low-variance spending must not be flagged.
def test_normal_spending_has_no_anomalies():
    assert client.post("/api/v1/billing/batch", json=_batch("S3", [10.0, 10.01] * 10)).status_code == 201
    r = client.get("/api/v1/billing/anomalies?min_observations=5&window=20&threshold=2")
    assert r.status_code == 200
    assert r.json() == []


# Re-running detection must not create duplicate alerts for the same incident.
def test_dedup_no_repeat_alerts():
    costs = [10.0, 10.01] * 7 + [100.0]
    client.post("/api/v1/billing/batch", json=_batch("EC2", costs))

    r1 = client.get("/api/v1/billing/anomalies?min_observations=5&window=20&threshold=2")
    events1 = client.get("/api/v1/anomaly-events/").json()
    r2 = client.get("/api/v1/billing/anomalies?min_observations=5&window=20&threshold=2")
    events2 = client.get("/api/v1/anomaly-events/").json()

    assert len(r1.json()) >= 1
    assert len(events1) == len(events2)  # no new events on re-run
    assert r1.json() == r2.json()        # identical findings returned


# is_anomaly is set by the system (detection), not by the client.
def test_is_anomaly_is_system_derived():
    costs = [10.0, 10.01] * 7 + [100.0]
    resp = client.post("/api/v1/billing/batch", json=_batch("EC2", costs))
    ids = [r["id"] for r in resp.json()]
    spike_id, normal_id = ids[-1], ids[0]

    assert client.get(f"/api/v1/billing/{spike_id}").json()["is_anomaly"] is False
    client.get("/api/v1/billing/anomalies?min_observations=5&window=20&threshold=2")
    assert client.get(f"/api/v1/billing/{spike_id}").json()["is_anomaly"] is True
    assert client.get(f"/api/v1/billing/{normal_id}").json()["is_anomaly"] is False
