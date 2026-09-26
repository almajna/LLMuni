"""The oracle's problem model: places, errands, opening-hours tables, and FIFO travel.

All times are integer minutes after midnight of the task day. A plan starts at `start`
at `depart`, performs every errand once at one of its option places (waiting for the
place to open if needed; service must end by closing time and by the errand's deadline),
then travels to `end` (if any) by `arrive_by`. Everything must be done by `horizon`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from llmuni.router import NO_TRIP, TravelMatrix

INF = 10**9


@dataclass(frozen=True)
class Errand:
    category: str
    service_min: int
    deadline: int | None = None  # the errand must be finished by this minute


@dataclass
class Instance:
    matrix: TravelMatrix
    start: int  # matrix index
    depart: int
    errands: list[Errand]
    options: list[np.ndarray]  # per errand: matrix indices of places that can serve it
    service_start: list[np.ndarray]  # per errand: (len(options), horizon + 2) earliest service start
    end: int | None = None
    arrive_by: int | None = None
    horizon: int = 23 * 60
    _option_pos: list[dict[int, int]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._option_pos = [{int(q): k for k, q in enumerate(opts)} for opts in self.options]

    def service_start_at(self, errand: int, place: int, arrive: int) -> int:
        """Earliest time errand can start at place when arriving at `arrive` (INF if impossible)."""
        k = self._option_pos[errand].get(place)
        if k is None:
            return INF
        return int(self.service_start[errand][k, min(arrive, self.horizon + 1)])


def service_table(intervals: list[tuple[int, int]], service: int, horizon: int) -> np.ndarray:
    """Earliest service start for every arrival minute 0..horizon+1 (INF where impossible):
    the first open interval in which `service` minutes fit, finishing by closing and by horizon.
    Non-decreasing in the arrival minute."""
    table = np.full(horizon + 2, INF, dtype=np.int64)
    minutes = np.arange(horizon + 2)
    for opens, closes in sorted(intervals, reverse=True):  # earlier intervals overwrite later ones
        last = min(closes, horizon) - service  # latest start that still finishes in time
        if last >= max(opens, 0):  # skip windows too short (or too late) for the service
            table[: last + 1] = np.maximum(minutes[: last + 1], opens)
    return table


def arrivals(tm: TravelMatrix, origins: np.ndarray, times: np.ndarray, dests: np.ndarray) -> np.ndarray:
    """Vectorized TravelMatrix.arrival: (len(origins), len(dests)) earliest arrival minutes, INF if unreachable."""
    origins, times, dests = np.asarray(origins), np.asarray(times, dtype=np.int64), np.asarray(dests)
    walk = tm.walk[np.ix_(origins, dests)].astype(np.int64)
    out = np.where(walk == NO_TRIP, INF, times[:, None] + walk)
    k = np.maximum(0, -(-(times - tm.start) // tm.step))
    on_grid = k < tm.arrive.shape[2]
    if on_grid.any():
        transit = tm.arrive[origins[on_grid][:, None], dests[None, :], k[on_grid][:, None]].astype(np.int64)
        out[on_grid] = np.minimum(out[on_grid], np.where(transit == NO_TRIP, INF, transit))
    return np.where(origins[:, None] == dests[None, :], times[:, None], out)


@dataclass(frozen=True)
class Stop:
    errand: int
    place: int
    arrive: int
    start: int  # service start, after any wait for opening
    done: int


@dataclass
class Outcome:
    """Result of following a fixed sequence of (errand, place) visits."""

    stops: list[Stop]
    feasible: bool
    finish: int | None  # arrival at the end, or completion of the last errand
    end_arrive: int | None = None
    failure: str | None = None  # "<kind>: <detail>", kind in unreachable/closed/deadline/incomplete/late
    failed_at: tuple[int, int, int] | None = None  # (errand, place, arrival minute) where the plan broke

    @property
    def failure_kind(self) -> str | None:
        return self.failure.split(":")[0] if self.failure else None


def simulate(inst: Instance, sequence: list[tuple[int, int]]) -> Outcome:
    """Follow (errand, place) visits in order with earliest arrivals, waiting for openings."""
    tm, t, here, stops = inst.matrix, inst.depart, inst.start, []
    for errand, place in sequence:
        arrive = tm.arrival(here, place, t)
        if arrive is None or arrive > inst.horizon:
            return Outcome(stops, False, None, failure=f"unreachable: errand {errand}'s store before the end of the day",
                           failed_at=(errand, place, arrive if arrive is not None else -1))
        start = inst.service_start_at(errand, place, arrive)
        if start >= INF:
            return Outcome(stops, False, None, failure=f"closed: errand {errand} cannot be served after arriving at {arrive}",
                           failed_at=(errand, place, arrive))
        done = start + inst.errands[errand].service_min
        stops.append(Stop(errand, place, arrive, start, done))
        deadline = inst.errands[errand].deadline
        if deadline is not None and done > deadline:
            return Outcome(stops, False, None, failure=f"deadline: errand {errand} done at {done} > {deadline}",
                           failed_at=(errand, place, arrive))
        t, here = done, place
    if len({e for e, _ in sequence}) != len(inst.errands):
        return Outcome(stops, False, None, failure="incomplete: not every errand is done")
    if inst.end is None:
        return Outcome(stops, True, t)
    arrive = tm.arrival(here, inst.end, t)
    limit = min(inst.horizon, inst.arrive_by if inst.arrive_by is not None else inst.horizon)
    if arrive is None or arrive > limit:
        return Outcome(stops, False, None, arrive, failure="late: cannot reach the end in time")
    return Outcome(stops, True, arrive, arrive)
