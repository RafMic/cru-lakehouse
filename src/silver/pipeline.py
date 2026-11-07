"""Silver tables built from bronze.agreements_detail_raw."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from silver.parsing import (
    explode_parties,
    latest_per_party,
    parse_agreements,
    with_party_identity_key,
)

# Databricks recommends these on every table a materialized view reads.
_INCREMENTAL_REFRESH_PROPERTIES = {
    "delta.enableDeletionVectors": "true",
    "delta.enableRowTracking": "true",
    "delta.enableChangeDataFeed": "true",
}


@dp.view
@dp.expect_or_drop("valid_id", "id_umowy IS NOT NULL")
@dp.expect_or_drop("valid_modification_date", "data_modyfikacji IS NOT NULL")
@dp.expect("has_value_or_confidential", "wartosc_przedmiotu IS NOT NULL OR niejawnosc_wartosci_przedmiotu IS NOT NULL")
@dp.expect("has_parties", "strony IS NOT NULL AND size(strony) > 0")
def _agreements_detail_parsed():
    return parse_agreements(spark.readStream.table("bronze.agreements_detail_raw"))


dp.create_streaming_table(
    "agreements",
    comment="Tracks the version history of each agreement as SCD type 2",
    table_properties=_INCREMENTAL_REFRESH_PROPERTIES,
)

dp.create_auto_cdc_flow(
    target="agreements",
    source="_agreements_detail_parsed",
    keys=["id_umowy"],
    # Two versions modified on the same date are ordered by when their landing file was written.
    sequence_by=F.struct("data_modyfikacji", "_file_modification_time"),
    except_column_list=["_file_modification_time"],
    stored_as_scd_type=2,
)


@dp.materialized_view(
    comment="Lists the parties of each agreement version, with that version's validity period",
    table_properties=_INCREMENTAL_REFRESH_PROPERTIES,
)
@dp.expect("registering_party_is_public", "party_key <> 0 OR rodzaj <=> 'JSFP'")
def parties():
    """Leave the address details to addresses, which each party references through address_id."""
    return with_party_identity_key(
        explode_parties(
            spark.read.table("agreements"),
            "id_umowy",
            "data_modyfikacji",
            "__START_AT",
            "__END_AT",
        )
    ).drop(
        "ulica",
        "numer_nieruchomosci",
        "numer_lokalu",
        "wojewodztwo",
        "powiat",
        "gmina_miasto_dzielnica",
        "miejscowosc",
        "kod_pocztowy",
    )


@dp.materialized_view(
    comment="Deduplicates the parties across agreements",
    table_properties=_INCREMENTAL_REFRESH_PROPERTIES,
)
def party_identities():
    """Return each party once, with the details from its most recently modified agreement."""
    current = spark.read.table("parties").filter("__END_AT IS NULL")
    return latest_per_party(current).drop("id_umowy", "party_key", "__START_AT", "__END_AT")


@dp.view
def _party_addresses():
    """Return the parties of each bronze record as the streaming source of addresses."""
    return explode_parties(
        spark.readStream.table("_agreements_detail_parsed"),
        "id_umowy",
        "data_modyfikacji",
        "_file_modification_time",
    ).where("address_id IS NOT NULL")


dp.create_streaming_table(
    "addresses",
    comment="Deduplicates the addresses of all parties",
    table_properties=_INCREMENTAL_REFRESH_PROPERTIES,
)

dp.create_auto_cdc_flow(
    target="addresses",
    source="_party_addresses",
    keys=["address_id"],
    sequence_by=F.struct("data_modyfikacji", "_file_modification_time"),
    column_list=[
        "address_id",
        "ulica",
        "numer_nieruchomosci",
        "numer_lokalu",
        "wojewodztwo",
        "powiat",
        "gmina_miasto_dzielnica",
        "miejscowosc",
        "kod_pocztowy",
    ],
    stored_as_scd_type=1,
)
