from pathlib import Path

import pytest

from ragops.fiches import iter_fiches, parse_fiche

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample"


def test_parses_real_fiche():
    f = parse_fiche((SAMPLE / "F1341.xml").read_bytes())
    assert f.id == "F1341"
    assert f.title.startswith("Carte d'identité")
    assert f.url.endswith("/vosdroits/F1341")
    assert f.kind == "Fiche d'information conditionnée"
    assert f.theme and f.dossier == "Carte d'identité"
    assert f.modified and len(f.modified) == 10
    assert [s.heading for s in f.sections][:2] == ["Introduction", "En France"]
    assert "mairie" in f.text


def test_chapter_titles_are_headings_not_body():
    f = parse_fiche((SAMPLE / "F2918.xml").read_bytes())
    heading = next(s.heading for s in f.sections if s.heading.startswith("À quel âge"))
    body = next(s.text for s in f.sections if s.heading == heading)
    assert heading not in body


def test_situations_are_parsed():
    xml = """<Publication ID="F1" type="Fiche d'information conditionnée"
      spUrl="https://www.service-public.gouv.fr/particuliers/vosdroits/F1"
      xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>Titre</dc:title><dc:date>modified 2026-01-02</dc:date>
      <ListeSituations><Situation><Titre><Paragraphe>Salarié</Paragraphe></Titre>
      <Texte><Paragraphe>Règle pour le salarié.</Paragraphe></Texte></Situation></ListeSituations>
    </Publication>"""
    f = parse_fiche(xml)
    assert [(s.heading, s.text) for s in f.sections] == [("Salarié", "Règle pour le salarié.")]
    assert f.modified == "2026-01-02"


def test_rejects_other_documents():
    with pytest.raises(ValueError):
        parse_fiche("<Noeud ID='N1'/>")


def test_iter_directory():
    ids = [f.id for f in iter_fiches(SAMPLE)]
    assert len(ids) == 16 and len(set(ids)) == 16
