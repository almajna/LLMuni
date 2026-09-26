---
version: 1
slug: "site-index-html"
primary_target: "site/index.html"
related_targets: ["site/src/main.ts"]
---

# Surface brief: LLMuni site (leaderboard + route replay)

## Scope and mode

One static page at the domain root: the route replay (explorer), the leaderboard board, how plans fail, and the
method. Mode: Read, with an Experience-led first viewport (the replay is the thesis). Two audiences, story first
(PRODUCT.md): visitors from the video want the headline and a replay; researchers want the full board and method.

## Job

Show who plans best, by how much against the provable optimum, and exactly how plans fail. Every number comes
from `results/` and `benchmark/`; sample sizes and run status (pilot or final, n tasks) stay visible.

## Decisions (made unattended, listed for the user's veto)

- The user pinned the world at Checkpoint 3: the night dispatch console, with the split-flap departure board
  (the roll's challenger) as the leaderboard. No new direction round was run; the pinned brief beats the roll.
- Code-led build: no image generation in this harness.
- Default replay: v2026.10-hard-010 (the chosen hero task), open book.

## Direction contract

THESIS: The benchmark is a dispatch floor at night: models are units sent across a live San Francisco map, each
on its own clock, the optimal plan runs in gold, and failures page in as alerts. It refuses the category default of
a white leaderboard table over a hero-metric row.

OWN-WORLD: Matte control-room slate (green-black, not blue), engraved hairline rules and small caps labels in
sage gray, lamp colors with fixed meanings (gold = optimal, red = failed, sage = done, gray = unverifiable), and a
split-flap board of real flap cells (two-tone halves, hairline split, warm white characters) set in Barlow
Condensed, California-signage lettering. Seven model colors kept clear of gold and red. No glow, no glass.

STORY: A visitor watches one errand day replayed (a famous model arrives late while gold finishes first), reads
the board to see every model's feasible rate and gap, sees how plans fail (closed, late, wrong address,
invented), and leaves trusting the method because scope and limits are printed on the console.

FIRST VIEWPORT: Full-bleed dark 3D map wall of SF with the hero task's routes. Left rail (~380px): call ticket
(the request, errands, deadlines), unit list with live clocks and status lamps, transport controls (play/scrub,
flap-digit clock). Top strip: flap-cell LLMUNI plate, one-line question, data stamp, nav. A one-line flap
message board states the headline measurement. Primary action: Play (the replay).

FORM: Night dispatch console, the assigned direction (1st on the ordered list, seed 4228c0ff), fused with the
split-flap departure board challenger for the leaderboard at the user's request. Signature interactions: the replay
race with unit clocks, and the board's flaps flipping through characters when mode or tier changes. Motion
grammar: time runs linear; flaps are fast, mechanical, staggered by column; alerts pulse once, never loop; reduced
motion swaps flips for instant values.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
