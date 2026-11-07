"""Entry points of the cru-ingestion job.

compute_pending_days publishes the days that have no success row in the ledger.
process_day writes one day's search pages and agreement details as JSON files, then records the outcome in the ledger.
"""

import argparse
import logging
from datetime import UTC, date, datetime

from pyspark.sql import SparkSession

from . import landing, ledger
from .client import CruClient, SearchPage
from .config import Settings

logger = logging.getLogger(__name__)


class IncompleteDayError(Exception):
    """Raised when a day ends with failed detail fetches or search problems, so its for_each iteration fails and is retried."""

    def __init__(self, day: date, failed_detail_count: int, search_problems: list[str]) -> None:
        parts = []
        if failed_detail_count:
            parts.append(f"{failed_detail_count} detail fetch(es) failed")
        if search_problems:
            parts.append(
                f"{len(search_problems)} search problem(s): {'; '.join(search_problems)}"
            )
        super().__init__(f"{day}: {'; '.join(parts)}")


def process_day(spark: SparkSession, settings: Settings, day: date) -> None:
    """Search one day, write its search pages and missing agreement details as JSON files, and record the outcome in the ledger.

    Raises IncompleteDayError if a detail fetch fails or a search problem comes up, and re-raises any other error, each after recording the day as failed.
    """
    started_at = datetime.now(tz=UTC)
    # Names this attempt's search page folder, e.g. 2026-10-22T030012Z.
    attempt = started_at.strftime("%Y-%m-%dT%H%M%SZ")
    try:
        with CruClient(settings) as client:
            agreement_ids = _search_and_land(client, settings, day, attempt)
            missing_ids = landing.filter_missing_details(settings, day, agreement_ids)
            if len(missing_ids) < len(agreement_ids):
                logger.info(
                    "%s: %d of %d agreements already landed, fetching %d",
                    day,
                    len(agreement_ids) - len(missing_ids),
                    len(agreement_ids),
                    len(missing_ids),
                )
            failed_detail_count = _fetch_and_land_details(client, settings, day, missing_ids)
            search_problems = client.search_problems
    except Exception as exc:
        # repr includes the error type, e.g. HTTPError('400 Client Error: ...').
        ledger.record_attempt(spark, settings.ledger_table, day, started_at, ledger.FAILED, error=repr(exc))
        raise

    if failed_detail_count or search_problems:
        error = IncompleteDayError(day, failed_detail_count, search_problems)
        ledger.record_attempt(spark, settings.ledger_table, day, started_at, ledger.FAILED, error=str(error))
        raise error
    ledger.record_attempt(spark, settings.ledger_table, day, started_at, ledger.SUCCESS)


def _search_and_land(client: CruClient, settings: Settings, day: date, attempt: str) -> list[str]:
    """Return the distinct IDs of the agreements changed on day.

    Searches the day twice and writes only the first search's pages, unchanged.
    """
    agreement_ids: list[str] = []
    for page in client.search_day(day):
        path = landing.search_page_path(
            settings, page.day, attempt, page.page_number, page.voivodeship
        )
        landing.write_json(path, page.payload)
        agreement_ids.extend(_agreement_ids(page))
    # An agreement edited during paging drops out of the day's results
    # and shifts the next one back to an offset already read,
    # so the second search catches the skipped agreement.
    for page in client.search_day(day):
        agreement_ids.extend(_agreement_ids(page))
    return list(dict.fromkeys(agreement_ids))


def _agreement_ids(page: SearchPage) -> list[str]:
    return [record["idUmowy"] for record in page.payload.get("content", [])]


def _fetch_and_land_details(client: CruClient, settings: Settings, day: date, agreement_ids: list[str]) -> int:
    """Fetch each agreement's details, write them under day's partition and return how many fetches failed."""
    failed_count = 0
    for agreement_id, detail in client.fetch_details(agreement_ids):
        if detail is None:
            failed_count += 1
            continue
        landing.write_json(
            landing.agreement_detail_path(settings, day, agreement_id), detail
        )
    return failed_count


def _optional_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def compute_pending_days_entrypoint() -> None:
    """Run the compute_pending_days task and publish the pending days as the pending_days task value."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # python_wheel_task passes named_parameters as --key=value command-line arguments.
    parser = argparse.ArgumentParser()
    # Job parameters arrive as strings, so backfill is "0" or "1" rather than a bool.
    parser.add_argument("--backfill", choices=["0", "1"], default="0")
    parser.add_argument("--date_from", type=_optional_date, default=None)
    parser.add_argument("--date_to", type=_optional_date, default=None)
    args, _ = parser.parse_known_args()

    spark = SparkSession.builder.getOrCreate()
    settings = Settings.from_env()
    pending_days = ledger.compute_pending_days(
        spark,
        settings,
        backfill=args.backfill == "1",
        date_from=args.date_from,
        date_to=args.date_to,
    )

    # Outside Databricks this import fails without Databricks credentials, so it isn't at the top of the file where it would break the unit tests.
    from databricks.sdk.runtime import dbutils

    # Passes the days to the process_days task, which reads them by the name pending_days.
    dbutils.jobs.taskValues.set(key="pending_days", value=pending_days)


def process_day_entrypoint() -> None:
    """Run one process_day iteration of the for_each task."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    args, _ = parser.parse_known_args()

    spark = SparkSession.builder.getOrCreate()
    settings = Settings.from_env()
    process_day(spark, settings, args.day)
