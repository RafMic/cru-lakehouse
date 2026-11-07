from pathlib import Path

import pytest

from cru_ingestion.config import Settings

from .helpers import BASE_URL


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Return settings with a temporary landing folder and a fake API URL, and without waits between requests or retries."""
    return Settings(
        catalog="cru_test",
        landing_volume_path=str(tmp_path / "landing"),
        ledger_table="cru_test.landing._ingestion_ledger",
        cru_base_url=BASE_URL,
        min_request_interval_seconds=0.0,
        retry_backoff_initial_seconds=0.0,
        retry_backoff_max_seconds=0.0,
        retry_max_attempts=3,
    )


@pytest.fixture
def job_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the environment variables that ingestion_job.yml gives the job."""
    monkeypatch.setenv("CATALOG", "cru_test")
    monkeypatch.setenv("LANDING_VOLUME_PATH", "/Volumes/cru_test/landing/raw_agreements")
    monkeypatch.setenv("LEDGER_TABLE", "cru_test.landing._ingestion_ledger")
