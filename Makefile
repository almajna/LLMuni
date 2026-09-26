# LLMuni pipeline. Stages are idempotent and cached; parameters live in config.yaml.
LLMUNI ?= uv run python -m llmuni

.PHONY: setup data router-check matrices tasks oracle examples estimate calibrate pilot eval test test-router

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

estimate:  ## cost estimates for calibration, pilot and final runs (no model calls)
	$(LLMUNI) eval --subset calibration --dry-run
	$(LLMUNI) eval --subset pilot --dry-run
	$(LLMUNI) eval --subset final --dry-run

calibrate:  ## 5 pilot tasks x models, open book: measures real token use (spends money, capped)
	$(LLMUNI) eval --subset calibration

pilot:  ## 15 tasks x models x closed/open book (spends money; total spend capped at BUDGET_USD)
	$(LLMUNI) eval --subset pilot

eval:   ## final run: 150 tasks, all modes (spends money; total spend capped at BUDGET_USD)
	$(LLMUNI) eval --subset final

test:   ## fast unit tests
	uv run pytest

test-router:  ## slow R5 integration tests (build the transport network)
	uv run pytest -m router
