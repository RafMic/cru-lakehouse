"""Settings for the ingestion job.

CATALOG, LANDING_VOLUME_PATH and LEDGER_TABLE differ per target and come from ingestion_job.yml, everything else has a fixed default.
"""

import os
from dataclasses import dataclass
from datetime import date
from importlib.metadata import version
from typing import Self


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Configuration of the ingestion tasks and the bronze notebook."""

    catalog: str
    landing_volume_path: str
    ledger_table: str
    # First day of data in the register, where compute_pending_days' range starts.
    initial_date: date = date(2026, 7, 1)
    cru_base_url: str = "https://rejestrumow.gov.pl/api-dp/v1"
    user_agent: str = f"cru-lakehouse-ingestion/{version('cru-ingestion')}"
    # The API's maximum page size.
    search_page_size: int = 100
    # Spaces out requests so the API doesn't rate limit the job.
    min_request_interval_seconds: float = 0.2
    request_timeout_seconds: float = 30.0
    retry_max_attempts: int = 5
    retry_backoff_initial_seconds: float = 1.0
    retry_backoff_max_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> Self:
        """Build the settings from the CATALOG, LANDING_VOLUME_PATH and LEDGER_TABLE environment variables.

        Raises RuntimeError if any of them is missing or empty.
        """
        return cls(
            catalog=_required_env("CATALOG", "cru_dev"),
            landing_volume_path=_required_env("LANDING_VOLUME_PATH", "/Volumes/cru_dev/landing/raw_agreements"),
            ledger_table=_required_env("LEDGER_TABLE", "cru_dev.landing._ingestion_ledger"),
        )


def _required_env(name: str, example: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required, e.g. {example}")
    return value
