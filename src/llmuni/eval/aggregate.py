"""results.json (the brief's section 10 keys, plus per-tier breakdowns) and leaderboard.json from graded rows.

Rates on feasible tasks: feasible_pct (plan replays feasible), impossible_plan_pct (plan breaks: closed store,
missed deadline, late, a store that does not exist, or a real store at a wrong address), unverifiable_pct,
false_infeasible_pct. Over answers that propose a plan: hallucination_pct (names a store found in neither OSM nor
the city's business registry), wrong_address_pct (a real store at an address where it is not) and
not_in_osm_pct (a real store OSM lacks, so its hours cannot be checked).
On infeasible tasks: correct_infeasible_pct. Gaps: (model finish - optimal finish) / (optimal finish - start)
over feasible replays, against the listed-store optimum (open book, tools) or the all-SF optimum (closed book).
"""

from __future__ import annotations

import json
from collections import Counter
from statistics import mean, median

from llmuni.config import Config
from llmuni.tasks.schema import Task

TIERS = ("easy", "medium", "hard")
IMPOSSIBLE = ("infeasible", "hallucinated", "wrong_address")  # the plan cannot be carried out as written


def pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def summarize(rows: list[dict]) -> dict:
    feasible = [r for r in rows if r["task_feasible"]]
    infeasible = [r for r in rows if not r["task_feasible"]]
    planned = [r for r in rows if r["claimed_feasible"]]
    gaps = [r["optimality_gap"] for r in feasible if r["status"] == "feasible" and r["optimality_gap"] is not None]
    tokens = [r["prompt_tokens"] + r["completion_tokens"] for r in rows]
    return {
        "tasks": len(rows),
        "feasible_pct": pct(sum(r["status"] == "feasible" for r in feasible), len(feasible)),
        "impossible_plan_pct": pct(sum(r["status"] in IMPOSSIBLE for r in feasible), len(feasible)),
        "unverifiable_pct": pct(sum(r["status"] == "unverifiable" for r in feasible), len(feasible)),
        "mean_gap": round(mean(gaps), 4) if gaps else None,
        "median_gap": round(median(gaps), 4) if gaps else None,
        "hallucination_pct": pct(sum(r["hallucinated_store"] for r in planned), len(planned)),
        "wrong_address_pct": pct(sum(r.get("wrong_address", False) for r in planned), len(planned)),
        "not_in_osm_pct": pct(sum(r.get("not_in_osm_stops", 0) > 0 for r in planned), len(planned)),
        "correct_infeasible_pct": pct(sum(r["correct_infeasible_call"] is True for r in infeasible), len(infeasible)),
        "false_infeasible_pct": pct(sum(r["false_infeasible_call"] for r in feasible), len(feasible)),
        "invalid_json_pct": pct(sum(r["status"] == "invalid_json" for r in rows), len(rows)),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "avg_tokens": round(mean(tokens)) if tokens else 0,
    }


def with_tiers(rows: list[dict]) -> dict:
    return summarize(rows) | {"by_tier": {tier: summarize([r for r in rows if r["tier"] == tier]) for tier in TIERS}}


def aggregate(cfg: Config, rows: list[dict], tasks: list[Task]) -> dict:
    manifest = json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))
    sources = manifest["sources"]
    per_model: dict[str, dict] = {}
    for r in rows:
        if not r["baseline"]:
            per_model.setdefault(r["model"], {}).setdefault(r["mode"], []).append(r)
    per_model = {m: {mode: with_tiers(rs) for mode, rs in modes.items()} for m, modes in per_model.items()}
    baselines = {name: with_tiers([r for r in rows if r["baseline"] and r["model"] == name])
                 for name in sorted({r["model"] for r in rows if r["baseline"]})}
    return {
        "benchmark_version": cfg.benchmark_version,
        "gtfs_versions": {k.removeprefix("gtfs_"): v["service_date_range"] for k, v in sources.items() if k.startswith("gtfs_")},
        "osm_date": (sources["osm"].get("snapshot_timestamp") or "")[:10],
        "n_tasks_by_tier": dict(Counter(t.tier for t in tasks)),
        "per_model": per_model,
        "baselines": baselines,
        "headline": headline(per_model),
    }


def headline(per_model: dict) -> dict:
    def best(mode: str, key: str, lowest: bool) -> tuple[str | None, float | None]:
        scored = [(m, modes[mode][key]) for m, modes in per_model.items() if mode in modes and modes[mode][key] is not None]
        if not scored:
            return None, None
        return (min if lowest else max)(scored, key=lambda kv: kv[1])

    top_closed, _ = best("closed_book", "feasible_pct", lowest=False)
    open_model, gap_open = best("open_book", "median_gap", lowest=True)
    tool_model, gap_tool = best("tool_use", "median_gap", lowest=True)
    return {
        "pct_impossible_best_model_closed_book":
            per_model[top_closed]["closed_book"]["impossible_plan_pct"] if top_closed else None,
        "best_model_closed_book": top_closed,
        "best_gap_open_book": gap_open,
        "best_model_open_book": open_model,
        "best_gap_tool_mode": gap_tool,
        "best_model_tool_mode": tool_model,
        "tool_mode_improvement_pct":
            round(100 * (gap_open - gap_tool) / gap_open, 1) if gap_open and gap_tool is not None else None,
    }


def leaderboard(results: dict) -> list[dict]:
    entries = []
    for model, modes in results["per_model"].items():
        for mode, s in modes.items():
            entries.append({"model": model, "mode": mode, **{k: s[k] for k in (
                "feasible_pct", "median_gap", "impossible_plan_pct", "hallucination_pct", "wrong_address_pct",
                "not_in_osm_pct", "unverifiable_pct",
                "correct_infeasible_pct", "false_infeasible_pct", "invalid_json_pct")},
                "cost_per_task_usd": round(s["cost_usd"] / s["tasks"], 4) if s["tasks"] else None})
    for name, s in results["baselines"].items():
        entries.append({"model": f"baseline:{name}", "mode": "open_book", "feasible_pct": s["feasible_pct"],
                        "median_gap": s["median_gap"], "impossible_plan_pct": s["impossible_plan_pct"],
                        "hallucination_pct": s["hallucination_pct"], "wrong_address_pct": s["wrong_address_pct"],
                        "not_in_osm_pct": s["not_in_osm_pct"], "unverifiable_pct": s["unverifiable_pct"],
                        "correct_infeasible_pct": s["correct_infeasible_pct"],
                        "false_infeasible_pct": s["false_infeasible_pct"], "invalid_json_pct": s["invalid_json_pct"],
                        "cost_per_task_usd": 0.0})
    return sorted(entries, key=lambda e: (e["mode"], -(e["feasible_pct"] or 0), e["median_gap"] if e["median_gap"] is not None else 9e9))


def write_results(cfg: Config, results: dict, run: str) -> None:
    out = cfg.root / "results" if run == "final" else cfg.root / "results" / run
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    board = leaderboard(results)
    (out / "leaderboard.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    cols = ["model", "mode", "feasible_pct", "median_gap", "impossible_plan_pct", "hallucination_pct",
            "wrong_address_pct", "not_in_osm_pct", "correct_infeasible_pct", "cost_per_task_usd"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join("—" if e[c] is None else str(e[c]) for c in cols) + " |" for e in board]
    (out / "leaderboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
