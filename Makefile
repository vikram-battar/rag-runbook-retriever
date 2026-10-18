.PHONY: test lint eval ingest clean

test:
	python3 -m pytest tests/ -q

lint:
	python3 -m py_compile $$(find src tests -name "*.py")
	python3 -c "import yaml, glob; [list(yaml.safe_load_all(open(f))) for f in glob.glob('**/*.y*ml', recursive=True) if '.git' not in f]"
	python3 -c "import json, glob; [json.load(open(f)) for f in glob.glob('**/*.json', recursive=True) if '.git' not in f]"

ingest:
	PYTHONPATH=src python3 -m runbook_rag ingest --runbooks data/runbooks --out index/store.json

eval: ingest
	PYTHONPATH=src python3 -m runbook_rag eval --store index/store.json --eval-set data/eval_set.json --k 3

clean:
	rm -rf index/ .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null; true
