"""Application configuration.

Settings are loaded from environment variables (and an optional ``.env`` file)
via pydantic-settings, so configuration stays typed, validated and separate
from application code. Defaults preserve the original behaviour, so the app
runs unchanged without any environment configuration.
"""

import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL connection string. docker compose injects this for you.
    database_url: str = "postgresql://sentinel:sentinel@db:5432/sentinel"

    # Anomaly detection: flag costs whose |z-score| exceeds this many std devs.
    anomaly_z_score_threshold: float = 2.0

    # Rolling-baseline window: number of prior observations (per service) used to
    # compute the mean/std a candidate is compared against. 168 = ~7 days of
    # hourly data. Kept as a count (not a time range) so it is trivial to explain.
    anomaly_detection_window: int = 168

    # Minimum prior observations required before a candidate can be judged.
    # Below this the engine reports "insufficient data" instead of guessing.
    anomaly_min_observations: int = 7

    # Root logging level.
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (env is read once per process)."""
    return Settings()


def configure_logging() -> None:
    """Configure root logging once. Safe to call multiple times."""
    level_name = get_settings().log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
