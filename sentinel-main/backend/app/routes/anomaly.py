import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.anomaly import AnomalyEvent
from app.schemas.anomaly import AnomalyEventResponse

logger = logging.getLogger("sentinel.anomaly")
router = APIRouter(prefix="/api/v1/anomaly-events", tags=["anomaly-events"])


@router.get("/", response_model=list[AnomalyEventResponse])
def list_anomaly_events(
    service: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """List persisted, de-duplicated anomaly alerts, optionally filtered by
    service or status. Newest first. This backs the dashboard's alert history."""
    stmt = db.query(AnomalyEvent)
    if service:
        stmt = stmt.filter(AnomalyEvent.service == service)
    if status:
        stmt = stmt.filter(AnomalyEvent.status == status)
    events = stmt.order_by(AnomalyEvent.detected_at.desc()).all()
    logger.info("listed %s anomaly events (service=%s, status=%s)", len(events), service, status)
    return events
