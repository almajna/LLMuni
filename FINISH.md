# Finishing the benchmark: `make finish`

> Draft. The command lands in Phase 7, after the hero-task pick; this page documents its contract.

```sh
make finish BUDGET_USD=<total dollars>
```

One command runs everything that remains for the final evaluation and publishes it:

1. **Final eval:** 150 tasks (50 per tier; `benchmark/v2026.10/final_ids.json`), closed and open book for every
   model, tool mode for the pilot's top 3 models; reasoning effort medium, max_tokens 8000.
2. **Results:** grades and aggregates into `results/results.json` and `results/leaderboard.json`.
3. **Site and video:** exports the data, builds the site (`site/`), renders both videos (`video/`).
4. **README:** regenerates the leaderboard table and headline numbers.
5. **Tests**, then **commit and push**.

## Budget and resuming

- `BUDGET_USD` caps **total** spend across every run ever made, as recorded in `results/answers/ledger.jsonl`
  (the calibration and pilot count). It is not an extra allowance.
- Before each call, the worst case (prompt, plus the larger of max_tokens and 1.5x the model's largest observed
  completion) must fit under the cap; otherwise the run stops cleanly and everything answered so far is graded.
- Answers are cached in `results/answers/<settings>/<model>/<mode>/<task>.json` and committed, so rerunning
  `make finish` (here or in a fresh clone) never pays for an answer twice; it only continues where it stopped.
- Leaderboards compare models only on tasks every model answered, so a stop part-way stays fair.

## Before running

- `OPENROUTER_API_KEY` in `.env`; Java 21 (portable JDK in `.tools/jdk-21`, see `config.yaml`) for itineraries.
- `make estimate` prints the expected and worst-case cost of what remains, calibrated from the answers so far.
