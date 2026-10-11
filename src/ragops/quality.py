"""Data-quality rules applied between the bronze and silver layers.

Errors block a fiche (it goes to quarantine); a run fails when the error rate is
above the tolerated threshold, so a broken feed never reaches the index.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass, field

from .fiches import Fiche

ID_PATTERN = re.compile(r"^F\d+$")
# www. for individuals, entreprendre. for the 12 fiches shared with the business site.
URL_PATTERN = re.compile(r"^https://([a-z-]+\.)?service-public\.gouv\.fr/")
MIN_TEXT_CHARS = 200
NAVIGATION_KINDS = {"Recherche guidée"}  # decision trees linking to other fiches


@dataclass
class Verdict:
    fiche_id: str
    errors: list[str] = field(default_factory=list)
    excluded: str | None = None  # valid page, but nothing to index

    @property
    def ok(self) -> bool:
        return not self.errors and self.excluded is None


def check_fiche(fiche: Fiche, today: dt.date | None = None) -> Verdict:
    today = today or dt.date.today()
    v = Verdict(fiche.id)
    if fiche.kind in NAVIGATION_KINDS:
        v.excluded = "page de navigation (recherche guidée)"
        return v
    if not ID_PATTERN.match(fiche.id):
        v.errors.append("identifiant invalide")
    if not fiche.title:
        v.errors.append("titre vide")
    if not URL_PATTERN.match(fiche.url):
        v.errors.append("URL hors service-public.gouv.fr")
    if fiche.modified is None:
        v.errors.append("date de modification absente")
    else:
        try:
            if dt.date.fromisoformat(fiche.modified) > today:
                v.errors.append("date de modification dans le futur")
        except ValueError:
            v.errors.append("date de modification illisible")
    if len(fiche.text) < MIN_TEXT_CHARS:
        v.errors.append(f"contenu trop court (< {MIN_TEXT_CHARS} caractères)")
    return v


@dataclass
class QualityReport:
    total: int
    valid: int
    excluded: int
    rejected: int
    duplicates: list[str]
    reasons: dict[str, int]
    error_rate: float

    def passed(self, max_error_rate: float = 0.01) -> bool:
        return not self.duplicates and self.error_rate <= max_error_rate


def check_corpus(fiches: list[Fiche], today: dt.date | None = None) -> tuple[list[Verdict], QualityReport]:
    verdicts = [check_fiche(f, today) for f in fiches]
    counts = Counter(f.id for f in fiches)
    duplicates = sorted(i for i, n in counts.items() if n > 1)
    for v in verdicts:
        if v.fiche_id in duplicates:
            v.errors.append("identifiant en double")
    reasons = Counter(e for v in verdicts for e in v.errors)
    rejected = sum(1 for v in verdicts if v.errors)
    excluded = sum(1 for v in verdicts if v.excluded and not v.errors)
    checked = len(fiches) - excluded
    report = QualityReport(
        total=len(fiches),
        valid=sum(1 for v in verdicts if v.ok),
        excluded=excluded,
        rejected=rejected,
        duplicates=duplicates,
        reasons=dict(reasons),
        error_rate=rejected / checked if checked else 0.0,
    )
    return verdicts, report
