"""Rolling-baseline cost anomaly detection.

The previous whole-population z-score had a flaw: a spike sat inside the data
used to compute mean/std, so it inflated the standard deviation and partly
masked itself. This module instead judges each candidate against a *trailing
window* of prior observations for the same service, excluding the candidate
itself:

    baseline  = the previous ``window`` observations of the same service
    mean, std = statistics over that baseline (candidate excluded)
    z         = (candidate.cost - mean) / std
    flag      = |z| > threshold   (and enough history exists)

Edges handled explicitly:
  * fewer than ``min_observations`` prior points  -> "insufficient_data"
  * zero variance in the baseline (std == 0)       -> "insufficient_data"
    (no division by zero, and a constant history cannot define "normal")

Worked example (window large enough to use all prior points):
    EC2 prior hourly costs: 1.8, 1.9, 2.0, 1.7, 2.1, 1.8  (mean=1.883, std=0.147)
    candidate:              15.5
    z = (15.5 - 1.883) / 0.147 = ~92.6   -> flagged, severity "high"
The candidate never contaminated its own baseline.
"""

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("sentinel.detection")


@dataclass
class AnomalyFinding:
    record_id: int
    service: str
    cost: float
    timestamp: datetime
    region: str
    account_id: str
    baseline_mean: float
    baseline_std: float
    z_score: float
    threshold: float
    severity: str
    detection_reason: str


def _severity(abs_z: float, threshold: float) -> str:
    """Map |z| to a coarse severity band, anchored on the threshold."""
    if abs_z > max(threshold * 2.5, 5.0):
        return "high"
    if abs_z > max(threshold * 1.5, 3.0):
        return "medium"
    return "low"


def _reason(service: str, cost: float, z: float, mean: float, std: float, n: int) -> str:
    direction = "above" if z > 0 else "below"
    return (
        f"{service} cost ${cost:.2f} is {abs(z):.1f} std devs {direction} its "
        f"{n}-point trailing baseline (mean ${mean:.2f}, std ${std:.2f})."
    )


def detect_anomalies(
    records,
    *,
    window: int,
    min_observations: int,
    threshold: float,
):
    """Return ``(findings, insufficient_count)`` for the given records.

    ``records`` is any iterable of objects with the attributes used below
    (a SQLAlchemy BillingRecord has them all). Findings are sorted by |z|
    descending. ``insufficient_count`` is how many candidates were skipped due
    to too little or non-varying history.
    """
    by_service: dict[str, list] = defaultdict(list)
    for r in records:
        by_service[r.service].append(r)

    findings: list[AnomalyFinding] = []
    insufficient = 0

    for service, recs in by_service.items():
        recs.sort(key=lambda r: r.timestamp)
        costs = [r.cost for r in recs]

        for i, r in enumerate(recs):
            # Trailing window: previous `window` observations, candidate excluded.
            start = max(0, i - window)
            baseline = costs[start:i]

            if len(baseline) < min_observations:
                insufficient += 1
                continue

            mean = statistics.mean(baseline)
            try:
                std = statistics.stdev(baseline)
            except statistics.StatisticsError:
                # stdev needs >= 2 points; guaranteed by min_observations but
                # guard anyway so the engine never crashes on edge inputs.
                insufficient += 1
                continue

            if std == 0:
                # Constant history carries no notion of "unusual"; skip cleanly.
                insufficient += 1
                continue

            z = (r.cost - mean) / std
            if abs(z) > threshold:
                findings.append(
                    AnomalyFinding(
                        record_id=r.id,
                        service=service,
                        cost=r.cost,
                        timestamp=r.timestamp,
                        region=r.region,
                        account_id=r.account_id,
                        baseline_mean=mean,
                        baseline_std=std,
                        z_score=z,
                        threshold=threshold,
                        severity=_severity(abs(z), threshold),
                        detection_reason=_reason(
                            service, r.cost, z, mean, std, len(baseline)
                        ),
                    )
                )

    findings.sort(key=lambda f: abs(f.z_score), reverse=True)
    logger.info(
        "detection: %s anomalies, %s insufficient (threshold=%.2f, window=%s, "
        "min_obs=%s, services=%s)",
        len(findings),
        insufficient,
        threshold,
        window,
        min_observations,
        len(by_service),
    )
    return findings, insufficient
