"""Retrieval evaluation and quality gate.

Each reference question names the fiche that answers it. A version is deployable
only if the right fiche comes back high enough, often enough.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .pipeline import build
from .retriever import TfidfRetriever


@dataclass
class Question:
    question: str
    expected: str | list[str]  # fiche id, or every fiche that fully answers

    @property
    def accepted(self) -> set[str]:
        return {self.expected} if isinstance(self.expected, str) else set(self.expected)


@dataclass
class Scores:
    n: int
    hit_at_1: float
    hit_at_3: float
    mrr_at_10: float
    misses: list[dict]


def load_questions(path: str | Path) -> list[Question]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [Question(**json.loads(line)) for line in lines if line.strip()]


def score(retriever: TfidfRetriever, questions: list[Question]) -> Scores:
    hit1 = hit3 = rr = 0.0
    misses = []
    for q in questions:
        ranked = [h.chunk.fiche_id for h in retriever.search_fiches(q.question, k=10)]
        rank = next((i + 1 for i, fid in enumerate(ranked) if fid in q.accepted), None)
        hit1 += rank == 1
        hit3 += rank is not None and rank <= 3
        rr += 1 / rank if rank else 0
        if rank is None or rank > 3:
            misses.append({"question": q.question, "expected": q.expected, "rank": rank, "got": ranked[:3]})
    n = len(questions) or 1
    return Scores(len(questions), hit1 / n, hit3 / n, rr / n, misses)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate retrieval and enforce the quality gate.")
    p.add_argument("--corpus", default="data/sample")
    p.add_argument("--questions", default="eval/questions.jsonl")
    p.add_argument("--min-hit3", type=float, default=0.85)
    p.add_argument("--min-mrr", type=float, default=0.7)
    p.add_argument("--report", help="write the scores as JSON")
    args = p.parse_args(argv)

    s = score(build(args.corpus).retriever, load_questions(args.questions))
    print(f"questions : {s.n}")
    print(f"hit@1     : {s.hit_at_1:.2f}")
    print(f"hit@3     : {s.hit_at_3:.2f}  (seuil {args.min_hit3})")
    print(f"MRR@10    : {s.mrr_at_10:.2f}  (seuil {args.min_mrr})")
    for m in s.misses:
        print(f"  manqué : {m['question']!r} attendu {m['expected']}, obtenu {m['got']}")
    if args.report:
        Path(args.report).write_text(json.dumps(asdict(s), ensure_ascii=False, indent=2), encoding="utf-8")

    passed = s.hit_at_3 >= args.min_hit3 and s.mrr_at_10 >= args.min_mrr
    print("seuil de qualité :", "OK" if passed else "ÉCHEC, déploiement bloqué")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
