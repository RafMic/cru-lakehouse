# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze layer
# MAGIC
# MAGIC Auto Loader appends each new agreement detail file in the landing volume to `bronze.agreements_detail_raw`.
# MAGIC
# MAGIC Every column is text, including nested objects such as `okresObowiazywania`, and Silver converts them to typed columns.
# MAGIC
# MAGIC The search pages stay as files in the landing volume, since Silver reads only the details.

# COMMAND ----------

from pyspark.sql import functions as F

from cru_ingestion.config import Settings

settings = Settings.from_env()
checkpoint_path = f"{settings.landing_volume_path}/_bronze_checkpoints/agreements_detail_raw"

# COMMAND ----------

(
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", checkpoint_path)
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    # Loads only complete files, skipping the .tmp files write_json renames once written.
    .option("pathGlobFilter", "*.json")
    .load(f"{settings.landing_volume_path}/agreements_detail")
    .select(
        "*",
        F.col("_metadata.file_path").alias("_source_file"),
        F.col("_metadata.file_modification_time").alias("_file_modification_time"),
        F.current_timestamp().alias("_ingested_at"),
    )
    .writeStream.format("delta")
    .option("checkpointLocation", checkpoint_path)
    # Adds the new columns from schema evolution to the table too.
    .option("mergeSchema", "true")
    .trigger(availableNow=True)
    .toTable(f"{settings.catalog}.bronze.agreements_detail_raw")
    .awaitTermination()
)
