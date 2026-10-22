.PHONY: install test lint bench bench-llm serve mcp docker
install:
	python -m venv .venv && .venv/bin/pip install -e ".[dev]"
test:
	.venv/bin/pytest -q
lint:
	.venv/bin/ruff check .
bench:
	.venv/bin/python -m sentinel bench --n 100 --json docs/results.json --svg docs/benchmark.svg
bench-llm:  # needs ANTHROPIC_API_KEY
	.venv/bin/python -m sentinel bench --n 30 --agents naive rules graph claude multi --json docs/results.json --svg docs/benchmark.svg
serve:
	.venv/bin/python -m sentinel serve
mcp:
	.venv/bin/python -m sentinel mcp --seed 7
docker:
	docker build -t sentinel . && docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY sentinel
