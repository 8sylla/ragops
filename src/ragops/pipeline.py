"""Local version of the Databricks pipeline: fiches → quality checks → passages → index."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from .chunking import Chunk, chunk_fiche
from .fiches import Fiche, iter_fiches
from .quality import QualityReport, check_corpus
from .retriever import TfidfRetriever


@dataclass
class Build:
    fiches: list[Fiche]
    chunks: list[Chunk]
    report: QualityReport
    retriever: TfidfRetriever


def build(source: str | Path, max_error_rate: float = 0.01) -> Build:
    fiches = list(iter_fiches(source))
    verdicts, report = check_corpus(fiches)
    if not report.passed(max_error_rate):
        raise RuntimeError(f"quality gate failed: {report}")
    valid = [f for f, v in zip(fiches, verdicts) if v.ok]
    chunks = [c for f in valid for c in chunk_fiche(f)]
    return Build(valid, chunks, report, TfidfRetriever(chunks))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the search index from the fiches.")
    parser.add_argument("--corpus", default="data/sample", help="directory of XML fiches or the official zip")
    parser.add_argument("--out", default="index.pkl")
    args = parser.parse_args()
    b = build(args.corpus)
    b.retriever.save(args.out)
    r = b.report
    print(f"{r.total} fiches · {r.valid} indexées · {r.excluded} exclues · {r.rejected} rejetées · {len(b.chunks)} passages → {args.out}")


if __name__ == "__main__":
    main()
