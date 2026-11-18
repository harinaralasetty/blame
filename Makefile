PYTHON ?= python3

.PHONY: test demo
test:
	$(PYTHON) -m unittest discover -s tests -v

demo:
	$(PYTHON) -m blame_cli report fixtures/synthetic.jsonl --out demo
	$(PYTHON) -m blame_cli report fixtures/inspect.json --out demo-inspect
	$(PYTHON) -m blame_cli report fixtures/harbor-job --out demo-harbor
	$(PYTHON) -m blame_cli report fixtures/swebench-eval --out demo-swebench
