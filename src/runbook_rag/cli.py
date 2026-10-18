"""Command line interface: ingest | query | eval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .embeddings import build_provider, get_provider
from .eval import run_eval
from .ingest import ingest_dir
from .store import VectorStore


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="runbook-rag",
        description="RAG pipeline over operational runbooks (ingest, query, eval).",
    )
    p.add_argument(
        "--provider",
        default=None,
        help="embedding provider: hashed-tfidf (default), sentence-transformers, openai. "
        "Also reads RAG_EMBEDDING_PROVIDER.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    ing = sub.add_parser("ingest", help="build a vector index from a runbooks directory")
    ing.add_argument("--runbooks", required=True, help="directory of .md runbooks")
    ing.add_argument("--out", required=True, help="where to write the index JSON")
    ing.add_argument("--strategy", default="sections", choices=["sections", "fixed"])
    ing.add_argument("--chunk-size", type=int, default=400)
    ing.add_argument("--overlap", type=int, default=80)

    q = sub.add_parser("query", help="ask a question against a built index")
    q.add_argument("--store", required=True, help="index JSON from `ingest`")
    q.add_argument("question", help="the question to ask")
    q.add_argument("--k", type=int, default=5)
    q.add_argument("--min-score", type=float, default=0.15)
    q.add_argument("--expand", action="store_true", help="enable ops-term query expansion")
    q.add_argument("--tag", default=None, help="filter chunks by tag")

    e = sub.add_parser("eval", help="run the labeled eval set against an index")
    e.add_argument("--store", required=True, help="index JSON from `ingest`")
    e.add_argument("--eval-set", required=True, help="labeled Q&A JSON file")
    e.add_argument("--k", type=int, default=3)
    e.add_argument("--min-score", type=float, default=0.0)
    e.add_argument("--expand", action="store_true")
    e.add_argument("--json", action="store_true", help="print raw JSON report")
    return p


def cmd_ingest(args) -> int:
    chunks = ingest_dir(args.runbooks, strategy=args.strategy, chunk_size=args.chunk_size, overlap=args.overlap)
    if not chunks:
        print(f"no runbooks found in {args.runbooks}", file=sys.stderr)
        return 1
    provider = get_provider(args.provider)
    provider.fit([c.text for c in chunks])
    vectors = provider.embed([c.text for c in chunks])
    store = VectorStore(provider.name, provider.state())
    store.add(chunks, vectors)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    store.save(out)
    print(f"ingested {len(chunks)} chunks from {args.runbooks} -> {out} (provider={provider.name})")
    return 0


def cmd_query(args) -> int:
    store = VectorStore.load(args.store)
    provider = build_provider(store.provider_name, store.provider_state)
    from .retrieve import retrieve

    where = {"tag": args.tag} if args.tag else None
    hits = retrieve(args.question, store, provider, k=args.k, min_score=args.min_score, expand=args.expand, where=where)
    if not hits:
        print(
            f"no confident match (cutoff={args.min_score}). "
            "not answering rather than guessing — try lowering --min-score or rephrasing."
        )
        return 0
    for i, h in enumerate(hits, 1):
        snippet = " ".join(h.chunk.text.split())
        print(f"[{i}] score={h.score:.3f} source={h.chunk.source} section={h.chunk.section or '-'}")
        print(f"    {snippet[:280]}{'...' if len(snippet) > 280 else ''}")
    return 0


def cmd_eval(args) -> int:
    store = VectorStore.load(args.store)
    provider = build_provider(store.provider_name, store.provider_state)
    eval_set = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    report = run_eval(store, provider, eval_set, k=args.k, min_score=args.min_score, expand=args.expand)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    agg = report["aggregate"]
    print(f"eval: n={agg['n']} provider={store.provider_name} k={args.k} min_score={args.min_score}")
    print(f"  recall@{args.k}:            {agg[f'recall@{args.k}']:.3f}")
    print(f"  recall@1:             {agg['recall@1']:.3f}")
    print(f"  mean top score:       {agg['mean_top_score']:.3f}")
    print(f"  mean faithfulness*:   {agg['mean_faithfulness_proxy']:.3f}")
    print(f"  no-match count:       {agg['no_match_count']}")
    print("  *faithfulness is a keyword-overlap proxy, not an LLM judge (see README)")
    print()
    for p in report["per_query"]:
        mark = "OK " if p[f"recall@{args.k}"] else "MISS"
        print(f"  [{mark}] {p['id']}: top={p['retrieved'][0] if p['retrieved'] else '-'} "
              f"(score={p['top_score']:.3f}) expected={p['expected']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "query":
        return cmd_query(args)
    if args.command == "eval":
        return cmd_eval(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
