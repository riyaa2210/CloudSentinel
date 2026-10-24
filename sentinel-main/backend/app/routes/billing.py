import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.billing import BillingRecord
from app.schemas.billing import (
    AnomalyResponse,
    BillingBatchCreate,
    BillingCreate,
    BillingResponse,
    SeedResponse,
    BillingSummary,
)
from app.services.mock_data import generate_mock_records

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.post("/", response_model=BillingResponse, status_code=201)
def ingest_single(record: BillingCreate, db: Session = Depends(get_db)):
    """Ingest a single billing record."""
    db_record = BillingRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@router.post("/batch", response_model=list[BillingResponse], status_code=201)
def ingest_batch(batch: BillingBatchCreate, db: Session = Depends(get_db)):
    """Ingest a batch of billing records."""
    db_records = [BillingRecord(**r.model_dump()) for r in batch.records]
    db.add_all(db_records)
    db.commit()
    for r in db_records:
        db.refresh(r)
    return db_records


@router.post("/seed", response_model=SeedResponse, status_code=201)
def seed_mock_data(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Generate and ingest realistic mock AWS billing data."""
    records = generate_mock_records(days=days)
    db.add_all(records)
    db.commit()
    return SeedResponse(
        message=f"Seeded {len(records)} billing records over {days} days",
        records_created=len(records),
    )

@router.get('/', response_model=list[BillingResponse])
def get_billing(
        service: str = Query(default=None),
        region: str = Query(default=None),
        db: Session = Depends(get_db)
):
    stmt = db.query(BillingRecord)
    if service:
        stmt = stmt.filter_by(service=service)
    if region:
        stmt = stmt.filter_by(region=region)
    records = stmt.all()
    return records

@router.get('/summary', response_model=list[BillingSummary])
def get_summary(
        db: Session = Depends(get_db)
):
    total_cost = db.query(BillingRecord.service, func.sum(BillingRecord.cost).label("total_cost")).group_by(BillingRecord.service)
    billing_data = [BillingSummary(service=row.service, total_cost=row.total_cost) for row in total_cost]
    return billing_data

@router.get('/anomalies', response_model=list[AnomalyResponse])
def get_anomalies(
        threshold: float = Query(default=2.0, ge=0),
        db: Session = Depends(get_db),
):
    """Return billing records with |z-score| > threshold, grouped by service."""
    records = db.query(BillingRecord).all()

    grouped = defaultdict(list)
    for r in records:
        grouped[r.service].append(r)

    anomalies = []
    for service, group in grouped.items():
        if len(group) < 2:
            continue
        costs = [r.cost for r in group]
        mean = statistics.mean(costs)
        std = statistics.stdev(costs)
        if std == 0:
            continue
        for r in group:
            z = (r.cost - mean) / std
            if abs(z) > threshold:
                anomalies.append(AnomalyResponse(
                    id=r.id,
                    service=r.service,
                    cost=r.cost,
                    timestamp=r.timestamp,
                    region=r.region,
                    account_id=r.account_id,
                    z_score=round(z, 3),
                ))

    anomalies.sort(key=lambda a: abs(a.z_score), reverse=True)
    return anomalies


@router.get('/{id}', response_model=BillingResponse)
def get_info(
        id: int,
        db: Session = Depends(get_db)
):
    record = db.get(BillingRecord, id)
    if not record:
        raise HTTPException(detail="Billing Record not found", status_code=404)
    return record
