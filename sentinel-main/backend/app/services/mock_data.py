import random
from datetime import datetime, timedelta, timezone

from app.models.billing import BillingRecord

# Realistic AWS service cost profiles (mean $/day, std dev)
SERVICE_PROFILES = {
    "EC2": (45.0, 8.0),
    "S3": (8.0, 2.0),
    "RDS": (25.0, 5.0),
    "Lambda": (3.0, 1.0),
    "CloudFront": (12.0, 3.0),
    "DynamoDB": (6.0, 1.5),
}

REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
ACCOUNTS = ["111111111111", "222222222222", "333333333333"]


def generate_mock_records(days: int = 30) -> list[BillingRecord]:
    """Generate realistic AWS billing data with injected anomalies.

    Hourly granularity, Gaussian cost distribution per service,
    with 3-5 random anomaly spikes at 5x-15x normal cost.
    """
    records: list[BillingRecord] = []
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)

    # Pre-pick anomaly injection points: 3-5 random (hour_offset, service) pairs
    total_hours = days * 24
    num_anomalies = random.randint(3, 5)
    anomaly_points: set[tuple[int, str]] = set()
    services = list(SERVICE_PROFILES.keys())
    while len(anomaly_points) < num_anomalies:
        hour = random.randint(0, total_hours - 1)
        svc = random.choice(services)
        anomaly_points.add((hour, svc))

    for hour_offset in range(total_hours):
        ts = start + timedelta(hours=hour_offset)
        region = random.choice(REGIONS)
        account = random.choice(ACCOUNTS)

        for service, (mean_daily, std_daily) in SERVICE_PROFILES.items():
            # Convert daily cost to hourly
            mean_hourly = mean_daily / 24
            std_hourly = std_daily / 24

            cost = max(0.01, random.gauss(mean_hourly, std_hourly))
            is_anomaly = False

            if (hour_offset, service) in anomaly_points:
                multiplier = random.uniform(5.0, 15.0)
                cost *= multiplier
                is_anomaly = True

            records.append(
                BillingRecord(
                    service=service,
                    cost=round(cost, 4),
                    timestamp=ts,
                    region=region,
                    account_id=account,
                    is_anomaly=is_anomaly,
                )
            )

    return records
