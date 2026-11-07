from datetime import date
from pathlib import Path

import pytest

from cru_ingestion import landing
from cru_ingestion.config import Settings


@pytest.mark.parametrize(
    ("voivodeship", "file_name"),
    [
        pytest.param(None, "p0000.json", id="whole_day"),
        pytest.param("Mazowieckie", "p0000_Mazowieckie.json", id="voivodeship"),
    ],
)
def test_search_page_path_layout(settings: Settings, voivodeship: str | None, file_name: str) -> None:
    path = landing.search_page_path(settings, date(2026, 10, 21), "2026-10-22T030012Z", 0, voivodeship)

    assert path.relative_to(settings.landing_volume_path).as_posix() == (
        f"agreements_search/year=2026/month=10/day=21/attempt=2026-10-22T030012Z/{file_name}"
    )


def test_filter_missing_details_keeps_only_ids_without_a_file(settings: Settings) -> None:
    day = date(2026, 8, 8)
    landing.write_json(landing.agreement_detail_path(settings, day, "landed"), {"idUmowy": "landed"})

    missing_ids = landing.filter_missing_details(settings, day, ["landed", "missing"])

    assert missing_ids == ["missing"]


def test_filter_missing_details_ignores_files_from_other_days(settings: Settings) -> None:
    # Agreement 1 changed on 7 August, so its details were saved in the 7 August folder.
    landing.write_json(landing.agreement_detail_path(settings, date(2026, 8, 7), "1"), {"idUmowy": "1"})

    # It changed again on 8 August, and the 7 August file must not stop its new details from being downloaded.
    missing_ids = landing.filter_missing_details(settings, date(2026, 8, 8), ["1"])

    assert missing_ids == ["1"]


def test_write_json_leaves_only_the_final_file(tmp_path: Path) -> None:
    path = tmp_path / "a.json"

    landing.write_json(path, {"idUmowy": "a"})

    assert [file.name for file in tmp_path.iterdir()] == ["a.json"]


def test_write_json_keeps_polish_letters_unescaped(tmp_path: Path) -> None:
    path = tmp_path / "a.json"

    landing.write_json(path, {"nazwa": "Łódź"})

    assert path.read_text(encoding="utf-8") == '{"nazwa": "Łódź"}'
