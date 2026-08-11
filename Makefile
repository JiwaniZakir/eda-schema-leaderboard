.PHONY: install ingest synth validate build serve test lint typecheck check clean

# Where the lab's results tree lives. Override for a different checkout:
#   make ingest EXPERIMENTS=../eda-schema-experiments
EXPERIMENTS ?= ../eda-schema-experiments

install:
	uv sync --all-extras

ingest:
	uv run python -m tools.ingest --source $(EXPERIMENTS)

synth:
	uv run python -m tools.synth

validate:
	uv run eda-validate

build:
	uv run python build.py

serve: build
	uv run python -m http.server -d dist 8000

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest

# The gate. Run this before any commit.
check: lint typecheck validate test build
	@echo "✓ check passed"

clean:
	rm -rf dist dist-drexel dist-neutral .pytest_cache .mypy_cache .ruff_cache
