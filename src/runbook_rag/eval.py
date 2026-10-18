"""Eval harness: retrieval recall@k and a faithfulness proxy.

Honest framing, stated up front:

- recall@k is real: for each labeled question, is the expected runbook in
  the top-k retrieved sources?
- faithfulness_proxy is a PROXY, not an LLM judge. There is no answer
  generation in this pipeline, so "faithfulness" here means: of the key
  terms a correct answer should contain, what fraction appear in the
  retrieved chunks? It measures whether retrieval surfaced groundable
  content, not whether a model stayed faithful. A real faithfulness score
  needs a judge model reading a generated answer — that's out of scope
  for the retrieval layer, and pretending otherwise would be dishonest.
"""

from __future__ import annotations

from .embeddings import EmbeddingProvider
from .retrieve import retrieve
from .store import VectorStore


def recall_at_k(ranked_sources: list[str], expected_source: str, k: int) -> float:
    return 1.0 if expected_source in ranked_sources[:k] else 0.0


def faithfulness_proxy(retrieved_texts: list[str], expected_keywords: list[str]) -> float:
    """Fraction of expected key terms found in the retrieved chunks."""
    if not expected_keywords:
        return 1.0
    blob = " ".join(retrieved_texts).lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in blob)
    return hits / len(expected_keywords)


def run_eval(
    store: VectorStore,
    provider: EmbeddingProvider,
    eval_set: list[dict],
    k: int = 3,
    min_score: float = 0.0,
    expand: bool = False,
) -> dict:
    per_query = []
    for item in eval_set:
        hits = retrieve(item["question"], store, provider, k=k, min_score=min_score, expand=expand)
        ranked = [h.chunk.source for h in hits]
        per_query.append(
            {
                "id": item.get("id"),
                "question": item["question"],
                "expected": item["expected_source"],
                "retrieved": ranked,
                "top_score": hits[0].score if hits else 0.0,
                f"recall@{k}": recall_at_k(ranked, item["expected_source"], k),
                "recall@1": recall_at_k(ranked, item["expected_source"], 1),
                "faithfulness_proxy": faithfulness_proxy(
                    [h.chunk.text for h in hits], item.get("expected_keywords", [])
                ),
            }
        )
    n = len(per_query)
    aggregate = {
        "n": n,
        f"recall@{k}": sum(p[f"recall@{k}"] for p in per_query) / n if n else 0.0,
        "recall@1": sum(p["recall@1"] for p in per_query) / n if n else 0.0,
        "mean_top_score": sum(p["top_score"] for p in per_query) / n if n else 0.0,
        "mean_faithfulness_proxy": sum(p["faithfulness_proxy"] for p in per_query) / n if n else 0.0,
        "no_match_count": sum(1 for p in per_query if not p["retrieved"]),
    }
    return {"per_query": per_query, "aggregate": aggregate}
