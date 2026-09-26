"""`make examples`: one worked example per tier (prompt, optimal plan, map with R5 itineraries)."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from llmuni.config import Config  # noqa: E402
from llmuni.data import osm  # noqa: E402
from llmuni.data.boundary import load_boundary  # noqa: E402
from llmuni.data.report import FONTS, INK, INK_2, MUTED, ROAD, ROAD_MAJOR, SERIES, SURFACE, _roads_in, label  # noqa: E402
from llmuni.oracle.run import load_tasks  # noqa: E402
from llmuni.router import Place, Router  # noqa: E402
from llmuni.router_check import describe  # noqa: E402
from llmuni.tasks.prompts import clock  # noqa: E402
from llmuni.tasks.schema import Task  # noqa: E402
from llmuni.travel import minutes, planning_pois  # noqa: E402


def run_examples_stage(cfg: Config) -> list[str]:
    version_dir = cfg.root / "benchmark" / cfg.benchmark_version
    tasks = {t.task_id: t for t in load_tasks(cfg)}
    oracle = {r["task_id"]: r for r in map(json.loads, (version_dir / "oracle.jsonl").read_text().splitlines())}
    pilot = json.loads((version_dir / "pilot_ids.json").read_text())
    chosen = [next(tid for tid in pilot if tasks[tid].tier == tier and oracle[tid]["feasible"]) for tier in cfg.tasks.tiers]

    pois = planning_pois(cfg).drop_duplicates("poi_id").set_index("poi_id")
    router = Router(cfg)
    sf, _ = load_boundary(cfg.data.boundary_query, cfg.paths.processed / "sf_boundary.geojson")
    sf_geom = sf.geometry.union_all()
    shapely.prepare(sf_geom)
    roads = _roads_in(osm.extract_roads(cfg.paths.raw / "sf.osm.pbf"), sf_geom)

    out = cfg.paths.reports / "phase4"
    out.mkdir(parents=True, exist_ok=True)
    sections = ["# Checkpoint 2: example tasks", ""]
    for task_id in chosen:
        task, plan = tasks[task_id], oracle[task_id]["optimum"]
        hops = plan_hops(router, task, plan, pois)
        png = out / f"example_{task.tier}.png"
        draw_plan(task, plan, hops, pois, roads, png)
        sections += example_markdown(task, oracle[task_id], hops, png.name)
    (out / "examples.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    return chosen


def plan_hops(router: Router, task: Task, plan: dict, pois: pd.DataFrame) -> list[dict]:
    """R5 itinerary for each hop of the plan: start -> stops -> end, leaving when the last stop is done."""
    day = date.fromisoformat(task.date)
    points = [(task.start.label, task.start.lat, task.start.lon, task.start.depart_time)]
    for stop in plan["stops"]:
        store = pois.loc[stop["poi_id"]]
        points.append((stop["name"], store["lat"], store["lon"], stop["done"]))
    if task.end:
        points.append((task.end.label, task.end.lat, task.end.lon, None))
    hops = []
    for (name_a, lat_a, lon_a, leave), (name_b, lat_b, lon_b, _) in zip(points, points[1:]):
        depart = datetime.combine(day, datetime.min.time()) + timedelta(minutes=minutes(leave))
        legs = router.itinerary(Place("a", lat_a, lon_a), Place("b", lat_b, lon_b), depart)
        hops.append({"from": name_a, "to": name_b, "legs": legs})
    return hops


def draw_plan(task: Task, plan: dict, hops: list[dict], pois: pd.DataFrame, roads, path: Path) -> None:
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": FONTS})
    stops = [pois.loc[s["poi_id"]] for s in plan["stops"]]
    candidates = [pois.loc[c.poi_id] for cands in task.candidates.values() for c in cands]
    points = [(task.start.lon, task.start.lat)] + [(s["lon"], s["lat"]) for s in stops + candidates]
    if task.end:
        points.append((task.end.lon, task.end.lat))
    for hop in hops:
        points += [xy for leg in hop["legs"] for xy in leg["coords"]]
    lons, lats = zip(*points)
    pad = 0.006
    lon0, lon1, lat0, lat1 = min(lons) - pad, max(lons) + pad, min(lats) - pad, max(lats) + pad
    aspect = 1 / math.cos(math.radians((lat0 + lat1) / 2))
    width = 9.0
    height = min(12.0, max(5.0, width * (lat1 - lat0) * aspect / (lon1 - lon0)))
    fig, ax = plt.subplots(figsize=(width, height + 1.0), facecolor=SURFACE)
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=1 - 1.0 / (height + 1.0))
    ax.set_axis_off()
    minor, major = roads
    ax.add_collection(LineCollection(minor, colors=ROAD, linewidths=0.4, zorder=1))
    ax.add_collection(LineCollection(major, colors=ROAD_MAJOR, linewidths=0.8, zorder=1))
    ax.scatter([c["lon"] for c in candidates], [c["lat"] for c in candidates], s=16, color=MUTED, linewidths=0, zorder=2)
    for hop in hops:
        for leg in hop["legs"]:
            if not leg["coords"]:
                continue
            xs, ys = zip(*leg["coords"])
            walking = leg["mode"] == "WALK"
            ax.plot(xs, ys, color=INK_2 if walking else SERIES, linewidth=1.4 if walking else 2.6,
                    linestyle=(0, (2, 2)) if walking else "-", solid_capstyle="round", zorder=3)
    for k, store in enumerate(stops, 1):
        ax.scatter(store["lon"], store["lat"], s=260, color=SERIES, edgecolors=SURFACE, linewidths=2, zorder=4)
        ax.text(store["lon"], store["lat"], str(k), color="white", fontsize=10, fontweight="bold",
                ha="center", va="center", zorder=5)
    ax.scatter(task.start.lon, task.start.lat, s=150, marker="s", color=INK, edgecolors=SURFACE, linewidths=2, zorder=3.5)
    if task.end:
        ax.scatter(task.end.lon, task.end.lat, s=190, marker="D", color=INK, edgecolors=SURFACE, linewidths=2, zorder=3.5)
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect(aspect)

    fig.text(0.02, 1 - 0.28 / (height + 1), f"{task.task_id}: optimal plan", fontsize=14, fontweight="semibold",
             color=INK, va="top")
    subtitle = f"{task.weekday} {task.date}, leave {task.start.label} {clock(task.start.depart_time)}, done {clock(plan['finish'])}"
    fig.text(0.02, 1 - 0.62 / (height + 1), subtitle, fontsize=9.5, color=INK_2, va="top")
    handles = [
        Line2D([], [], color=SERIES, linewidth=2.6, label="Muni / BART"),
        Line2D([], [], color=INK_2, linewidth=1.4, linestyle=(0, (2, 2)), label="Walk"),
        Line2D([], [], marker="o", linestyle="", markersize=6, markerfacecolor=MUTED, markeredgecolor=MUTED,
               label="Other listed stores"),
        Line2D([], [], marker="s", linestyle="", markersize=7, markerfacecolor=INK, markeredgecolor=INK, label="Start"),
    ] + ([Line2D([], [], marker="D", linestyle="", markersize=7, markerfacecolor=INK, markeredgecolor=INK,
                 label="End")] if task.end else [])
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8.5, labelcolor=INK_2)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def example_markdown(task: Task, record: dict, hops: list[dict], png: str) -> list[str]:
    plan, best = record["optimum"], record["global_optimum"]
    lines = [f"## {task.tier.title()}: {task.task_id}", "", f"> {task.prompt}", "",
             "| # | Errand | Store | Arrive | Start | Done | Getting there |", "|---|---|---|---|---|---|---|"]
    for k, (stop, hop) in enumerate(zip(plan["stops"], hops), 1):
        wait = f" (waits {stop['wait_min']} min)" if stop["wait_min"] else ""
        lines.append(f"| {k} | {label(stop['category'])} | {stop['name']} | {clock(stop['arrive'])}{wait} "
                     f"| {clock(stop['start'])} | {clock(stop['done'])} | {describe(hop['legs'])} |")
    if task.end:
        lines.append(f"| → | End | {task.end.label} | {clock(plan['end_arrive'])} | | | {describe(hops[-1]['legs'])} |")
    lines += [
        "",
        f"Optimal finish **{clock(plan['finish'])}** ({plan['duration_min']} min) over the listed stores; "
        f"over every store in SF: {clock(best['finish'])} ({best['duration_min']} min).",
        "",
        f"![{task.task_id}]({png})",
        "",
    ]
    return lines
