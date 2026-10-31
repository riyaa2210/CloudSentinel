from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnomalyEvent(Base):
    """A persisted, de-duplicated anomaly alert.

    One row per billing record (``billing_record_id`` is unique), so re-running
    detection never creates a duplicate alert for the same unresolved incident.
    The remediation workflow (Phase 3) transitions ``status``; here it starts as
    ``open``.
    """

    __tablename__ = "anomaly_events"
    __table_args__ = (
        Index("ix_anomaly_events_service", "service"),
        Index("ix_anomaly_events_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    billing_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_records.id"), unique=True, nullable=False
    )
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_cost: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_mean: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_std: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    detection_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
