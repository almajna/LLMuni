# Finishing the benchmark: `make finish`

```sh
make finish BUDGET_USD=<total dollars>              # closed + open book for every model (this release)
make finish BUDGET_USD=<total dollars> TOOL_MODE=3  # v2: also tool use for the pilot's top 3 models
```

One command runs everything that remains for the final evaluation and publishes it:

1. **Final eval** (`llmuni eval --subset final`): the final subset (`benchmark/v2026.10/final_ids.json`, 150 tasks)
   runs in **rounds of one task per tier**, the 15-task pilot first. Every model answers closed and open book
   (reasoning effort medium, `max_tokens` 8000); with `TOOL_MODE=N`, the pilot's top N open-book models also run
   with the travel-time tool (up to 40 calls per task).
2. **Results** (`make results`): every cached answer is re-graded (no model calls) into `results/results.json`,
   `results/leaderboard.json`, `results/leaderboard.md` and `results/grades.jsonl`.
3. **Site data** (`make site-data`): `site/public/data/*.json` and `video/src/data/hero.json`. Every hop the
   replay draws is routed with R5 (Java 21, cached in `cache/site_routes.json`); without Java the hops are drawn
   straight.
4. **Site** (`make site`): `site/dist/`, a static build.
5. **Video** (`make video`, `make gif`): `video/out/llmuni_16x9.mp4`, `video/out/llmuni_4x5.mp4` and the README
   GIF `docs/hero.gif`. The hero task is `site.hero_task` in `config.yaml`.
6. **README** (`make readme`): rewrites the headline and leaderboard blocks between their markers.
7. **Tests**, then **commit and push** to `origin main`.

Steps 2-7 are `make publish`, which spends nothing and can be rerun on its own.

## Budget and resuming

- `BUDGET_USD` caps **total** spend across every run ever made, as recorded in `results/answers/ledger.jsonl`
  (calibration, pilot and final all count). It is not an extra allowance: `make finish BUDGET_USD=29` after
  $27.14 of spend has $1.86 left to use.
- A round starts only if the budget left, minus what started rounds are still expected to cost, covers 1.25x
  the round's expected cost (`eval.round_margin`, calibrated per model, mode and tier from cached answers).
  So a budget stop ends the run between rounds: the tiers stay balanced and no task is left answered by only
  some models.
- Inside a round each call still reserves its worst case (prompt, plus the larger of `max_tokens` and 1.5x the
  model's largest completion so far) and is refused if it cannot fit, which makes `BUDGET_USD` a hard cap.
- Answers are cached in `results/answers/<settings>/<model>/<mode>/<task>.json` and committed, so rerunning
  `make finish` (here or in a fresh clone) never pays for an answer twice; it continues with the next round.
- Leaderboards compare models only on tasks every model answered in that mode.

## What each budget buys

| Total `BUDGET_USD` | Tasks (per tier) | Notes |
|---:|---|---|
| 29 | 30 (10) | this release: pilot + rounds 6-10, $27.14 spent |
| ~45 | ~48 (16) | about $2.63 per round of three tasks (closed + open, 7 models) |
| ~140 | 150 (50) | the full final subset, closed + open |
| +~210 | 150 (50) | tool mode for 3 models (uncalibrated estimate; `make estimate` refines it) |

`make estimate` prints the expected and worst-case cost of what remains and how many rounds fit.

## Before running

- `OPENROUTER_API_KEY` in `.env` (only step 1 calls models).
- Python via `uv` (`make setup`), the data and tasks (`make data tasks oracle`), Java 21 for routes (the portable
  JDK in `.tools/jdk-21`, see `config.yaml`), Node 20+ for the site and video, and `ffmpeg` for the GIF.

## Deploying (not done by `make finish`)

The site is a static folder. `site/public/data/` is committed, so a host can build it without Python:
build command `npm run build`, output directory `dist`, root directory `site`. Nothing in the repo deploys it.
