import random
from datetime import date

import numpy as np
import pytest

from llmuni.oracle.brute import brute_force
from llmuni.oracle.dp import solve
from llmuni.oracle.model import INF, Errand, Instance, arrivals, service_table, simulate
from llmuni.router import NO_TRIP, TravelMatrix, fifo_arrivals

START, STEP, N_DEP = 480, 5, 60  # grid 8:00-12:55


def random_instance(seed: int, n_errands: int = 3, per_errand: int = 3) -> Instance:
    rng = np.random.default_rng(seed)
    n = 1 + n_errands * per_errand + 1  # start, option places, end
    minutes = rng.integers(3, 45, size=(n, n, N_DEP)).astype(np.uint16)
    minutes[rng.random((n, n, N_DEP)) < 0.05] = NO_TRIP
    walk = rng.integers(10, 90, size=(n, n)).astype(np.uint16)
    np.fill_diagonal(walk, 0)
    tm = TravelMatrix([f"p{i}" for i in range(n)], date(2026, 10, 7), START, STEP, fifo_arrivals(minutes, START, STEP), walk)
    errands, options, tables = [], [], []
    horizon = 15 * 60
    for e in range(n_errands):
        service = int(rng.integers(5, 25))
        deadline = int(rng.integers(560, 800)) if rng.random() < 0.3 else None
        errands.append(Errand(f"c{e}", service, deadline))
        opts = np.arange(1 + e * per_errand, 1 + (e + 1) * per_errand)
        options.append(opts)
        rows = []
        for _ in opts:
            opens = int(rng.integers(420, 660))
            intervals = [(opens, opens + int(rng.integers(30, 300)))]
            if rng.random() < 0.3:  # a second shift after a break
                intervals.append((intervals[0][1] + 60, intervals[0][1] + 240))
            rows.append(service_table(intervals, service, horizon))
        tables.append(np.stack(rows))
    end = n - 1 if rng.random() < 0.6 else None
    arrive_by = int(rng.integers(600, 900)) if end is not None and rng.random() < 0.5 else None
    return Instance(tm, 0, int(rng.integers(470, 560)), errands, options, tables, end, arrive_by, horizon)


@pytest.mark.parametrize("seed", range(150))
def test_dp_matches_brute_force(seed):
    inst = random_instance(seed)
    dp, brute = solve(inst), brute_force(inst)
    assert (dp is None) == (brute is None)
    if dp is not None:
        assert dp.finish == brute.finish


def random_static_problem(seed: int):
    from llmuni.oracle.milp import StaticProblem

    rng = np.random.default_rng(seed)
    n_errands, per = 3, int(rng.integers(2, 4))
    n = 1 + n_errands * per + 1
    travel = rng.integers(3, 40, size=(n, n))
    np.fill_diagonal(travel, 0)
    groups = [list(range(1 + e * per, 1 + (e + 1) * per)) for e in range(n_errands)]
    windows = {}
    for group in groups:
        for v in group:
            opens = int(rng.integers(420, 700))
            windows[v] = (opens, opens + int(rng.integers(40, 360)))
    service = [int(rng.integers(5, 25)) for _ in groups]
    deadlines = [int(rng.integers(560, 900)) if rng.random() < 0.3 else None for _ in groups]
    end = n - 1 if rng.random() < 0.6 else None
    arrive_by = int(rng.integers(650, 950)) if end is not None and rng.random() < 0.5 else None
    return StaticProblem(travel, int(rng.integers(450, 600)), groups, service, windows, deadlines, end, arrive_by, 1080)


@pytest.mark.parametrize("seed", range(40))
def test_dp_matches_highs_milp_on_static_problems(seed):
    from llmuni.oracle.milp import solve_milp, static_instance

    problem = random_static_problem(seed)
    dp = solve(static_instance(problem))
    milp = solve_milp(problem)
    assert (dp is None) == (milp is None)
    if dp is not None:
        assert dp.finish == milp


def test_vectorized_arrivals_match_scalar():
    inst = random_instance(7)
    tm = inst.matrix
    origins = np.array([0, 1, 2, 3, 0])
    times = np.array([470, 481, 500, 777, 1000])
    dests = np.arange(tm.walk.shape[0])
    vec = arrivals(tm, origins, times, dests)
    for a, (i, t) in enumerate(zip(origins, times)):
        for b, j in enumerate(dests):
            scalar = tm.arrival(int(i), int(j), int(t))
            assert vec[a, b] == (INF if scalar is None else scalar)


def test_service_table_waits_for_opening_and_respects_closing():
    table = service_table([(600, 660), (720, 780)], service=20, horizon=900)
    assert table[500] == 600  # early: wait until 10:00
    assert table[630] == 630  # open with 30 min left: start now
    assert table[645] == 720  # only 15 min before closing: wait for the second shift
    assert table[761] == INF  # too late for either shift
    assert (np.diff(table) >= 0).all()  # arriving later never lets service start earlier


def test_service_table_skips_windows_too_short_or_too_late():
    assert (service_table([(720, 730)], service=15, horizon=900) == INF).all()  # 10-minute window, 15-minute errand
    # an overnight shift opening at 22:55: a 10-minute errand would end after the 23:00 horizon
    assert (service_table([(1375, 1560)], service=10, horizon=1380) == INF).all()


@pytest.mark.parametrize("seed", range(30))
def test_every_finite_service_start_fits_inside_a_window(seed):
    rng = np.random.default_rng(seed)
    horizon, service = 1380, int(rng.integers(5, 30))
    opens = np.sort(rng.integers(300, 1500, size=3))
    intervals = [(int(o), int(o + rng.integers(1, 200))) for o in opens]
    table = service_table(intervals, service, horizon)
    for arrive, start in enumerate(table):
        if start < INF:
            assert start >= arrive and start + service <= horizon
            assert any(o <= start and start + service <= c for o, c in intervals)


@pytest.mark.parametrize("seed", range(40))
def test_earliest_completion_matches_brute_force_over_partial_plans(seed):
    import itertools

    from llmuni.oracle.dp import earliest_completion

    inst = random_instance(seed)
    target, m = 0, len(inst.errands)
    brute = None
    for size in range(1, m + 1):
        for order in itertools.permutations(range(m), size):
            if order[-1] != target:
                continue
            for places in itertools.product(*(inst.options[e] for e in order)):
                out = simulate(inst, [(e, int(p)) for e, p in zip(order, places)])
                complete = len(out.stops) == size and out.failure_kind in (None, "incomplete")
                if complete and (brute is None or out.stops[-1].done < brute):
                    brute = out.stops[-1].done
    assert earliest_completion(inst, target) == brute


def test_simulate_reports_why_a_plan_fails():
    inst = random_instance(3)
    late_first = [(0, int(inst.options[0][0]))]
    outcome = simulate(inst, late_first)
    assert not outcome.feasible and outcome.failure


def test_multi_errand_place_needs_no_travel_between_errands():
    tm = TravelMatrix(["s", "x"], date(2026, 10, 7), START, STEP,
                      fifo_arrivals(np.full((2, 2, N_DEP), 10, np.uint16), START, STEP),
                      np.array([[0, 30], [30, 0]], np.uint16))
    table = service_table([(0, 1439)], 10, 1200)
    inst = Instance(tm, 0, 540, [Errand("coffee", 10), Errand("bakery", 10)],
                    [np.array([1]), np.array([1])], [table[None], table[None]], horizon=1200)
    outcome = solve(inst)
    # 9:00 -> next grid departure 9:00, 10 min ride, coffee 9:10-9:20, bakery 9:20-9:30 at the same place
    assert outcome.finish == 570
