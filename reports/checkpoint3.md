# Checkpoint 3: pilot (15 tasks x 7 models x closed + open book)

- **Spend:** $13.14 total of the $27 cap: calibration $2.55, pilot $10.59. Every answer is cached in
  `results/answers/` with the ledger. Settings: reasoning effort medium, max_tokens 8000.
- **Open book** (12 feasible tasks): Grok 4.7 and Gemini 3.1 Pro were feasible on all 12, but +8.7% and +10.5%
  slower than optimal. GPT-6 Astra was feasible on 11/12 and closest to optimal (+1.7% median). Claude Fable
  5.1 was feasible on 10/12 (+8.7%). The greedy baseline scored 75% (+8.7%), Qwen 3.8 Max Prime 75%,
  DeepSeek V4 Pro 58%, Llama 4 Maverick 50%. All models except Llama called all 3 impossible tasks impossible.
  Full table: [`results/pilot/leaderboard.md`](../results/pilot/leaderboard.md).
- **Closed book:** 0% feasible for every model; 42–92% of plans are impossible and 92–100% name at least one
  store the grader could not match. **Caveat:** "hallucinated" currently includes real chains given a wrong
  address and real stores missing from OSM. *Proposal (no spend):* split it into *wrong address for a real
  store*, *not in OSM* and *no such store* before the final run.
- **Provider behavior:** Qwen and DeepSeek often use all 8,000 tokens on reasoning, and their repair retry
  usually recovers the answer. Grok and DeepSeek ignore max_tokens (up to 39k tokens in one call). The ledger
  now reserves 1.5x each model's largest completion, so the budget cap still holds.
- **Hero candidates:** [`checkpoint3/heroes.md`](checkpoint3/heroes.md), with maps:
  (1) **Claude Fable 5.1 arrives at a closed store** (closed book, hard-098);
  (2) **GPT-6 Astra is late to the meet-up** (open book, hard-010; clean, since the stores were given);
  (3) **GPT-6 Astra arrives at a closed store** (closed book, medium-047).
  Alternates: GPT-6 Astra invents "Dolores Cleaners" (hard-023), pending the hallucination split above.
- **Final run estimate** (150 tasks; closed + open for 7 models, tool mode for the top 3: Grok, Gemini,
  GPT-6 Astra): **$329 expected**. That is ~$118 for closed + open (calibrated) and ~$210 for tool mode
  (uncalibrated, 12 turns per task assumed). Detail: [`results/cost_estimate_final.md`](../results/cost_estimate_final.md).
- **Phase 7 scaffolds**, with nothing built or rendered: `site/` (Vite + deck.gl + MapLibre; leaderboard and replay
  explorer reading whatever results exist via `llmuni site-data`), `video/` (Remotion, the brief's 6 shots,
  placeholder hero), README structure, `FINISH.md`.
- **Site direction** (impeccable roll, seed 4228c0ff): assigned *night dispatch console* (routes as units on a
  map wall, clocks per model, failure alerts). The strongest challenger is a *split-flap departure board*
  leaderboard; impeccable's pick is a *pocket transit timetable*.
- **Decisions needed:** (a) hero task; (b) site direction; (c) the hallucination split; (d) final-run scope:
  closed + open only (~$118) or with tool mode (~$329); the budget is enforced either way.
