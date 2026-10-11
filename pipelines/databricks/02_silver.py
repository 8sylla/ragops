# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Silver : fiches structurées et contrôles qualité
# MAGIC
# MAGIC Parse les fiches (`F…`) avec le même code que l'API (`src/ragops`), applique les règles de
# MAGIC `ragops.quality`, écrit les fiches valides dans `silver_fiches` et les rejets, avec leur motif,
# MAGIC dans `silver_quarantine`. Le run échoue si le taux d'erreur dépasse le seuil : un flux cassé
# MAGIC n'atteint jamais l'index.
# MAGIC
# MAGIC Environ 3 000 fiches : le parsing tient sur le driver. Au-delà, passer par `mapInPandas` et un wheel.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "ragops")
dbutils.widgets.text("max_error_rate", "0.01")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
max_error_rate = float(dbutils.widgets.get("max_error_rate"))

# COMMAND ----------

import os
import sys

# Dossier Git Databricks : le notebook est dans pipelines/databricks, le code dans src/.
sys.path.insert(0, os.path.abspath("../../src"))

from ragops.fiches import parse_fiche
from ragops.quality import check_corpus

# COMMAND ----------

rows = spark.table(f"{catalog}.{schema}.bronze_publications").filter("doc_type = 'F'").select("doc_id", "xml").collect()
fiches, parse_errors = [], []
for row in rows:
    try:
        fiches.append(parse_fiche(row.xml))
    except Exception as exc:  # malformed XML goes to quarantine, it does not stop the run
        parse_errors.append((row.doc_id, f"XML illisible : {exc}"))

verdicts, report = check_corpus(fiches)
print(report)

# COMMAND ----------

from pyspark.sql import Row

valid = [f for f, v in zip(fiches, verdicts) if v.ok]
silver = spark.createDataFrame(
    [
        Row(
            fiche_id=f.id,
            title=f.title,
            url=f.url,
            kind=f.kind,
            theme=f.theme,
            dossier=f.dossier,
            description=f.description,
            modified=f.modified,
            sections=[Row(heading=s.heading, text=s.text) for s in f.sections],
            text_chars=len(f.text),
        )
        for f in valid
    ]
)
silver.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.{schema}.silver_fiches")

quarantine = [(v.fiche_id, "; ".join(v.errors)) for v in verdicts if v.errors] + parse_errors
excluded = [(v.fiche_id, v.excluded) for v in verdicts if v.excluded and not v.errors]
spark.createDataFrame(
    [Row(fiche_id=i, status="rejected", reason=r) for i, r in quarantine]
    + [Row(fiche_id=i, status="excluded", reason=r) for i, r in excluded],
    "fiche_id string, status string, reason string",
).write.mode("overwrite").saveAsTable(f"{catalog}.{schema}.silver_quarantine")

# COMMAND ----------

if not report.passed(max_error_rate) or parse_errors:
    raise RuntimeError(
        f"Seuil de qualité dépassé : {report.rejected} rejets, {len(parse_errors)} XML illisibles, "
        f"doublons {report.duplicates}. Voir {catalog}.{schema}.silver_quarantine."
    )
print(f"{len(valid)} fiches valides, {report.excluded} pages de navigation exclues, {report.rejected} rejets.")
