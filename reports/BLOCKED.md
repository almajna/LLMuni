# Blocked items (overnight run, 2026-09-26)

## R5 street/transit geometry for the route replay

**What:** draw each replayed hop along the actual streets and transit lines, from R5's `DetailedItineraries`,
instead of a schematic arc (`llmuni site-data --routes`, cached in `cache/site_routes.json`).

**Tried three times, then moved on:**

1. 837 hops, 6 threads, 5-minute departure window: about one core busy and under 25 hops done in 7 minutes
   (r5py serializes the calls); stopped.
2. 2 threads, 1-minute window: `java.lang.OutOfMemoryError: Java heap space` within a minute (heap capped at
   4 GB by `router.max_memory`, the cap that keeps the matrix job clear of the memory reaper).
3. A single hop in isolation, with trips capped at 60 minutes and walks at 15: still out of heap.

**Why it blocks tonight:** the itinerary search needs more than 4 GB of Java heap on this network, and the
machine had about 2 GB free while other sessions and Firefox were running.

**What shipped instead:** each hop is a shallow arc between the stops, timed by the grader's replay, and the site
says so under the replay controls ("Arcs join each plan's stops in visiting order, not the streets taken").
Every clock, arrival and failure is still the exact timetable replay; only the drawn path is schematic.

**To unblock (about 10 minutes on a machine with 8+ GB free):** set `router.max_memory: 8G` in `config.yaml`, run
`uv run python -m llmuni site-data --routes`, then `make publish`. Hops R5 routes are drawn along streets and
lines; the rest stay arcs.
