from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
import requests
import responses
from freezegun import freeze_time
from pytest_mock import MockerFixture

from cru_ingestion.client import (
    MAX_RESULTS_PER_QUERY,
    VOIVODESHIPS,
    CruClient,
    SearchPage,
)
from cru_ingestion.config import Settings

from .helpers import BASE_URL, add_search_response, search_body


@responses.activate
def test_search_day_single_page_under_cap(settings: Settings) -> None:
    day = date(2026, 8, 8)
    add_search_response(2, [{"idUmowy": "a"}], limit=1)
    add_search_response(2, [{"idUmowy": "a"}, {"idUmowy": "b"}], limit=100)

    with CruClient(settings) as client:
        pages = list(client.search_day(day))

    assert len(pages) == 1
    assert pages[0] == SearchPage(
        day=day,
        page_number=0,
        payload=search_body(2, [{"idUmowy": "a"}, {"idUmowy": "b"}]),
        voivodeship=None,
    )


@responses.activate
def test_search_day_paginates(settings: Settings) -> None:
    day = date(2026, 8, 8)
    add_search_response(150, [{"idUmowy": "0"}], limit=1)
    page0_content = [{"idUmowy": str(i)} for i in range(100)]
    page1_content = [{"idUmowy": str(i)} for i in range(100, 150)]
    add_search_response(150, page0_content, limit=100)
    add_search_response(150, page1_content, limit=100, offset=100)

    with CruClient(settings) as client:
        pages = list(client.search_day(day))

    assert [p.page_number for p in pages] == [0, 1]
    assert len(pages[0].payload["content"]) == 100
    assert len(pages[1].payload["content"]) == 50


@responses.activate
def test_search_day_voivodeship_fallback_over_cap(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    day = date(2026, 8, 6)
    day_filter = {"dataModyfikacjiOd": "2026.08.06", "dataModyfikacjiDo": "2026.08.06"}
    page_size = settings.search_page_size
    add_search_response(6000 + MAX_RESULTS_PER_QUERY + 1, [{"idUmowy": "0"}], limit=1, body={"inne": day_filter})

    def probe_response(voivodeship: str, count: int, content: list[dict]) -> None:
        add_search_response(
            count, content, limit=1, body={"inne": day_filter, "jsfp": {"wojewodztwo": voivodeship}}
        )

    # The first two voivodeships cover the day's total between them, and the other 14 have no agreements.
    probe_response(VOIVODESHIPS[0], 6000, [{"idUmowy": "0"}])
    # The second voivodeship has more agreements than one search can return, so the client logs a warning.
    probe_response(VOIVODESHIPS[1], MAX_RESULTS_PER_QUERY + 1, [{"idUmowy": "6000"}])
    for voivodeship in VOIVODESHIPS[2:]:
        probe_response(voivodeship, 0, [])

    def page_responses(voivodeship: str, total: int, first_id: int, offsets: range) -> None:
        for offset in offsets:
            ids = range(first_id + offset, first_id + offset + page_size)
            add_search_response(
                total,
                [{"idUmowy": str(i)} for i in ids],
                limit=page_size,
                offset=offset,
                body={"inne": day_filter, "jsfp": {"wojewodztwo": voivodeship}},
            )

    # Each page reply matches only its voivodeship's filter, so a search without the filter fails the test.
    page_responses(VOIVODESHIPS[0], 6000, 0, range(0, 6000, page_size))
    page_responses(VOIVODESHIPS[1], MAX_RESULTS_PER_QUERY + 1, 6000, range(0, MAX_RESULTS_PER_QUERY, page_size))

    with CruClient(settings) as client:
        pages = list(client.search_day(day))

    assert [(p.voivodeship, len(p.payload["content"])) for p in pages] == (
        [(VOIVODESHIPS[0], 100)] * 60 + [(VOIVODESHIPS[1], 100)] * 100
    )
    # One count request for the day, one per voivodeship, and 160 pages.
    assert len(responses.calls) == 177
    # A voivodeship still over the cap is a logged, accepted limitation, not a failed day.
    assert client.search_problems == []
    assert "fetching only the first 10000" in caplog.text


@responses.activate
def test_search_day_flags_records_missing_from_voivodeship_split(settings: Settings) -> None:
    day = date(2026, 8, 6)
    day_filter = {"dataModyfikacjiOd": "2026.08.06", "dataModyfikacjiDo": "2026.08.06"}
    page_size = settings.search_page_size
    first_voivodeship = {"inne": day_filter, "jsfp": {"wojewodztwo": VOIVODESHIPS[0]}}
    add_search_response(MAX_RESULTS_PER_QUERY + 1, [{"idUmowy": "0"}], limit=1, body={"inne": day_filter})
    add_search_response(6000, [{"idUmowy": "0"}], limit=1, body=first_voivodeship)
    for voivodeship in VOIVODESHIPS[1:]:
        add_search_response(0, [], limit=1, body={"inne": day_filter, "jsfp": {"wojewodztwo": voivodeship}})
    for offset in range(0, 6000, page_size):
        add_search_response(
            6000,
            [{"idUmowy": str(i)} for i in range(offset, offset + page_size)],
            limit=page_size,
            offset=offset,
            body=first_voivodeship,
        )

    with CruClient(settings) as client:
        list(client.search_day(day))
        # process_day searches each day twice, and the missing agreements are reported only once.
        list(client.search_day(day))

    assert client.search_problems == ["the voivodeship searches found 6000 of 10001 agreements, 4001 not fetched"]


@responses.activate
def test_fetch_details_dedupes_and_yields_in_order(settings: Settings) -> None:
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", json={"idUmowy": "1"})
    responses.add(responses.GET, f"{BASE_URL}/agreement/2", json={"idUmowy": "2"})

    with CruClient(settings) as client:
        results = list(client.fetch_details(["1", "2", "1"]))

    assert results == [("1", {"idUmowy": "1"}), ("2", {"idUmowy": "2"})]
    assert len(responses.calls) == 2


@responses.activate
def test_fetch_details_does_not_retry_404(settings: Settings) -> None:
    responses.add(responses.GET, f"{BASE_URL}/agreement/bad", status=404)

    with CruClient(settings) as client:
        results = list(client.fetch_details(["bad"]))

    assert results == [("bad", None)]
    # 404 isn't in _RETRYABLE_STATUS_CODES, so it isn't retried.
    assert len(responses.calls) == 1


@responses.activate
def test_fetch_details_continues_after_a_failure(settings: Settings) -> None:
    responses.add(responses.GET, f"{BASE_URL}/agreement/bad", status=404)
    responses.add(responses.GET, f"{BASE_URL}/agreement/good", json={"idUmowy": "good"})

    with CruClient(settings) as client:
        results = list(client.fetch_details(["bad", "good"]))

    assert results == [("bad", None), ("good", {"idUmowy": "good"})]


@responses.activate
def test_fetch_details_retries_server_errors(settings: Settings) -> None:
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", status=503)
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", status=503)
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", json={"idUmowy": "1"})

    with CruClient(settings) as client:
        results = list(client.fetch_details(["1"]))

    assert results == [("1", {"idUmowy": "1"})]
    assert len(responses.calls) == 3


@responses.activate
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(requests.exceptions.ConnectionError("Connection aborted"), id="connection_error"),
        pytest.param(requests.exceptions.ReadTimeout("Read timed out"), id="timeout"),
    ],
)
def test_fetch_details_retries_network_errors(settings: Settings, error: requests.RequestException) -> None:
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", body=error)
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", json={"idUmowy": "1"})

    with CruClient(settings) as client:
        results = list(client.fetch_details(["1"]))

    assert results == [("1", {"idUmowy": "1"})]
    assert len(responses.calls) == 2


@responses.activate
@pytest.mark.parametrize(
    ("retry_after", "expected_wait"),
    [pytest.param("7", 7.0, id="below_cap"), pytest.param("3600", 30.0, id="above_cap")],
)
def test_fetch_details_honours_retry_after(
    settings: Settings, mocker: MockerFixture, retry_after: str, expected_wait: float
) -> None:
    sleep = mocker.patch("cru_ingestion.client.time.sleep")

    responses.add(responses.GET, f"{BASE_URL}/agreement/1", status=429, headers={"Retry-After": retry_after})
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", json={"idUmowy": "1"})

    with CruClient(replace(settings, retry_backoff_max_seconds=30.0)) as client:
        list(client.fetch_details(["1"]))

    sleep.assert_called_once_with(expected_wait)


@responses.activate
def test_fetch_details_retries_when_retry_after_is_a_date(settings: Settings, mocker: MockerFixture) -> None:
    sleep = mocker.patch("cru_ingestion.client.time.sleep")
    # Retry-After can also be a date, which the client doesn't read, so it waits its own backoff and retries.
    responses.add(
        responses.GET,
        f"{BASE_URL}/agreement/1",
        status=429,
        headers={"Retry-After": "Fri, 30 Oct 2026 07:28:00 GMT"},
    )
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", json={"idUmowy": "1"})

    with CruClient(replace(settings, retry_backoff_initial_seconds=2.0, retry_backoff_max_seconds=30.0)) as client:
        results = list(client.fetch_details(["1"]))

    assert results == [("1", {"idUmowy": "1"})]
    assert len(responses.calls) == 2
    # The first backoff is 2 seconds plus a random extra of up to 1 second.
    sleep.assert_called_once()
    assert 2.0 <= sleep.call_args.args[0] <= 3.0


@responses.activate
def test_fetch_details_yields_none_when_retries_run_out(settings: Settings) -> None:
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", status=503)
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", status=503)
    responses.add(responses.GET, f"{BASE_URL}/agreement/1", status=503)

    with CruClient(settings) as client:
        results = list(client.fetch_details(["1"]))

    assert results == [("1", None)]
    assert len(responses.calls) == settings.retry_max_attempts


@responses.activate
def test_fetch_details_spaces_requests(settings: Settings, mocker: MockerFixture) -> None:
    sleep = mocker.patch("cru_ingestion.client.time.sleep")

    responses.add(responses.GET, f"{BASE_URL}/agreement/1", json={"idUmowy": "1"})
    responses.add(responses.GET, f"{BASE_URL}/agreement/2", json={"idUmowy": "2"})

    with (
        freeze_time(datetime(2026, 8, 8, tzinfo=UTC)) as clock,
        CruClient(replace(settings, min_request_interval_seconds=0.2)) as client,
    ):
        details = client.fetch_details(["1", "2"])
        next(details)
        clock.tick(0.05)  # 0.05 seconds pass, so the client must wait the remaining 0.15.
        next(details)

    sleep.assert_called_once_with(pytest.approx(0.15))
