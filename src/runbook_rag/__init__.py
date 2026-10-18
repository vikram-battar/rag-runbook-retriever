"""runbook_rag: a small RAG pipeline over operational runbooks.

The retrieval layer an incident-diagnosis agent would call. Honest about
what's real and what's a proxy — see README.md.
"""

from .ingest import Chunk, chunk_fixed, chunk_sections, ingest_dir, ingest_runbook
from .embeddings import (
    EmbeddingProvider,
    HashedTfidfProvider,
    OpenAIProvider,
    SentenceTransformerProvider,
    build_provider,
    get_provider,
)
from .store import SearchResult, VectorStore
from .retrieve import expand_query, retrieve
from .eval import faithfulness_proxy, recall_at_k, run_eval

__all__ = [
    "Chunk",
    "chunk_fixed",
    "chunk_sections",
    "ingest_dir",
    "ingest_runbook",
    "EmbeddingProvider",
    "HashedTfidfProvider",
    "OpenAIProvider",
    "SentenceTransformerProvider",
    "build_provider",
    "get_provider",
    "SearchResult",
    "VectorStore",
    "expand_query",
    "retrieve",
    "faithfulness_proxy",
    "recall_at_k",
    "run_eval",
]
