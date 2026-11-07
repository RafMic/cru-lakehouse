import pytest

from cru_ingestion.config import Settings

pytestmark = pytest.mark.usefixtures("job_environment")

_MESSAGES = [
    pytest.param("CATALOG", "CATALOG is required, e.g. cru_dev", id="CATALOG"),
    pytest.param("LANDING_VOLUME_PATH", "LANDING_VOLUME_PATH is required, e.g. /Volumes/cru_dev/landing/raw_agreements", id="LANDING_VOLUME_PATH"),
    pytest.param("LEDGER_TABLE", "LEDGER_TABLE is required, e.g. cru_dev.landing._ingestion_ledger", id="LEDGER_TABLE"),
]


def test_from_env_reads_required_variables() -> None:
    settings = Settings.from_env()

    assert settings.catalog == "cru_test"
    assert settings.landing_volume_path == "/Volumes/cru_test/landing/raw_agreements"
    assert settings.ledger_table == "cru_test.landing._ingestion_ledger"


@pytest.mark.parametrize(("name", "message"), _MESSAGES)
def test_from_env_rejects_missing_variable(monkeypatch: pytest.MonkeyPatch, name: str, message: str) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(RuntimeError) as error:
        Settings.from_env()

    assert str(error.value) == message


@pytest.mark.parametrize(("name", "message"), _MESSAGES)
def test_from_env_rejects_empty_variable(monkeypatch: pytest.MonkeyPatch, name: str, message: str) -> None:
    monkeypatch.setenv(name, "")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env()

    assert str(error.value) == message
