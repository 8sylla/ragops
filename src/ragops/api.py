"""HTTP API: search the fiches and answer with sources.

Answers are extractive for now (the best passages, each with its source); the LLM
generation step comes with milestone 2, behind the same evaluation gate.
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field

from .pipeline import build
from .retriever import TfidfRetriever

REQUESTS = Counter("ragops_requests_total", "Requests served", ["endpoint"])
LATENCY = Histogram("ragops_request_seconds", "Request latency", ["endpoint"])
EMPTY = Counter("ragops_empty_results_total", "Queries with no passage found")

state: dict[str, TfidfRetriever] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    index = os.getenv("RAGOPS_INDEX")
    if index and os.path.exists(index):
        state["retriever"] = TfidfRetriever.load(index)
    else:
        state["retriever"] = build(os.getenv("RAGOPS_CORPUS", "data/sample")).retriever
    yield
    state.clear()


app = FastAPI(title="RAGOps", version="0.1.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def measure(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    endpoint = request.url.path
    if not endpoint.startswith("/metrics"):
        REQUESTS.labels(endpoint).inc()
        LATENCY.labels(endpoint).observe(time.perf_counter() - start)
    return response


def retriever() -> TfidfRetriever:
    if "retriever" not in state:
        raise HTTPException(503, "index not loaded")
    return state["retriever"]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "passages": len(retriever().chunks)}


def _source(hit) -> dict:
    c = hit.chunk
    return {
        "fiche": c.fiche_id,
        "title": c.title,
        "section": c.heading,
        "url": c.url,
        "score": round(hit.score, 4),
        "passage": c.text,
    }


@app.get("/search")
def search(q: str, k: int = 5) -> dict:
    if not q.strip():
        raise HTTPException(422, "empty query")
    hits = retriever().search_fiches(q, k=max(1, min(k, 20)))
    if not hits:
        EMPTY.inc()
    return {"query": q, "results": [_source(h) for h in hits]}


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.post("/ask")
def ask(body: Question) -> dict:
    hits = retriever().search_fiches(body.question, k=3)
    if not hits:
        EMPTY.inc()
        return {"answer": "Je ne trouve pas de fiche qui réponde à cette question.", "sources": []}
    best = hits[0].chunk
    return {
        "answer": f"D'après la fiche « {best.title} » ({best.heading or 'présentation'}) :\n{best.text}",
        "sources": [_source(h) for h in hits],
    }
