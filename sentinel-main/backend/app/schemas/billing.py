from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BillingCreate(BaseModel):
    service: str
    cost: float
    timestamp: datetime
    region: str
    account_id: str
    is_anomaly: bool = False


class BillingBatchCreate(BaseModel):
    records: list[BillingCreate]


class BillingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    cost: float
    timestamp: datetime
    region: str
    account_id: str
    is_anomaly: bool
    created_at: datetime


class SeedResponse(BaseModel):
    message: str
    records_created: int

class BillingSummary(BaseModel):
    service: str
    total_cost: float


class AnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    cost: float
    timestamp: datetime
    region: str
    account_id: str
    z_score: float
