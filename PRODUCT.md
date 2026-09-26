# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vite + deck.gl (TripsLayer, ScatterplotLayer) over a MapLibre dark basemap with no API key (brief section 2).
Static site deployed to Vercel at the domain root. The data comes from the benchmark's own JSON outputs.

## Users

Two audiences, story first: people arriving from the LLMuni video or a social post who want the headline and a
route replay, and ML researchers and builders who want the full leaderboard, per-tier and per-mode breakdowns,
and the method.

## Product Purpose

LLMuni is a live benchmark: LLMs plan real San Francisco errand days on Muni, BART and foot, and every plan is
replayed on the real timetable and graded against a provably optimal plan. The site shows who is best, by how
much, and exactly how plans fail (closed stores, missed deadlines, stores that don't exist).

## Positioning

The only planning benchmark here whose ground truth is an exact optimum on the real transit timetable and real
opening hours, with every model plan replayed on the same clock. Claims are measurements, not judgments.

## Operating Context

Results come from `results/` (leaderboard.json, results.json, grades.jsonl), tasks and optimal plans from
`benchmark/v2026.10/`. The benchmark is versioned by month and regenerated from the newest GTFS ("live").
The site updates whenever those files change; the `make finish` command rebuilds it.

## Capabilities and Constraints

- Leaderboard: feasible %, median optimality gap, impossible-plan %, hallucination %, correct "impossible"
  calls, cost per task; per mode (closed book, open book, tool use) and per tier (easy, medium, hard).
- Task explorer: 3D SF, each model's route replayed over time in its own color, the optimal route in gold,
  red pulse and "CLOSED" when a plan reaches a closed store, and a timeline of each model's clock vs optimal.
- Numbers shown must be the benchmark's own outputs; pilot results are labeled as a pilot (n tasks).
- Independent research project: no SFMTA/Muni/BART marks or official styling.

## Evidence on Hand

Real benchmark outputs only: `results/**` and `benchmark/v2026.10/**`. No testimonials, users or press exist;
none may be invented.

## Product Principles

1. Measurements over adjectives: every claim traces to a number in the results files.
2. Show the failure, not just the score: a replay of a model arriving at a closed store beats a paragraph.
3. Honest scope: sample sizes, pilot status and limitations are always visible.
4. The optimal plan is the reference point everywhere.
