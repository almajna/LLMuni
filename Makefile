# LLMuni pipeline. Stages are idempotent and cached; parameters live in config.yaml.
LLMUNI ?= uv run python -m llmuni

.PHONY: setup data test

setup:  ## install the locked Python environment
	uv sync

data:   ## download GTFS + OSM, pin versions in data/MANIFEST.json, build POIs + Phase 1 report
	$(LLMUNI) data

test:
	uv run pytest
