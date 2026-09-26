"""`make grader-check`: round-trip the grader on real data. Each feasible task's all-SF optimal plan is
restated the way a closed-book model would answer (store name + street address, no ids), then matched and
replayed. A faithful grader recovers every store and reproduces the optimal finish (gap 0)."""

from __future__ import annotations

import json
from collections import Counter

from llmuni.config import Config
from llmuni.grader.answer import Answer, AnswerStop
from llmuni.grader.geocode import build_geocoder
from llmuni.grader.match import StoreMatcher
from llmuni.grader.replay import Grader
from llmuni.oracle.run import load_tasks, oracle_context


def run_grader_check(cfg: Config) -> dict:
    tasks = {t.task_id: t for t in load_tasks(cfg)}
    version_dir = cfg.root / "benchmark" / cfg.benchmark_version
    oracle = {r["task_id"]: r for r in map(json.loads, (version_dir / "oracle.jsonl").read_text().splitlines())}
    builder, pois = oracle_context(cfg)
    osm_sha = json.loads(cfg.paths.manifest.read_text())["sources"]["osm"]["sha256"]
    geocoder = build_geocoder(cfg.paths.raw / "sf.osm.pbf", cfg.paths.cache / f"geocoder_{osm_sha[:16]}.pkl")
    grader = Grader(builder, StoreMatcher(pois, geocoder), oracle)
    stores = pois.drop_duplicates("poi_id").set_index("poi_id")

    outcomes, methods, misses = Counter(), Counter(), []
    stops_total = stops_same = 0
    for task_id, record in oracle.items():
        plan = record["global_optimum"]
        if plan is None:
            continue
        answer = Answer(feasible=True, stops=[
            AnswerStop(category=s["category"], store_name=s["name"],
                       address=stores.at[s["poi_id"], "address"] if isinstance(stores.at[s["poi_id"], "address"], str) else None)
            for s in plan["stops"]])
        grade = grader.grade(tasks[task_id], answer, "closed_book")
        exact = grade.status == "feasible" and grade.optimality_gap == 0
        outcomes["exact" if exact else grade.status] += 1
        for stop, logged in zip(plan["stops"], grade.stops):
            stops_total += 1
            stops_same += logged["poi_id"] == stop["poi_id"]
            methods[logged["method"]] += 1
            if logged["poi_id"] != stop["poi_id"] and len(misses) < 12:
                misses.append(f"{task_id}: {stop['name']} -> {logged['poi_id']} ({logged['match']}, {logged['method']})")

    summary = {"tasks": sum(outcomes.values()), "outcomes": dict(outcomes), "stops": stops_total,
               "stops_recovered": stops_same, "methods": dict(methods), "examples_of_misses": misses}
    lines = [
        "# Phase 5: grader round trip",
        "",
        "Each feasible task's all-SF optimal plan, restated as a closed-book answer (store name + address, no ids),",
        "then matched and replayed by the grader.",
        "",
        f"- Tasks replayed to exactly the optimal finish: **{outcomes['exact']}/{summary['tasks']}**; "
        f"other outcomes: {', '.join(f'{k} {v}' for k, v in outcomes.items() if k != 'exact') or 'none'}.",
        f"- Stops matched back to the optimal plan's own store: **{stops_same}/{stops_total}** "
        f"(by method: {', '.join(f'{k} {v}' for k, v in methods.most_common())}).",
    ]
    if misses:
        lines += ["", "Stops matched to a different store (name-only fallback picks a branch of the same chain):", ""]
        lines += [f"- {m}" for m in misses]
    out = cfg.paths.reports / "phase5"
    out.mkdir(parents=True, exist_ok=True)
    (out / "grader_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
