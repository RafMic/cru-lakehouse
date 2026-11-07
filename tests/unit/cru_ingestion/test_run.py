import json
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import ANY, MagicMock

import pytest
import requests
import responses
from freezegun import freeze_time
from pytest_mock import MockerFixture

from cru_ingestion import landing, ledger, run
from cru_ingestion.client import VOIVODESHIPS
from cru_ingestion.config import Settings
from cru_ingestion.run import IncompleteDayError, process_day

from .helpers import BASE_URL, add_search_response


@pytest.fixture
def record_attempt(mocker: MockerFixture) -> MagicMock:
    """Replace ledger.record_attempt with a mock, since writing a Delta table needs Delta Lake, which the unit tests don't install."""
    return mocker.patch.object(ledger, "record_attempt", autospec=True)


@pytest.fixture
def job_environment(job_environment: None, mocker: MockerFixture) -> None:
    """Extend job_environment with a mocked run.SparkSession, so the tests can verify the session each entry point passes on."""
    mocker.patch.object(run, "SparkSession")


@responses.activate
@freeze_time(datetime(2026, 8, 9, 1, 0, 12, tzinfo=UTC))
def test_process_day_lands_search_pages_and_details(settings: Settings, record_attempt: MagicMock) -> None:
    day_filter = {"dataModyfikacjiOd": "2026.08.08", "dataModyfikacjiDo": "2026.08.08"}
    add_search_response(2, [{"idUmowy": "a"}], limit=1, body={"inne": day_filter})
    add_search_response(2, [{"idUmowy": "a"}, {"idUmowy": "b"}], limit=100, body={"inne": day_filter})

    for agreement_id in ("a", "b"):
        responses.add(responses.GET, f"{BASE_URL}/agreement/{agreement_id}", json={"idUmowy": agreement_id})

    process_day(spark=None, settings=settings, day=date(2026, 8, 8))

    volume = Path(settings.landing_volume_path)
    search_pages = list((volume / "agreements_search").rglob("*.json"))
    assert len(search_pages) == 1
    assert search_pages[0].parent.name == "attempt=2026-08-09T010012Z"
    assert json.loads(search_pages[0].read_text(encoding="utf-8")) == {
        "totalMatchingElements": 2,
        "content": [{"idUmowy": "a"}, {"idUmowy": "b"}],
    }
    details = (volume / "agreements_detail").rglob("*.json")
    assert sorted(path.stem for path in details) == ["a", "b"]
    # One count request and one page for each of the two searches, then one request per agreement.
    assert len(responses.calls) == 6
    record_attempt.assert_called_once_with(
        None,
        settings.ledger_table,
        date(2026, 8, 8),
        datetime(2026, 8, 9, 1, 0, 12, tzinfo=UTC),
        "success",
    )


@responses.activate
@pytest.mark.usefixtures("record_attempt")
def test_process_day_second_search_finds_agreement_skipped_during_paging(settings: Settings) -> None:
    # The first search reads a and b. Then b is edited and leaves the day, so c moves to offset 1 and offset 2 is empty.
    add_search_response(3, [{"idUmowy": "a"}], limit=1)
    add_search_response(3, [{"idUmowy": "a"}, {"idUmowy": "b"}], limit=2)
    add_search_response(2, [], limit=2, offset=2)
    # The second search sees the changed list.
    add_search_response(2, [{"idUmowy": "a"}], limit=1)
    add_search_response(2, [{"idUmowy": "a"}, {"idUmowy": "c"}], limit=2)

    for agreement_id in ("a", "b", "c"):
        responses.add(responses.GET, f"{BASE_URL}/agreement/{agreement_id}", json={"idUmowy": agreement_id})

    process_day(spark=None, settings=replace(settings, search_page_size=2), day=date(2026, 8, 8))

    details = (Path(settings.landing_volume_path) / "agreements_detail").rglob("*.json")
    assert sorted(path.stem for path in details) == ["a", "b", "c"]


@responses.activate
@pytest.mark.usefixtures("record_attempt")
def test_process_day_skips_details_already_written(settings: Settings) -> None:
    # Agreement a's details are already saved from an earlier failed attempt for 8 August.
    landing.write_json(landing.agreement_detail_path(settings, date(2026, 8, 8), "a"), {"idUmowy": "a"})
    add_search_response(2, [{"idUmowy": "a"}], limit=1)
    add_search_response(2, [{"idUmowy": "a"}, {"idUmowy": "b"}], limit=100)
    for agreement_id in ("a", "b"):
        responses.add(responses.GET, f"{BASE_URL}/agreement/{agreement_id}", json={"idUmowy": agreement_id})

    process_day(spark=None, settings=settings, day=date(2026, 8, 8))

    responses.assert_call_count(f"{BASE_URL}/agreement/a", 0)
    responses.assert_call_count(f"{BASE_URL}/agreement/b", 1)


@responses.activate
@pytest.mark.usefixtures("record_attempt")
def test_process_day_lands_details_under_processed_day(settings: Settings) -> None:
    add_search_response(1, [{"idUmowy": "a"}], limit=1)
    add_search_response(1, [{"idUmowy": "a"}], limit=100)
    # Agreement a was edited again on 9 August before its details were fetched, and they still go under 8 August.
    responses.add(responses.GET, f"{BASE_URL}/agreement/a", json={"idUmowy": "a", "dataModyfikacji": "09.08.2026"})

    process_day(spark=None, settings=settings, day=date(2026, 8, 8))

    detail_file = Path(settings.landing_volume_path, "agreements_detail/year=2026/month=08/day=08/a.json")
    assert json.loads(detail_file.read_text(encoding="utf-8")) == {"idUmowy": "a", "dataModyfikacji": "09.08.2026"}


@responses.activate
def test_process_day_records_failed_details(settings: Settings, record_attempt: MagicMock) -> None:
    add_search_response(1, [{"idUmowy": "bad"}], limit=1)
    add_search_response(1, [{"idUmowy": "bad"}], limit=100)
    responses.add(responses.GET, f"{BASE_URL}/agreement/bad", status=404)

    with pytest.raises(IncompleteDayError) as error:
        process_day(spark=None, settings=settings, day=date(2026, 8, 8))

    message = "2026-08-08: 1 detail fetch(es) failed"
    assert str(error.value) == message
    record_attempt.assert_called_once_with(
        None, settings.ledger_table, date(2026, 8, 8), ANY, "failed", error=message
    )
    assert not (Path(settings.landing_volume_path) / "agreements_detail").exists()


@responses.activate
def test_process_day_records_search_problem(settings: Settings, record_attempt: MagicMock) -> None:
    day_filter = {"dataModyfikacjiOd": "2026.08.08", "dataModyfikacjiDo": "2026.08.08"}
    # Above 10,000 agreements the day is searched per voivodeship.
    add_search_response(10001, [{"idUmowy": "a"}], limit=1, body={"inne": day_filter})
    # Only Dolnośląskie finds an agreement, so 10,000 are missing.
    dolnoslaskie = {"inne": day_filter, "jsfp": {"wojewodztwo": "Dolnośląskie"}}
    add_search_response(1, [{"idUmowy": "a"}], limit=1, body=dolnoslaskie)
    add_search_response(1, [{"idUmowy": "a"}], limit=100, body=dolnoslaskie)
    for voivodeship in VOIVODESHIPS[1:]:
        add_search_response(0, [], limit=1, body={"inne": day_filter, "jsfp": {"wojewodztwo": voivodeship}})
    responses.add(responses.GET, f"{BASE_URL}/agreement/a", json={"idUmowy": "a"})

    with pytest.raises(IncompleteDayError) as error:
        process_day(spark=None, settings=settings, day=date(2026, 8, 8))

    # The day is searched twice, and the problem is counted once.
    message = "2026-08-08: 1 search problem(s): the voivodeship searches found 1 of 10001 agreements, 10000 not fetched"
    assert str(error.value) == message
    record_attempt.assert_called_once_with(
        None, settings.ledger_table, date(2026, 8, 8), ANY, "failed", error=message
    )
    # A failed day still keeps the details it downloaded.
    assert Path(settings.landing_volume_path, "agreements_detail/year=2026/month=08/day=08/a.json").exists()


@responses.activate
def test_process_day_records_unexpected_error(settings: Settings, record_attempt: MagicMock) -> None:
    responses.add(responses.POST, f"{BASE_URL}/agreements/search", status=400)

    with pytest.raises(requests.exceptions.HTTPError) as error:
        process_day(spark=None, settings=settings, day=date(2026, 8, 8))

    record_attempt.assert_called_once_with(
        None, settings.ledger_table, date(2026, 8, 8), ANY, "failed", error=repr(error.value)
    )


@pytest.mark.parametrize(
    ("argv", "backfill", "date_from", "date_to"),
    [
        # ingestion_job.yml defaults date_from and date_to to "", so a scheduled run passes them empty.
        pytest.param(["compute_pending_days", "--backfill=0", "--date_from=", "--date_to="], False, None, None, id="scheduled"),
        pytest.param(["compute_pending_days", "--backfill=1", "--date_from=2026-08-01", "--date_to=2026-08-02"], True, date(2026, 8, 1), date(2026, 8, 2), id="backfill"),
    ],
)
@pytest.mark.usefixtures("job_environment")
def test_compute_pending_days_entrypoint_passes_arguments_and_sets_task_value(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    argv: list[str],
    backfill: bool,
    date_from: date | None,
    date_to: date | None,
) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    compute_pending_days_mock = mocker.patch.object(
        ledger, "compute_pending_days", autospec=True, return_value=["2026-08-01", "2026-08-02"]
    )
    runtime = MagicMock()
    monkeypatch.setitem(sys.modules, "databricks.sdk.runtime", runtime)

    run.compute_pending_days_entrypoint()

    settings = Settings(
        catalog="cru_test",
        landing_volume_path="/Volumes/cru_test/landing/raw_agreements",
        ledger_table="cru_test.landing._ingestion_ledger",
    )
    compute_pending_days_mock.assert_called_once_with(
        run.SparkSession.builder.getOrCreate.return_value,
        settings,
        backfill=backfill,
        date_from=date_from,
        date_to=date_to,
    )
    # The for_each task in ingestion_job.yml reads this task value key.
    runtime.dbutils.jobs.taskValues.set.assert_called_once_with(
        key="pending_days", value=["2026-08-01", "2026-08-02"]
    )


@pytest.mark.usefixtures("job_environment")
def test_compute_pending_days_entrypoint_rejects_unknown_backfill_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["compute_pending_days", "--backfill=true"])

    with pytest.raises(SystemExit) as error:
        run.compute_pending_days_entrypoint()

    assert error.value.code == 2
    assert "argument --backfill: invalid choice: 'true'" in capsys.readouterr().err


@pytest.mark.usefixtures("job_environment")
def test_process_day_entrypoint_passes_day(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.setattr(sys, "argv", ["process_day", "--day=2026-08-08"])
    process_day_mock = mocker.patch.object(run, "process_day", autospec=True)

    run.process_day_entrypoint()

    settings = Settings(
        catalog="cru_test",
        landing_volume_path="/Volumes/cru_test/landing/raw_agreements",
        ledger_table="cru_test.landing._ingestion_ledger",
    )
    process_day_mock.assert_called_once_with(
        run.SparkSession.builder.getOrCreate.return_value, settings, date(2026, 8, 8)
    )
