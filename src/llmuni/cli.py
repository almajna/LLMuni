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
    ev = stages.add_parser("eval", help="baselines + model runs (cached, within BUDGET_USD) + grading")
    ev.add_argument("--pilot", action="store_true", help="the pilot subset and pilot modes")
    ev.add_argument("--dry-run", action="store_true", help="print the cost estimate; call no model")
    ev.add_argument("--baselines-only", action="store_true", help="grade the free baselines only")
    ev.add_argument("--models", nargs="*", help="override eval.models")
    ev.add_argument("--modes", nargs="*", help="override the modes")

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
    elif args.stage == "eval":
        from llmuni.eval.run import run_eval

        run_eval(cfg, pilot=args.pilot, dry_run=args.dry_run, baselines_only=args.baselines_only,
                 models=args.models, modes=args.modes)
