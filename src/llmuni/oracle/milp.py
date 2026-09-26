"""MILP cross-check with HiGHS on the static-time relaxation: travel times fixed (e.g. at their
value for the departure time) and one opening window per store. The DP solves the same static
problem through a TravelMatrix whose arrivals are t + travel, so both must agree exactly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import highspy
import numpy as np

from llmuni.oracle.model import Errand, Instance, service_table
from llmuni.router import TravelMatrix


@dataclass
class StaticProblem:
    travel: np.ndarray  # (n, n) minutes; node 0 is the start
    depart: int
    groups: list[list[int]]  # per errand: its option nodes
    service: list[int]  # per errand
    windows: dict[int, tuple[int, int]]  # per option node: one (open, close) window
    deadlines: list[int | None]  # per errand
    end: int | None
    arrive_by: int | None
    horizon: int


def solve_milp(p: StaticProblem) -> int | None:
    """Minimum finish time (arrival at the end, else completion of the last errand); None if infeasible."""
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    integer = highspy.HighsVarType.kInteger
    errand_of = {v: e for e, group in enumerate(p.groups) for v in group}
    nodes = list(errand_of)
    big_m = p.horizon + int(p.travel.max()) + max(p.service) + 10

    y = {v: h.addVariable(0, 1, type=integer) for v in nodes}  # store v is visited
    start_at = {v: h.addVariable(0, p.horizon) for v in nodes}  # service start at v
    finish = h.addVariable(0, p.horizon)
    arc = {}
    for u in [0, *nodes]:
        for w in [*nodes, "finish"]:
            same_errand = u != 0 and w != "finish" and errand_of[u] == errand_of[w]
            if u != w and not same_errand and not (u == 0 and w == "finish"):
                arc[u, w] = h.addVariable(0, 1, type=integer)

    for group in p.groups:
        h.addConstr(sum(y[v] for v in group) == 1)
    h.addConstr(sum(arc[0, w] for w in nodes) == 1)
    h.addConstr(sum(arc[u, "finish"] for u in nodes) == 1)
    for v in nodes:
        h.addConstr(sum(var for (u, w), var in arc.items() if w == v) == y[v])
        h.addConstr(sum(var for (u, w), var in arc.items() if u == v) == y[v])

    for (u, w), var in arc.items():  # MTZ-style timing; positive service times rule out cycles
        if w == "finish":
            tail = int(p.travel[u, p.end]) if p.end is not None else 0
            h.addConstr(finish >= start_at[u] + p.service[errand_of[u]] + tail - big_m * (1 - var))
        elif u == 0:
            h.addConstr(start_at[w] >= p.depart + int(p.travel[0, w]) - big_m * (1 - var))
        else:
            h.addConstr(start_at[w] >= start_at[u] + p.service[errand_of[u]] + int(p.travel[u, w]) - big_m * (1 - var))

    for v in nodes:
        opens, closes = p.windows[v]
        service = p.service[errand_of[v]]
        h.addConstr(start_at[v] >= opens * y[v])
        h.addConstr(start_at[v] + service <= min(closes, p.horizon) + big_m * (1 - y[v]))
        deadline = p.deadlines[errand_of[v]]
        if deadline is not None:
            h.addConstr(start_at[v] + service <= deadline + big_m * (1 - y[v]))
    if p.end is not None and p.arrive_by is not None:
        h.addConstr(finish <= p.arrive_by)

    h.minimize(finish)
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        return None
    return round(h.val(finish))


def static_instance(p: StaticProblem) -> Instance:
    """The same static problem for the DP: grid arrivals dep + travel and walking = travel, so
    TravelMatrix.arrival(i, j, t) == t + travel[i, j] for every t."""
    n = p.travel.shape[0]
    departures = np.arange(0, p.horizon + 1, 5)
    arrive = (departures[None, None, :] + p.travel[:, :, None]).astype(np.uint16)
    tm = TravelMatrix([f"n{i}" for i in range(n)], date(2026, 10, 7), 0, 5, arrive, p.travel.astype(np.uint16))
    errands = [Errand(f"e{e}", p.service[e], p.deadlines[e]) for e in range(len(p.groups))]
    options = [np.array(group) for group in p.groups]
    tables = [np.stack([service_table([p.windows[v]], p.service[e], p.horizon) for v in group])
              for e, group in enumerate(p.groups)]
    return Instance(tm, 0, p.depart, errands, options, tables, p.end, p.arrive_by, p.horizon)
