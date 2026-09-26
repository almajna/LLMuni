# LLMuni build plan

Source brief: [`errandarena-scope.md`](../errandarena-scope.md). The project is named **LLMuni** wherever the brief says ErrandArena / errand-arena.

## Phases

| Phase | Entry point | Status |
|---|---|---|
| 1. Data | `make data` | done |
| 2. Router | `make router-check` | done |
| 3. Task generator | `make matrices`, `make tasks` | done |
| 4. Oracle | `make oracle`, `make examples` | done; **Checkpoint 2** in `reports/checkpoint2.md` |
| 5. Grader | (used by `make pilot` / `make eval`) | code and tests done |
| 6. Evaluation | `make estimate`, `make pilot`, `make eval` | done: pilot (**Checkpoint 3**) and final run, 30 tasks |
| 7. Site + video | `make finish` / `make publish` | built overnight; Checkpoint 4 replaced by `reports/MORNING.md` |
| 8. RL (optional) | | needs separate approval and a cost estimate |

## Decisions

Checkpoint 1 (2026-09-25):

- **Pharmacy** = `amenity=pharmacy` or `healthcare=pharmacy`, plus `shop=chemist` only for chains with a
  prescription counter (Walgreens, CVS, Rite Aid, Safeway, Costco). Generic chemists don't count.
- **Pharmacy hours:** `opening_hours:pharmacy` (the counter) wins over the store's `opening_hours`.
- **Hours status:** every POI is `valid`, `closed_all_week`, `unknown` (has `unknown` periods), `missing`, or
  `unparseable`. Only `valid` places become task candidates. In closed-book mode a stop at a store whose hours
  are unknown, missing, or unparseable is scored **unverifiable** and reported separately, never as infeasible.
- **Electronics** is dropped (6 valid POIs, below the 15 minimum).
- **Sources:** Muni GTFS comes from DataSF `dni7-qpv3` (the zip linked from sfmta.com was stale); OSM is
  BBBike's San Francisco extract.

Checkpoint 2 (2026-09-25): post offices are USPS only; libraries are SF Public Library branches only.

## Budget and run plan (2026-09-26)

- **$30 total for now.** Calibration (5 tasks x 7 models, open book) then a 15-task pilot (5 per tier) x 7
  models x closed + open book, hard cap **$27 total spend** (the ledger in `results/answers/` caps TOTAL spend).
- Every paid call uses the final-run settings (reasoning effort medium, max_tokens 8000) so pilot answers are
  reused by the final run.
- **Checkpoint 3:** leaderboard, 3 hero-task proposals, exact cost estimate for the final run: 150 tasks, closed +
  open book for all models, tool mode for the top 3.
- After the hero pick: Phase 7 (site + Remotion video + README) from the pilot results, and one command
  `make finish BUDGET_USD=<x>` that runs everything remaining for the final eval (reusing cached answers),
  regenerates results, site, video and README, runs tests, commits and pushes; it stops cleanly at the budget
  and resumes without paying twice. Documented in `FINISH.md`.

## Checkpoint 3 additions

- Propose three **hero tasks** in which a well-known frontier model fails visibly (arrives at a closed store,
  misses a deadline, names a store that doesn't exist) and the optimal plan is clearly better. They drive the video.
- The eval config uses each lab's **latest flagship** model; show the model list for approval before the pilot.

## Standing rules

- Stop at every checkpoint with a report of at most 10 bullets; commit and push to `origin main` after each phase.
- Never spend beyond `BUDGET_USD`; no GPU work without explicit approval.
- Render the video with Remotion (not Puppeteer).

## Checkpoint 3 decisions (2026-09-26)

- **Budget:** no top-up; **$29 total cap** including the $13.14 already spent. Final run = closed + open book for
  all 7 models on as many additional tasks as fit, balanced across tiers: rounds of one task per tier, each
  admitted only if 1.25x its expected cost fits. Result: rounds 6-10 (15 new tasks, 30 in all, 10 per tier),
  **$27.14 total**. Round 11 was refused with $1.86 left.
- **Tool mode:** not run; kept in `make finish` as the optional v2 step (`TOOL_MODE=3`).
- **Hero task:** v2026.10-hard-010 (GPT-6 Astra, open book, late to the meet-up).
- **Site:** night dispatch console with a split-flap departure board for the leaderboard.
- **Hallucination split:** "hallucinated" became *not in OSM* (unverifiable), *wrong address* and *no such store*,
  using SF's Registered Business Locations as the second source.
- **Overnight run (2026-09-26):** the user asked for an unattended build to launch-ready: design calls made
  without Checkpoint 4, listed in `reports/MORNING.md` for veto. Never deploy, never make the repo public.
