# Morning report: LLMuni, overnight run (2026-09-26)

Everything you asked for is built, committed and pushed to `origin main`, which is still private. Nothing is
deployed. Total model spend is **$27.14 of the $29 cap**. `.env` was never read or edited.

## What's done

- **Final run:** closed and open book for all 7 models on 15 more tasks (rounds 6-10, one task per tier each).
  That makes **30 tasks, 10 per tier**. Round 11 was refused automatically: it needed 1.25 × $2.63 and only $1.86
  was left. No memory stops; it finished on the first attempt. Every answer and the ledger are committed.
- **Hallucination split:** the grader now checks stores missing from OpenStreetMap against San Francisco's
  business registry (DataSF). The old "hallucinated" label now splits three ways:
  - *not in OSM* (a real store, counted as unverifiable);
  - *wrong address*;
  - *no such store*.

  A stop that cannot exist now outranks an earlier stop that is merely unverifiable. Tests cover all of it.
- **Results and leaderboard:** `results/results.json`, `results/leaderboard.{json,md}` and
  `results/grades.jsonl`. The README's headline and leaderboard are generated from them (`make readme`).
- **Site:** night dispatch console with a split-flap standings board. It has a 3D replay of any task
  (default: hard-010), the board with mode and tier switches, a "How plans fail" chart and a method section.
  It was built with impeccable + emil-design-eng and reviewed by a fresh reviewer.
  Result: [see "Site review" below].
- **Video:** Remotion, 42 s, hero task hard-010, both formats rendered. **README:** GIF at the top, generated
  tables, reproduce steps and limitations. **FINISH.md** and **`make finish`**: tool mode is the opt-in v2 step
  (`TOOL_MODE=3`).
- **Tests:** all 326 pass (`uv run pytest`; the R5 integration tests stay opt-in via `make test-router`). Both
  TypeScript projects typecheck and the site builds (`site/dist`).

## Final headline numbers (30 tasks, 27 feasible and 3 impossible by design)

| Open book | Feasible | Vs optimal (median) |
|---|---:|---:|
| GPT-6 Astra | 96% | +1.8% |
| Grok 4.7 | 96% | +7.0% |
| Gemini 3.1 Pro | 93% | +8.3% |
| Claude Fable 5.1 | 85% | +2.2% |
| Qwen 3.8 Max Prime | 78% | +13.2% |
| *Greedy baseline* | *70%* | *+8.5%* |
| DeepSeek V4 Pro | 59% | +11.3% |
| Llama 4 Maverick | 56% | +26.4% |

- **Closed book:** 0% feasible for every model. Pooled over all models, 82% of the plans are impossible:
  - 111 wrong addresses;
  - 20 stores found in neither source;
  - 10 closed or late.

  A further 30 plans can't be checked. Grok 4.7 has the fewest impossible plans (41%).
- Every model except Llama called all 3 impossible tasks impossible. The greedy baseline beats DeepSeek and
  Llama in open book.

## Where to look

- **Videos:** `video/out/llmuni_16x9.mp4` (1920×1080) and `video/out/llmuni_4x5.mp4` (1080×1350). Both are
  silent and 42 s. README GIF: `docs/hero.gif`.
- **Site preview:** screenshots in `reports/phase7/`: `desktop.png`, `mobile.png`, and `closed-book.png` for the
  closed-book state. To run it locally: `cd site && npm install && npm run dev`. For the production build:
  `npm run build && npx vite preview`, served from `site/dist`.
- **Numbers:** `results/leaderboard.md`; method in `docs/methods.md`; blocked item in `reports/BLOCKED.md`.

## Design decisions I made (veto any)

**Benchmark and grading**

1. **Final-run sizing.** The final run uses whole rounds (one task per tier), each started only if 1.25× its
   expected cost fits. That margin left $1.86 unspent rather than risk a half-answered round.
2. **Ledger behavior.** The ledger now waits for in-flight calls instead of refusing them. Final-run concurrency
   was 6.
3. **The split's second source** is SF Registered Business Locations. *Not in OSM* is scored unverifiable, like
   unknown hours. *Wrong address* and *no such store* make a plan impossible. "No such store %" is an upper bound:
   a store registered under a different legal name lands there.
4. **Precedence.** A stop that cannot exist beats an earlier unverifiable stop. This moved closed-book impossible
   rates from 22-82% to 41-96%.
5. **Closed-book ties.** Every model is at 0% feasible, so ranks break on fewest impossible plans, then fewest
   invented stores. The headline's "best closed-book model" is therefore Grok 4.7.

**Site**

6. **Materials and type.** Green-black slate, not blue, with Barlow and Barlow Condensed (California signage
   lettering), self-hosted. Gold means optimal only and red means failure only; the seven model colors avoid both.
7. **First viewport.** The replay is the first viewport (hero hard-010, open book). It autoplays once, except
   with reduced motion. A split-flap message board states the leader.
8. **Map.** A custom slate map style over OpenFreeMap tiles (no key needed): dashed rail lines, 3D buildings,
   neighborhood labels.
9. **Hops are timed arcs, not street paths.** A caption says so (R5 geometry is blocked; see `BLOCKED.md`).
10. **One mode switch.** Open/closed drives the replay, the board and the failure chart together. A tier switch
    filters the board only.
11. **Board motion.** The board flips when it scrolls into view and on every switch. Baselines are dimmed and
    unranked.
12. **Failure chart.** "Can't be checked" is separated from "impossible" so closed-book 0% isn't overstated.
13. **Committed site data.** `site/public/data` is committed and `npm run build` no longer calls Python, so a host
    can build the site as-is.
14. **From the finish review.**
    - Every unit gets a round status lamp: a ring while its outcome is open, then gold, sage, red or gray the
      moment it is decided.
    - A run and sample stamp sits in the top strip.
    - The headline note gives its denominator (26 of 27 feasible tasks).
    - "Travel tool · v2" shows as a disabled mode.
    - Closed book prints its ordering rule.
    - Phones get a two-row flap headline and a second flap line of key numbers under each board row.
    - A social card (`site/public/og.png`, a frame of the video) is wired into the page's meta tags.

**Video**

15. **Deterministic map.** A pre-rendered street and rail plate from our own OSM and GTFS data, with a
    CSS 3D camera. Deterministic, and no map API.
16. **Title line.** The brief's line was "I gave AI 300 real San Francisco errand days". It became "I gave 7
    frontier AI models real San Francisco errand days…", because 30 of the 300 tasks were run.
17. **Third stat card.** The brief's "with a travel-time tool" card is replaced by "77% [of closed-book plans]
    sent you to a store that isn't there", since tool mode wasn't run.
18. **Stat card 1.** It pools every model's closed-book plans (82%) instead of "the best model's" rate.
19. **Arrivals board.** The finish shot is an arrivals board: short names in 16:9, full names in 4:5.
20. **No soundtrack.** CRF 23 encodes (about 24 MB and 17 MB). The end card shows github.com/almajna/LLMuni.
21. **README GIF.** 15 s of the race at 640 px and 8 fps (5.7 MB).

## Blocked

- **R5 street and transit geometry for the replay:** out of Java heap at 4 GB, three attempts. Shipped as timed
  arcs instead. The 10-minute fix on a machine with 8 GB free is in `reports/BLOCKED.md`.

## To launch (what's left for you)

1. **Review and veto.** Watch the two videos, open the site (`cd site && npm install && npm run dev`), and veto
   any decision above.
2. **Make the repo public** (GitHub → Settings → Change visibility). The site, README and end card all link to
   github.com/almajna/LLMuni.
3. **Deploy the site.** On Vercel, import the repo with root directory `site`, build command `npm run build`
   and output `dist`. No environment variables are needed.
4. **Post the video.** Use 4:5 for feeds and 16:9 for YouTube/X, with the site link. Add music if you like;
   both renders are silent.
5. **Optional, more budget:** `make finish BUDGET_USD=<new total> TOOL_MODE=3` adds tool mode (about $210) and
   more rounds of tasks (about $2.63 per three tasks).
