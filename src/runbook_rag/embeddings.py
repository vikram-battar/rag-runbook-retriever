"""Pluggable embedding providers behind one interface.

Honest framing, stated up front:

- HashedTfidfProvider is a sparse term-overlap baseline. It is NOT semantic
  embeddings. It exists so the whole pipeline runs offline with zero network
  and no heavy dependencies, and so the eval harness has a floor to beat.
- SentenceTransformerProvider and OpenAIProvider are real dense embeddings
  but need their packages / API keys. They are optional.

Provider selection: --provider flag, or RAG_EMBEDDING_PROVIDER env var.
"""

from __future__ import annotations

import abc
import hashlib
import os
import re
from collections import Counter

import numpy as np


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class EmbeddingProvider(abc.ABC):
    """Common interface. embed() returns L2-normalized row vectors."""

    name: str = "base"
    dim: int = 0

    @abc.abstractmethod
    def fit(self, texts: list[str]) -> "EmbeddingProvider":
        """Fit any corpus statistics (e.g. IDF). No-op for dense providers."""

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) array of L2-normalized vectors."""

    def state(self) -> dict:
        """Serializable state needed to re-embed queries later."""
        return {"dim": self.dim}

    @classmethod
    def from_state(cls, state: dict) -> "EmbeddingProvider":
        raise NotImplementedError


class HashedTfidfProvider(EmbeddingProvider):
    """Sparse hashed TF-IDF baseline. Deterministic, offline, no semantics.

    Tokens are hashed into `dim` buckets (signed hashing to reduce collision
    bias), weighted by smoothed IDF fitted on the corpus. Good enough to
    rank runbooks by term overlap; it will not understand synonyms or
    paraphrase — that's exactly what the eval measures.
    """

    name = "hashed-tfidf"

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.idf: np.ndarray | None = None

    @staticmethod
    def _bucket(token: str, dim: int) -> tuple[int, int]:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        return h % dim, 1 if (h >> 8) % 2 == 0 else -1

    def fit(self, texts: list[str]) -> "HashedTfidfProvider":
        df = np.zeros(self.dim)
        n = 0
        for text in texts:
            toks = set(_tokens(text))
            if not toks:
                continue
            n += 1
            for tok in toks:
                idx, _ = self._bucket(tok, self.dim)
                df[idx] += 1
        # smoothed IDF: common terms -> ~1, rare terms -> higher
        self.idf = np.log((1 + n) / (1 + df)) + 1.0
        return self

    def _vectorize(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim)
        counts = Counter(_tokens(text))
        for tok, c in counts.items():
            idx, sign = self._bucket(tok, self.dim)
            v[idx] += sign * c
        idf = self.idf if self.idf is not None else np.ones(self.dim)
        v = v * idf
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.array([self._vectorize(t) for t in texts])

    def state(self) -> dict:
        return {
            "dim": self.dim,
            "idf": self.idf.tolist() if self.idf is not None else None,
        }

    @classmethod
    def from_state(cls, state: dict) -> "HashedTfidfProvider":
        p = cls(dim=state.get("dim", 512))
        idf = state.get("idf")
        p.idf = np.array(idf, dtype=float) if idf is not None else None
        return p


class SentenceTransformerProvider(EmbeddingProvider):
    """Dense embeddings via sentence-transformers. Needs the package."""

    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed. "
                "pip install sentence-transformers, or use --provider hashed-tfidf."
            ) from e
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def fit(self, texts: list[str]) -> "SentenceTransformerProvider":
        return self  # nothing to fit

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(vecs, dtype=float)

    def state(self) -> dict:
        return {"dim": self.dim}


class OpenAIProvider(EmbeddingProvider):
    """Dense embeddings via the OpenAI API. Needs OPENAI_API_KEY."""

    name = "openai"

    def __init__(self, model: str = "text-embedding-3-small"):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "openai is not installed. pip install openai, "
                "or use --provider hashed-tfidf."
            ) from e
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        # text-embedding-3-small -> 1536
        self.dim = 1536

    def fit(self, texts: list[str]) -> "OpenAIProvider":
        return self  # nothing to fit

    def embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            out.extend([d.embedding for d in resp.data])
        arr = np.asarray(out, dtype=float)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        return arr / np.maximum(norms, 1e-12)


_PROVIDERS = {
    "hashed-tfidf": HashedTfidfProvider,
    "sentence-transformers": SentenceTransformerProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: str | None = None, **kwargs) -> EmbeddingProvider:
    """Build a provider by name; falls back to RAG_EMBEDDING_PROVIDER env, then hashed-tfidf."""
    name = name or os.environ.get("RAG_EMBEDDING_PROVIDER", "hashed-tfidf")
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"unknown embedding provider: {name!r} (choices: {sorted(_PROVIDERS)})")
    return cls(**kwargs)


def build_provider(name: str, state: dict) -> EmbeddingProvider:
    """Rebuild a provider from persisted state (for re-embedding queries)."""
    if name == "hashed-tfidf":
        return HashedTfidfProvider.from_state(state)
    if name == "sentence-transformers":
        return SentenceTransformerProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"unknown embedding provider: {name!r}")
