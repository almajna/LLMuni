# LLMuni pipeline. Stages are idempotent and cached; parameters live in config.yaml.
LLMUNI ?= uv run python -m llmuni

.PHONY: setup data router-check matrices tasks oracle examples estimate pilot eval test test-router

setup:  ## install the locked Python environment
	uv sync

data:   ## download GTFS + OSM, pin versions in data/MANIFEST.json, build POIs + Phase 1 report
	$(LLMUNI) data

router-check:  ## route known SF trips with R5 (needs Java 21) and write reports/phase2
	$(LLMUNI) router-check

matrices:  ## R5 travel matrices for every service day (~2 h once; cached in cache/router)
	$(LLMUNI) matrices

tasks: matrices  ## seeded task set with oracle-verified (in)feasibility -> benchmark/<version>/
	$(LLMUNI) tasks

oracle:  ## optimal plans + brute-force and MILP cross-checks -> benchmark/<version>/oracle.jsonl
	$(LLMUNI) oracle

examples:  ## worked example per tier with itinerary maps -> reports/phase4/
	$(LLMUNI) examples

estimate:  ## pilot cost estimate only (no model calls)
	$(LLMUNI) eval --pilot --dry-run

pilot:  ## pilot: 50 tasks x models x closed/open book, capped at BUDGET_USD (spends money)
	$(LLMUNI) eval --pilot

eval:   ## full run: all tasks x models x all modes, capped at BUDGET_USD (spends money)
	$(LLMUNI) eval

test:   ## fast unit tests
	uv run pytest

test-router:  ## slow R5 integration tests (build the transport network)
	uv run pytest -m router
