# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Gold : passages prêts pour la recherche
# MAGIC
# MAGIC Découpe chaque fiche valide en passages (même logique que `ragops.chunking`), écrit la table
# MAGIC `gold_chunks` et exporte une copie Parquet dans le volume `exports`, que l'API peut charger.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "ragops")
dbutils.widgets.text("max_chars", "1200")
dbutils.widgets.text("overlap", "150")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
max_chars = int(dbutils.widgets.get("max_chars"))
overlap = int(dbutils.widgets.get("overlap"))

# COMMAND ----------

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

from ragops.chunking import chunk_fiche
from ragops.fiches import Fiche, Section

# COMMAND ----------

from pyspark.sql import Row

fiches = [
    Fiche(
        id=r.fiche_id,
        title=r.title,
        url=r.url,
        kind=r.kind,
        theme=r.theme,
        dossier=r.dossier,
        description=r.description,
        modified=r.modified,
        sections=[Section(s.heading, s.text) for s in r.sections],
    )
    for r in spark.table(f"{catalog}.{schema}.silver_fiches").collect()
]

chunks = spark.createDataFrame(
    [Row(**c.to_dict(), chars=len(c.text)) for f in fiches for c in chunk_fiche(f, max_chars, overlap)]
)
chunks.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{schema}.gold_chunks")

# COMMAND ----------

spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.exports")
chunks.write.mode("overwrite").parquet(f"/Volumes/{catalog}/{schema}/exports/gold_chunks")

display(
    spark.table(f"{catalog}.{schema}.gold_chunks").selectExpr(
        "count(*) as passages", "count(distinct fiche_id) as fiches", "round(avg(chars)) as caracteres_moyens", "max(chars) as caracteres_max"
    )
)
