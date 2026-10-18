# rag-runbook-retriever

I spent enough time watching incident-response demos where the "AI" part got all the attention and the retrieval part was an afterthought — a vector DB, some embeddings, hope. The thing is, retrieval quality is what makes or breaks RAG. If the retriever hands the model the wrong runbook, the model writes a confident wrong answer. If it hands over nothing with confidence, at least you know you're on your own.

So I built the retrieval layer properly: ingest runbooks, chunk them two ways, embed them behind a swappable provider interface, serve top-k with a minimum-score cutoff, and — the part I actually care about — an eval harness that scores it like you'd score a model.

This is a portfolio reference implementation I built from scratch. Not from any employer.

## what it does

- **ingest**: loads markdown runbooks, chunks them by section (markdown headers) or fixed-size with overlap, extracts titles/tags. Each chunk is prefixed with its runbook and section so a chunk retrieved alone still carries context.
- **embed**: pluggable providers behind one interface. `hashed-tfidf` (default) is a sparse TF-IDF baseline over hashed token buckets — deterministic, offline, zero heavy deps. `sentence-transformers` and `openai` are real dense embeddings, optional, selected by flag.
- **store**: in-memory cosine-similarity store, persisted to JSON, with metadata filtering (by tag or source).
- **retrieve**: top-k with a minimum-score cutoff. Below the cutoff you get an explicit "no confident match" instead of the least-bad chunk dressed up as an answer.
- **eval**: labeled Q&A set scored for recall@k, plus a faithfulness proxy (below).

## try it

```bash
pip install -r requirements.txt

# build the index from the sample runbooks
PYTHONPATH=src python3 -m runbook_rag ingest --runbooks data/runbooks --out index/store.json

# ask a question
PYTHONPATH=src python3 -m runbook_rag query --store index/store.json "pod keeps getting OOMKilled with exit 137" --k 3

# run the eval set
PYTHONPATH=src python3 -m runbook_rag eval --store index/store.json --eval-set data/eval_set.json --k 3

# or everything at once
make eval
```

The cutoff is the honesty mechanism. Ask it something out of domain and it tells you so:

```bash
PYTHONPATH=src python3 -m runbook_rag query --store index/store.json "how do i bake sourdough" --k 3 --min-score 0.25
# no confident match (cutoff=0.25). not answering rather than guessing — try lowering --min-score or rephrasing.
```

## what's real and what's a proxy

I want to be precise here, because RAG marketing usually isn't:

- **hashed-tfidf is a sparse baseline, not embeddings.** It matches on term overlap weighted by IDF. It doesn't understand synonyms or paraphrase. It exists so the pipeline runs offline and so the eval has a floor to beat. Swap in `sentence-transformers` (`--provider sentence-transformers`) or OpenAI (`--provider openai`, needs `OPENAI_API_KEY`) for real dense vectors — the interface is identical.
- **the faithfulness score is a keyword-overlap proxy, not an LLM judge.** There's no answer generation in this pipeline, so "faithfulness" here means: of the key terms a correct answer should contain, what fraction appear in the retrieved chunks. It measures whether retrieval surfaced groundable content. A real faithfulness score needs a judge model reading a generated answer — that's the agent's job, one layer up.
- **the min-score cutoff is tunable and corpus-dependent.** I measured it: on the sample corpus, in-domain questions score 0.125–0.485 at the top hit (mean 0.32); a deliberately out-of-domain probe scored 0.167. No single cutoff separates perfectly with the sparse baseline — that's a real finding, not a bug, and it's why the cutoff is a flag, not a constant. Tune it against your own corpus, and prefer dense embeddings if the separation band is too narrow.

## eval results (hashed-tfidf baseline, 18 labeled questions, 9 runbooks)

```
recall@3:            1.000
recall@1:            1.000
mean top score:      0.320
mean faithfulness*:  0.856
```

Every question retrieves its runbook first. The faithfulness proxy says the retrieved chunks contain ~86% of the key terms a correct answer needs. These numbers are on a small synthetic corpus with a sparse baseline — treat them as "the pipeline works end to end," not as a claim about production. The interesting number to watch when you swap providers is how much recall@1 and the score separation improve.

## layout

```
src/runbook_rag/   ingest, embeddings, store, retrieve, eval, cli
data/runbooks/     9 synthetic runbooks (OOMKilled, disk pressure, TLS, DNS, DB pools, bad deploys, CPU, queues, evictions)
data/eval_set.json 18 labeled question -> runbook pairs
tests/             28 tests
```

## dev

```bash
make test   # pytest
make lint   # py_compile + yaml/json checks
make eval   # ingest + run the eval set
```

Or Docker: `docker build -t runbook-rag .` then `docker run --rm runbook-rag query --store ...` (mount your index).

## license

MIT.
