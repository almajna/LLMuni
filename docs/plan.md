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
| 6. Evaluation | `make estimate`, `make pilot`, `make eval` | code done; pilot ends at **Checkpoint 3** |
| 7. Site + video | `make site`, Remotion | ends at **Checkpoint 4** |
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

## Checkpoint 3 additions

- Propose three **hero tasks** in which a well-known frontier model fails visibly (arrives at a closed store,
  misses a deadline, names a store that doesn't exist) and the optimal plan is clearly better. They drive the video.
- The eval config uses each lab's **latest flagship** model; show the model list for approval before the pilot.

## Standing rules

- Stop at every checkpoint with a report of at most 10 bullets; commit and push to `origin main` after each phase.
- Never spend beyond `BUDGET_USD`; no GPU work without explicit approval.
- Render the video with Remotion (not Puppeteer).
