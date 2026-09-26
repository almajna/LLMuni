"""`make site-data`: compact JSON for the site (site/public/data/) and the video (video/src/data/), read
from the most complete results available (final, else pilot, else calibration). Read-only on results/.

`llmuni site-data --routes` first routes every hop of every plan the replay draws with R5 (cached in
cache/site_routes.json, see site.routes); without it, hops without a cached itinerary are drawn straight.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

from llmuni.config import Config
from llmuni.oracle.run import load_tasks
from llmuni.site.routes import cache_path, compute_routes, hop_key, plan_hops, timed_path
from llmuni.travel import minutes, planning_pois

log = logging.getLogger(__name__)
RUNS = ("", "pilot", "calibration")  # results/, results/pilot, results/calibration
REPLAY_MODES = ("open_book", "closed_book")
REFERENCE = {"closed_book": "global_optimum", "open_book": "optimum", "tool_use": "optimum"}


def latest_run(cfg: Config) -> tuple[str, Path] | None:
    for run in RUNS:
        folder = cfg.root / "results" / run
        if (folder / "results.json").exists() and (folder / "grades.jsonl").exists():
            return (run or "final"), folder
    return None


def failure_kind(grade: dict) -> str:
    """One word for how a plan on a feasible task ended: feasible, closed, deadline, late, unreachable,
    incomplete, wrong_address, no_such_store, unverifiable, invalid_plan, declined or invalid_json."""
    if grade["status"] == "infeasible":
        return (grade["failure"] or "infeasible").split(":")[0]
    if grade["status"] == "hallucinated":
        return "no_such_store"
    return grade["status"]


def export_site_data(cfg: Config, hero_task: str | None = None, routes: bool = False) -> dict:
    found = latest_run(cfg)
    if found is None:
        raise FileNotFoundError("no results yet: run `make pilot` (or baselines) first")
    run, folder = found
    results = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    grades = [json.loads(line) for line in (folder / "grades.jsonl").read_text(encoding="utf-8").splitlines() if line]
    version_dir = cfg.root / "benchmark" / cfg.benchmark_version
    oracle = {r["task_id"]: r for r in map(json.loads, (version_dir / "oracle.jsonl").read_text().splitlines())}
    task_ids = sorted({g["task_id"] for g in grades})
    tasks = {t.task_id: t for t in load_tasks(cfg) if t.task_id in task_ids}
    stores = planning_pois(cfg).drop_duplicates("poi_id").set_index("poi_id")

    def where(poi_id):
        return [round(float(stores.at[poi_id, "lon"]), 6), round(float(stores.at[poi_id, "lat"]), 6)] \
            if poi_id in stores.index else None

    def oracle_plan(plan):
        if plan is None:
            return None
        return {"finish": minutes(plan["finish"]), "end_arrive": minutes(plan["end_arrive"]) if plan["end_arrive"] else None,
                "stops": [{"category": s["category"], "name": s["name"], "at": where(s["poi_id"]),
                           "arrive": minutes(s["arrive"]), "done": minutes(s["done"])} for s in plan["stops"]]}

    plans: dict[str, dict] = {}
    for tid, task in tasks.items():
        entry = {"optimal": oracle_plan(oracle[tid]["optimum"]), "optimal_all_sf": oracle_plan(oracle[tid]["global_optimum"]),
                 "plans": []}
        for g in (g for g in grades if g["task_id"] == tid):
            entry["plans"].append({
                "model": g["model"], "mode": g["mode"], "baseline": g["baseline"], "status": g["status"],
                "kind": failure_kind(g), "failure": g["failure"], "gap": g["optimality_gap"],
                "finish": minutes(g["finish"]) if g["finish"] else None,
                "end_arrive": minutes(g["end_arrive"]) if g.get("end_arrive") else None,
                "stops": [{"category": s["category"], "name": s["store_name"], "at": where(s["poi_id"]) if s.get("poi_id") else None,
                           "match": s["match"], "reason": s.get("reason"),
                           "arrive": minutes(s["arrive"]) if s.get("arrive") else None,
                           "done": minutes(s["done"]) if s.get("done") else None, "failed": s.get("failed")}
                          for s in g["stops"]],
            })
        plans[tid] = entry

    routed = add_paths(cfg, tasks, plans, routes)

    task_list = [{
        "id": t.task_id, "tier": t.tier, "weekday": t.weekday, "date": t.date, "prompt": t.prompt,
        "infeasible": t.design.infeasible, "reason": t.design.reason,
        "start": {"label": t.start.label, "at": [t.start.lon, t.start.lat], "depart": minutes(t.start.depart_time)},
        "end": None if t.end is None else {"label": t.end.label, "at": [t.end.lon, t.end.lat],
                                           "arrive_by": minutes(t.end.arrive_by) if t.end.arrive_by else None},
        "errands": [{"category": e.category, "brand": e.brand, "deadline": minutes(e.deadline) if e.deadline else None}
                    for e in t.errands],
    } for t in tasks.values()]

    failures: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for g in grades:
        if g["task_feasible"]:
            failures[g["mode"]][g["model"]][failure_kind(g)] += 1

    sources = json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))["sources"]
    models = [m for m in cfg.eval.models if m in results["per_model"]]
    meta = {"run": run, "benchmark_version": results["benchmark_version"], "osm_date": results["osm_date"],
            "gtfs_versions": results["gtfs_versions"], "tasks": len(task_list),
            "tasks_by_tier": dict(Counter(t["tier"] for t in task_list)),
            "feasible_tasks": sum(not t["infeasible"] for t in task_list), "models": models,
            "registry_date": (sources.get("registry", {}).get("downloaded_at") or "")[:10] or None,
            "spend_usd_total": results.get("spend_usd_total"), "routed_hops": routed,
            "hero_task": hero_task or cfg.site.hero_task}
    board = json.loads((folder / "leaderboard.json").read_text(encoding="utf-8"))
    site = cfg.root / "site" / "public" / "data"
    site.mkdir(parents=True, exist_ok=True)
    for name, obj in {"meta": meta, "results": results, "leaderboard": board, "tasks": task_list, "plans": plans,
                      "failures": failures}.items():
        (site / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")

    hero = meta["hero_task"] if meta["hero_task"] in plans else \
        next((t["id"] for t in task_list if t["tier"] == "hard" and not t["infeasible"]), task_list[0]["id"])
    video = cfg.root / "video" / "src" / "data"
    video.mkdir(parents=True, exist_ok=True)
    (video / "hero.json").write_text(json.dumps({
        "task": next(t for t in task_list if t["id"] == hero), **plans[hero], "headline": results["headline"],
        "results": {m: {mode: {k: s[k] for k in ("feasible_pct", "median_gap", "impossible_plan_pct", "tasks")}
                        for mode, s in modes.items()} for m, modes in results["per_model"].items()},
        "failures": failures, "leaderboard": board, "meta": meta, "placeholder": hero != meta["hero_task"]},
        indent=1), encoding="utf-8")
    return meta


def add_paths(cfg: Config, tasks: dict, plans: dict[str, dict], routes: bool) -> list[int]:
    """Give the optimal plans and every model plan of the replayed modes a timed [lon, lat, minute] path;
    returns [hops drawn along an R5 itinerary, hops in all]."""
    jobs = []  # (target dict, day, hops)
    for tid, entry in plans.items():
        task = tasks[tid]
        start, end = (task.start.lon, task.start.lat), (task.end.lon, task.end.lat) if task.end else None
        depart = minutes(task.start.depart_time)
        for key in ("optimal", "optimal_all_sf"):
            plan = entry[key]
            if plan:
                jobs.append((plan, task.date, plan_hops(start, depart, plan["stops"], end, plan["end_arrive"])))
        for plan in entry["plans"]:
            if not plan["baseline"] and plan["mode"] in REPLAY_MODES:
                jobs.append((plan, task.date, plan_hops(start, depart, plan["stops"], end, plan["end_arrive"])))
    wanted = {hop_key(day, a, b, leave): (day, a, b, leave) for _, day, hops in jobs for a, b, leave, _ in hops}
    path = cache_path(cfg)
    legs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if routes:
        try:
            legs = compute_routes(cfg, wanted)
        except Exception as exc:  # no Java or no network build: keep cached itineraries, draw the rest straight
            log.warning("site routes unavailable (%s); hops without a cached itinerary are drawn straight", exc)
    for plan, day, hops in jobs:
        plan["path"] = [[round(x, 6), round(y, 6), round(t, 2)] for x, y, t in timed_path(hops, legs, day)]
    return [sum(1 for k in wanted if legs.get(k)), len(wanted)]
