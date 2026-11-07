from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from freezegun import freeze_time

from cru_ingestion import ledger
from cru_ingestion.config import Settings


def test_pending_days_skips_done_days() -> None:
    pending = ledger.pending_days(date(2026, 8, 1), date(2026, 8, 3), {date(2026, 8, 2)})

    assert pending == ["2026-08-01", "2026-08-03"]


@pytest.fixture
def ledger_settings(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Return settings whose pending days are 1, 3 and 4 August."""
    # 2 August is already done.
    monkeypatch.setattr(ledger, "_successful_days", lambda spark, table: {date(2026, 8, 2)})
    # 3:00 on 5 August in Warsaw, so 4 August is the last finished day.
    with freeze_time(datetime(2026, 8, 5, 1, 0, tzinfo=UTC)):
        # Downloads start on 1 August.
        yield replace(settings, initial_date=date(2026, 8, 1))


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        pytest.param(datetime(2026, 10, 19, 21, 30, tzinfo=UTC), ["2026-10-18"], id="23:30_on_19_october_in_warsaw"),
        pytest.param(datetime(2026, 10, 19, 22, 30, tzinfo=UTC), ["2026-10-18", "2026-10-19"], id="00:30_on_20_october_in_warsaw"),
    ],
)
def test_compute_pending_days_uses_warsaw_time(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, now: datetime, expected: list[str]
) -> None:
    monkeypatch.setattr(ledger, "_successful_days", lambda spark, table: set())
    settings = replace(settings, initial_date=date(2026, 10, 18))

    with freeze_time(now):
        pending = ledger.compute_pending_days(None, settings, backfill=False, date_from=None, date_to=None)

    assert pending == expected


@pytest.mark.parametrize(
    ("backfill", "date_from", "date_to", "expected"),
    [
        pytest.param(False, None, None, ["2026-08-01", "2026-08-03", "2026-08-04"], id="scheduled"),
        # Dates without backfill are ignored, so a scheduled run keeps its full range.
        pytest.param(False, date(2026, 8, 3), date(2026, 8, 3), ["2026-08-01", "2026-08-03", "2026-08-04"], id="scheduled_ignores_dates"),
        pytest.param(True, date(2026, 8, 3), date(2026, 8, 3), ["2026-08-03"], id="backfill_both_dates"),
        pytest.param(True, date(2026, 8, 3), None, ["2026-08-03", "2026-08-04"], id="backfill_date_from_only"),
        pytest.param(True, None, date(2026, 8, 3), ["2026-08-01", "2026-08-03"], id="backfill_date_to_only"),
        pytest.param(True, None, None, ["2026-08-01", "2026-08-03", "2026-08-04"], id="backfill_no_dates"),
    ],
)
def test_compute_pending_days_applies_dates_only_with_backfill(
    ledger_settings: Settings,
    backfill: bool,
    date_from: date | None,
    date_to: date | None,
    expected: list[str],
) -> None:
    assert (
        ledger.compute_pending_days(None, ledger_settings, backfill=backfill, date_from=date_from, date_to=date_to)
        == expected
    )


@pytest.mark.parametrize(
    ("date_from", "date_to", "message"),
    [
        pytest.param(date(2026, 8, 1), date(2026, 8, 5), "date_to 2026-08-05 is after 2026-08-04, the last finished day in Warsaw time", id="date_to_after_yesterday"),
        pytest.param(date(2026, 8, 5), None, "date_from 2026-08-05 is after 2026-08-04, the last finished day in Warsaw time", id="date_from_after_yesterday"),
        pytest.param(date(2026, 8, 3), date(2026, 8, 1), "date_from 2026-08-03 is after date_to 2026-08-01", id="date_from_after_date_to"),
    ],
)
def test_compute_pending_days_rejects_invalid_dates(
    ledger_settings: Settings, date_from: date | None, date_to: date | None, message: str
) -> None:
    with pytest.raises(ValueError) as error:
        ledger.compute_pending_days(None, ledger_settings, backfill=True, date_from=date_from, date_to=date_to)

    assert str(error.value) == message
