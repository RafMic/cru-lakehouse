"""Records every ingestion attempt per day in a Delta table and determines which days are still pending.

Tracking each day separately lets a failed day be retried on the next run while later days carry on.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DateType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from .config import Settings

# The register's days are Polish local time.
_WARSAW_TZ = ZoneInfo("Europe/Warsaw")

# Values of the status column.
SUCCESS = "success"
FAILED = "failed"

_LEDGER_SCHEMA = StructType(
    [
        StructField("day", DateType(), nullable=False),
        StructField("status", StringType(), nullable=False),
        StructField("attempted_at", TimestampType(), nullable=False),
        StructField("error", StringType(), nullable=True),
    ]
)


def record_attempt(
    spark: SparkSession,
    table: str,
    day: date,
    attempted_at: datetime,
    status: str,
    *,
    error: str | None = None,
) -> None:
    """Append the outcome of one attempt to the ledger table."""
    _ensure_table(spark, table)
    attempt = spark.createDataFrame(
        [(day, status, attempted_at, error)], _LEDGER_SCHEMA
    )
    # Appends never conflict when for_each iterations write at the same time.
    attempt.write.format("delta").mode("append").saveAsTable(table)


def compute_pending_days(
    spark: SparkSession,
    settings: Settings,
    *,
    backfill: bool,
    date_from: date | None,
    date_to: date | None,
) -> list[str]:
    """Return ISO dates from initial_date to yesterday in Warsaw time with no success row.

    date_from and date_to replace the range ends only when backfill is True, so stray dates can't change a scheduled run.
    Raises ValueError if date_to is after yesterday, since an unfinished day would be recorded as successful.
    Raises ValueError if date_from is after yesterday.
    Raises ValueError if date_from is after date_to.
    """
    yesterday = _yesterday(datetime.now(tz=UTC))
    start = date_from if backfill and date_from else settings.initial_date
    end = date_to if backfill and date_to else yesterday
    if end > yesterday:
        raise ValueError(f"date_to {end} is after {yesterday}, the last finished day in Warsaw time")
    if start > yesterday:
        raise ValueError(f"date_from {start} is after {yesterday}, the last finished day in Warsaw time")
    if start > end:
        raise ValueError(f"date_from {start} is after date_to {end}")
    return pending_days(start, end, _successful_days(spark, settings.ledger_table))


def pending_days(start: date, end: date, done: set[date]) -> list[str]:
    """Return the ISO dates from start to end, inclusive, that aren't in done."""
    days = (start + timedelta(days=offset) for offset in range((end - start).days + 1))
    return [day.isoformat() for day in days if day not in done]


def _successful_days(spark: SparkSession, table: str) -> set[date]:
    _ensure_table(spark, table)
    rows = spark.table(table).filter(F.col("status") == SUCCESS).select("day").collect()
    return {row["day"] for row in rows}


def _yesterday(now: datetime) -> date:
    return (now.astimezone(_WARSAW_TZ) - timedelta(days=1)).date()


def _ensure_table(spark: SparkSession, table: str) -> None:
    # Mode "ignore" creates the table only when it doesn't exist yet.
    empty = spark.createDataFrame([], _LEDGER_SCHEMA)
    empty.write.format("delta").mode("ignore").saveAsTable(table)
