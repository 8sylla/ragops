"""Parse the Service-Public.gouv.fr XML feed (flux 3.5, « vosdroits ») into plain records.

One file per publication. Practical sheets ("fiches") have IDs like F1341; resources
(R…) and theme pages (N…) are not parsed here.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

DC = "{http://purl.org/dc/elements/1.1/}"
FICHE_FILE = re.compile(r"(?:^|/)(F\d+)\.xml$")
BASE_URL = "https://www.service-public.gouv.fr/particuliers/vosdroits/"


@dataclass
class Section:
    heading: str
    text: str


@dataclass
class Fiche:
    id: str
    title: str
    url: str
    kind: str  # e.g. "Fiche d'information", "Question-réponse", "Recherche guidée"
    theme: str | None
    dossier: str | None
    description: str
    modified: str | None  # YYYY-MM-DD
    sections: list[Section] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(s.text for s in self.sections)

    def to_dict(self) -> dict:
        return asdict(self)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _text(el: ET.Element) -> str:
    return _clean("".join(el.itertext()))


def _paragraphs(el: ET.Element, skip: ET.Element | None = None) -> list[str]:
    """Paragraph texts under `el`, in document order, without those inside `skip`."""
    skipped = {id(node) for node in skip.iter()} if skip is not None else set()
    out: list[str] = []
    for p in el.iter("Paragraphe"):
        if id(p) in skipped:
            continue
        t = _text(p)
        if t and (not out or out[-1] != t):
            out.append(t)
    return out


def _titled_blocks(blocks: list[ET.Element]) -> list[Section]:
    sections = []
    for block in blocks:
        titre = block.find("Titre")
        heading = _text(titre) if titre is not None else ""
        paras = _paragraphs(block, skip=titre)
        if paras:
            sections.append(Section(heading, "\n".join(paras)))
    return sections


def parse_fiche(xml: bytes | str) -> Fiche:
    root = ET.fromstring(xml)
    if root.tag != "Publication":
        raise ValueError(f"not a Publication document: <{root.tag}>")
    fid = root.get("ID") or ""
    modified = re.search(r"\d{4}-\d{2}-\d{2}", root.findtext(f"{DC}date") or "")

    sections: list[Section] = []
    intro = root.find("Introduction")
    if intro is not None and (paras := _paragraphs(intro)):
        sections.append(Section("Introduction", "\n".join(paras)))

    texte = root.find("Texte")
    if texte is not None:
        chapitres = texte.findall("Chapitre")
        if chapitres:
            sections += _titled_blocks(chapitres)
        elif paras := _paragraphs(texte):
            sections.append(Section("", "\n".join(paras)))

    # "Fiches conditionnées": one block per situation (salarié, fonctionnaire…).
    sections += _titled_blocks(root.findall("ListeSituations/Situation"))

    return Fiche(
        id=fid,
        title=_clean(root.findtext(f"{DC}title") or ""),
        url=root.get("spUrl") or BASE_URL + fid,
        kind=root.get("type") or "",
        theme=root.findtext("Theme/Titre"),
        dossier=root.findtext("DossierPere/Titre"),
        description=_clean(root.findtext(f"{DC}description") or ""),
        modified=modified.group(0) if modified else None,
        sections=sections,
    )


def iter_fiches(source: str | Path) -> Iterator[Fiche]:
    """Fiches from a directory of XML files or from the official zip archive."""
    source = Path(source)
    if source.is_dir():
        for path in sorted(source.glob("F*.xml")):
            yield parse_fiche(path.read_bytes())
    elif zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            for name in sorted(z.namelist()):
                if FICHE_FILE.search(name):
                    yield parse_fiche(z.read(name))
    else:
        raise FileNotFoundError(f"expected a directory or a zip archive: {source}")
