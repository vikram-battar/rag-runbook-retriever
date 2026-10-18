"""Tests for retrieval: cutoff behavior and query expansion."""

import numpy as np

from runbook_rag.embeddings import HashedTfidfProvider
from runbook_rag.ingest import Chunk
from runbook_rag.retrieve import expand_query, retrieve
from runbook_rag.store import VectorStore


def _store():
    chunks = [
        Chunk("pod OOMKilled out of memory raise limits", "oom.md", "OOM", "", ["k8s"], 0),
        Chunk("dns nameserver resolution fails", "dns.md", "DNS", "", ["net"], 1),
    ]
    p = HashedTfidfProvider(dim=128).fit([c.text for c in chunks])
    s = VectorStore(p.name, p.state())
    s.add(chunks, p.embed([c.text for c in chunks]))
    return s, p


def test_retrieve_returns_ranked_hits():
    s, p = _store()
    hits = retrieve("pod out of memory", s, p, k=2, min_score=0.0)
    assert hits[0].chunk.source == "oom.md"


def test_retrieve_cutoff_returns_empty_instead_of_guessing():
    s, p = _store()
    hits = retrieve("quantum banana pancakes", s, p, k=2, min_score=0.5)
    assert hits == []


def test_expand_query_adds_synonyms():
    expanded = expand_query("pod crashloop exit 137")
    assert "oomkilled" in expanded.lower()
    assert "backoff" in expanded.lower()
    # no recognized keyword -> unchanged
    assert expand_query("hello world") == "hello world"


def test_retrieve_with_expansion_still_works():
    s, p = _store()
    hits = retrieve("exit 137 crashloop", s, p, k=2, min_score=0.0, expand=True)
    assert hits  # expansion shouldn't break retrieval
    assert hits[0].chunk.source == "oom.md"
