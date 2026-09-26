"""Exact label-setting DP for the time-dependent generalized TSP with time windows.

State: (set of errands done, current place). Label: the earliest time the state can be
reached. Travel is FIFO (router.TravelMatrix.arrival) and earliest service start is
non-decreasing in arrival time (model.service_table), so reaching a state earlier never
hurts: any plan from a later label can be copied from the earlier one by waiting. Keeping
only the earliest label per state therefore loses no optimal plan (docs/methods.md).
"""

from __future__ import annotations

import numpy as np

from llmuni.oracle.model import INF, Instance, Outcome, arrivals, simulate


def solve(inst: Instance) -> Outcome | None:
    """Minimum-finish-time plan, or None if no plan satisfies every constraint."""
    best, parent, via = _labels(inst)
    full = (1 << len(inst.errands)) - 1
    places = np.flatnonzero(best[full] < INF)
    if places.size == 0:
        return None
    times = best[full, places]
    limit = inst.horizon
    if inst.end is not None:
        finish = arrivals(inst.matrix, places, times, np.array([inst.end]))[:, 0]
        if inst.arrive_by is not None:
            limit = min(limit, inst.arrive_by)
    else:
        finish = times
    finish = np.where(finish > limit, INF, finish)
    if finish.min() >= INF:
        return None
    place = int(places[np.argmin(finish)])

    sequence, mask = [], full
    while mask:
        e = int(via[mask, place])
        sequence.append((e, place))
        mask, place = mask & ~(1 << e), int(parent[mask, place])
    outcome = simulate(inst, sequence[::-1])
    assert outcome.feasible and outcome.finish == int(finish.min()), "DP plan must replay to its own optimum"
    return outcome


def earliest_completion(inst: Instance, errand: int) -> int | None:
    """Earliest time any partial plan can finish `errand` (other errands may come first); None if never."""
    best, _, via = _labels(inst)
    done = np.where(via == errand, best, INF).min()
    return None if done >= INF else int(done)


def _labels(inst: Instance) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Earliest time per (errands-done mask, place), with the predecessor place and last errand."""
    m, n = len(inst.errands), inst.matrix.arrive.shape[0]
    full = (1 << m) - 1
    best = np.full((1 << m, n), INF, dtype=np.int64)
    parent = np.full((1 << m, n), -1, dtype=np.int64)
    via = np.full((1 << m, n), -1, dtype=np.int64)
    best[0, inst.start] = inst.depart

    for mask in sorted(range(full), key=lambda x: bin(x).count("1")):
        places = np.flatnonzero(best[mask] < INF)
        if places.size == 0:
            continue
        times = best[mask, places]
        for e, errand in enumerate(inst.errands):
            if mask >> e & 1 or inst.options[e].size == 0:
                continue
            opts = inst.options[e]
            arrive = np.minimum(arrivals(inst.matrix, places, times, opts), inst.horizon + 1)
            start = inst.service_start[e][np.arange(opts.size)[None, :], arrive]
            done = np.where(start >= INF, INF, start + errand.service_min)
            if errand.deadline is not None:
                done = np.where(done > errand.deadline, INF, done)
            j = np.argmin(done, axis=0)
            cand = done[j, np.arange(opts.size)]
            new = mask | (1 << e)
            better = cand < best[new, opts]
            best[new, opts[better]] = cand[better]
            parent[new, opts[better]] = places[j[better]]
            via[new, opts[better]] = e
    return best, parent, via
