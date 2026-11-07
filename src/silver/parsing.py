"""Transformations that build the Silver tables, kept apart from the pipeline code so tests can import it."""

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DecimalType,
    StringType,
    StructField,
    StructType,
)
from pyspark.sql.window import Window

_DATE_FORMAT = "dd.MM.yyyy"

# Schemas of the nested objects that bronze stores as JSON text.
_OKRES_SCHEMA = StructType(
    [
        StructField("umowaNaCzasNieoznaczony", BooleanType()),
        StructField("okres", StringType()),
    ]
)

_PODSTAWOWE_SCHEMA = StructType(
    [
        StructField("statusUmowy", StringType()),
        StructField("numerUmowy", StringType()),
        StructField("brakNumeruUmowy", BooleanType()),
        StructField("dataZawarciaUmowy", StringType()),
        StructField("dataZakonczeniaUmowy", StringType()),
    ]
)

_NIEJAWNOSC_SCHEMA = StructType(
    [
        StructField("podstawa", StringType()),
        StructField("zakres", StringType()),
        StructField("organLubOsobaWylaczajaca", StringType()),
        StructField("komentarz", StringType()),
    ]
)

_SZCZEGOLY_SCHEMA = StructType(
    [
        StructField("przedmiotUmowy", StringType()),
        StructField("niejawnoscPrzedmiotu", _NIEJAWNOSC_SCHEMA),
        StructField("wartoscPrzedmiotu", DecimalType(18, 2)),
        StructField("niejawnoscWartosciPrzedmiotu", _NIEJAWNOSC_SCHEMA),
        StructField("opisWartosciPrzedmiotu", StringType()),
    ]
)

_ADRES_SCHEMA = StructType(
    [
        StructField("ulica", StringType()),
        StructField("numerNieruchomosci", StringType()),
        StructField("numerLokalu", StringType()),
        StructField("wojewodztwo", StringType()),
        StructField("powiat", StringType()),
        StructField("gminaMiastoDzielnica", StringType()),
        StructField("miejscowosc", StringType()),
        StructField("kodPocztowy", StringType()),
    ]
)

_STRONA_SCHEMA = StructType(
    [
        StructField("kraj", StringType()),
        StructField("rodzaj", StringType()),
        StructField("nazwa", StringType()),
        StructField("nip", StringType()),
        StructField("regon", StringType()),
        StructField("imie", StringType()),
        StructField("nazwisko", StringType()),
        StructField("czyKonsorcjum", BooleanType()),
        StructField("daneAdresowe", _ADRES_SCHEMA),
        StructField("niejawnoscStrony", _NIEJAWNOSC_SCHEMA),
    ]
)

_STRONY_SCHEMA = ArrayType(_STRONA_SCHEMA)

_ZMIANA_SCHEMA = StructType(
    [
        StructField("rodzajZmiany", StringType()),
        StructField("dataZmiany", StringType()),
        StructField("komentarz", StringType()),
    ]
)

_ZMIANY_SCHEMA = ArrayType(_ZMIANA_SCHEMA)


def parse_agreements(bronze: DataFrame) -> DataFrame:
    """Return the bronze records with typed snake_case columns.

    strony holds the cleaned parties, and zmiany_umowy holds the reported changes, such as a cession or expiry.
    """
    okres = F.from_json("okresObowiazywania", _OKRES_SCHEMA)
    podstawowe = F.from_json("podstawoweDane", _PODSTAWOWE_SCHEMA)
    szczegoly = F.from_json("szczegolyUmowy", _SZCZEGOLY_SCHEMA)
    strony = F.from_json("stronyUmowy", _STRONY_SCHEMA)
    zmiany = F.from_json("zmianyUmowy", _ZMIANY_SCHEMA)

    return bronze.select(
        F.col("idUmowy").alias("id_umowy"),
        F.try_to_date("dataModyfikacji", _DATE_FORMAT).alias("data_modyfikacji"),
        "_file_modification_time",
        F.try_to_date("dataPublikacji", _DATE_FORMAT).alias("data_publikacji"),
        F.col("finansowanaZeSrodkow").cast("boolean").alias("finansowana_ze_srodkow"),
        okres["umowaNaCzasNieoznaczony"].alias("umowa_na_czas_nieoznaczony"),
        okres["okres"].alias("okres_obowiazywania"),
        podstawowe["statusUmowy"].alias("status_umowy"),
        podstawowe["numerUmowy"].alias("numer_umowy"),
        podstawowe["brakNumeruUmowy"].alias("brak_numeru_umowy"),
        F.try_to_date(podstawowe["dataZawarciaUmowy"], _DATE_FORMAT).alias(
            "data_zawarcia_umowy"
        ),
        F.try_to_date(podstawowe["dataZakonczeniaUmowy"], _DATE_FORMAT).alias(
            "data_zakonczenia_umowy"
        ),
        szczegoly["przedmiotUmowy"].alias("przedmiot_umowy"),
        _clean_niejawnosc(szczegoly["niejawnoscPrzedmiotu"]).alias("niejawnosc_przedmiotu"),
        szczegoly["wartoscPrzedmiotu"].alias("wartosc_przedmiotu"),
        _clean_niejawnosc(szczegoly["niejawnoscWartosciPrzedmiotu"]).alias("niejawnosc_wartosci_przedmiotu"),
        szczegoly["opisWartosciPrzedmiotu"].alias("opis_wartosci_przedmiotu"),
        F.transform(
            zmiany,
            lambda zmiana: F.struct(
                zmiana["rodzajZmiany"].alias("rodzaj_zmiany"),
                F.try_to_date(zmiana["dataZmiany"], _DATE_FORMAT).alias("data_zmiany"),
                zmiana["komentarz"].alias("komentarz"),
            ),
        ).alias("zmiany_umowy"),
        F.transform(strony, _clean_party).alias("strony"),
    )


def explode_parties(agreements: DataFrame, *columns: str) -> DataFrame:
    """Flatten strony into separate party rows, each keeping the given agreement columns.

    party_key numbers the parties from 0, in the order the source lists them.
    """
    return (
        agreements.select(*columns, F.posexplode("strony").alias("party_key", "strona"))
        .select(*columns, "party_key", "strona.*")
    )


def with_party_identity_key(parties: DataFrame) -> DataFrame:
    """Add party_identity_key, which matches a party across agreements.

    It is the NIP or REGON, else the name and address, otherwise a key unique to the party's agreement.
    """
    return parties.withColumn(
        "party_identity_key",
        F.coalesce(
            "nip",
            "regon",
            F.when(
                F.col("nazwa").isNotNull() & F.col("address_id").isNotNull(),
                F.concat_ws("|", "nazwa", "address_id"),
            ),
            F.concat_ws("|", "id_umowy", F.col("party_key").cast("string")),
        ),
    )


def latest_per_party(parties: DataFrame) -> DataFrame:
    """Keep each party's row from its most recently modified agreement."""
    window = Window.partitionBy("party_identity_key").orderBy(F.desc("data_modyfikacji"), "id_umowy", "party_key")
    return parties.withColumn("_rn", F.row_number().over(window)).filter("_rn = 1").drop("_rn")


def _clean_party(strona: Column) -> Column:
    """Clean one party and rename its fields to snake_case.

    address_id is a hash of the address fields, so parties at the same address share one addresses row.
    """
    address = {field: _clean_text(strona["daneAdresowe"][field]) for field in _ADRES_SCHEMA.fieldNames()}
    # initcap capitalises only after spaces, so each part of a name such as KUJAWSKO-POMORSKIE is capitalised separately.
    address["wojewodztwo"] = F.array_join(F.transform(F.split(address["wojewodztwo"], "-"), F.initcap), "-")
    return F.struct(
        _clean_text(strona["kraj"]).alias("kraj"),
        _clean_text(strona["rodzaj"]).alias("rodzaj"),
        _clean_text(strona["nazwa"]).alias("nazwa"),
        _clean_text(strona["nip"]).alias("nip"),
        _clean_text(strona["regon"]).alias("regon"),
        _clean_text(strona["imie"]).alias("imie"),
        _clean_text(strona["nazwisko"]).alias("nazwisko"),
        strona["czyKonsorcjum"].alias("czy_konsorcjum"),
        _clean_niejawnosc(strona["niejawnoscStrony"]).alias("niejawnosc_strony"),
        F.when(
            F.coalesce(*address.values()).isNotNull(),
            F.sha2(F.concat_ws("|", *[F.coalesce(field, F.lit("")) for field in address.values()]), 256),
        ).alias("address_id"),
        address["ulica"].alias("ulica"),
        address["numerNieruchomosci"].alias("numer_nieruchomosci"),
        address["numerLokalu"].alias("numer_lokalu"),
        address["wojewodztwo"].alias("wojewodztwo"),
        address["powiat"].alias("powiat"),
        address["gminaMiastoDzielnica"].alias("gmina_miasto_dzielnica"),
        address["miejscowosc"].alias("miejscowosc"),
        address["kodPocztowy"].alias("kod_pocztowy"),
    )


def _clean_niejawnosc(niejawnosc: Column) -> Column:
    fields = {
        "podstawa": _clean_text(niejawnosc["podstawa"]),
        "zakres": _clean_text(niejawnosc["zakres"]),
        "organ_lub_osoba_wylaczajaca": _clean_text(niejawnosc["organLubOsobaWylaczajaca"]),
        "komentarz": _clean_text(niejawnosc["komentarz"]),
    }
    return F.when(
        F.coalesce(*fields.values()).isNotNull(),
        F.struct(*[value.alias(name) for name, value in fields.items()]),
    )


def _clean_text(value: Column) -> Column:
    return F.nullif(F.trim(value), F.lit(""))
