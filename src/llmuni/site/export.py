"""`make site-data`: compact JSON for the site (site/public/data/) and the video (video/src/data/), read
from the most complete results available (final, else pilot, else calibration). Read-only on results/."""

from __future__ import annotations

import json
from pathlib import Path

from llmuni.config import Config
from llmuni.oracle.run import load_tasks
from llmuni.travel import minutes, planning_pois

RUNS = ("", "pilot", "calibration")  # results/, results/pilot, results/calibration


def latest_run(cfg: Config) -> tuple[str, Path] | None:
    for run in RUNS:
        folder = cfg.root / "results" / run
        if (folder / "results.json").exists() and (folder / "grades.jsonl").exists():
            return (run or "final"), folder
    return None


def export_site_data(cfg: Config, hero_task: str | None = None) -> dict:
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

    plans = {}
    for tid, task in tasks.items():
        entry = {"optimal": oracle_plan(oracle[tid]["optimum"]), "optimal_all_sf": oracle_plan(oracle[tid]["global_optimum"]),
                 "plans": []}
        for g in (g for g in grades if g["task_id"] == tid):
            entry["plans"].append({
                "model": g["model"], "mode": g["mode"], "baseline": g["baseline"], "status": g["status"],
                "failure": g["failure"], "gap": g["optimality_gap"],
                "finish": minutes(g["finish"]) if g["finish"] else None,
                "stops": [{"category": s["category"], "name": s["store_name"], "at": where(s["poi_id"]) if s.get("poi_id") else None,
                           "match": s["match"], "arrive": minutes(s["arrive"]) if s.get("arrive") else None,
                           "done": minutes(s["done"]) if s.get("done") else None, "failed": s.get("failed")}
                          for s in g["stops"]],
            })
        plans[tid] = entry

    task_list = [{
        "id": t.task_id, "tier": t.tier, "weekday": t.weekday, "date": t.date, "prompt": t.prompt,
        "infeasible": t.design.infeasible, "reason": t.design.reason,
        "start": {"label": t.start.label, "at": [t.start.lon, t.start.lat], "depart": minutes(t.start.depart_time)},
        "end": None if t.end is None else {"label": t.end.label, "at": [t.end.lon, t.end.lat],
                                           "arrive_by": minutes(t.end.arrive_by) if t.end.arrive_by else None},
        "errands": [{"category": e.category, "brand": e.brand, "deadline": minutes(e.deadline) if e.deadline else None}
                    for e in t.errands],
    } for t in tasks.values()]

    meta = {"run": run, "benchmark_version": results["benchmark_version"], "osm_date": results["osm_date"],
            "gtfs_versions": results["gtfs_versions"], "tasks": len(task_list), "spend_usd_total": results.get("spend_usd_total")}
    board = json.loads((folder / "leaderboard.json").read_text(encoding="utf-8"))
    site = cfg.root / "site" / "public" / "data"
    site.mkdir(parents=True, exist_ok=True)
    for name, obj in {"meta": meta, "results": results, "leaderboard": board, "tasks": task_list, "plans": plans}.items():
        (site / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")

    hero = hero_task or next((t["id"] for t in task_list if t["tier"] == "hard" and not t["infeasible"]), task_list[0]["id"])
    video = cfg.root / "video" / "src" / "data"
    video.mkdir(parents=True, exist_ok=True)
    (video / "hero.json").write_text(json.dumps({
        "task": next(t for t in task_list if t["id"] == hero), **plans[hero], "headline": results["headline"],
        "leaderboard": board, "meta": meta, "placeholder": hero_task is None}, indent=1), encoding="utf-8")
    return meta
