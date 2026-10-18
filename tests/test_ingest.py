"""Tests for ingestion: parsing, chunking strategies, metadata."""

from pathlib import Path

import pytest

from runbook_rag.ingest import (
    Chunk,
    chunk_fixed,
    chunk_sections,
    ingest_dir,
    ingest_runbook,
    parse_runbook,
)

DATA = Path(__file__).resolve().parent.parent / "data" / "runbooks"


def test_parse_runbook_extracts_title_tags_sections(tmp_path):
    p = tmp_path / "rb.md"
    p.write_text(
        "# My Runbook\n\ntags: kubernetes, memory\n\n## Symptoms\n\nPods die.\n\n## Fix\n\nRaise limits.\n"
    )
    title, tags, sections = parse_runbook(p)
    assert title == "My Runbook"
    assert tags == ["kubernetes", "memory"]
    assert [h for h, _ in sections] == ["Symptoms", "Fix"]
    assert "Pods die." in sections[0][1]


def test_parse_runbook_title_fallback(tmp_path):
    p = tmp_path / "some-thing.md"
    p.write_text("## Only\n\nbody here\n")
    title, tags, sections = parse_runbook(p)
    assert title == "some thing"
    assert tags == []


def test_chunk_fixed_overlap():
    words = [f"w{i}" for i in range(100)]
    chunks = chunk_fixed(" ".join(words), chunk_size=30, overlap=10)
    assert len(chunks) == 5  # 0,20,40,60,80
    assert chunks[0].split()[:30] == words[:30]
    # overlap: chunk 2 starts where chunk 1 started + 20
    assert chunks[1].split()[0] == "w20"
    assert chunks[1].split()[-1] == "w49"


def test_chunk_fixed_empty():
    assert chunk_fixed("") == []
    assert chunk_fixed("   ") == []


def test_chunk_sections_prefixes_context():
    chunks = chunk_sections("T", ["a"], [("S1", "body one"), ("S2", "body two")], source="f.md")
    assert len(chunks) == 2
    assert chunks[0].text.startswith("T — S1")
    assert chunks[0].source == "f.md"
    assert chunks[0].tags == ["a"]
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


def test_chunk_sections_splits_long_sections():
    body = " ".join(f"w{i}" for i in range(1000))
    chunks = chunk_sections("T", [], [("Long", body)], max_words=100, overlap=20)
    assert len(chunks) > 5
    for c in chunks:
        assert len(c.text.split()) <= 100 + 10  # prefix adds a few words


def test_ingest_runbook_strategies():
    path = DATA / "oomkilled-crashloop.md"
    by_section = ingest_runbook(path, strategy="sections")
    fixed = ingest_runbook(path, strategy="fixed")
    assert by_section and fixed
    assert all(c.source == "oomkilled-crashloop.md" for c in by_section)
    assert all("OOMKilled CrashLoop" in c.title for c in by_section)
    assert {"kubernetes", "memory", "crashloop", "oomkilled"} <= set(by_section[0].tags)
    assert {c.section for c in by_section} >= {"Symptoms", "Diagnosis", "Resolution"}
    with pytest.raises(ValueError):
        ingest_runbook(path, strategy="bogus")


def test_ingest_dir_loads_all_runbooks_sorted():
    chunks = ingest_dir(DATA)
    sources = sorted({c.source for c in chunks})
    assert len(sources) == 9
    assert sources == sorted(sources)
    assert len(chunks) > 9  # multiple sections each
    assert all(c.text.strip() for c in chunks)


def test_chunk_roundtrip():
    c = Chunk(text="t", source="s", title="ti", section="sec", tags=["x"], chunk_index=3)
    assert Chunk.from_dict(c.to_dict()) == c
