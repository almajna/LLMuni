"""`make heroes`: hero-task candidates for the video: a well-known frontier model fails visibly (closed
store, missed deadline or meet-up, invented store) on a feasible task whose optimal plan is clearly better."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from llmuni.config import Config  # noqa: E402
from llmuni.data.report import FONTS, INK, INK_2, MUTED, SURFACE, label  # noqa: E402
from llmuni.oracle.run import load_tasks  # noqa: E402
from llmuni.tasks.prompts import clock  # noqa: E402
from llmuni.travel import planning_pois  # noqa: E402

FAMOUS = ["openai/gpt-6-astra", "anthropic/claude-fable-5.1", "google/gemini-3.1-pro-preview", "x-ai/grok-4.7"]
KINDS = {"closed": "arrives at a closed store", "deadline": "misses a deadline", "late": "is late to the meet-up",
         "hallucinated": "sends you to a store that doesn't exist"}
FAIL, GOLD = "#d03b3b", "#eda100"  # status critical; oracle gold (brief section 9)


def run_heroes(cfg: Config, subset: str = "pilot", per_kind: int = 2) -> list[dict]:
    grades = [json.loads(line) for line in (cfg.root / "results" / subset / "grades.jsonl").read_text().splitlines()]
    tasks = {t.task_id: t for t in load_tasks(cfg)}
    oracle = {r["task_id"]: r for r in map(json.loads, (cfg.root / "benchmark" / cfg.benchmark_version / "oracle.jsonl")
                                              .read_text().splitlines())}
    candidates = []
    for g in grades:
        if g["baseline"] or not g["task_feasible"] or g["model"] not in FAMOUS:
            continue
        kind = "hallucinated" if g["status"] == "hallucinated" else (
            (g["failure"] or "").split(":")[0] if g["status"] == "infeasible" else None)
        if kind not in KINDS:
            continue
        best = oracle[g["task_id"]]["global_optimum" if g["mode"] == "closed_book" else "optimum"]
        candidates.append({**g, "kind": kind, "best": best, "rank": (FAMOUS.index(g["model"]),
                           {"hard": 0, "medium": 1, "easy": 2}[g["tier"]])})
    chosen, seen = [], set()
    for kind in KINDS:
        for c in sorted((c for c in candidates if c["kind"] == kind), key=lambda c: c["rank"]):
            if c["task_id"] not in seen and sum(x["kind"] == kind for x in chosen) < per_kind:
                chosen.append(c)
                seen.add(c["task_id"])
    pois = planning_pois(cfg).drop_duplicates("poi_id").set_index("poi_id")
    out = cfg.paths.reports / "checkpoint3"
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Checkpoint 3: hero-task candidates", "",
             "A well-known frontier model fails visibly on a feasible task; the optimal plan (gold) is clearly better.", ""]
    for k, c in enumerate(chosen, 1):
        task = tasks[c["task_id"]]
        png = out / f"hero_{k}_{c['kind']}.png"
        draw(task, c, pois, png)
        lines += section(k, task, c, png.name)
    (out / "heroes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chosen


def section(k: int, task, c: dict, png: str) -> list[str]:
    model = c["model"].split("/")[1]
    lines = [f"## {k}. {model} {KINDS[c['kind']]} ({c['mode'].replace('_', ' ')}, {task.task_id})", "",
             f"> {task.prompt}", "", f"**{model}** ({c['status']}: {c['failure']})", "",
             "| # | Errand | Store | Arrive | Done |", "|---|---|---|---|---|"]
    for i, s in enumerate(c["stops"], 1):
        mark = f" **← {s['failed']}**" if s.get("failed") else (" **← not a real store**" if s["match"] == "hallucinated" else "")
        lines.append(f"| {i} | {label(s['category'])} | {s['store_name']} | {clock(s['arrive']) if s.get('arrive') else '—'}"
                     f" | {clock(s['done']) if s.get('done') else '—'}{mark} |")
    best = c["best"]
    lines += ["", f"**Optimal** (done {clock(best['finish'])}):", "", "| # | Errand | Store | Arrive | Done |", "|---|---|---|---|---|"]
    lines += [f"| {i} | {label(s['category'])} | {s['name']} | {clock(s['arrive'])} | {clock(s['done'])} |"
              for i, s in enumerate(best["stops"], 1)]
    return lines + ["", f"![{task.task_id}]({png})", ""]


def draw(task, c: dict, pois: pd.DataFrame, path: Path) -> None:
    """Straight-line sketch of both routes (the video uses real itineraries)."""
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": FONTS})
    def route(stops, key):
        pts = [(task.start.lon, task.start.lat)]
        pts += [(pois.at[s[key], "lon"], pois.at[s[key], "lat"]) for s in stops if s.get(key) in pois.index]
        return pts + ([(task.end.lon, task.end.lat)] if task.end else [])
    model_pts, best_pts = route(c["stops"], "poi_id"), route(c["best"]["stops"], "poi_id")
    lons, lats = zip(*(model_pts + best_pts))
    aspect = 1 / math.cos(math.radians(sum(lats) / len(lats)))
    fig, ax = plt.subplots(figsize=(7, 6), facecolor=SURFACE)
    ax.set_axis_off()
    for pts, color, width, z in ((best_pts, GOLD, 3.2, 2), (model_pts, FAIL, 2.0, 3)):
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=color, linewidth=width, marker="o", markersize=6, zorder=z,
                markeredgecolor=SURFACE, solid_capstyle="round")
    ax.scatter([task.start.lon], [task.start.lat], marker="s", s=90, color=INK, zorder=4)
    if task.end:
        ax.scatter([task.end.lon], [task.end.lat], marker="D", s=90, color=INK, zorder=4)
    pad = 0.004
    ax.set_xlim(min(lons) - pad, max(lons) + pad)
    ax.set_ylim(min(lats) - pad, max(lats) + pad)
    ax.set_aspect(aspect)
    ax.set_title(f"{task.task_id}: {c['model'].split('/')[1]} {KINDS[c['kind']]}", loc="left", fontsize=11, color=INK)
    ax.legend(handles=[Line2D([], [], color=GOLD, linewidth=3.2, label=f"Optimal, done {clock(c['best']['finish'])}"),
                       Line2D([], [], color=FAIL, linewidth=2.0, label=f"{c['model'].split('/')[1]}: {c['kind']}"),
                       Line2D([], [], color=MUTED, marker="s", linestyle="", label="Start / end (diamond)")],
              loc="lower left", frameon=False, fontsize=8.5, labelcolor=INK_2)
    fig.savefig(path, dpi=130, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
