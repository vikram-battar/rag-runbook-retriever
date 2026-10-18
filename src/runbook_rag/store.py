"""In-memory vector store with cosine similarity, persisted to JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .ingest import Chunk


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


def _matches(chunk: Chunk, where: dict) -> bool:
    for key, value in where.items():
        if key == "tag":
            if str(value).lower() not in chunk.tags:
                return False
        elif key == "source":
            if chunk.source != value:
                return False
        elif getattr(chunk, key, None) != value:
            return False
    return True


class VectorStore:
    """Cosine-similarity store. Vectors are expected L2-normalized."""

    def __init__(self, provider_name: str, provider_state: dict):
        self.provider_name = provider_name
        self.provider_state = provider_state
        self.chunks: list[Chunk] = []
        self.vectors: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self.chunks)

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        arr = np.asarray(vectors, dtype=float)
        self.chunks.extend(chunks)
        self.vectors = arr if self.vectors is None else np.vstack([self.vectors, arr])

    def search(
        self,
        query_vec: np.ndarray,
        k: int = 5,
        min_score: float = 0.0,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """Top-k by cosine similarity, skipping anything below min_score.

        Metadata filtering applies after scoring; k counts only matches.
        """
        if self.vectors is None or not self.chunks:
            return []
        q = np.asarray(query_vec, dtype=float)
        scores = self.vectors @ q
        order = np.argsort(scores)[::-1]
        results: list[SearchResult] = []
        for i in order:
            s = float(scores[int(i)])
            if s < min_score:
                break
            chunk = self.chunks[int(i)]
            if where and not _matches(chunk, where):
                continue
            results.append(SearchResult(chunk=chunk, score=s))
            if len(results) >= k:
                break
        return results

    def save(self, path: str | Path) -> None:
        payload = {
            "provider": {"name": self.provider_name, "state": self.provider_state},
            "chunks": [c.to_dict() for c in self.chunks],
            "vectors": self.vectors.tolist() if self.vectors is not None else [],
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "VectorStore":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls(
            provider_name=payload["provider"]["name"],
            provider_state=payload["provider"]["state"],
        )
        store.chunks = [Chunk.from_dict(d) for d in payload["chunks"]]
        vecs = payload["vectors"]
        store.vectors = np.array(vecs, dtype=float) if vecs else None
        return store
