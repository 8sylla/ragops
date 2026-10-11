import datetime as dt
from dataclasses import replace
from pathlib import Path

from ragops.chunking import chunk_fiche
from ragops.fiches import Section, iter_fiches
from ragops.quality import check_corpus, check_fiche

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"
FICHES = list(iter_fiches(SAMPLE))


def test_chunks_stay_small_and_point_to_their_fiche():
    for f in FICHES:
        chunks = chunk_fiche(f, max_chars=1200, overlap=150)
        assert chunks, f.id
        for c in chunks:
            assert c.fiche_id == f.id and c.url == f.url
            assert len(c.text) <= 1200 + 150 + 1


def test_long_paragraph_is_split_on_sentences():
    f = replace(FICHES[0], sections=[Section("S", " ".join(["Une phrase assez longue."] * 200))])
    chunks = chunk_fiche(f, max_chars=300, overlap=0)
    assert len(chunks) > 5
    assert all(c.text.endswith(".") for c in chunks)


def test_sample_corpus_passes_quality_gate():
    _, report = check_corpus(FICHES)
    assert report.passed() and report.valid == 16


def test_rules_catch_broken_records():
    good = FICHES[0]
    today = dt.date(2026, 10, 11)
    assert check_fiche(good, today).ok
    assert "URL hors service-public.gouv.fr" in check_fiche(replace(good, url="https://example.com/F1"), today).errors
    assert "date de modification dans le futur" in check_fiche(replace(good, modified="2099-01-01"), today).errors
    assert any("trop court" in e for e in check_fiche(replace(good, sections=[]), today).errors)
    assert check_fiche(replace(good, kind="Recherche guidée"), today).excluded


def test_duplicates_fail_the_run():
    _, report = check_corpus(FICHES + [FICHES[0]])
    assert report.duplicates == [FICHES[0].id]
    assert not report.passed()
