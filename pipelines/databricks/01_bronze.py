# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Bronze : ingestion brute du flux Service-Public.gouv.fr
# MAGIC
# MAGIC Télécharge l'archive XML officielle (flux 3.5, Licence Ouverte / Etalab 2.0), la dépose dans un volume
# MAGIC Unity Catalog, puis charge chaque fichier tel quel dans la table Delta `bronze_publications`.
# MAGIC Rien n'est transformé ici : la couche bronze garde la source rejouable.
# MAGIC
# MAGIC Si le calcul serverless n'a pas accès à internet, déposer `vosdroits-latest.zip` à la main dans
# MAGIC le volume `raw` et laisser `source_url` vide.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "ragops")
dbutils.widgets.text("source_url", "https://lecomarquage.service-public.gouv.fr/vdd/3.5/part/zip/vosdroits-latest.zip")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
source_url = dbutils.widgets.get("source_url").strip()

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.raw")

# COMMAND ----------

import datetime as dt
import io
import os
import urllib.request
import zipfile

run_date = dt.date.today().isoformat()
volume = f"/Volumes/{catalog}/{schema}/raw"
landing = f"{volume}/vosdroits/{run_date}"
os.makedirs(landing, exist_ok=True)

if source_url:
    archive = urllib.request.urlopen(source_url, timeout=300).read()
else:
    archive = open(f"{volume}/vosdroits-latest.zip", "rb").read()

with zipfile.ZipFile(io.BytesIO(archive)) as z:
    names = [n for n in z.namelist() if n.endswith(".xml")]
    for name in names:
        with open(f"{landing}/{os.path.basename(name)}", "wb") as out:
            out.write(z.read(name))

print(f"{len(names)} fichiers XML déposés dans {landing}")

# COMMAND ----------

from pyspark.sql import functions as F

bronze = (
    spark.read.format("binaryFile")
    .option("pathGlobFilter", "*.xml")
    .load(landing)
    .select(
        F.regexp_extract("path", r"([A-Z]+\d+)\.xml$", 1).alias("doc_id"),
        F.col("path").alias("source_path"),
        F.decode("content", "UTF-8").alias("xml"),
    )
    .withColumn("doc_type", F.substring("doc_id", 1, 1))
    .withColumn("run_date", F.lit(run_date))
    .withColumn("ingested_at", F.current_timestamp())
)

(
    bronze.write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{catalog}.{schema}.bronze_publications")
)

display(spark.table(f"{catalog}.{schema}.bronze_publications").groupBy("doc_type").count().orderBy("doc_type"))
