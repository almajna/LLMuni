# LLMuni pipeline. Stages are idempotent and cached; parameters live in config.yaml.
LLMUNI ?= uv run python -m llmuni
# v2: tool_use for the pilot's top N open-book models (make finish BUDGET_USD=<x> TOOL_MODE=3)
TOOL_MODE ?= 0

.PHONY: setup data router-check matrices tasks oracle examples estimate calibrate pilot eval test test-router \n	finish publish results site-data site video gif readme commit

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

eval:   ## final run in balanced rounds (spends money; total spend capped at BUDGET_USD; TOOL_MODE=N adds tool use)
	$(LLMUNI) eval --subset final --tool-models $(TOOL_MODE)

test:   ## fast unit tests
	uv run pytest

test-router:  ## slow R5 integration tests (build the transport network)
	uv run pytest -m router

# ---- make finish: everything after the pilot, in one command (see FINISH.md) ----

finish:  ## final eval under BUDGET_USD (total cap), then results, site, video, README, tests, commit + push
	@test -n "$(BUDGET_USD)" || { echo "usage: make finish BUDGET_USD=<total dollars> [TOOL_MODE=3]"; exit 2; }
	BUDGET_USD=$(BUDGET_USD) $(LLMUNI) eval --subset final --tool-models $(TOOL_MODE)
	$(MAKE) publish

publish: results site-data site video gif readme test commit  ## no spend: rebuild every published artifact from results/

results:  ## re-grade every cached answer (no model calls) -> results/
	$(LLMUNI) eval --subset final --grade-only --tool-models $(TOOL_MODE)

site-data:  ## site + video JSON, routing each replayed hop with R5 (cached; needs Java)
	$(LLMUNI) site-data --routes

video/public/basemap.png: data/MANIFEST.json
	$(LLMUNI) video-basemap

site:  ## static site -> site/dist (deploy that folder; see FINISH.md)
	cd site && npm ci --no-audit --no-fund && npx vite build

video: video/public/basemap.png  ## Remotion renders -> video/out/llmuni_16x9.mp4 and llmuni_4x5.mp4
	cd video && npm ci --no-audit --no-fund && npx remotion render src/index.ts LLMuni-16x9 out/llmuni_16x9.mp4 --concurrency=4 		&& npx remotion render src/index.ts LLMuni-4x5 out/llmuni_4x5.mp4 --concurrency=4

gif:  ## README hero GIF from the 16:9 render (the race)
	ffmpeg -y -loglevel error -ss 6.5 -t 14 -i video/out/llmuni_16x9.mp4 -vf "fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" docs/hero.gif

readme:  ## rewrite the README's headline and leaderboard blocks
	$(LLMUNI) readme

commit:  ## commit the published artifacts and push
	git add -A results benchmark docs README.md FINISH.md site video/out video/src video/public data/MANIFEST.json
	git diff --cached --quiet || git commit -m "make finish: results, site, video and README from $$(git rev-parse --short HEAD)"
	git push origin main
