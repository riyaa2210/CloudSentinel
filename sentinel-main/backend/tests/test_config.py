from app.config import Settings, get_settings


def test_default_settings():
    s = get_settings()
    assert s.anomaly_z_score_threshold == 2.0
    assert s.log_level == "INFO"
    assert s.database_url  # non-empty, set by conftest to sqlite


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("ANOMALY_Z_SCORE_THRESHOLD", "3.5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = Settings()  # fresh instance, not the lru_cached one
    assert s.anomaly_z_score_threshold == 3.5
    assert s.log_level == "DEBUG"
