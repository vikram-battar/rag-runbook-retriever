"""Document ingestion: load markdown runbooks, chunk them, extract metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    text: str
    source: str  # filename, e.g. "oomkilled-crashloop.md"
    title: str  # runbook title (first # header)
    section: str  # ## header this chunk came from ("" if none)
    tags: list[str] = field(default_factory=list)
    chunk_index: int = 0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "title": self.title,
            "section": self.section,
            "tags": self.tags,
            "chunk_index": self.chunk_index,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(
            text=d["text"],
            source=d["source"],
            title=d["title"],
            section=d.get("section", ""),
            tags=d.get("tags", []),
            chunk_index=d.get("chunk_index", 0),
        )


def parse_runbook(path: str | Path) -> tuple[str, list[str], list[tuple[str, str]]]:
    """Parse a markdown runbook.

    Returns (title, tags, sections) where sections is a list of
    (header, body) tuples. Title is the first `#` header. Tags come from
    an optional `tags: a, b, c` line. Everything else groups under the
    most recent `##` header.
    """
    text = Path(path).read_text(encoding="utf-8")
    title = ""
    tags: list[str] = []
    sections: list[tuple[str, str]] = []
    current_header = ""
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body or current_header:
            sections.append((current_header, body))

    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush()
            level = len(m.group(1))
            header_text = m.group(2).strip()
            if level == 1 and not title:
                title = header_text
                current_header, current_lines = "", []
            else:
                current_header, current_lines = header_text, []
            continue
        tm = re.match(r"^tags:\s*(.+)$", line.strip(), re.IGNORECASE)
        if tm:
            tags = [t.strip().lower() for t in tm.group(1).split(",") if t.strip()]
            continue
        current_lines.append(line)
    flush()

    if not title:
        title = Path(path).stem.replace("-", " ")
    return title, tags, [(h, b) for h, b in sections if b]


def chunk_fixed(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    """Split text into word-based chunks of ~chunk_size words with overlap."""
    words = text.split()
    if not words:
        return []
    step = max(chunk_size - overlap, 1)
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), step)]


def chunk_sections(
    title: str,
    tags: list[str],
    sections: list[tuple[str, str]],
    source: str = "",
    max_words: int = 400,
    overlap: int = 80,
) -> list[Chunk]:
    """One chunk per section; long sections are further split with overlap.

    Each chunk is prefixed with "title — section" so a chunk retrieved on
    its own still carries its context.
    """
    chunks: list[Chunk] = []
    for header, body in sections:
        prefix = f"{title} — {header}" if header else title
        for piece in chunk_fixed(body, max_words, overlap):
            chunks.append(
                Chunk(
                    text=f"{prefix}\n{piece}",
                    source=source,
                    title=title,
                    section=header,
                    tags=list(tags),
                    chunk_index=len(chunks),
                )
            )
    return chunks


def ingest_runbook(
    path: str | Path, strategy: str = "sections", chunk_size: int = 400, overlap: int = 80
) -> list[Chunk]:
    """Ingest one runbook file. Strategy: "sections" or "fixed"."""
    path = Path(path)
    title, tags, sections = parse_runbook(path)
    if strategy == "fixed":
        full = "\n\n".join(body for _, body in sections)
        return [
            Chunk(
                text=f"{title}\n{piece}",
                source=path.name,
                title=title,
                section="",
                tags=tags,
                chunk_index=i,
            )
            for i, piece in enumerate(chunk_fixed(full, chunk_size, overlap))
        ]
    if strategy != "sections":
        raise ValueError(f"unknown chunking strategy: {strategy!r}")
    return chunk_sections(title, tags, sections, source=path.name, max_words=chunk_size, overlap=overlap)


def ingest_dir(
    runbooks_dir: str | Path, strategy: str = "sections", chunk_size: int = 400, overlap: int = 80
) -> list[Chunk]:
    """Ingest every .md file in a directory, sorted for determinism."""
    chunks: list[Chunk] = []
    for p in sorted(Path(runbooks_dir).glob("*.md")):
        chunks.extend(ingest_runbook(p, strategy=strategy, chunk_size=chunk_size, overlap=overlap))
    return chunks
