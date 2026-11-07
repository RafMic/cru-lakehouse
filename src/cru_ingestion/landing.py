"""Writes the raw JSON files to the landing volume, partitioned by the day being ingested."""

import json
from datetime import date
from pathlib import Path

from .config import Settings


def search_page_path(
    settings: Settings, day: date, attempt: str, page_number: int, voivodeship: str | None
) -> Path:
    """Return the path of one search page, e.g. agreements_search/year=2026/month=10/day=21/attempt=2026-10-22T030012Z/p0000_Mazowieckie.json.

    Each attempt gets its own folder, so a day searched again never overwrites or mixes with an earlier search.
    """
    suffix = f"_{voivodeship}" if voivodeship else ""
    return (
        Path(settings.landing_volume_path)
        / "agreements_search"
        / _date_partition(day)
        / f"attempt={attempt}"
        / f"p{page_number:04d}{suffix}.json"
    )


def agreement_detail_path(settings: Settings, day: date, agreement_id: str) -> Path:
    """Return the path of one agreement's details, e.g. agreements_detail/year=2026/month=10/day=21/<agreement_id>.json."""
    return (
        Path(settings.landing_volume_path)
        / "agreements_detail"
        / _date_partition(day)
        / f"{agreement_id}.json"
    )


def _date_partition(day: date) -> Path:
    return (
        Path(f"year={day.year:04d}")
        / f"month={day.month:02d}"
        / f"day={day.day:02d}"
    )


def write_json(path: Path, payload: object) -> None:
    """Write payload as UTF-8 JSON, creating missing folders and keeping Polish letters unescaped.

    The JSON is written to a temporary file first and renamed to path once complete.
    Auto Loader reads each file only once, so a file must be complete before it appears under its final name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Bronze ignores a .tmp file left by a crash.
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def filter_missing_details(settings: Settings, day: date, agreement_ids: list[str]) -> list[str]:
    """Return the IDs that have no detail file for day yet."""
    return [
        agreement_id
        for agreement_id in agreement_ids
        if not agreement_detail_path(settings, day, agreement_id).exists()
    ]
