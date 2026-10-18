"""Top-k retrieval with a minimum-score cutoff and optional query expansion.

The cutoff is the honesty mechanism: if nothing scores above it, we return
no confident match instead of serving up the least-bad chunk and pretending
it's relevant. An agent calling this gets an explicit "don't know" signal.
"""

from __future__ import annotations

from .embeddings import EmbeddingProvider
from .store import SearchResult, VectorStore

# Small static synonym map for ops terms. A heuristic, not semantics:
# it helps the sparse baseline match "exit 137" to OOMKilled docs.
EXPANSIONS = {
    "crashloop": "crashloop crash looping backoff restart",
    "oom": "oom out of memory oomkilled killed",
    "137": "137 oomkilled out of memory exit code",
    "dns": "dns name resolution nameserver ndots",
    "tls": "tls certificate ssl expired cert",
    "cert": "cert certificate tls ssl expired",
    "5xx": "5xx 500 502 503 bad gateway server error",
    "disk": "disk pressure eviction node filesystem full",
    "latency": "latency slow p99 throttling",
    "throttl": "throttling cpu limits cpu",
    "queue": "queue lag backlog workers consumer",
    "connection": "connection refused timeout exhausted pool",
}


def expand_query(query: str) -> str:
    """Append expansion terms for recognized ops keywords."""
    lowered = query.lower()
    extra = [exp for key, exp in EXPANSIONS.items() if key in lowered]
    return f"{query} {' '.join(extra)}" if extra else query


def retrieve(
    query: str,
    store: VectorStore,
    provider: EmbeddingProvider,
    k: int = 5,
    min_score: float = 0.15,
    expand: bool = False,
    where: dict | None = None,
) -> list[SearchResult]:
    """Return up to k hits scoring >= min_score. Empty list = no confident match."""
    q = expand_query(query) if expand else query
    qvec = provider.embed([q])[0]
    return store.search(qvec, k=k, min_score=min_score, where=where)
