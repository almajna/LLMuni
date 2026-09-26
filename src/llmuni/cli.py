"""Command-line entry point: `python -m llmuni <stage>` (wrapped by the Makefile)."""

from __future__ import annotations

import argparse
import json
import logging

from llmuni.config import load_config


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="llmuni", description="LLMuni benchmark pipeline")
    parser.add_argument("--config", help="path to config.yaml (default: nearest one at or above the cwd)")
    stages = parser.add_subparsers(dest="stage", required=True)

    data = stages.add_parser("data", help="fetch GTFS + OSM, write MANIFEST.json, build POIs and the Phase 1 report")
    data.add_argument("--refresh", action="store_true", help="re-download sources even if cached")
    stages.add_parser("router-check", help="route known SF trips with R5 and measure matrix throughput")
    stages.add_parser("matrices", help="precompute planning travel matrices for every service day (R5, slow)")
    stages.add_parser("tasks", help="generate the task set with oracle-verified (in)feasibility")
    stages.add_parser("oracle", help="optimal plans for every task + brute-force and MILP cross-checks")
    stages.add_parser("examples", help="one worked example per tier with an itinerary map (R5)")
    stages.add_parser("grader-check", help="round-trip optimal plans through the grader (name + address only)")
    stages.add_parser("heroes", help="hero-task candidates for the video from the pilot grades")
    sd = stages.add_parser("site-data", help="export site and video data from the latest results")
    sd.add_argument("--hero", help="task id for the replay's default and the video's hero (default: site.hero_task)")
    sd.add_argument("--routes", action="store_true", help="route every replayed hop with R5 first (cached; needs Java)")
    stages.add_parser("readme", help="rewrite the README's headline and leaderboard blocks from the latest results")
    stages.add_parser("video-basemap", help="the video's map plate (streets + rail) -> video/public/basemap.png")
    ev = stages.add_parser("eval", help="baselines + model runs (cached, total spend capped at BUDGET_USD) + grading")
    ev.add_argument("--subset", choices=["calibration", "pilot", "final"], default="pilot")
    ev.add_argument("--dry-run", action="store_true", help="write the cost estimate; call no model")
    ev.add_argument("--baselines-only", action="store_true", help="grade the free baselines only")
    ev.add_argument("--models", nargs="*", help="override eval.models")
    ev.add_argument("--grade-only", action="store_true", help="grade cached answers only; call no model")
    ev.add_argument("--tool-models", type=int, help="final run: tool_use for the pilot's top N models "
                                                   "(default eval.tool_mode_models)")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    cfg = load_config(args.config)

    if args.stage == "data":
        from llmuni.data.pipeline import run_data_stage

        run_data_stage(cfg, refresh=args.refresh)
    elif args.stage == "router-check":
        from llmuni.router_check import run_router_check

        run_router_check(cfg)
    elif args.stage == "matrices":
        from llmuni.tasks.landmarks import load_landmarks
        from llmuni.travel import Matrices, planning_pois, routable_places

        Matrices(cfg, routable_places(load_landmarks(cfg), planning_pois(cfg))).precompute()
    elif args.stage == "tasks":
        from llmuni.tasks.generate import run_tasks_stage

        run_tasks_stage(cfg)
    elif args.stage == "oracle":
        from llmuni.oracle.run import run_oracle_stage

        run_oracle_stage(cfg)
    elif args.stage == "examples":
        from llmuni.oracle.examples import run_examples_stage

        run_examples_stage(cfg)
    elif args.stage == "grader-check":
        from llmuni.grader.check import run_grader_check

        print(json.dumps(run_grader_check(cfg), indent=2))
    elif args.stage == "heroes":
        from llmuni.eval.heroes import run_heroes

        for c in run_heroes(cfg):
            print(c["task_id"], c["model"], c["mode"], c["kind"], c["failure"])
    elif args.stage == "site-data":
        from llmuni.site.export import export_site_data

        print(json.dumps(export_site_data(cfg, args.hero, routes=args.routes)))
    elif args.stage == "readme":
        from llmuni.site.readme import run_readme

        run_readme(cfg)
    elif args.stage == "video-basemap":
        from llmuni.site.basemap import run_basemap

        print(json.dumps(run_basemap(cfg)))
    elif args.stage == "eval":
        from llmuni.eval.run import run_eval

        run_eval(cfg, subset=args.subset, dry_run=args.dry_run, baselines_only=args.baselines_only,
                 models=args.models, tool_models=args.tool_models, grade_only=args.grade_only)
