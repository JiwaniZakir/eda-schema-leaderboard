.PHONY: install ingest synth validate build serve lint typecheck test check clean

# Where the lab's results tree lives. Override for a different checkout:
#   make ingest EXPERIMENTS=~/Downloads/eda-ml-models
EXPERIMENTS ?= ../eda-schema-experiments

# Post-reset the repo has no Python. Each target below skips loudly rather than
# passing silently, and starts doing real work the moment its phase lands.
# A skip names the phase that creates it, so a green `make check` on an empty
# repo can never be mistaken for a green `make check` on a built one.
#
# Each guard is a SINGLE recipe line. Make runs every line in its own shell, so
# a two-line `test ... || { echo; exit 0; }` form exits only that line's shell
# and then runs the command anyway. That bug was here and is why these are if/fi.
PY_SOURCES := $(wildcard build.py tools/*.py tools/**/*.py tests/*.py)

install:
	uv sync --all-extras

ingest:
	@if [ ! -f tools/ingest.py ]; then echo "ingest: tools/ingest.py does not exist yet (Phase 4)"; exit 1; fi; uv run python -m tools.ingest --source $(EXPERIMENTS)

synth:
	@if [ ! -f tools/synth.py ]; then echo "synth: tools/synth.py does not exist yet (Phase 7, if ever)"; exit 1; fi; uv run python -m tools.synth

validate:
	@if [ ! -f tools/validate.py ]; then echo "validate: SKIPPED, tools/validate.py does not exist yet (Phase 1)"; else uv run eda-validate; fi

build:
	@if [ ! -f build.py ]; then echo "build:    SKIPPED, build.py does not exist yet (Phase 3)"; else uv run python build.py; fi

serve: build
	@if [ ! -d dist ]; then echo "serve: nothing built yet (Phase 3)"; exit 1; fi; uv run python -m http.server -d dist 8000

lint:
	@if [ -z "$(PY_SOURCES)" ]; then echo "lint:     SKIPPED, no Python in the repo yet (Phase 1)"; else uv run ruff check . && uv run ruff format --check .; fi

typecheck:
	@if [ -z "$(PY_SOURCES)" ]; then echo "typecheck: SKIPPED, no Python in the repo yet (Phase 1)"; else uv run mypy; fi

test:
	@if [ ! -d tests ]; then echo "test:     SKIPPED, tests/ does not exist yet (Phase 1)"; else uv run pytest; fi

# The gate. Run this before any commit.
check: lint typecheck validate test build
	@echo "✓ check passed"

clean:
	rm -rf dist dist-drexel dist-neutral .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
