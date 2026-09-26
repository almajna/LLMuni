"""`make eval` / `make pilot`: baselines, cost estimate, model calls (cached, within budget), grading,
and aggregation into results/results.json and results/leaderboard.json."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from llmuni.config import Config
from llmuni.eval import prompts
from llmuni.eval.aggregate import aggregate, write_results
from llmuni.eval.baselines import BASELINES, greedy, random_plan
from llmuni.eval.client import BudgetExceeded, Ledger, OpenRouter, estimate_tokens, fetch_pricing
from llmuni.eval.tools import TravelTool
from llmuni.grader.answer import parse_answer
from llmuni.grader.geocode import build_geocoder
from llmuni.grader.match import StoreMatcher
from llmuni.grader.replay import Grader
from llmuni.oracle.run import load_tasks, oracle_context
from llmuni.tasks.schema import Task

log = logging.getLogger(__name__)


def run_eval(cfg: Config, *, pilot: bool, dry_run: bool = False, baselines_only: bool = False,
             models: list[str] | None = None, modes: list[str] | None = None) -> dict | None:
    run = "pilot" if pilot else "full"
    tasks = load_tasks(cfg)
    if pilot:
        ids = set(json.loads((benchmark_dir(cfg) / "pilot_ids.json").read_text()))
        tasks = [t for t in tasks if t.task_id in ids]
    modes = modes or (cfg.eval.pilot_modes if pilot else cfg.eval.modes)
    models = [] if baselines_only else (models or cfg.eval.models)

    todo = [(m, mode, t) for m in models for mode in modes for t in tasks if not transcript_path(cfg, m, mode, t).exists()]
    if models:
        pricing = fetch_pricing(models)
        estimate = estimate_cost(cfg, todo, pricing)
        write_estimate(cfg, run, estimate, len(tasks), models, modes)
        log.info("estimated cost of %d uncached calls: $%.2f (budget $%.2f)", len(todo), estimate["total"], cfg.eval.budget())
        if dry_run:
            return estimate
        if estimate["total"] > cfg.eval.budget():
            raise BudgetExceeded(f"estimated ${estimate['total']:.2f} exceeds the ${cfg.eval.budget():.2f} budget; "
                                 "reduce models, modes or tasks, or raise BUDGET_USD")
        call_models(cfg, run, todo, pricing)

    builder, pois = oracle_context(cfg)
    geocoder = build_geocoder(cfg.paths.raw / "sf.osm.pbf", cfg.paths.cache / f"geocoder_{osm_sha(cfg)[:16]}.pkl")
    oracle = {r["task_id"]: r for r in map(json.loads, (benchmark_dir(cfg) / "oracle.jsonl").read_text().splitlines())}
    grader = Grader(builder, StoreMatcher(pois, geocoder), oracle)

    rows = []
    for task in tasks:
        inst = builder.instance(task, "candidates")
        for name in BASELINES:
            answer = greedy(task, inst) if name == "greedy" else random_plan(task, f"{cfg.seed}:{task.task_id}")
            rows.append(row(task, name, "open_book", grader.grade(task, answer, "open_book"), baseline=True))
        for model in models:
            for mode in modes:
                path = transcript_path(cfg, model, mode, task)
                if not path.exists():
                    continue  # stopped by the budget
                transcript = json.loads(path.read_text(encoding="utf-8"))
                answer, error, pure = parse_answer(transcript["final_text"])
                grade = grader.grade(task, answer, mode)
                rows.append(row(task, model, mode, grade, transcript=transcript, pure_json=pure, parse_error=error))
    out = cfg.root / "results"
    out.mkdir(exist_ok=True)
    (out / f"grades_{run}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    results = aggregate(cfg, rows, tasks)
    write_results(cfg, results, run)
    return results


def call_models(cfg: Config, run: str, todo: list[tuple[str, str, Task]], pricing: dict) -> None:
    ledger = Ledger(cfg.paths.cache / "llm" / f"ledger_{run}.jsonl", cfg.eval.budget())
    client = OpenRouter(cfg, ledger, pricing)
    builder, _ = oracle_context(cfg)
    with ThreadPoolExecutor(cfg.eval.concurrency) as pool:
        futures = {pool.submit(converse, cfg, client, builder, model, mode, task): (model, mode, task.task_id)
                   for model, mode, task in todo}
        for future in as_completed(futures):
            model, mode, task_id = futures[future]
            try:
                future.result()
            except BudgetExceeded as exc:
                log.warning("budget reached, skipping %s/%s/%s: %s", model, mode, task_id, exc)
            except Exception as exc:  # one failing call must not sink the run; it is retried next time
                log.error("%s/%s/%s failed: %s", model, mode, task_id, exc)
    log.info("spent $%.2f of $%.2f", ledger.spent, ledger.budget)


def converse(cfg: Config, client: OpenRouter, builder, model: str, mode: str, task: Task) -> dict:
    """One task for one model in one mode: tool calls (tool_use), one repair retry, cached transcript."""
    messages = prompts.messages(task, mode, cfg.eval.max_tool_calls)
    tools = [prompts.TOOL_SPEC] if mode == "tool_use" else None
    tool = TravelTool(task, builder.matrices.for_day(date.fromisoformat(task.date)), cfg.eval.max_tool_calls) if tools else None
    usage, cost, latency, finish_reasons, repaired, text = Counter(), 0.0, 0.0, [], False, ""
    for _ in range(cfg.eval.max_tool_calls + 3):
        reply = client.chat(model, messages, tools)
        cost += reply["cost_usd"]
        latency += reply["latency_s"]
        finish_reasons.append(reply["finish_reason"])
        usage.update({k: v for k, v in reply["usage"].items() if isinstance(v, int)})
        details = reply["usage"].get("completion_tokens_details") or {}
        usage["reasoning_tokens"] += details.get("reasoning_tokens") or 0
        message = reply["message"]
        messages.append({k: message[k] for k in ("role", "content", "tool_calls", "reasoning_details") if message.get(k)})
        if tools and message.get("tool_calls"):
            for call in message["tool_calls"]:
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(tool(args))})
            continue
        text = message.get("content") or ""
        answer, error, _ = parse_answer(text)
        if answer is None and not repaired:
            messages.append(prompts.repair_message(error))
            repaired = True
            continue
        break
    transcript = {
        "model": model, "mode": mode, "task_id": task.task_id, "final_text": text, "repaired": repaired,
        "tool_calls": tool.calls if tool else 0, "cost_usd": cost, "latency_s": round(latency, 2),
        "prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"], "finish_reasons": finish_reasons, "messages": messages,
    }
    path = transcript_path(cfg, model, mode, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(transcript, ensure_ascii=False, indent=1), encoding="utf-8")
    return transcript


def estimate_cost(cfg: Config, todo: list[tuple[str, str, Task]], pricing: dict) -> dict:
    """Expected and worst-case cost of the uncached calls, per model."""
    per_model: dict[str, dict] = {}
    for model, mode, task in todo:
        price_in, price_out = pricing[model]
        prompt = estimate_tokens(prompts.messages(task, mode, cfg.eval.max_tool_calls),
                                 [prompts.TOOL_SPEC] if mode == "tool_use" else None)
        turns = cfg.eval.est_tool_turns if mode == "tool_use" else 1
        expected = (turns * prompt + 60 * turns * turns) * price_in + (cfg.eval.est_output_tokens + 300 * (turns - 1)) * price_out
        worst = turns * (1.25 * prompt * price_in + cfg.eval.max_output_tokens * price_out)
        entry = per_model.setdefault(model, {"calls": 0, "expected": 0.0, "worst": 0.0})
        entry["calls"] += 1
        entry["expected"] += expected
        entry["worst"] += worst
    return {"per_model": per_model, "total": sum(e["expected"] for e in per_model.values()),
            "worst": sum(e["worst"] for e in per_model.values())}


def write_estimate(cfg: Config, run: str, estimate: dict, n_tasks: int, models: list[str], modes: list[str]) -> None:
    lines = [f"# Cost estimate: {run} run", "",
             f"{n_tasks} tasks x {len(models)} models x modes {', '.join(modes)}; uncached calls only. "
             f"Expected assumes {cfg.eval.est_output_tokens} output tokens per answer (reasoning included); "
             f"worst case assumes every call hits max_tokens={cfg.eval.max_output_tokens}.", "",
             "| Model | Calls | Expected | Worst case |", "|---|---:|---:|---:|"]
    for model, e in sorted(estimate["per_model"].items(), key=lambda kv: -kv[1]["expected"]):
        lines.append(f"| {model} | {e['calls']} | ${e['expected']:.2f} | ${e['worst']:.2f} |")
    lines += [f"| **Total** | {sum(e['calls'] for e in estimate['per_model'].values())} | "
              f"**${estimate['total']:.2f}** | ${estimate['worst']:.2f} |", "",
              f"Budget: ${cfg.eval.budget():.2f} (hard cap; calls stop before it would be exceeded)."]
    out = cfg.root / "results"
    out.mkdir(exist_ok=True)
    (out / f"cost_estimate_{run}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def row(task: Task, model: str, mode: str, grade, *, baseline: bool = False, transcript: dict | None = None,
        pure_json: bool | None = None, parse_error: str | None = None) -> dict:
    t = transcript or {}
    return {"task_id": task.task_id, "tier": task.tier, "task_feasible": not task.design.infeasible,
            "model": model, "mode": mode, "baseline": baseline, **grade.as_dict(),
            "pure_json": pure_json, "parse_error": parse_error, "repaired": t.get("repaired", False),
            "cost_usd": t.get("cost_usd", 0.0), "prompt_tokens": t.get("prompt_tokens", 0),
            "completion_tokens": t.get("completion_tokens", 0), "reasoning_tokens": t.get("reasoning_tokens", 0),
            "latency_s": t.get("latency_s"), "tool_calls": t.get("tool_calls", 0),
            "truncated": "length" in (t.get("finish_reasons") or [])}


def transcript_path(cfg: Config, model: str, mode: str, task: Task) -> Path:
    return cfg.paths.cache / "llm" / re.sub(r"[^\w.-]+", "_", model) / mode / f"{task.task_id}.json"


def benchmark_dir(cfg: Config) -> Path:
    return cfg.root / "benchmark" / cfg.benchmark_version


def osm_sha(cfg: Config) -> str:
    return json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))["sources"]["osm"]["sha256"]
