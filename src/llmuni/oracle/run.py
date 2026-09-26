"""`make oracle`: optimal plans (or proofs of infeasibility) for every task, plus the brute-force and
MILP cross-checks. Writes benchmark/<version>/oracle.jsonl and reports/phase4/oracle_summary.md."""

from __future__ import annotations

import json
import logging
from datetime import date
from time import perf_counter

import numpy as np
import pandas as pd

from llmuni.config import Config
from llmuni.oracle.brute import brute_force
from llmuni.oracle.build import UNIVERSES, InstanceBuilder
from llmuni.oracle.dp import solve
from llmuni.oracle.milp import StaticProblem, solve_milp, static_instance
from llmuni.oracle.model import Instance, Outcome
from llmuni.tasks.landmarks import load_landmarks
from llmuni.tasks.schema import Task
from llmuni.travel import Matrices, hhmm, minutes, planning_pois, routable_places

log = logging.getLogger(__name__)


def load_tasks(cfg: Config) -> list[Task]:
    path = cfg.root / "benchmark" / cfg.benchmark_version / "tasks.jsonl"
    return [Task.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def oracle_context(cfg: Config) -> tuple[InstanceBuilder, pd.DataFrame]:
    pois = planning_pois(cfg)
    landmarks = load_landmarks(cfg)
    return InstanceBuilder(cfg, Matrices(cfg, routable_places(landmarks, pois)), pois), pois


def run_oracle_stage(cfg: Config) -> list[dict]:
    tasks = load_tasks(cfg)
    builder, pois = oracle_context(cfg)
    names = pois.drop_duplicates("poi_id").set_index("poi_id")["name"].to_dict()
    records, timings = [], []
    for n, task in enumerate(tasks, 1):
        record = {"task_id": task.task_id, "tier": task.tier}
        for universe in UNIVERSES:
            started = perf_counter()
            inst = builder.instance(task, universe)
            outcome = solve(inst)
            timings.append({"tier": task.tier, "universe": universe, "seconds": perf_counter() - started})
            key = "optimum" if universe == "candidates" else "global_optimum"
            record[key] = describe(task, inst, outcome, names)
        feasible = record["optimum"] is not None
        if feasible == task.design.infeasible or (record["global_optimum"] is None) != (not feasible):
            raise AssertionError(f"{task.task_id}: oracle disagrees with the task design")
        record["feasible"] = feasible
        record["reason"] = task.design.reason
        records.append(record)
        if n % 25 == 0:
            log.info("oracle: %d/%d tasks", n, len(tasks))

    brute = check_brute_force(builder, [t for t in tasks if t.tier == "easy"], records)
    milp = check_milp(builder, [t for t in tasks if t.tier == "easy" and not t.design.infeasible])
    out = cfg.root / "benchmark" / cfg.benchmark_version / "oracle.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    write_summary(cfg, tasks, records, pd.DataFrame(timings), brute, milp)
    return records


def describe(task: Task, inst: Instance, outcome: Outcome | None, names: dict[str, str]) -> dict | None:
    """JSON-ready plan: stops with store ids, names and times; None when infeasible."""
    if outcome is None:
        return None
    ids = inst.matrix.ids
    depart = minutes(task.start.depart_time)
    return {
        "finish": hhmm(outcome.finish),
        "duration_min": outcome.finish - depart,
        "end_arrive": hhmm(outcome.end_arrive) if outcome.end_arrive is not None else None,
        "stops": [
            {
                "category": task.errands[s.errand].category,
                "poi_id": ids[s.place],
                "name": names.get(ids[s.place]),
                "arrive": hhmm(s.arrive),
                "start": hhmm(s.start),
                "done": hhmm(s.done),
                "wait_min": s.start - s.arrive,
            }
            for s in outcome.stops
        ],
    }


def check_brute_force(builder: InstanceBuilder, tasks: list[Task], records: list[dict]) -> dict:
    """Exhaustive enumeration over the listed stores must reproduce every DP optimum."""
    by_id = {r["task_id"]: r for r in records}
    agree = 0
    for task in tasks:
        best = brute_force(builder.instance(task, "candidates"))
        expected = by_id[task.task_id]["optimum"]
        same = (best is None and expected is None) or (
            best is not None and expected is not None and hhmm(best.finish) == expected["finish"])
        if not same:
            raise AssertionError(f"{task.task_id}: brute force {best and hhmm(best.finish)} != DP {expected}")
        agree += 1
    return {"tasks": len(tasks), "agree": agree}


def check_milp(builder: InstanceBuilder, tasks: list[Task]) -> dict:
    """Static relaxation of each task (travel times fixed at departure, stores with a single opening
    window that day): the DP and the HiGHS MILP must find the same optimum."""
    checked = agree = 0
    for task in tasks:
        problem = static_problem(builder, task)
        if problem is None:
            continue
        checked += 1
        dp = solve(static_instance(problem))
        milp = solve_milp(problem)
        if (dp is None and milp is None) or (dp is not None and dp.finish == milp):
            agree += 1
        else:
            log.warning("%s: static DP %s vs MILP %s", task.task_id, dp and dp.finish, milp)
    return {"checked": checked, "agree": agree, "skipped": len(tasks) - checked}


def static_problem(builder: InstanceBuilder, task: Task) -> StaticProblem | None:
    inst = builder.instance(task, "candidates")
    day = date.fromisoformat(task.date)
    nodes = [inst.start]
    groups, windows = [], {}
    for spec, opts in zip(task.errands, inst.options):
        group = []
        for q in opts:
            intervals = builder.intervals(inst.matrix.ids[q], day)
            if len(intervals) == 1:
                windows[len(nodes)] = intervals[0]
                group.append(len(nodes))
                nodes.append(int(q))
        if not group:
            return None
        groups.append(group)
    end = None
    if inst.end is not None:
        end = len(nodes)
        nodes.append(inst.end)
    arrive = [[inst.matrix.arrival(a, b, inst.depart) for b in nodes] for a in nodes]
    if any(t is None for row in arrive for t in row):
        return None  # a pair is unreachable at departure time; no static relaxation
    travel = np.array(arrive) - inst.depart
    np.fill_diagonal(travel, 0)
    return StaticProblem(travel, inst.depart, groups, [e.service_min for e in inst.errands], windows,
                         [e.deadline for e in inst.errands], end, inst.arrive_by, inst.horizon)


def write_summary(cfg: Config, tasks: list[Task], records: list[dict], timings: pd.DataFrame,
                  brute: dict, milp: dict) -> None:
    rows = []
    for tier in cfg.tasks.tiers:
        group = [r for r in records if r["tier"] == tier]
        feasible = [r for r in group if r["feasible"]]
        gains = [r["optimum"]["duration_min"] - r["global_optimum"]["duration_min"] for r in feasible]
        rows.append({
            "tier": tier,
            "tasks": len(group),
            "feasible": len(feasible),
            "optimal duration, median (min)": int(np.median([r["optimum"]["duration_min"] for r in feasible])),
            "global beats listed stores": sum(g > 0 for g in gains),
            "median gain (min)": int(np.median([g for g in gains if g > 0])) if any(g > 0 for g in gains) else 0,
            "DP seconds, p95 (global)": round(timings[(timings.tier == tier) & (timings.universe == "global")]
                                              ["seconds"].quantile(0.95), 2),
        })
    header = list(rows[0])
    lines = [
        f"# Phase 4: oracle for {cfg.benchmark_version}",
        "",
        "Optimum over the listed stores (open-book / tool modes) and over every valid store in SF (closed book).",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
        *("| " + " | ".join(str(r[h]) for h in header) + " |" for r in rows),
        "",
        f"- Brute force (every order x every listed store) reproduces the DP optimum on "
        f"{brute['agree']}/{brute['tasks']} easy tasks.",
        f"- HiGHS MILP on static relaxations agrees with the DP on {milp['agree']}/{milp['checked']} easy tasks "
        f"({milp['skipped']} skipped: a listed store had split hours that day).",
        f"- Every infeasible task is proven infeasible by the exhaustive DP in both universes.",
    ]
    out = cfg.paths.reports / "phase4"
    out.mkdir(parents=True, exist_ok=True)
    (out / "oracle_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
