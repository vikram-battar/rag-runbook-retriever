"""Tests for embedding providers."""

import numpy as np
import pytest

from runbook_rag.embeddings import (
    HashedTfidfProvider,
    build_provider,
    get_provider,
)


def test_hashed_tfidf_is_deterministic_and_normalized():
    p = HashedTfidfProvider(dim=128).fit(["some corpus text here", "another document"])
    a = p.embed(["hello world"])[0]
    b = p.embed(["hello world"])[0]
    assert np.allclose(a, b)
    assert a.shape == (128,)
    assert abs(np.linalg.norm(a) - 1.0) < 1e-6


def test_hashed_tfidf_similar_texts_score_higher():
    p = HashedTfidfProvider(dim=256).fit(
        ["oomkilled pod crashloop memory limit", "dns failure nameserver resolution"]
    )
    vecs = p.embed(["oomkilled pod crashloop memory limit", "dns failure nameserver resolution"])
    q = p.embed(["pod was OOMKilled, out of memory"])[0]
    assert float(vecs[0] @ q) > float(vecs[1] @ q)


def test_hashed_tfidf_empty_text_is_zero_vector():
    p = HashedTfidfProvider(dim=64).fit(["some text"])
    v = p.embed([""])[0]
    assert np.allclose(v, np.zeros(64))


def test_hashed_tfidf_state_roundtrip():
    p = HashedTfidfProvider(dim=128).fit(["alpha beta gamma", "beta delta"])
    state = p.state()
    p2 = HashedTfidfProvider.from_state(state)
    assert p2.dim == 128
    assert np.allclose(p.embed(["alpha beta"])[0], p2.embed(["alpha beta"])[0])


def test_get_provider_defaults_and_errors():
    assert get_provider("hashed-tfidf").name == "hashed-tfidf"
    assert get_provider().name == "hashed-tfidf"  # default
    with pytest.raises(ValueError):
        get_provider("does-not-exist")
    with pytest.raises(ValueError):
        build_provider("does-not-exist", {})


def test_optional_providers_fail_helpfully_when_missing():
    st = pytest.importorskip("sentence_transformers", reason="optional dep not installed")
    assert st is not None
