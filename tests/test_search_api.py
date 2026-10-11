from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ragops.evaluate import Question, score
from ragops.pipeline import build

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built():
    return build(ROOT / "data" / "sample")


def test_search_finds_the_right_fiche(built):
    hits = built.retriever.search_fiches("renouveler ma carte d'identité en mairie", k=3)
    assert hits[0].chunk.fiche_id == "F1341"
    assert len({h.chunk.fiche_id for h in hits}) == len(hits)


def test_score_counts_ranks(built):
    s = score(built.retriever, [Question("procuration de vote", "F1604"), Question("procuration de vote", "F0")])
    assert s.n == 2 and s.hit_at_3 == 0.5 and s.misses[0]["expected"] == "F0"


def test_score_accepts_several_answers(built):
    s = score(built.retriever, [Question("procuration de vote", ["F0", "F1604"])])
    assert s.hit_at_1 == 1.0


def test_index_round_trip(built, tmp_path):
    path = tmp_path / "index.pkl"
    built.retriever.save(path)
    from ragops.retriever import TfidfRetriever

    again = TfidfRetriever.load(path)
    assert again.search("APL locataire")[0].chunk.fiche_id == built.retriever.search("APL locataire")[0].chunk.fiche_id


def test_api(monkeypatch):
    monkeypatch.setenv("RAGOPS_CORPUS", str(ROOT / "data" / "sample"))
    from ragops.api import app

    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        r = client.get("/search", params={"q": "bourse de lycée montant"}).json()
        assert r["results"][0]["fiche"] == "F616"
        a = client.post("/ask", json={"question": "Comment voter par procuration ?"}).json()
        assert a["sources"][0]["url"].endswith("F1604")
        assert client.post("/ask", json={"question": "xy"}).status_code == 422
        assert "ragops_requests_total" in client.get("/metrics/").text
