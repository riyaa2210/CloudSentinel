import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.anomaly import AnomalyEvent
from app.models.billing import BillingRecord
from app.schemas.anomaly import AnomalyResponse
from app.schemas.billing import (
    BillingBatchCreate,
    BillingCreate,
    BillingResponse,
    BillingSummary,
    SeedResponse,
)
from app.services.detection import detect_anomalies
from app.services.mock_data import generate_mock_records

logger = logging.getLogger("sentinel.billing")
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.post("/", response_model=BillingResponse, status_code=201)
def ingest_single(record: BillingCreate, db: Session = Depends(get_db)):
    """Ingest a single billing record. is_anomaly is system-derived, not client-set."""
    db_record = BillingRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    logger.info(
        "ingested record id=%s service=%s cost=%.2f",
        db_record.id,
        db_record.service,
        db_record.cost,
    )
    return db_record


@router.post("/batch", response_model=list[BillingResponse], status_code=201)
def ingest_batch(batch: BillingBatchCreate, db: Session = Depends(get_db)):
    """Ingest a batch of billing records."""
    db_records = [BillingRecord(**r.model_dump()) for r in batch.records]
    db.add_all(db_records)
    db.commit()
    for r in db_records:
        db.refresh(r)
    logger.info("ingested batch of %s records", len(db_records))
    return db_records


@router.post("/seed", response_model=SeedResponse, status_code=201)
def seed_mock_data(
    days: int = Query(default=30, ge=1, le=365),
    seed: int | None = Query(default=None, description="RNG seed for deterministic data"),
    replace: bool = Query(
        default=False, description="Delete existing records before seeding"
    ),
    db: Session = Depends(get_db),
):
    """Generate and ingest realistic mock billing data.

    Pass a ``seed`` for a reproducible dataset (handy for demos and tests).
    Set ``replace=true`` to clear existing records first.
    """
    if replace:
        deleted = db.query(BillingRecord).delete()
        db.commit()
        logger.info("seed: cleared %s existing records", deleted)
    records = generate_mock_records(days=days, seed=seed)
    db.add_all(records)
    db.commit()
    logger.info(
        "seed: created %s records (days=%s, seed=%s)", len(records), days, seed
    )
    return SeedResponse(
        message=f"Seeded {len(records)} billing records over {days} days",
        records_created=len(records),
        seed_used=seed,
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
    total_cost = (
        db.query(BillingRecord.service, func.sum(BillingRecord.cost).label("total_cost"))
        .group_by(BillingRecord.service)
    )
    billing_data = [
        BillingSummary(service=row.service, total_cost=row.total_cost)
        for row in total_cost
    ]
    return billing_data


@router.get('/anomalies', response_model=list[AnomalyResponse])
def get_anomalies(
        threshold: float | None = Query(default=None, ge=0),
        window: int | None = Query(default=None, ge=1),
        min_observations: int | None = Query(default=None, ge=1),
        db: Session = Depends(get_db),
):
    """Detect anomalies against a rolling per-service baseline.

    Each candidate is compared to the previous ``window`` observations of the
    same service (candidate excluded), so a spike never inflates its own
    baseline. Findings are persisted as AnomalyEvents with de-duplication: an
    already-alerted record is not re-alerted. ``threshold``, ``window`` and
    ``min_observations`` default to configured values.
    """
    settings = get_settings()
    effective_threshold = (
        threshold if threshold is not None else settings.anomaly_z_score_threshold
    )
    effective_window = (
        window if window is not None else settings.anomaly_detection_window
    )
    effective_min = (
        min_observations
        if min_observations is not None
        else settings.anomaly_min_observations
    )

    records = db.query(BillingRecord).all()
    findings, insufficient = detect_anomalies(
        records,
        window=effective_window,
        min_observations=effective_min,
        threshold=effective_threshold,
    )

    anomalies = []
    for f in findings:
        event = (
            db.query(AnomalyEvent)
            .filter(AnomalyEvent.billing_record_id == f.record_id)
            .first()
        )
        if event is None:
            event = AnomalyEvent(
                billing_record_id=f.record_id,
                service=f.service,
                observed_cost=f.cost,
                baseline_mean=f.baseline_mean,
                baseline_std=f.baseline_std,
                z_score=f.z_score,
                threshold=f.threshold,
                severity=f.severity,
                detection_reason=f.detection_reason,
                status="open",
            )
            db.add(event)
            db.flush()  # populate event.id (and persist) without committing yet
            rec = db.get(BillingRecord, f.record_id)
            if rec is not None:
                rec.is_anomaly = True
            logger.warning(
                "new anomaly: service=%s cost=%.2f z=%.2f severity=%s",
                f.service, f.cost, f.z_score, f.severity,
            )
        anomalies.append(
            AnomalyResponse(
                id=f.record_id,
                service=f.service,
                cost=f.cost,
                timestamp=f.timestamp,
                region=f.region,
                account_id=f.account_id,
                z_score=round(f.z_score, 3),
                baseline_mean=round(f.baseline_mean, 4),
                baseline_std=round(f.baseline_std, 4),
                threshold=f.threshold,
                severity=f.severity,
                detection_reason=f.detection_reason,
                anomaly_event_id=event.id,
            )
        )

    db.commit()
    logger.info(
        "anomalies: %s found, %s insufficient (threshold=%.2f, window=%s, min_obs=%s)",
        len(anomalies),
        insufficient,
        effective_threshold,
        effective_window,
        effective_min,
    )
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
