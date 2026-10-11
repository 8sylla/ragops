"""Lexical baseline retriever (TF-IDF).

It runs anywhere (laptop, CI, a small pod) and gives the quality gate a reference
score. A dense retriever (embeddings + pgvector) must beat it to replace it.
"""

from __future__ import annotations

import pickle
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from .chunking import Chunk

# Short French stop-word list (accents removed, like the normalised text).
STOP_WORDS = sorted(
    set(
        """a ai au aux avec c ce ces cet cette d dans de des du elle elles en est et
        etre il ils j je l la le les leur leurs lui m ma mais me mes moi mon n ne nos
        notre nous on ou par pas peut peuvent pour qu que qui s sa se ses si son sont
        sur ta te tes toi ton tu un une vos votre vous y faut faire comment quel quelle
        quels quelles quoi est-ce dois doit""".split()
    )
)


def normalize(text: str) -> str:
    text = text.lower().replace("’", " ").replace("'", " ")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


@dataclass
class Hit:
    chunk: Chunk
    score: float


class TfidfRetriever:
    def __init__(self, chunks: list[Chunk]):
        if not chunks:
            raise ValueError("cannot index an empty corpus")
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(
            preprocessor=normalize,
            stop_words=STOP_WORDS,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
        )
        # The title is repeated so it weighs more than any single sentence.
        docs = [f"{c.title} {c.title} {c.heading} {c.text}" for c in chunks]
        self.matrix = self.vectorizer.fit_transform(docs)

    def search(self, query: str, k: int = 5) -> list[Hit]:
        scores = linear_kernel(self.vectorizer.transform([query]), self.matrix).ravel()
        best = scores.argsort()[::-1][:k]
        return [Hit(self.chunks[i], float(scores[i])) for i in best if scores[i] > 0]

    def search_fiches(self, query: str, k: int = 3, pool: int = 50) -> list[Hit]:
        """Best passage of each of the k best fiches."""
        seen: set[str] = set()
        hits = []
        for hit in self.search(query, k=pool):
            if hit.chunk.fiche_id not in seen:
                seen.add(hit.chunk.fiche_id)
                hits.append(hit)
            if len(hits) == k:
                break
        return hits

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(pickle.dumps(self))

    @staticmethod
    def load(path: str | Path) -> "TfidfRetriever":
        obj = pickle.loads(Path(path).read_bytes())
        if not isinstance(obj, TfidfRetriever):
            raise TypeError(f"{path} is not a TfidfRetriever index")
        return obj
