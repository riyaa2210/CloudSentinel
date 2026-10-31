from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnomalyResponse(BaseModel):
    """An anomaly found by on-demand detection (enriched with the baseline
    that produced it, so a reviewer can see *why* it was flagged)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    cost: float
    timestamp: datetime
    region: str
    account_id: str
    z_score: float
    baseline_mean: float
    baseline_std: float
    threshold: float
    severity: str
    detection_reason: str
    anomaly_event_id: int | None = None


class AnomalyEventResponse(BaseModel):
    """A persisted, de-duplicated alert and its current status."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    billing_record_id: int
    service: str
    observed_cost: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    threshold: float
    severity: str
    detection_reason: str
    status: str
    detected_at: datetime
    created_at: datetime
