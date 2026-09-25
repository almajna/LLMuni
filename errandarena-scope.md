# ErrandArena — Can AI Actually Plan a Day in San Francisco?

Build brief for Claude Code. Read fully before writing code. Work phase by phase. Stop at every **[CHECKPOINT]** and report to the human in ≤10 bullet points (what was done, key numbers, anything needing a decision).

---

## 0. One-line goal

A live benchmark where LLMs plan real SF errand days on Muni + BART + walking, graded against a **provably optimal** plan from an exact solver, replayed against the real transit timetable. Ship: benchmark code, leaderboard, results, a 3D route-replay site, and a 30–45 s video.

## 1. Deliverables

1. Repo `errand-arena` — reproducible (`make data && make tasks && make oracle && make eval && make site`).
2. `benchmark/` — versioned task set `v2026.10` (JSONL) + oracle solutions.
3. `results/leaderboard.json` + `results/results.json` (keys in §10).
4. `site/` — static site (Vite + deck.gl): leaderboard + task explorer with 3D route replay. Deployable to GitHub Pages / Vercel.
5. `video/errandarena_4x5.mp4` (1080×1350) and `_16x9.mp4` (1920×1080).
6. `README.md` (hero GIF, one-paragraph pitch, leaderboard table, method, limitations) and `docs/methods.md`.

## 2. Stack

- Python 3.11: `pandas`, `geopandas`, `shapely`, `osmnx`, `r5py` (needs Java 21 JDK), `opening_hours` parser (e.g., `opening-hours-py` or equivalent; pick one that parses OSM syntax), `highspy`, `pydantic`, `httpx`, `rapidfuzz`, `tenacity`.
- LLM access: **OpenRouter** via one env var `OPENROUTER_API_KEY` (OpenAI-compatible API). Never hardcode or commit keys. `.env` in `.gitignore`.
- Frontend: Vite + deck.gl (`TripsLayer`, `PolygonLayer` extruded buildings, `ScatterplotLayer`) + MapLibre dark basemap (no key).
- Video: Puppeteer deterministic frame capture → ffmpeg.

## 3. Phase 1 — Data

- **Muni GTFS**: SFMTA production feed (links from `https://www.sfmta.com/reports/gtfs-transit-data` or DataSF dataset `dni7-qpv3`).
- **BART GTFS**: BART developer page (`google_transit.zip`).
- **OSM**: SF extract (Geofabrik NorCal clipped to SF, or Overpass) as `.osm.pbf` for r5py; POIs with tags + `opening_hours`.
- **Errand categories** (initial): pharmacy, post_office, supermarket (+ brand filters: Trader Joe's, Safeway, Whole Foods), hardware, bank/ATM, library, coffee, bakery, dry_cleaning, bookstore, florist, bike_shop, electronics. Keep only POIs with parseable `opening_hours`.
- Pin GTFS feed versions + OSM snapshot date in `data/MANIFEST.json` (benchmark versioning).

**Acceptance:** POI table with counts per category; % with valid hours; map PNG of POIs. **[CHECKPOINT 1]** — report category coverage; drop categories with <15 valid POIs.

## 4. Phase 2 — Router

- `r5py` TransportNetwork from OSM pbf + both GTFS feeds. Modes: WALK + TRANSIT. Walk speed 1.3 m/s default (config).
- Function `travel_time(from, to, depart_dt) -> minutes` and `itinerary(from, to, depart_dt) -> legs[]` (for visualization).
- Precompute per-task time-dependent matrices at 5-min departure resolution over the task horizon; cache to disk.
- Sanity tests: 5 known trips (e.g., Powell → Civic Center BART, Mission/16th → Ferry Building) return plausible times.

## 5. Phase 3 — Task generator

Task schema (pydantic):
```
task_id, tier, weekday, start: {lat, lon, label, depart_time},
errands: [{category, brand?, service_min, deadline?}],
end: {lat, lon, label, arrive_by} | null,
objective: "min_finish_time",
candidates: {category: [poi_id, name, address, lat, lon, opening_hours]}  # top-K open, K=6
```
- Start/end points: named intersections/landmarks across neighborhoods (Mission, SoMa, Sunset, Richmond, Marina, Castro, Chinatown, Bayview, Dogpatch, Haight). Human-readable labels.
- Tiers: **easy** 3 errands, loose; **medium** 4–5, one closing soon; **hard** 6–7, tight windows, cross-city, rare categories.
- ~10% **infeasible** tasks (correct answer: "impossible" + reason). Verify infeasibility via oracle.
- Size: 300 tasks (100/tier) for v1; 50-task pilot subset.
- Render each task to a natural-language prompt (friendly, specific, no hints about optimal order).
- Seeded; `make tasks MONTH=2026-10` regenerates a fresh set from the newest GTFS ("live" benchmark, anti-contamination).

## 6. Phase 4 — Oracle (exact)

- Problem: time-dependent generalized TSP with time windows (choose one POI per category, order, respect opening hours incl. service time, deadlines, end arrive_by). Minimize finish time.
- **Primary solver: exact label-setting DP** over (visited-category set, current POI, earliest time). Transit travel times are FIFO at the chosen resolution → earliest-arrival labels dominate; document the FIFO argument in `docs/methods.md`. Allow waiting at a store until it opens.
- **Cross-check: MILP in HiGHS** on a static-time relaxation (fixed-departure matrix) — used to validate DP on small instances and for the write-up.
- Output per task: optimal sequence, POI ids, timestamps, legs, finish time; or proof of infeasibility.
- Tests: brute-force enumeration matches DP on all easy tasks.

**[CHECKPOINT 2]** — show 3 example tasks (one per tier) with prompt, optimal plan, map PNG.

## 7. Phase 5 — Grader

- Required model output: strict JSON `{feasible: bool, stops: [{category, store_name, address, poi_id?}], reason?}` (JSON schema in prompt; one repair retry on parse failure, then score as invalid).
- **Store matching**: `poi_id` if given; else fuzzy name + address geocode → nearest POI within 150 m of same category. Unmatched = hallucinated store.
- **Replay**: simulate the model's order with the real router (earliest arrival, wait if closed-but-opening-later is allowed only if it waits explicitly? → policy: simulator waits automatically, counts time). Check hours at arrival, service time, deadlines, arrive_by.
- Metrics per task: `valid_json`, `feasible_replay`, `hallucinated_store`, `optimality_gap = (model_finish − opt_finish)/(opt_finish − start)`, `correct_infeasible_call`, tokens, cost, latency.

## 8. Phase 6 — Evaluation modes

- **A. Closed-book**: prompt only. Model must name real stores (tests SF knowledge + planning).
- **B. Open-book**: candidate stores with ids, addresses, hours, coordinates provided. No travel times.
- **C. Tool-use**: B + function `get_travel_time(from_id, to_id, depart_time)` backed by the router, max 40 calls/task.
- Models (config list, via OpenRouter): current frontier from OpenAI, Anthropic, Google, xAI, plus strong open-weights (DeepSeek, Qwen, Llama). Also baselines: **greedy nearest-open-store** and **random order**.
- Temperature: provider default; 1 sample per task for v1.
- **Cost control (mandatory)**: estimate cost before every run and print it; hard cap `BUDGET_USD` in config (default 25 for pilot, 150 for full). Cache every response to disk; never re-call a cached (model, task, mode).

**[CHECKPOINT 3]** — pilot: 50 tasks × all models × modes A/B. Report cost, parse-failure rate, early leaderboard. **Wait for human approval before full run.**

## 9. Phase 7 — Site + video

**Site**
- Leaderboard: feasibility %, mean gap, hallucination %, cost/task, per mode, per tier.
- Task explorer: 3D SF (extruded OSM buildings, dark basemap). Each model's route animated (TripsLayer) in its own color; oracle in **gold**. Stores as pins; arrival at a closed store → red pulse + label "CLOSED". Side timeline: each model's clock vs optimal.

**Video (30–45 s, deterministic render)**
1. Text on black: "I gave AI 300 real San Francisco errand days."
2. 3D SF fly-in; one hard task appears as a checklist.
3. Models' routes race across the city; two flash red at closed stores / missed deadline.
4. Gold optimal route finishes first; clock comparison.
5. Stat cards: "X% of AI plans were impossible", "best model: Y% slower than optimal", "with a travel-time tool: Z%".
6. End card: leaderboard + repo URL placeholder.

**[CHECKPOINT 4]** — video draft for review.

## 10. `results/results.json` keys

```
benchmark_version, gtfs_versions, osm_date, n_tasks_by_tier,
per_model: {model: {mode: {feasible_pct, mean_gap, median_gap, hallucination_pct,
            correct_infeasible_pct, cost_usd, avg_tokens}}},
baselines: {greedy: {...}, random: {...}},
headline: {pct_impossible_best_model_closed_book, best_gap_open_book, best_gap_tool_mode,
           tool_mode_improvement_pct}
```

## 11. Phase 8 (optional, separate approval) — RL

- GRPO fine-tune a small open model (Qwen-family 3–7B) with TRL on a rented GPU (Modal/RunPod).
- Reward: +1 feasible, −gap, −1 invalid/hallucinated. Train on generated tasks disjoint from the eval set.
- **Do not start or spend on GPU without explicit human approval**; write a cost estimate first.

## 12. Limitations (must appear in README)

- Scheduled GTFS, not real-time; no delays modeled.
- OSM opening hours can be incomplete or outdated; tasks only use POIs with parseable hours.
- Walking speed and service times are assumptions (in config).
- Models are sampled once at default temperature.

## 13. Engineering rules

- All params in `config.yaml`; fixed seeds; idempotent cached stages.
- Unit tests: hours parsing, DP vs brute force, grader replay on hand-built plans, store matcher.
- Commit per phase. Secrets only via env vars. Never commit `.env`, raw OSM pbf, or cache dirs >50 MB.
