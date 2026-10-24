import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sentinel:sentinel@db:5432/sentinel",
)

# Anomaly detection thresholds
ANOMALY_Z_SCORE_THRESHOLD = 2.0  # Flag costs > 2 std devs from mean
