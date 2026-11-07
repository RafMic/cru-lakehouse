from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from pyspark.sql import SparkSession

from gold.modeling import (
    UNKNOWN_DATE_KEY,
    UNKNOWN_KEY,
    agreement_changes,
    agreement_facts,
    link_agreements,
    mark_buyers,
    with_unknown_row,
)

_PARTIES_SCHEMA = "id_umowy string, party_key int, rodzaj string, nazwa string"

_AGREEMENTS_SCHEMA = (
    "id_umowy string, data_zawarcia_umowy date, data_zakonczenia_umowy date, umowa_na_czas_nieoznaczony boolean, "
    "wartosc_przedmiotu decimal(18,2), "
    "zmiany_umowy array<struct<rodzaj_zmiany: string, data_zmiany: date, komentarz: string>>"
)


def _party(
    *,
    id_umowy: str = "00000003",
    party_key: int = 1,
    rodzaj: str | None = "Przedsiębiorca",
    nazwa: str = "Firma X sp. z o.o.",
) -> dict[str, object]:
    return {"id_umowy": id_umowy, "party_key": party_key, "rodzaj": rodzaj, "nazwa": nazwa}


def _agreement(
    *,
    id_umowy: str = "00000003",
    data_zawarcia_umowy: date | None = date(2026, 8, 1),
    data_zakonczenia_umowy: date | None = date(2026, 12, 31),
    umowa_na_czas_nieoznaczony: bool = False,
    wartosc_przedmiotu: Decimal | None = Decimal("125000.50"),
    zmiany_umowy: Sequence[dict[str, object]] = (),
) -> dict[str, object]:
    return {
        "id_umowy": id_umowy,
        "data_zawarcia_umowy": data_zawarcia_umowy,
        "data_zakonczenia_umowy": data_zakonczenia_umowy,
        "umowa_na_czas_nieoznaczony": umowa_na_czas_nieoznaczony,
        "wartosc_przedmiotu": wartosc_przedmiotu,
        "zmiany_umowy": zmiany_umowy,
    }


def test_mark_buyers_keeps_only_the_first_party_as_buyer_when_all_are_public(spark: SparkSession) -> None:
    parties = spark.createDataFrame(
        [
            _party(id_umowy="00000001", party_key=0, rodzaj="JSFP", nazwa="URZĄD MIASTA W JELENIEJ GÓRZE"),
            _party(id_umowy="00000001", rodzaj="JSFP", nazwa="POWIAT ZĄBKOWICKI"),
            _party(party_key=0, rodzaj="JSFP", nazwa="EUROPEJSKIE CENTRUM SOLIDARNOŚCI"),
            _party(),
        ],
        _PARTIES_SCHEMA,
    )

    rows = mark_buyers(parties).orderBy("id_umowy", "party_key").collect()

    assert [(row.nazwa, row.is_buyer) for row in rows] == [
        ("URZĄD MIASTA W JELENIEJ GÓRZE", True),
        ("POWIAT ZĄBKOWICKI", False),
        ("EUROPEJSKIE CENTRUM SOLIDARNOŚCI", True),
        ("Firma X sp. z o.o.", False),
    ]


def test_mark_buyers_keeps_every_public_body_as_buyer_when_not_all_are_public(spark: SparkSession) -> None:
    parties = spark.createDataFrame(
        [
            _party(id_umowy="00000002", party_key=0, rodzaj="JSFP", nazwa="MIASTO ZĄBKI"),
            _party(id_umowy="00000002"),
            _party(id_umowy="00000002", party_key=2, rodzaj="JSFP", nazwa='ŻŁOBEK "ZĄBKOWSKIE PROMYKI"'),
        ],
        _PARTIES_SCHEMA,
    )

    rows = mark_buyers(parties).orderBy("party_key").collect()

    assert [(row.nazwa, row.is_buyer) for row in rows] == [
        ("MIASTO ZĄBKI", True),
        ("Firma X sp. z o.o.", False),
        ('ŻŁOBEK "ZĄBKOWSKIE PROMYKI"', True),
    ]


def test_mark_buyers_treats_a_party_without_a_kind_as_vendor(spark: SparkSession) -> None:
    parties = spark.createDataFrame(
        [
            _party(party_key=0, rodzaj="JSFP", nazwa="EUROPEJSKIE CENTRUM SOLIDARNOŚCI"),
            _party(),
            _party(party_key=2, rodzaj=None, nazwa="Firma Y sp. z o.o."),
        ],
        _PARTIES_SCHEMA,
    )

    rows = mark_buyers(parties).orderBy("party_key").collect()

    assert [(row.nazwa, row.is_buyer) for row in rows] == [
        ("EUROPEJSKIE CENTRUM SOLIDARNOŚCI", True),
        ("Firma X sp. z o.o.", False),
        ("Firma Y sp. z o.o.", False),
    ]


def test_link_agreements_keeps_every_party_of_an_agreement(spark: SparkSession) -> None:
    agreements = spark.createDataFrame([_agreement()], _AGREEMENTS_SCHEMA)
    vendors = spark.createDataFrame(
        [("00000003", "0987654321"), ("00000003", "1234567890")], "id_umowy string, vendor_key string"
    )

    rows = link_agreements(agreements, vendors).orderBy("vendor_key").collect()

    assert [tuple(row) for row in rows] == [("00000003", "0987654321"), ("00000003", "1234567890")]


def test_link_agreements_keeps_one_row_per_link(spark: SparkSession) -> None:
    agreements = spark.createDataFrame([_agreement()], _AGREEMENTS_SCHEMA)
    vendors = spark.createDataFrame(
        [("00000003", "0987654321"), ("00000003", "0987654321")], "id_umowy string, vendor_key string"
    )

    rows = link_agreements(agreements, vendors).collect()

    assert [tuple(row) for row in rows] == [("00000003", "0987654321")]


def test_link_agreements_points_an_agreement_without_parties_to_unknown(spark: SparkSession) -> None:
    agreements = spark.createDataFrame([_agreement(), _agreement(id_umowy="00000002")], _AGREEMENTS_SCHEMA)
    buyers = spark.createDataFrame(
        [("00000003", "1111111112", "a1")], "id_umowy string, buyer_key string, geography_key string"
    )

    rows = link_agreements(agreements, buyers).orderBy("id_umowy").collect()

    assert [tuple(row) for row in rows] == [
        ("00000002", UNKNOWN_KEY, UNKNOWN_KEY),
        ("00000003", "1111111112", "a1"),
    ]


def test_with_unknown_row_fills_text_columns_and_leaves_the_others_empty(spark: SparkSession) -> None:
    vendors = spark.createDataFrame(
        [("0987654321", "Firma X sp. z o.o.", False)], "vendor_key string, nazwa string, czy_konsorcjum boolean"
    )

    rows = with_unknown_row(vendors, "vendor_key", UNKNOWN_KEY, "nazwa").orderBy("vendor_key").collect()

    assert [row.asDict() for row in rows] == [
        {"vendor_key": "0987654321", "nazwa": "Firma X sp. z o.o.", "czy_konsorcjum": False},
        {"vendor_key": UNKNOWN_KEY, "nazwa": "Unknown", "czy_konsorcjum": None},
    ]


def test_agreement_facts_gives_the_unknown_date_key_without_a_signing_date(spark: SparkSession) -> None:
    agreements = spark.createDataFrame(
        [
            _agreement(data_zawarcia_umowy=date(2026, 8, 1)),
            _agreement(id_umowy="00000002", data_zawarcia_umowy=None),
        ],
        _AGREEMENTS_SCHEMA,
    )

    rows = agreement_facts(agreements).orderBy("id_umowy").collect()

    assert [(row.id_umowy, row.date_key) for row in rows] == [
        ("00000002", UNKNOWN_DATE_KEY),
        ("00000003", 20260801),
    ]


def test_agreement_facts_leaves_the_value_empty_when_it_is_confidential(spark: SparkSession) -> None:
    agreements = spark.createDataFrame(
        [
            _agreement(wartosc_przedmiotu=Decimal("125000.50")),
            _agreement(id_umowy="00000002", wartosc_przedmiotu=None),
        ],
        _AGREEMENTS_SCHEMA,
    )

    rows = agreement_facts(agreements).orderBy("id_umowy").collect()

    assert [(row.id_umowy, row.wartosc_przedmiotu) for row in rows] == [
        ("00000002", None),
        ("00000003", Decimal("125000.50")),
    ]


def test_agreement_facts_leaves_the_duration_empty_for_open_ended_agreements(spark: SparkSession) -> None:
    agreements = spark.createDataFrame(
        [
            _agreement(
                data_zawarcia_umowy=date(2026, 8, 1),
                data_zakonczenia_umowy=date(2026, 12, 31),
            ),
            _agreement(
                id_umowy="00000002",
                data_zakonczenia_umowy=None,
                umowa_na_czas_nieoznaczony=True,
            ),
        ],
        _AGREEMENTS_SCHEMA,
    )

    rows = agreement_facts(agreements).orderBy("id_umowy").collect()

    assert [(row.id_umowy, row.czas_trwania_dni) for row in rows] == [
        ("00000002", None),
        ("00000003", 152),
    ]


def test_agreement_changes_keys_each_change_by_its_agreement_and_position(spark: SparkSession) -> None:
    zmiany = [
        {"rodzaj_zmiany": "Cesja umowy", "data_zmiany": date(2026, 10, 9), "komentarz": "Przejęcie umowy przez nowego wykonawcę"},
        {"rodzaj_zmiany": "Wygaśnięcie umowy", "data_zmiany": date(2026, 10, 11), "komentarz": "umowa zrealizowana"},
    ]
    agreements = spark.createDataFrame([_agreement(id_umowy="00000003", zmiany_umowy=zmiany)], _AGREEMENTS_SCHEMA)

    rows = agreement_changes(agreements).orderBy("change_key").collect()

    assert [row.asDict() for row in rows] == [
        {
            "id_umowy": "00000003",
            "change_key": "00000003|0",
            "date_key": 20261009,
            "rodzaj_zmiany": "Cesja umowy",
            "komentarz": "Przejęcie umowy przez nowego wykonawcę",
        },
        {
            "id_umowy": "00000003",
            "change_key": "00000003|1",
            "date_key": 20261011,
            "rodzaj_zmiany": "Wygaśnięcie umowy",
            "komentarz": "umowa zrealizowana",
        },
    ]


def test_agreement_changes_skips_agreements_without_changes(spark: SparkSession) -> None:
    agreements = spark.createDataFrame([_agreement(zmiany_umowy=[])], _AGREEMENTS_SCHEMA)

    assert agreement_changes(agreements).collect() == []
