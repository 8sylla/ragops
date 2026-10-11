"""Split fiches into passages small enough to retrieve and quote."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .fiches import Fiche


@dataclass
class Chunk:
    id: str  # "<fiche id>-<n>"
    fiche_id: str
    title: str
    url: str
    heading: str
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def _pieces(paragraph: str, max_chars: int) -> list[str]:
    """A paragraph longer than max_chars, cut at sentence boundaries."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    out, current = [], ""
    for sentence in re.split(r"(?<=[.!?:;])\s+", paragraph):
        if current and len(current) + 1 + len(sentence) > max_chars:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


def _tail(text: str, n: int) -> str:
    """The last ~n characters of text, starting on a word boundary."""
    if n <= 0 or len(text) <= n:
        return text if n > 0 else ""
    cut = text[-n:]
    return cut[cut.find(" ") + 1 :] if " " in cut else cut


def chunk_fiche(fiche: Fiche, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    """Passages of at most ~max_chars, never crossing a section, with a small overlap."""
    chunks: list[Chunk] = []
    for section in fiche.sections:
        paragraphs = [p for para in section.text.split("\n") for p in _pieces(para, max_chars)]
        current = ""
        for para in paragraphs:
            if current and len(current) + 1 + len(para) > max_chars:
                chunks.append(_make(fiche, section.heading, current, len(chunks)))
                current = f"{_tail(current, overlap)}\n{para}".strip()
            else:
                current = f"{current}\n{para}".strip()
        if current:
            chunks.append(_make(fiche, section.heading, current, len(chunks)))
    return chunks


def _make(fiche: Fiche, heading: str, text: str, n: int) -> Chunk:
    return Chunk(
        id=f"{fiche.id}-{n}",
        fiche_id=fiche.id,
        title=fiche.title,
        url=fiche.url,
        heading=heading,
        text=text,
    )
