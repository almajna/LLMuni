# LLMuni methods

LLMuni asks language models to plan a day of errands in San Francisco on Muni, BART and foot, then grades
each plan against a provably optimal one computed on the same transit timetable.

## 1. Data

- **Transit:** the SFMTA production GTFS feed (DataSF `dni7-qpv3`) and BART's GTFS feed. Each feed is pinned by
  URL, SHA-256, calendar range and the number of trips it runs on each day of the reference week
  (`data/MANIFEST.json`).
- **Streets and stores:** BBBike's San Francisco extract of OpenStreetMap, pinned by SHA-256 and replication
  timestamp. Stores are OSM features in 12 errand categories (pharmacy, post office, supermarket, hardware,
  bank/ATM, library, café, bakery, dry cleaner, bookstore, florist, bike shop) that are named, publicly
  accessible, inside the city boundary, and de-duplicated (same name within 75 m).
- **Opening hours** are parsed with `opening-hours-py` in local time. A store is **valid** if its hours parse,
  contain no `unknown` periods, and open at least once in the reference week (Monday Oct 5 – Sunday Oct 11,
  2026, chosen to avoid public holidays). Only valid stores are ever offered as candidates. Pharmacies use the
  prescription counter's hours (`opening_hours:pharmacy`) when mapped.

## 2. Travel times

Door-to-door times come from [R5](https://github.com/conveyal/r5) through `r5py`: walking at 1.3 m/s plus every
Muni and BART trip in the timetable, with walking legs capped at 30 minutes and trips at 150 minutes.

For each distinct service day (Monday–Friday share one timetable; Saturday and Sunday differ), R5 computes the
travel time between every pair of routable places (the ~930 valid stores and 30 start/end landmarks) for
departures every 5 minutes from 07:00 to 22:00. Each search uses a one-minute departure window, so it is the
exact earliest arrival for that departure minute.

### The arrival function is FIFO

Let `D_k` be the grid departures and `τ_k(i, j)` R5's door-to-door minutes leaving `i` at `D_k`. Because a
traveler may wait at `i` for a later departure, define

```
A_k(i, j) = min over k' ≥ k of ( D_k' + τ_k'(i, j) )
```

so `A_k ≤ A_{k+1}`. A traveler ready to leave `i` at time `t` arrives at

```
arrival(i, j, t) = min( t + walk(i, j),  A_{κ(t)}(i, j) ),   κ(t) = first k with D_k ≥ t
```

Both terms are non-decreasing in `t`, so their minimum is too: **leaving later never arrives earlier**. Every
value is achievable (walk now, or wait for grid departure `D_κ(t)` and follow R5's trip), so the oracle never
relies on a connection that does not exist. The price of the 5-minute grid is at most 5 minutes of extra waiting
per transit leg. Model plans are replayed with the same function, so every plan is timed on the same clock.

## 3. Oracle

A task has a start and departure time, errands (category, minutes of service, optional deadline by which the
errand must be finished), an optional end with an optional arrive-by time, and a candidate set of stores per
errand. A plan visits one store per errand in some order, waits for a store to open if it arrives early, must
finish service before closing time and before the errand's deadline, and then travels to the end. The
objective is the earliest finish: arrival at the end, or completion of the last errand when there is no end.

### Exact label-setting DP

States are `(set of errands done, current store)`, labelled with the earliest time the state can be reached.
From each label the DP tries every remaining errand at every store that can serve it, computing the arrival
(FIFO function above), the earliest service start (the first opening window with room for the service; a
non-decreasing function of arrival time), and the completion time.

**Why keeping only the earliest label is exact.** Suppose a plan reaches state `L` at time `t`, and consider
its continuation. Starting the same continuation from `L` at `t' ≤ t`: each travel leg arrives no later
(FIFO), each service starts no later (earliest start is non-decreasing), so each completion and the final
arrival are no later, and every constraint (closing time, deadline, arrive-by, end of day) is an upper bound
that therefore still holds. So an earlier label dominates a later one for the same state, and discarding later
labels loses no optimal plan. The DP explores `2^m × (stores)` states for `m ≤ 7` errands; if no label reaches
the final state, the task is proven infeasible.

### Two universes

- **Listed stores:** the optimum over each task's `K = 6` candidate stores per errand. Open-book and tool-use
  models choose from these, so their optimality gap is measured against this optimum.
- **All of San Francisco:** the optimum over every valid store that can serve the errand that day. Closed-book
  models may name any store, so they are measured against this one and can never beat "optimal".

### Validation

- **Brute force:** enumerating every errand order and every store choice reproduces the DP optimum on 150
  random FIFO instances (split shifts, deadlines, unreachable pairs, arrive-by times) and on every easy task.
- **MILP (HiGHS):** on the static-time relaxation (travel times fixed at departure, one opening window per
  store), a generalized TSP with time windows solved as a mixed-integer program agrees with the DP on 40 random
  instances and on the easy tasks' relaxations.

## 4. Grading

Models must reply with one JSON object: `{"feasible": bool, "stops": [{"category", "store_name", "address",
"poi_id"?}], "reason"?}`. A reply that cannot be parsed gets one repair request; if that fails too, the answer
is **invalid JSON**.

**Store matching.** Each stop is matched to an OSM store of its errand's category, in this order: the given
`poi_id`; a store at the same house number and street; the best-named store within 150 m of the address,
geocoded offline against the OSM extract (house numbers, else the nearest number on the same street, or a street
intersection); and, only when there is no usable address, the name alone (a chain's branch nearest the
previous stop). A stop that matches no store is **hallucinated**. A matched store whose hours are missing,
unparseable or `unknown`, or a real store that OSM maps under a different category (a Safeway named for a
pharmacy errand), is **unverifiable**: reported separately, never counted as feasible or infeasible.

**Replay.** The plan is replayed with the oracle's own simulator: FIFO travel, waiting for a store to open,
service that must end before closing and before any deadline, and the arrive-by time at the end. A plan is
**feasible** only if every stop verifies; otherwise it is **infeasible** (with the first failure: closed store,
missed deadline, late arrival, unreachable), hallucinated, or unverifiable.

**Metrics.** On feasible tasks: feasible %, impossible-plan % (infeasible or hallucinated), unverifiable %,
false-"impossible" %, and the optimality gap `(model finish − optimal finish) / (optimal finish − start)` of
feasible replays. On infeasible tasks: the share correctly declared impossible. Closed-book answers are
measured against the all-SF optimum, open-book and tool answers against the listed-store optimum.

## 5. Evaluation

- **A. Closed book:** the prompt only. **B. Open book:** plus the six listed stores per errand (ids,
  addresses, coordinates, OSM opening hours), no travel times. **C. Tool use:** B plus `get_travel_time(from,
  to, depart)`, answered by the same FIFO arrival function the grader uses, at most 40 calls per task.
- **Baselines** over the listed stores: greedy (always finish the next errand as early as possible, ignoring
  deadlines and the end) and random (random order and store).
- Models run through OpenRouter at the provider's default temperature, one sample per task.
- **Cost control.** Every run prints an estimate first. Every call reserves its worst case (prompt × 1.25 plus
  `max_tokens` at the output price; reasoning tokens bill as output and count toward `max_tokens`), and is
  refused unless spent + reserved + that worst case stays within `BUDGET_USD`; spend is settled with the cost
  OpenRouter reports. Responses are cached per (model, mode, task), so nothing is paid for twice.
