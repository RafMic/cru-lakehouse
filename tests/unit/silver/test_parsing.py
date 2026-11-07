import json
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import ANY

import pytest
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

from silver.parsing import (
    explode_parties,
    latest_per_party,
    parse_agreements,
    with_party_identity_key,
)

_BRONZE_SCHEMA = StructType(
    [
        StructField("idUmowy", StringType()),
        StructField("dataModyfikacji", StringType()),
        StructField("_file_modification_time", TimestampType()),
        StructField("dataPublikacji", StringType()),
        StructField("finansowanaZeSrodkow", StringType()),
        StructField("okresObowiazywania", StringType()),
        StructField("podstawoweDane", StringType()),
        StructField("szczegolyUmowy", StringType()),
        StructField("stronyUmowy", StringType()),
        StructField("zmianyUmowy", StringType()),
    ]
)


def _address(
    *,
    ulica: str | None = "Nowe Ogrody",
    numer_nieruchomosci: str | None = "8/12",
    numer_lokalu: str | None = None,
    wojewodztwo: str | None = "POMORSKIE",
    powiat: str | None = "Gdańsk",
    gmina_miasto_dzielnica: str | None = "Gdańsk",
    miejscowosc: str | None = "Gdańsk",
    kod_pocztowy: str | None = "80-803",
) -> dict[str, str | None]:
    return {
        "ulica": ulica,
        "numerNieruchomosci": numer_nieruchomosci,
        "numerLokalu": numer_lokalu,
        "wojewodztwo": wojewodztwo,
        "powiat": powiat,
        "gminaMiastoDzielnica": gmina_miasto_dzielnica,
        "miejscowosc": miejscowosc,
        "kodPocztowy": kod_pocztowy,
    }


def _party(
    *,
    nazwa: str | None,
    rodzaj: str,
    nip: str | None = None,
    regon: str | None = None,
    imie: str | None = None,
    nazwisko: str | None = None,
    czy_konsorcjum: bool | None = False,
    dane_adresowe: dict[str, str | None] | None = None,
    niejawnosc_strony: dict[str, str | None] | None = None,
) -> dict:
    return {
        "kraj": "Polska",
        "rodzaj": rodzaj,
        "nazwa": nazwa,
        "nip": nip,
        "regon": regon,
        "imie": imie,
        "nazwisko": nazwisko,
        "czyKonsorcjum": czy_konsorcjum,
        "daneAdresowe": _address() if dane_adresowe is None else dane_adresowe,
        "niejawnoscStrony": niejawnosc_strony,
    }


def _bronze(
    spark: SparkSession,
    *,
    id_umowy: str = "00000000-0000-0000-0000-000000000001",
    data_modyfikacji: str = "11.10.2026",
    podstawowe_dane: dict | None = None,
    szczegoly_umowy: dict | None = None,
    strony_umowy: list[dict] | None = None,
    zmiany_umowy: Sequence[dict] = (),
) -> DataFrame:
    """Return one bronze record, with the nested objects as JSON text, the way Auto Loader stores them."""
    if podstawowe_dane is None:
        podstawowe_dane = {
            "statusUmowy": "Aktywna",
            "numerUmowy": "ZP/12/2026",
            "brakNumeruUmowy": False,
            "dataZawarciaUmowy": "01.08.2026",
            "dataZakonczeniaUmowy": "31.07.2027",
        }
    if szczegoly_umowy is None:
        szczegoly_umowy = {
            "przedmiotUmowy": "Dostawa sprzętu komputerowego",
            "niejawnoscPrzedmiotu": None,
            "wartoscPrzedmiotu": 125000.5,
            "niejawnoscWartosciPrzedmiotu": None,
            "opisWartosciPrzedmiotu": None,
        }
    if strony_umowy is None:
        strony_umowy = [_party(nazwa="Gmina Miasta Gdańska", rodzaj="JSFP")]
    record = {
        "idUmowy": id_umowy,
        "dataModyfikacji": data_modyfikacji,
        "_file_modification_time": datetime(2026, 10, 12, 2, 0),
        "dataPublikacji": "04.08.2026",
        "finansowanaZeSrodkow": "true",
        "okresObowiazywania": {"umowaNaCzasNieoznaczony": False, "okres": "12 miesięcy"},
        "podstawoweDane": podstawowe_dane,
        "szczegolyUmowy": szczegoly_umowy,
        "stronyUmowy": strony_umowy,
        "zmianyUmowy": list(zmiany_umowy),
    }
    row = {
        name: json.dumps(value) if isinstance(value, dict | list) else value
        for name, value in record.items()
    }
    return spark.createDataFrame([row], _BRONZE_SCHEMA)


def test_parse_agreements_converts_text_to_typed_columns(spark: SparkSession) -> None:
    row = parse_agreements(_bronze(spark)).drop("strony").first()

    assert row.asDict() == {
        "id_umowy": "00000000-0000-0000-0000-000000000001",
        "data_modyfikacji": date(2026, 10, 11),
        "_file_modification_time": datetime(2026, 10, 12, 2, 0),
        "data_publikacji": date(2026, 8, 4),
        "finansowana_ze_srodkow": True,
        "umowa_na_czas_nieoznaczony": False,
        "okres_obowiazywania": "12 miesięcy",
        "status_umowy": "Aktywna",
        "numer_umowy": "ZP/12/2026",
        "brak_numeru_umowy": False,
        "data_zawarcia_umowy": date(2026, 8, 1),
        "data_zakonczenia_umowy": date(2027, 7, 31),
        "przedmiot_umowy": "Dostawa sprzętu komputerowego",
        "niejawnosc_przedmiotu": None,
        "wartosc_przedmiotu": Decimal("125000.50"),
        "niejawnosc_wartosci_przedmiotu": None,
        "opis_wartosci_przedmiotu": None,
        "zmiany_umowy": [],
    }


def test_parse_agreements_turns_invalid_dates_into_nulls(spark: SparkSession) -> None:
    podstawowe = {
        "statusUmowy": "Aktywna",
        "numerUmowy": "ZP/12/2026",
        "brakNumeruUmowy": False,
        "dataZawarciaUmowy": "31.02.2026",
        "dataZakonczeniaUmowy": "",
    }

    row = parse_agreements(_bronze(spark, podstawowe_dane=podstawowe)).first()

    assert row.data_zawarcia_umowy is None
    assert row.data_zakonczenia_umowy is None


def test_parse_agreements_renames_value_confidentiality_fields(spark: SparkSession) -> None:
    szczegoly = {
        "przedmiotUmowy": "artystyczne wykonanie",
        "niejawnoscPrzedmiotu": None,
        "wartoscPrzedmiotu": None,
        "niejawnoscWartosciPrzedmiotu": {
            "podstawa": "INNA",
            "zakres": "Wartość umowy",
            "organLubOsobaWylaczajaca": "Dyrektor NFM",
            "komentarz": "art. 29a ustawy z dnia 25 października 1991 r. o organizowaniu i prowadzeniu działalności kulturalnej",
        },
        "opisWartosciPrzedmiotu": None,
    }

    row = parse_agreements(_bronze(spark, szczegoly_umowy=szczegoly)).first()

    assert row.wartosc_przedmiotu is None
    assert row.niejawnosc_przedmiotu is None
    assert row.niejawnosc_wartosci_przedmiotu.asDict() == {
        "podstawa": "INNA",
        "zakres": "Wartość umowy",
        "organ_lub_osoba_wylaczajaca": "Dyrektor NFM",
        "komentarz": "art. 29a ustawy z dnia 25 października 1991 r. o organizowaniu i prowadzeniu działalności kulturalnej",
    }


def test_parse_agreements_renames_subject_confidentiality_fields(spark: SparkSession) -> None:
    szczegoly = {
        "przedmiotUmowy": None,
        "niejawnoscPrzedmiotu": {
            "podstawa": "INNA",
            "zakres": "Przedmiot umowy",
            "organLubOsobaWylaczajaca": "Wójt Gminy Łękawica",
            "komentarz": "art.28 ustawy o ochronie ludności i obronie cywilnej",
        },
        "wartoscPrzedmiotu": 79430.9,
        "niejawnoscWartosciPrzedmiotu": None,
        "opisWartosciPrzedmiotu": None,
    }

    row = parse_agreements(_bronze(spark, szczegoly_umowy=szczegoly)).first()

    assert row.przedmiot_umowy is None
    assert row.niejawnosc_wartosci_przedmiotu is None
    assert row.niejawnosc_przedmiotu.asDict() == {
        "podstawa": "INNA",
        "zakres": "Przedmiot umowy",
        "organ_lub_osoba_wylaczajaca": "Wójt Gminy Łękawica",
        "komentarz": "art.28 ustawy o ochronie ludności i obronie cywilnej",
    }


def test_parse_agreements_renames_party_confidentiality_fields(spark: SparkSession) -> None:
    niejawnosc = {
        "podstawa": "Art. 5 ust. 2 ustawy o dostępie do informacji publicznej",
        "zakres": "Dane strony umowy",
        "organLubOsobaWylaczajaca": "Jan Kowalski",
        "komentarz": None,
    }
    strony = [
        _party(nazwa="Gmina Miasta Gdańska", rodzaj="JSFP"),
        _party(
            nazwa=None,
            rodzaj="Osoba fizyczna",
            dane_adresowe=dict.fromkeys(_address()),
            niejawnosc_strony=niejawnosc,
        ),
    ]

    row = parse_agreements(_bronze(spark, strony_umowy=strony)).first()

    assert row.strony[0].niejawnosc_strony is None
    assert row.strony[1].niejawnosc_strony.asDict() == {
        "podstawa": "Art. 5 ust. 2 ustawy o dostępie do informacji publicznej",
        "zakres": "Dane strony umowy",
        "organ_lub_osoba_wylaczajaca": "Jan Kowalski",
        "komentarz": None,
    }


def test_parse_agreements_parses_changes(spark: SparkSession) -> None:
    zmiany = [
        {"rodzajZmiany": "Aneks do umowy", "dataZmiany": "11.10.2026", "komentarz": "Zmiana terminu dostawy"},
        {"rodzajZmiany": "Cesja umowy", "dataZmiany": "09.10.2026", "komentarz": None},
    ]

    row = parse_agreements(_bronze(spark, zmiany_umowy=zmiany)).first()

    assert [zmiana.asDict() for zmiana in row.zmiany_umowy] == [
        {"rodzaj_zmiany": "Aneks do umowy", "data_zmiany": date(2026, 10, 11), "komentarz": "Zmiana terminu dostawy"},
        {"rodzaj_zmiany": "Cesja umowy", "data_zmiany": date(2026, 10, 9), "komentarz": None},
    ]


def test_parse_agreements_cleans_parties(spark: SparkSession) -> None:
    strona = _party(
        nazwa="UNIWERSYTET EKONOMICZNY W KATOWICACH",
        rodzaj="JSFP",
        nip="6340008825",
        regon="000001548",
        czy_konsorcjum=None,
        dane_adresowe=_address(
            ulica="ul. 1 Maja",
            numer_nieruchomosci="50",
            wojewodztwo="ŚLĄSKIE",
            powiat="Katowice",
            gmina_miasto_dzielnica="Katowice",
            miejscowosc="Katowice",
            kod_pocztowy="40-287",
        ),
    )
    osoba = _party(
        nazwa=None,
        rodzaj="Osoba fizyczna",
        imie="Jan",
        nazwisko="Kowalski",
        dane_adresowe=dict.fromkeys(_address()),
    )

    row = parse_agreements(_bronze(spark, strony_umowy=[strona, osoba])).first()

    assert row.strony[0].asDict() == {
        "kraj": "Polska",
        "rodzaj": "JSFP",
        "nazwa": "UNIWERSYTET EKONOMICZNY W KATOWICACH",
        "nip": "6340008825",
        "regon": "000001548",
        "imie": None,
        "nazwisko": None,
        "czy_konsorcjum": None,
        "niejawnosc_strony": None,
        "address_id": ANY,
        "ulica": "ul. 1 Maja",
        "numer_nieruchomosci": "50",
        "numer_lokalu": None,
        "wojewodztwo": "Śląskie",
        "powiat": "Katowice",
        "gmina_miasto_dzielnica": "Katowice",
        "miejscowosc": "Katowice",
        "kod_pocztowy": "40-287",
    }
    assert row.strony[1].asDict() == {
        "kraj": "Polska",
        "rodzaj": "Osoba fizyczna",
        "nazwa": None,
        "nip": None,
        "regon": None,
        "imie": "Jan",
        "nazwisko": "Kowalski",
        "czy_konsorcjum": False,
        "niejawnosc_strony": None,
        "address_id": None,
        "ulica": None,
        "numer_nieruchomosci": None,
        "numer_lokalu": None,
        "wojewodztwo": None,
        "powiat": None,
        "gmina_miasto_dzielnica": None,
        "miejscowosc": None,
        "kod_pocztowy": None,
    }


def test_parse_agreements_cleans_nip_and_regon(spark: SparkSession) -> None:
    strona = _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca", nip="", regon=" 220000001 ")

    row = parse_agreements(_bronze(spark, strony_umowy=[strona])).first()

    assert row.strony[0].nip is None
    assert row.strony[0].regon == "220000001"


def test_parse_agreements_normalises_voivodeship_case(spark: SparkSession) -> None:
    strony = [
        _party(
            nazwa="Gmina Miasta Gdańska",
            rodzaj="JSFP",
            dane_adresowe=_address(wojewodztwo="KUJAWSKO-POMORSKIE"),
        ),
        _party(
            nazwa="Firma X sp. z o.o.",
            rodzaj="Przedsiębiorca",
            dane_adresowe=_address(wojewodztwo="kujawsko-pomorskie"),
        ),
    ]

    row = parse_agreements(_bronze(spark, strony_umowy=strony)).first()

    assert row.strony[0].address_id == row.strony[1].address_id
    assert {strona.wojewodztwo for strona in row.strony} == {"Kujawsko-Pomorskie"}


def test_parse_agreements_trims_address_fields_and_party_type(spark: SparkSession) -> None:
    strony = [
        _party(
            nazwa="Gmina Miasta Gdańska",
            rodzaj="JSFP ",
            dane_adresowe=_address(miejscowosc="Gdańsk "),
        ),
        _party(
            nazwa="Firma X sp. z o.o.",
            rodzaj="Przedsiębiorca",
            dane_adresowe=_address(miejscowosc="Gdańsk"),
        ),
    ]

    row = parse_agreements(_bronze(spark, strony_umowy=strony)).first()

    assert row.strony[0].address_id == row.strony[1].address_id
    assert row.strony[0].miejscowosc == "Gdańsk"
    assert row.strony[0].rodzaj == "JSFP"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("ulica", "ul. Długa", id="ulica"),
        pytest.param("numer_nieruchomosci", "10", id="numerNieruchomosci"),
        pytest.param("numer_lokalu", "4", id="numerLokalu"),
        pytest.param("wojewodztwo", "MAZOWIECKIE", id="wojewodztwo"),
        pytest.param("powiat", "gdański", id="powiat"),
        pytest.param("gmina_miasto_dzielnica", "Pruszcz Gdański", id="gminaMiastoDzielnica"),
        pytest.param("miejscowosc", "Sopot", id="miejscowosc"),
        pytest.param("kod_pocztowy", "80-804", id="kodPocztowy"),
    ],
)
def test_parse_agreements_gives_each_address_its_own_address_id(
    spark: SparkSession, field: str, value: str
) -> None:
    strony = [
        _party(nazwa="Gmina Miasta Gdańska", rodzaj="JSFP"),
        _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca", dane_adresowe=_address(**{field: value})),
    ]

    row = parse_agreements(_bronze(spark, strony_umowy=strony)).first()

    assert row.strony[0].address_id != row.strony[1].address_id


def test_parse_agreements_leaves_address_id_empty_without_an_address(spark: SparkSession) -> None:
    strony = [
        _party(
            nazwa=None,
            rodzaj="Osoba fizyczna",
            imie="Jan",
            nazwisko="Kowalski",
            dane_adresowe=dict.fromkeys(_address()),
        )
    ]

    strona = parse_agreements(_bronze(spark, strony_umowy=strony)).first().strony[0]

    assert strona.address_id is None


def test_parse_agreements_treats_empty_address_fields_as_missing(spark: SparkSession) -> None:
    strony = [
        _party(
            nazwa=None,
            rodzaj="Osoba fizyczna",
            imie="Jan",
            nazwisko="Kowalski",
            dane_adresowe=dict.fromkeys(_address(), ""),
        )
    ]

    strona = parse_agreements(_bronze(spark, strony_umowy=strony)).first().strony[0]

    assert strona.address_id is None
    assert strona.miejscowosc is None


def test_explode_parties_keys_parties_by_position(spark: SparkSession) -> None:
    strony = [
        _party(nazwa="Gmina Miasta Gdańska", rodzaj="JSFP"),
        _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca"),
        _party(nazwa="Firma Y S.A.", rodzaj="Przedsiębiorca"),
    ]

    agreements = parse_agreements(_bronze(spark, strony_umowy=strony))

    rows = explode_parties(agreements, "id_umowy").orderBy("party_key").collect()

    assert [(row.party_key, row.nazwa) for row in rows] == [
        (0, "Gmina Miasta Gdańska"),
        (1, "Firma X sp. z o.o."),
        (2, "Firma Y S.A."),
    ]


def test_explode_parties_returns_no_rows_without_parties(spark: SparkSession) -> None:
    agreements = parse_agreements(_bronze(spark, strony_umowy=[]))

    assert explode_parties(agreements, "id_umowy").count() == 0


def test_with_party_identity_key_uses_the_first_available_identifier(spark: SparkSession) -> None:
    strony = [
        _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca", nip="0987654321", regon="220000001"),
        _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca", regon="220000001"),
        _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca"),
        _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca", dane_adresowe=dict.fromkeys(_address())),
    ]
    parties = explode_parties(parse_agreements(_bronze(spark, strony_umowy=strony)), "id_umowy")

    rows = with_party_identity_key(parties).orderBy("party_key").collect()

    assert [row.party_identity_key for row in rows] == [
        "0987654321",
        "220000001",
        f"Firma X sp. z o.o.|{rows[2].address_id}",
        "00000000-0000-0000-0000-000000000001|3",
    ]


def test_latest_per_party_keeps_the_newest_agreement(spark: SparkSession) -> None:
    older = _bronze(
        spark,
        id_umowy="a",
        data_modyfikacji="01.09.2026",
        strony_umowy=[
            _party(nazwa="Gmina Miasta Gdańska", rodzaj="JSFP"),
            _party(nazwa="Firma X", rodzaj="Przedsiębiorca", nip="0987654321"),
        ],
    )
    newer = _bronze(
        spark,
        id_umowy="b",
        data_modyfikacji="11.10.2026",
        strony_umowy=[
            _party(nazwa="Gmina Miasta Gdańska", rodzaj="JSFP"),
            _party(nazwa="Firma X sp. z o.o.", rodzaj="Przedsiębiorca", nip="0987654321"),
        ],
    )
    parties = explode_parties(parse_agreements(older.unionByName(newer)), "id_umowy", "data_modyfikacji")

    rows = latest_per_party(with_party_identity_key(parties)).collect()

    assert sorted(row.nazwa for row in rows) == ["Firma X sp. z o.o.", "Gmina Miasta Gdańska"]
