"""Synchronous client for the CRU search and detail endpoints.

Sends one request at a time.
The job's for_each task fetches several days in parallel, each with its own client.
"""

import itertools
import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Self

import requests
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import Settings

logger = logging.getLogger(__name__)

# Date format of the modification-date filter in _search.
_SEARCH_DATE_FORMAT = "%Y.%m.%d"

# Ascending modification date as the search sortKey.
_SEARCH_SORT_KEY = "modificationDateAsc"

# API cap on results per search query.
MAX_RESULTS_PER_QUERY = 10000

# Splits days above the cap by the institution's voivodeship.
VOIVODESHIPS = (
    "Dolnośląskie",
    "Kujawsko-Pomorskie",
    "Lubelskie",
    "Lubuskie",
    "Łódzkie",
    "Małopolskie",
    "Mazowieckie",
    "Opolskie",
    "Podkarpackie",
    "Podlaskie",
    "Pomorskie",
    "Śląskie",
    "Świętokrzyskie",
    "Warmińsko-Mazurskie",
    "Wielkopolskie",
    "Zachodniopomorskie",
)

# Retried up to retry_max_attempts, any other HTTP error fails immediately.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


@dataclass(frozen=True)
class SearchPage:
    """One search response page, stored unmodified."""

    day: date
    page_number: int
    payload: dict
    voivodeship: str | None


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


def _retry_after_seconds(retry_state: RetryCallState) -> float | None:
    """Return the failed response's Retry-After header in seconds, or None if it's missing or not a number."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if not isinstance(exc, requests.HTTPError) or exc.response is None:
        return None
    try:
        return max(float(exc.response.headers["Retry-After"]), 0.0)
    except (KeyError, ValueError):
        return None


class CruClient:
    """Searches and downloads CRU agreements, spacing out requests and retrying temporary failures."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = requests.Session()
        self._session.headers["User-Agent"] = settings.user_agent
        self._last_request_at = float("-inf")
        # Search problems that make process_day record the day as failed.
        self.search_problems: list[str] = []
        self._retryer = Retrying(
            retry=retry_if_exception(_is_retryable),
            wait=self._retry_delay,
            stop=stop_after_attempt(settings.retry_max_attempts),
            reraise=True,
        )
        self._backoff = wait_exponential_jitter(
            multiplier=settings.retry_backoff_initial_seconds,
            max=settings.retry_backoff_max_seconds,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._session.close()

    def search_day(self, day: date) -> Iterator[SearchPage]:
        """Yield every page of search results for agreements changed on day.

        Searches each voivodeship separately when the day exceeds MAX_RESULTS_PER_QUERY.
        """
        for voivodeship in self._iter_voivodeship_filters(day):
            yield from self._iter_pages(day, voivodeship)

    def _iter_voivodeship_filters(self, day: date) -> Iterator[str | None]:
        """Yield None to search the whole day at once, or each voivodeship when the day exceeds MAX_RESULTS_PER_QUERY."""
        probe = self._search(day, offset=0, limit=1)
        total = probe.get("totalMatchingElements", 0)
        if total <= MAX_RESULTS_PER_QUERY:
            yield None
        else:
            yield from self._iter_voivodeships(day, total)

    def _iter_voivodeships(self, day: date, day_total: int) -> Iterator[str]:
        """Yield each voivodeship with agreements changed on day.

        Records a search problem if their counts fall short of day_total.
        """
        covered = 0
        for voivodeship in VOIVODESHIPS:
            probe = self._search(day, offset=0, limit=1, voivodeship=voivodeship)
            count = probe.get("totalMatchingElements", 0)
            if count == 0:
                continue
            covered += count
            if count > MAX_RESULTS_PER_QUERY:
                logger.warning(
                    "%s, %s: %d agreements, fetching only the first %d",
                    day,
                    voivodeship,
                    count,
                    MAX_RESULTS_PER_QUERY,
                )
            yield voivodeship
        if covered < day_total:
            message = f"the voivodeship searches found {covered} of {day_total} agreements, {day_total - covered} not fetched"
            logger.warning("%s: %s", day, message)
            # process_day searches each day twice, so the same problem can come up again.
            if message not in self.search_problems:
                self.search_problems.append(message)

    def _iter_pages(self, day: date, voivodeship: str | None) -> Iterator[SearchPage]:
        """Yield the pages of one search until the last result the API returns."""
        offset = 0
        for page_number in itertools.count():
            payload = self._search(
                day, offset=offset, limit=self._settings.search_page_size, voivodeship=voivodeship
            )
            yield SearchPage(day, page_number, payload, voivodeship)
            content = payload.get("content", [])
            offset += len(content)
            reachable = min(payload.get("totalMatchingElements", 0), MAX_RESULTS_PER_QUERY)
            if not content or offset >= reachable:
                return

    def _search(self, day: date, *, offset: int, limit: int, voivodeship: str | None = None) -> dict:
        """Return one raw page of the agreements modified on day, optionally limited to one voivodeship."""
        search_date = day.strftime(_SEARCH_DATE_FORMAT)
        body: dict = {"inne": {"dataModyfikacjiOd": search_date, "dataModyfikacjiDo": search_date}}
        if voivodeship is not None:
            body["jsfp"] = {"wojewodztwo": voivodeship}
        response = self._request(
            "POST",
            f"{self._settings.cru_base_url}/agreements/search",
            params={"offset": offset, "limit": limit, "sortKey": _SEARCH_SORT_KEY},
            json=body,
        )
        return response.json()

    def fetch_details(self, agreement_ids: Iterable[str]) -> Iterator[tuple[str, dict | None]]:
        """Yield (id, details) for each distinct ID in order, with None as details when the fetch fails."""
        for agreement_id in dict.fromkeys(agreement_ids):
            try:
                detail = self._fetch_detail(agreement_id)
            except requests.RequestException:
                logger.exception("Failed to fetch agreement %s", agreement_id)
                detail = None
            yield agreement_id, detail

    def _fetch_detail(self, agreement_id: str) -> dict:
        """Return one agreement's details."""
        response = self._request(
            "GET", f"{self._settings.cru_base_url}/agreement/{agreement_id}"
        )
        return response.json()

    def _request(
        self, method: str, url: str, *, params: dict | None = None, json: dict | None = None
    ) -> requests.Response:
        """Return the first successful response, or raise the error that ended the retries."""
        return self._retryer(self._send, method, url, params=params, json=json)

    def _send(
        self, method: str, url: str, *, params: dict | None = None, json: dict | None = None
    ) -> requests.Response:
        """Make a single attempt, returning its response or raising its error."""
        self._throttle()
        response = self._session.request(
            method, url, params=params, json=json, timeout=self._settings.request_timeout_seconds
        )
        response.raise_for_status()
        return response

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self._settings.min_request_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _retry_delay(self, retry_state: RetryCallState) -> float:
        """Return how long to wait before retrying: the server's Retry-After if given, otherwise exponential backoff, up to retry_backoff_max_seconds."""
        retry_after = _retry_after_seconds(retry_state)
        if retry_after is not None:
            return min(retry_after, self._settings.retry_backoff_max_seconds)
        return self._backoff(retry_state)
