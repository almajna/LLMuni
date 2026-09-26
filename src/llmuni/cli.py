"""Command-line entry point: `python -m llmuni <stage>` (wrapped by the Makefile)."""

from __future__ import annotations

import argparse
import logging

from llmuni.config import load_config


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="llmuni", description="LLMuni benchmark pipeline")
    parser.add_argument("--config", help="path to config.yaml (default: nearest one at or above the cwd)")
    stages = parser.add_subparsers(dest="stage", required=True)

    data = stages.add_parser("data", help="fetch GTFS + OSM, write MANIFEST.json, build POIs and the Phase 1 report")
    data.add_argument("--refresh", action="store_true", help="re-download sources even if cached")
    stages.add_parser("router-check", help="route known SF trips with R5 and measure matrix throughput")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    cfg = load_config(args.config)

    if args.stage == "data":
        from llmuni.data.pipeline import run_data_stage

        run_data_stage(cfg, refresh=args.refresh)
    elif args.stage == "router-check":
        from llmuni.router_check import run_router_check

        run_router_check(cfg)
