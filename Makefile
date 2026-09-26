# LLMuni pipeline. Stages are idempotent and cached; parameters live in config.yaml.
LLMUNI ?= uv run python -m llmuni

.PHONY: setup data router-check test test-router

setup:  ## install the locked Python environment
	uv sync

data:   ## download GTFS + OSM, pin versions in data/MANIFEST.json, build POIs + Phase 1 report
	$(LLMUNI) data

router-check:  ## route known SF trips with R5 (needs Java 21) and write reports/phase2
	$(LLMUNI) router-check

test:   ## fast unit tests
	uv run pytest

test-router:  ## slow R5 integration tests (build the transport network)
	uv run pytest -m router
