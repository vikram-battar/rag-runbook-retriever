"""Tests for the vector store: ranking, cutoff, filters, persistence."""

import numpy as np
import pytest

from runbook_rag.embeddings import HashedTfidfProvider
from runbook_rag.ingest import Chunk
from runbook_rag.store import VectorStore


def _mini_store():
    chunks = [
        Chunk("pod OOMKilled out of memory raise limits", "oom.md", "OOM", "Fix", ["k8s"], 0),
        Chunk("dns nameserver resolution fails", "dns.md", "DNS", "Fix", ["net"], 1),
        Chunk("disk pressure evict images prune", "disk.md", "Disk", "Fix", ["k8s"], 2),
    ]
    p = HashedTfidfProvider(dim=128).fit([c.text for c in chunks])
    vecs = p.embed([c.text for c in chunks])
    store = VectorStore(p.name, p.state())
    store.add(chunks, vecs)
    return store, p


def test_search_ranks_relevant_chunk_first():
    store, p = _mini_store()
    q = p.embed(["my pod ran out of memory and got OOMKilled"])[0]
    hits = store.search(q, k=3)
    assert hits[0].chunk.source == "oom.md"
    assert hits[0].score > hits[1].score


def test_search_min_score_cutoff():
    store, p = _mini_store()
    q = p.embed(["completely unrelated banana pancake recipe"])[0]
    hits = store.search(q, k=3, min_score=0.99)
    assert hits == []


def test_search_k_limits_results():
    store, p = _mini_store()
    q = p.embed(["pod"])[0]
    assert len(store.search(q, k=2)) == 2


def test_search_metadata_filter():
    store, p = _mini_store()
    q = p.embed(["pod disk memory"])[0]
    hits = store.search(q, k=5, where={"tag": "net"})
    assert all("net" in h.chunk.tags for h in hits)
    assert hits and hits[0].chunk.source == "dns.md"
    hits2 = store.search(q, k=5, where={"source": "disk.md"})
    assert [h.chunk.source for h in hits2] == ["disk.md"]


def test_search_empty_store():
    store = VectorStore("hashed-tfidf", {"dim": 64})
    assert store.search(np.zeros(64), k=3) == []


def test_save_load_roundtrip(tmp_path):
    store, p = _mini_store()
    path = tmp_path / "store.json"
    store.save(path)
    loaded = VectorStore.load(path)
    assert loaded.provider_name == "hashed-tfidf"
    assert len(loaded) == 3
    q = p.embed(["out of memory OOMKilled"])[0]
    assert loaded.search(q, k=1)[0].chunk.source == "oom.md"
    # vectors survived the round trip
    assert np.allclose(loaded.vectors, store.vectors)
