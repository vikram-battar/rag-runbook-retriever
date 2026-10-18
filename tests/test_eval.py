"""Tests for the eval harness: metric math and end-to-end scoring."""

from runbook_rag.embeddings import HashedTfidfProvider
from runbook_rag.eval import faithfulness_proxy, recall_at_k, run_eval
from runbook_rag.ingest import Chunk
from runbook_rag.store import VectorStore


def test_recall_at_k():
    ranked = ["a.md", "b.md", "c.md"]
    assert recall_at_k(ranked, "a.md", 1) == 1.0
    assert recall_at_k(ranked, "b.md", 1) == 0.0
    assert recall_at_k(ranked, "b.md", 3) == 1.0
    assert recall_at_k(ranked, "z.md", 3) == 0.0
    assert recall_at_k([], "a.md", 3) == 0.0


def test_faithfulness_proxy():
    texts = ["The pod was OOMKilled. Raise the memory limits."]
    assert faithfulness_proxy(texts, ["oomkilled", "memory", "limits"]) == 1.0
    assert faithfulness_proxy(texts, ["oomkilled", "banana"]) == 0.5
    assert faithfulness_proxy(texts, []) == 1.0
    assert faithfulness_proxy([], ["x"]) == 0.0


def test_run_eval_end_to_end():
    chunks = [
        Chunk("pod OOMKilled out of memory raise memory limits", "oom.md", "OOM", "", [], 0),
        Chunk("dns nameserver resolution fails check resolv.conf", "dns.md", "DNS", "", [], 1),
    ]
    p = HashedTfidfProvider(dim=128).fit([c.text for c in chunks])
    store = VectorStore(p.name, p.state())
    store.add(chunks, p.embed([c.text for c in chunks]))
    eval_set = [
        {
            "id": "e1",
            "question": "pod ran out of memory and got OOMKilled",
            "expected_source": "oom.md",
            "expected_keywords": ["oomkilled", "memory", "limits"],
        },
        {
            "id": "e2",
            "question": "cannot resolve dns names",
            "expected_source": "dns.md",
            "expected_keywords": ["dns", "nameserver"],
        },
    ]
    report = run_eval(store, p, eval_set, k=2, min_score=0.0)
    agg = report["aggregate"]
    assert agg["n"] == 2
    assert agg["recall@2"] == 1.0
    assert agg["recall@1"] == 1.0
    assert agg["mean_faithfulness_proxy"] == 1.0
    assert len(report["per_query"]) == 2
    assert report["per_query"][0]["expected"] == "oom.md"


def test_run_eval_counts_misses():
    chunks = [Chunk("totally unrelated content here", "x.md", "X", "", [], 0)]
    p = HashedTfidfProvider(dim=64).fit([c.text for c in chunks])
    store = VectorStore(p.name, p.state())
    store.add(chunks, p.embed([c.text for c in chunks]))
    eval_set = [
        {"id": "e1", "question": "something else entirely", "expected_source": "missing.md",
         "expected_keywords": ["zzz"]},
    ]
    report = run_eval(store, p, eval_set, k=3, min_score=0.99)
    assert report["aggregate"]["recall@3"] == 0.0
    assert report["aggregate"]["no_match_count"] == 1
