"""Gold tables, a star schema built from the current version of each Silver agreement.

CRU marks no buyer or vendor, so the first listed party, which registered the agreement, counts as the buyer, and other public bodies join it only next to a party of another kind.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from gold.modeling import (
    UNKNOWN_DATE_KEY,
    UNKNOWN_KEY,
    agreement_changes,
    agreement_facts,
    date_key,
    link_agreements,
    mark_buyers,
    with_unknown_row,
)

# The register opened on this date, so no agreement or change is older.
_DATE_RANGE_START = "2026-07-01"

# Rolls forward with each refresh, so the range never needs a manual update.
_DATE_RANGE_END_BUFFER_DAYS = 365 * 5


@dp.materialized_view(
    name="gold.dim_date",
    comment="Lists every day from the register's start to five years ahead",
    schema="""
        date_key INT NOT NULL, date DATE, year INT, quarter INT, month INT, day_of_month INT, day_name STRING,
        CONSTRAINT dim_date_pk PRIMARY KEY (date_key) RELY
    """,
)
def dim_date():
    dates = (
        spark.range(1)
        .select(
            F.explode(
                F.sequence(
                    F.to_date(F.lit(_DATE_RANGE_START)),
                    F.date_add(F.current_date(), _DATE_RANGE_END_BUFFER_DAYS),
                )
            ).alias("date")
        )
        .select(
            date_key("date"),
            "date",
            F.year("date").alias("year"),
            F.quarter("date").alias("quarter"),
            F.month("date").alias("month"),
            F.dayofmonth("date").alias("day_of_month"),
            F.date_format("date", "EEEE").alias("day_name"),
        )
    )
    return with_unknown_row(dates, "date_key", UNKNOWN_DATE_KEY, "day_name")


@dp.materialized_view(
    name="gold.dim_geography",
    comment="Holds the addresses of the parties",
    schema="""
        geography_key STRING NOT NULL, wojewodztwo STRING, powiat STRING, gmina_miasto_dzielnica STRING,
        miejscowosc STRING, kod_pocztowy STRING, ulica STRING, numer_nieruchomosci STRING, numer_lokalu STRING,
        CONSTRAINT dim_geography_pk PRIMARY KEY (geography_key) RELY
    """,
)
def dim_geography():
    address_columns = [
        "wojewodztwo",
        "powiat",
        "gmina_miasto_dzielnica",
        "miejscowosc",
        "kod_pocztowy",
        "ulica",
        "numer_nieruchomosci",
        "numer_lokalu",
    ]
    addresses = spark.read.table("silver.addresses").select(
        F.col("address_id").alias("geography_key"), *address_columns
    )
    return with_unknown_row(addresses, "geography_key", UNKNOWN_KEY, *address_columns)


def _current_agreements():
    return spark.read.table("silver.agreements").filter("__END_AT IS NULL")


def _current_parties():
    return mark_buyers(spark.read.table("silver.parties").filter("__END_AT IS NULL"))


@dp.materialized_view(
    name="gold.dim_buyer",
    comment="Lists the parties that appear as buyers",
    schema="""
        buyer_key STRING NOT NULL, nazwa STRING, nip STRING, regon STRING, kraj STRING,
        CONSTRAINT dim_buyer_pk PRIMARY KEY (buyer_key) RELY
    """,
)
def dim_buyer():
    buyer_keys = _current_parties().filter("is_buyer").select("party_identity_key")
    buyers = (
        spark.read.table("silver.party_identities")
        .join(buyer_keys, "party_identity_key", "left_semi")
        .select(F.col("party_identity_key").alias("buyer_key"), "nazwa", "nip", "regon", "kraj")
    )
    return with_unknown_row(buyers, "buyer_key", UNKNOWN_KEY, "nazwa", "nip", "regon", "kraj")


@dp.materialized_view(
    name="gold.dim_vendor",
    comment="Lists the parties that appear as vendors",
    schema="""
        vendor_key STRING NOT NULL, nazwa STRING, imie STRING, nazwisko STRING, nip STRING, regon STRING,
        kraj STRING, rodzaj STRING, czy_konsorcjum BOOLEAN,
        CONSTRAINT dim_vendor_pk PRIMARY KEY (vendor_key) RELY
    """,
)
def dim_vendor():
    vendor_keys = _current_parties().filter("NOT is_buyer").select("party_identity_key")
    vendors = (
        spark.read.table("silver.party_identities")
        .join(vendor_keys, "party_identity_key", "left_semi")
        .select(
            F.col("party_identity_key").alias("vendor_key"),
            "nazwa",
            "imie",
            "nazwisko",
            "nip",
            "regon",
            "kraj",
            "rodzaj",
            "czy_konsorcjum",
        )
    )
    return with_unknown_row(
        vendors, "vendor_key", UNKNOWN_KEY, "nazwa", "imie", "nazwisko", "nip", "regon", "kraj", "rodzaj"
    )


@dp.materialized_view(
    name="gold.bridge_agreement_buyer",
    comment="Links each agreement to its buyers and their addresses",
    schema="""
        id_umowy STRING NOT NULL, buyer_key STRING NOT NULL, geography_key STRING NOT NULL,
        CONSTRAINT bridge_agreement_buyer_pk PRIMARY KEY (id_umowy, buyer_key, geography_key) RELY,
        CONSTRAINT bridge_agreement_buyer_fact_agreement_fk FOREIGN KEY (id_umowy) REFERENCES gold.fact_agreement,
        CONSTRAINT bridge_agreement_buyer_dim_buyer_fk FOREIGN KEY (buyer_key) REFERENCES gold.dim_buyer,
        CONSTRAINT bridge_agreement_buyer_dim_geography_fk FOREIGN KEY (geography_key) REFERENCES gold.dim_geography
    """,
)
def bridge_agreement_buyer():
    """Return every buyer on each agreement, since joint purchases and cessions list more than one."""
    buyers = _current_parties().filter("is_buyer").select(
        "id_umowy",
        F.col("party_identity_key").alias("buyer_key"),
        F.coalesce("address_id", F.lit(UNKNOWN_KEY)).alias("geography_key"),
    )
    return link_agreements(_current_agreements(), buyers)


@dp.materialized_view(
    name="gold.bridge_agreement_vendor",
    comment="Links each agreement to its vendors",
    schema="""
        id_umowy STRING NOT NULL, vendor_key STRING NOT NULL,
        CONSTRAINT bridge_agreement_vendor_pk PRIMARY KEY (id_umowy, vendor_key) RELY,
        CONSTRAINT bridge_agreement_vendor_fact_agreement_fk FOREIGN KEY (id_umowy) REFERENCES gold.fact_agreement,
        CONSTRAINT bridge_agreement_vendor_dim_vendor_fk FOREIGN KEY (vendor_key) REFERENCES gold.dim_vendor
    """,
)
def bridge_agreement_vendor():
    """Return every vendor on each agreement, since consortia and cessions list more than one."""
    vendors = _current_parties().filter("NOT is_buyer").select(
        "id_umowy", F.col("party_identity_key").alias("vendor_key")
    )
    return link_agreements(_current_agreements(), vendors)


@dp.materialized_view(
    name="gold.fact_agreement",
    comment="Records the signing date, value and duration of each agreement",
    schema="""
        id_umowy STRING NOT NULL, date_key INT NOT NULL, wartosc_przedmiotu DECIMAL(18, 2), czas_trwania_dni INT,
        CONSTRAINT fact_agreement_pk PRIMARY KEY (id_umowy) RELY,
        CONSTRAINT fact_agreement_dim_date_fk FOREIGN KEY (date_key) REFERENCES gold.dim_date
    """,
)
def fact_agreement():
    return agreement_facts(_current_agreements())


@dp.materialized_view(
    name="gold.dim_change",
    comment="Holds the type and comment of each reported change",
    schema="""
        change_key STRING NOT NULL, rodzaj_zmiany STRING, komentarz STRING,
        CONSTRAINT dim_change_pk PRIMARY KEY (change_key) RELY
    """,
)
def dim_change():
    return agreement_changes(_current_agreements()).select("change_key", "rodzaj_zmiany", "komentarz")


@dp.materialized_view(
    name="gold.fact_agreement_change",
    comment="Records the date of each reported change",
    schema="""
        id_umowy STRING NOT NULL, change_key STRING NOT NULL, date_key INT NOT NULL,
        CONSTRAINT fact_agreement_change_pk PRIMARY KEY (change_key) RELY,
        CONSTRAINT fact_agreement_change_fact_agreement_fk FOREIGN KEY (id_umowy) REFERENCES gold.fact_agreement,
        CONSTRAINT fact_agreement_change_dim_change_fk FOREIGN KEY (change_key) REFERENCES gold.dim_change,
        CONSTRAINT fact_agreement_change_dim_date_fk FOREIGN KEY (date_key) REFERENCES gold.dim_date
    """,
)
def fact_agreement_change():
    return agreement_changes(_current_agreements()).select("id_umowy", "change_key", "date_key")
