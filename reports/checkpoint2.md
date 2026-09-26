# Checkpoint 2: tasks and oracle (v2026.10)

- **Task set:** 300 tasks, 100 per tier, in [`benchmark/v2026.10/tasks.jsonl`](../benchmark/v2026.10/tasks.jsonl).
  30 of them (10 per tier) are infeasible by design: every store of one errand closed (9), a deadline no
  plan can meet (9), or a meet-up time no plan can reach (12). A stratified 50-task pilot subset (17/17/16,
  6 infeasible) is in `pilot_ids.json`. Summary: [`phase3/tasks_summary.md`](phase3/tasks_summary.md).
- **Tiers:** easy has 3 errands, 30% of them with a meet-up. Medium has 4–5 errands; 97 of them leave 1–2.5 h
  before the nearby stores for one errand close. Hard has 6–7 errands, always with a cross-city meet-up, 1–2
  deadlines set within 5–20 min of the optimal plan's own timing, and at least 2 rare categories. Starts and
  ends are 30 named intersections in 14 neighborhoods; all seven weekdays are used.
- **Travel times:** R5 matrices for the three distinct service days (Mon–Fri, Sat, Sun): 962 places
  (932 stores + 30 landmarks) × 181 departures (07:00–22:00, every 5 min). Arrivals are FIFO by construction;
  the proof is in [`docs/methods.md`](../docs/methods.md).
- **Oracle:** an exact label-setting DP, solving both universes for every task in under 0.9 s (p95, hard tier).
  Median optimal durations: 60 / 95 / 146 min for easy / medium / hard. Optimal plans are in `oracle.jsonl`.
- **Checked four ways:** brute force matches the DP on 100/100 easy tasks and on 150 random instances. HiGHS
  MILP matches on 90/90 easy static relaxations and 40 random instances. The DP proves every infeasible task
  infeasible in both universes. An independent code review found one real bug (a window shorter than the
  errand was accepted); it is fixed and covered by regression tests.
- **Two universes matter:** searching every store in SF beats the 6 listed stores on 24 / 58 / 64 tasks
  (median 4 / 4 / 8 min faster). So closed-book answers are scored against the all-SF optimum, and open-book
  and tool answers against the listed-store optimum. No mode can beat its own "optimal".
- **Examples** (prompt, optimal plan, map from R5 itineraries): [`phase4/examples.md`](phase4/examples.md):
  easy [map](phase4/example_easy.png), medium [map](phase4/example_medium.png), hard [map](phase4/example_hard.png).
- **Decision needed: what counts as a post office?** 12 of the 41 valid "post offices" are FedEx Office or
  The UPS Store, and about 5 more are private mailbox counters. The medium example's optimal plan mails its
  package at a FedEx Office. *Recommendation:* keep only USPS offices and stations (~16 valid; 15 is the
  minimum), since "post office" means USPS to most people. The alternative is to reword the errand as "a post
  office or shipping store" and keep all 41.
- **Decision needed: libraries.** 8 of the 23 valid libraries are special or research libraries (Internet
  Archive, Prelinger, UCSF Kalmanovitz, the Botanical Garden's library, …) where nobody returns library books.
  *Recommendation:* keep only SF Public Library branches (15 valid, exactly the minimum). Either change means
  regenerating tasks and oracle (~15 min, no spend).
- **Ops:** R5 was stopped twice for low memory. Precomputation is now resumable per block and memory-mapped,
  with the JVM capped at 4 GB. The matrices (~1 GB) live in `cache/` and are not committed.
