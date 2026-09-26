"""`make calibrate` / `make pilot` / `make finish`: baselines, a cost estimate, model calls (cached per
settings, one ledger capping TOTAL spend at BUDGET_USD), grading, and aggregation.

Subsets are nested (calibration in pilot in final) and answers are cached per (settings, model, mode, task),
so rerunning a subset, or moving to a larger one, never pays twice for an answer.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from statistics import mean

from llmuni.config import Config
from llmuni.eval import prompts
from llmuni.eval.aggregate import aggregate, write_results
from llmuni.eval.baselines import BASELINES, greedy, random_plan
from llmuni.eval.client import BudgetExceeded, Ledger, OpenRouter, estimate_tokens, fetch_models
from llmuni.eval.tools import TravelTool
from llmuni.grader.answer import parse_answer
from llmuni.grader.geocode import build_geocoder
from llmuni.grader.match import StoreMatcher
from llmuni.grader.registry import load_registry
from llmuni.grader.replay import Grader
from llmuni.oracle.run import load_tasks, oracle_context
from llmuni.tasks.generate import final_rounds
from llmuni.tasks.schema import Task

log = logging.getLogger(__name__)
SUBSETS = ("calibration", "pilot", "final")


def run_eval(cfg: Config, *, subset: str, dry_run: bool = False, baselines_only: bool = False,
             models: list[str] | None = None, tool_models: int | None = None, grade_only: bool = False) -> dict | None:
    tasks = subset_tasks(cfg, subset)
    models = [] if baselines_only else (models or cfg.eval.models)
    plan = run_plan(cfg, subset, models, tool_models)  # {mode: [models]}
    todo = [(model, mode, task) for task in tasks for mode, ms in plan.items() for model in ms
            if not transcript_path(cfg, model, mode, task).exists()]
    if models and not grade_only:
        info = fetch_models(models)
        calls = call_estimates(cfg, todo, info)
        ledger = Ledger(ledger_path(cfg), cfg.eval.budget())
        rounds = task_rounds(cfg) if subset == "final" else None
        estimate = estimate_cost(calls)
        if rounds:
            estimate["fit"] = rounds_that_fit(calls, rounds, ledger.budget - ledger.spent, cfg.eval.round_margin)
        write_estimate(cfg, subset, estimate, len(tasks), plan)
        log.info("%s: %d uncached calls, expected $%.2f; spent so far $%.2f of the $%.2f budget%s",
                 subset, len(todo), estimate["total"], ledger.spent, ledger.budget,
                 f"; {describe_fit(estimate['fit'])}" if rounds else "")
        if dry_run:
            return estimate
        gate = RoundGate(ledger, {c["key"]: c["expected"] for c in calls}, rounds, cfg.eval.round_margin) if rounds else None
        call_models(cfg, todo, info, ledger, gate)
    return grade_subset(cfg, subset, tasks, plan)


def subset_tasks(cfg: Config, subset: str) -> list[Task]:
    """The subset's tasks; the final subset in run order (pilot first, then one task per tier per round)."""
    ids = set(json.loads((benchmark_dir(cfg) / f"{subset}_ids.json").read_text()))
    tasks = [t for t in load_tasks(cfg) if t.task_id in ids]
    if subset == "final":
        rounds = task_rounds(cfg)
        tasks.sort(key=lambda t: rounds[t.task_id])
    return tasks


def task_rounds(cfg: Config) -> dict[str, int]:
    """Round of each final-subset task (1-based; rounds 1-5 are the pilot), see tasks.generate.final_rounds."""
    return {task_id: k for k, ids in enumerate(final_rounds(cfg, load_tasks(cfg)), 1) for task_id in ids}


def run_plan(cfg: Config, subset: str, models: list[str], tool_models: int | None = None) -> dict[str, list[str]]:
    """Which models run in which mode: calibration is open book; the pilot uses pilot_modes; the final run
    uses the configured modes for every model, plus tool use for the pilot's top `tool_models` models
    (default eval.tool_mode_models: 0, i.e. tool mode is the optional v2 step)."""
    if subset == "calibration":
        return {"open_book": models}
    if subset == "pilot":
        return {mode: models for mode in cfg.eval.pilot_modes}
    plan = {mode: models for mode in cfg.eval.modes}
    n = cfg.eval.tool_mode_models if tool_models is None else tool_models
    top = top_models(cfg, n)
    if top:
        plan["tool_use"] = [m for m in top if m in models]
    return plan


def top_models(cfg: Config, n: int) -> list[str]:
    """The pilot's best models in open book: feasible % first, then median gap."""
    path = cfg.root / "results" / "pilot" / "results.json"
    if not path.exists() or n <= 0:
        return []
    per_model = json.loads(path.read_text())["per_model"]
    scored = [(m, s["open_book"]) for m, s in per_model.items() if "open_book" in s]
    scored.sort(key=lambda kv: (-(kv[1]["feasible_pct"] or 0), kv[1]["median_gap"] if kv[1]["median_gap"] is not None else 9))
    return [m for m, _ in scored[:n]]


class RoundGate:
    """Admits the final run's rounds (one task per tier) in order, each only if the budget left, minus what
    the admitted rounds are still expected to spend, covers `margin` x the round's expected cost. The first
    refusal ends the run, so every tier keeps the same number of tasks and no task is left half-answered
    by the budget. The ledger still caps every single call at its worst case."""

    def __init__(self, ledger: Ledger, expected: dict[tuple[str, str, str], float], rounds: dict[str, int],
                 margin: float) -> None:
        self.ledger, self.rounds, self.margin = ledger, rounds, margin
        self.pending = dict(expected)  # (model, mode, task_id) -> expected USD, until the call finishes
        self.cost: dict[int, float] = defaultdict(float)
        for (_, _, task_id), usd in expected.items():
            self.cost[rounds[task_id]] += usd
        self.admitted: set[int] = set()
        self.refused_from: int | None = None
        self._lock = threading.Lock()

    def admit(self, key: tuple[str, str, str]) -> bool:
        with self._lock:
            r = self.rounds[key[2]]
            if r in self.admitted:
                return True
            if self.refused_from is not None and r >= self.refused_from:
                return False
            outstanding = sum(usd for k, usd in self.pending.items() if self.rounds[k[2]] in self.admitted)
            left = self.ledger.budget - self.ledger.spent - outstanding
            if left >= self.margin * self.cost[r]:
                self.admitted.add(r)
                log.info("round %d admitted: expected $%.2f, $%.2f left after admitted rounds", r, self.cost[r], left)
                return True
            self.refused_from = r
            log.warning("round %d not started: it is expected to cost $%.2f (x%.2f margin) but only $%.2f is left "
                        "after admitted rounds; the run ends after the admitted rounds", r, self.cost[r], self.margin, left)
            return False

    def done(self, key: tuple[str, str, str]) -> None:
        with self._lock:
            self.pending.pop(key, None)


class RoundRefused(BudgetExceeded):
    pass


def call_models(cfg: Config, todo: list[tuple[str, str, Task]], info: dict, ledger: Ledger,
                gate: RoundGate | None = None) -> None:
    client = OpenRouter(cfg, ledger, info)
    builder, _ = oracle_context(cfg)

    def run(model: str, mode: str, task: Task) -> dict:
        key = (model, mode, task.task_id)
        if gate and not gate.admit(key):
            raise RoundRefused(f"round {gate.rounds[task.task_id]} not admitted")
        try:
            return converse(cfg, client, builder, model, mode, task)
        finally:
            if gate:
                gate.done(key)

    stopped = False
    with ThreadPoolExecutor(cfg.eval.concurrency) as pool:  # submitted task by task (FIFO): a budget stop
        futures = {pool.submit(run, model, mode, task): (model, mode, task.task_id)  # leaves whole tasks
                   for model, mode, task in todo}                                   # answered by every model
        for future in as_completed(futures):
            model, mode, task_id = futures[future]
            try:
                future.result()
            except RoundRefused:
                pass  # logged once by the gate
            except BudgetExceeded as exc:
                if not stopped:
                    log.warning("budget reached; unanswered calls are left for a later run: %s", exc)
                stopped = True
            except Exception as exc:  # one failing call must not sink the run; it is retried next time
                log.error("%s/%s/%s failed: %s", model, mode, task_id, exc)
    log.info("total spent $%.2f of the $%.2f budget", ledger.spent, ledger.budget)


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
        "model": model, "mode": mode, "task_id": task.task_id, "settings": settings_tag(cfg), "final_text": text,
        "repaired": repaired, "tool_calls": tool.calls if tool else 0, "cost_usd": cost, "latency_s": round(latency, 2),
        "prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"], "turns": len(finish_reasons), "finish_reasons": finish_reasons,
        "messages": [{k: v for k, v in m.items() if k != "reasoning_details"} for m in messages],  # opaque, large
    }
    path = transcript_path(cfg, model, mode, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(transcript, ensure_ascii=False, indent=1), encoding="utf-8")
    return transcript


def grade_subset(cfg: Config, subset: str, tasks: list[Task], plan: dict[str, list[str]]) -> dict:
    builder, pois = oracle_context(cfg)
    geocoder = build_geocoder(cfg.paths.raw / "sf.osm.pbf", cfg.paths.cache / f"geocoder_{osm_sha(cfg)[:16]}.pkl")
    oracle = {r["task_id"]: r for r in map(json.loads, (benchmark_dir(cfg) / "oracle.jsonl").read_text().splitlines())}
    grader = Grader(builder, StoreMatcher(pois, geocoder, registry=load_registry(cfg)), oracle)
    rows = []
    for task in tasks:
        inst = builder.instance(task, "candidates")
        for name in BASELINES:
            answer = greedy(task, inst) if name == "greedy" else random_plan(task, f"{cfg.seed}:{task.task_id}")
            rows.append(row(task, name, "open_book", grader.grade(task, answer, "open_book"), baseline=True))
        for mode, models in plan.items():
            for model in models:
                path = transcript_path(cfg, model, mode, task)
                if path.exists():
                    transcript = json.loads(path.read_text(encoding="utf-8"))
                    answer, error, pure = parse_answer(transcript["final_text"])
                    rows.append(row(task, model, mode, grader.grade(task, answer, mode), transcript=transcript,
                                    pure_json=pure, parse_error=error))
    rows = common_tasks(rows, plan)
    out = cfg.root / "results" / ("" if subset == "final" else subset)
    out.mkdir(parents=True, exist_ok=True)
    (out / "grades.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    results = aggregate(cfg, rows, [t for t in tasks if any(r["task_id"] == t.task_id for r in rows)])
    results["spend_usd_total"] = round(Ledger(ledger_path(cfg), cfg.eval.budget()).spent, 4)
    write_results(cfg, results, subset)
    return results


def common_tasks(rows: list[dict], plan: dict[str, list[str]]) -> list[dict]:
    """Per mode, keep only tasks every model of that mode answered, so models are compared like for like
    even if the budget stopped a run part-way. Baselines follow the open-book task set."""
    answered = defaultdict(set)
    for r in rows:
        if not r["baseline"]:
            answered[(r["mode"], r["model"])].add(r["task_id"])
    keep = {mode: set.intersection(*(answered[(mode, m)] for m in models)) if models else set()
            for mode, models in plan.items()}
    open_tasks = keep.get("open_book")
    return [r for r in rows if (r["baseline"] and (open_tasks is None or r["task_id"] in open_tasks))
            or (not r["baseline"] and r["task_id"] in keep.get(r["mode"], set()))]


def call_estimates(cfg: Config, todo: list[tuple[str, str, Task]], info: dict) -> list[dict]:
    """Expected and worst-case cost of each uncached call. Expected costs are measured means from cached
    transcripts with the same settings (per model, mode and tier where available), else token estimates."""
    measured = measured_usage(cfg)
    largest = Ledger(ledger_path(cfg), cfg.eval.budget()).max_completion
    calls = []
    for model, mode, task in todo:
        price_in, price_out = info[model]["price_in"], info[model]["price_out"]
        output_cap = max(cfg.eval.max_output_tokens, int(1.5 * largest.get(model, 0)))  # as the ledger reserves
        prompt = estimate_tokens(prompts.messages(task, mode, cfg.eval.max_tool_calls),
                                 [prompts.TOOL_SPEC] if mode == "tool_use" else None)
        seen = measured.get((model, mode, task.tier)) or measured.get((model, mode))
        out = measured.get((model, "open_book"), {}).get("completion_tokens", cfg.eval.est_output_tokens)
        out = seen["completion_tokens"] if seen else out
        if mode == "tool_use" and seen:
            expected, turns = seen["cost_usd"], seen["turns"]
        elif mode == "tool_use":  # turns grow the prompt; tool-calling turns are shorter than a full answer
            turns = cfg.eval.est_tool_turns
            expected = (turns * prompt + 75 * turns * turns) * price_in + (out + 0.5 * out * (turns - 1)) * price_out
        else:
            turns = 2  # worst case: the answer plus one repair retry (expected uses measured means)
            expected = seen["cost_usd"] if seen else prompt * price_in + out * price_out
        n_calls = cfg.eval.max_tool_calls + 3 if mode == "tool_use" else turns
        calls.append({"key": (model, mode, task.task_id), "model": model, "expected": expected,
                      "worst": n_calls * (1.25 * prompt * price_in + output_cap * price_out),
                      "calibrated": (model, "open_book") in measured})
    return calls


def estimate_cost(calls: list[dict]) -> dict:
    """Expected and worst-case cost of the uncached calls, per model."""
    per_model: dict[str, dict] = {}
    for c in calls:
        entry = per_model.setdefault(c["model"], {"calls": 0, "expected": 0.0, "worst": 0.0, "calibrated": c["calibrated"]})
        entry["calls"] += 1
        entry["expected"] += c["expected"]
        entry["worst"] += c["worst"]
    return {"per_model": per_model, "total": sum(e["expected"] for e in per_model.values()),
            "worst": sum(e["worst"] for e in per_model.values())}


def rounds_that_fit(calls: list[dict], rounds: dict[str, int], left: float, margin: float) -> dict:
    """How many rounds with uncached calls RoundGate would admit if every call cost its expected amount."""
    cost: dict[int, float] = defaultdict(float)
    for c in calls:
        cost[rounds[c["key"][2]]] += c["expected"]
    admitted, spend = [], 0.0
    for r in sorted(cost):
        if left - spend < margin * cost[r]:
            break
        admitted.append(r)
        spend += cost[r]
    tasks = {c["key"][2] for c in calls if rounds[c["key"][2]] in admitted}
    return {"rounds": admitted, "tasks": len(tasks), "expected": spend, "left": left, "margin": margin}


def describe_fit(fit: dict) -> str:
    if not fit["rounds"]:
        return f"no further round fits in the ${fit['left']:.2f} left"
    return (f"rounds {fit['rounds'][0]}-{fit['rounds'][-1]} fit ({fit['tasks']} new tasks, one per tier per round): "
            f"expected ${fit['expected']:.2f} of the ${fit['left']:.2f} left")


def measured_usage(cfg: Config) -> dict[tuple, dict]:
    """Mean cost, completion tokens and turns per (model, mode) and per (model, mode, tier) over cached
    transcripts with the current settings."""
    groups = defaultdict(list)
    root = answers_dir(cfg) / settings_tag(cfg)
    tiers = {t.task_id: t.tier for t in load_tasks(cfg)}
    for path in root.glob("*/*/*.json"):
        t = json.loads(path.read_text(encoding="utf-8"))
        groups[(t["model"], t["mode"])].append(t)
        groups[(t["model"], t["mode"], tiers.get(t["task_id"]))].append(t)
    return {key: {"cost_usd": mean(t["cost_usd"] for t in ts), "completion_tokens": mean(t["completion_tokens"] for t in ts),
                  "turns": mean(t.get("turns", 1) for t in ts), "n": len(ts)} for key, ts in groups.items()}


def write_estimate(cfg: Config, subset: str, estimate: dict, n_tasks: int, plan: dict[str, list[str]]) -> None:
    modes = "; ".join(f"{mode}: {len(ms)} models" for mode, ms in plan.items())
    lines = [f"# Cost estimate: {subset}", "",
             f"{n_tasks} tasks ({modes}); uncached calls only; reasoning effort {cfg.eval.reasoning_effort}, "
             f"max_tokens {cfg.eval.max_output_tokens}. *Calibrated* rows use measured costs of cached answers "
             f"(per model, mode and tier); the worst case assumes every call hits its output cap.", "",
             "| Model | Calls | Calibrated | Expected | Worst case |", "|---|---:|:---:|---:|---:|"]
    for model, e in sorted(estimate["per_model"].items(), key=lambda kv: -kv[1]["expected"]):
        lines.append(f"| {model} | {e['calls']} | {'yes' if e['calibrated'] else 'no'} | ${e['expected']:.2f} | ${e['worst']:.2f} |")
    lines += [f"| **Total** | {sum(e['calls'] for e in estimate['per_model'].values())} | | "
              f"**${estimate['total']:.2f}** | ${estimate['worst']:.2f} |", "",
              f"Budget: ${cfg.eval.budget():.2f} total across all runs (hard cap)."]
    if "fit" in estimate:
        lines += ["", f"Under this budget: {describe_fit(estimate['fit'])}. A round (one task per tier) starts only "
                      f"if the budget left covers {estimate['fit']['margin']}x its expected cost."]
    out = cfg.root / "results"
    out.mkdir(exist_ok=True)
    (out / f"cost_estimate_{subset}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def row(task: Task, model: str, mode: str, grade, *, baseline: bool = False, transcript: dict | None = None,
        pure_json: bool | None = None, parse_error: str | None = None) -> dict:
    t = transcript or {}
    return {"task_id": task.task_id, "tier": task.tier, "task_feasible": not task.design.infeasible,
            "model": model, "mode": mode, "baseline": baseline, **grade.as_dict(),
            "pure_json": pure_json, "parse_error": parse_error, "repaired": t.get("repaired", False),
            "cost_usd": t.get("cost_usd", 0.0), "prompt_tokens": t.get("prompt_tokens", 0),
            "completion_tokens": t.get("completion_tokens", 0), "reasoning_tokens": t.get("reasoning_tokens", 0),
            "latency_s": t.get("latency_s"), "tool_calls": t.get("tool_calls", 0), "turns": t.get("turns", 0),
            "truncated": "length" in (t.get("finish_reasons") or [])}


def settings_tag(cfg: Config) -> str:
    return f"reasoning-{cfg.eval.reasoning_effort or 'default'}_max{cfg.eval.max_output_tokens}"


def answers_dir(cfg: Config) -> Path:
    """Paid-for model answers and the spend ledger: committed, so no clone ever pays for them twice."""
    return cfg.root / "results" / "answers"


def transcript_path(cfg: Config, model: str, mode: str, task: Task) -> Path:
    return answers_dir(cfg) / settings_tag(cfg) / re.sub(r"[^\w.-]+", "_", model) / mode / f"{task.task_id}.json"


def ledger_path(cfg: Config) -> Path:
    return answers_dir(cfg) / "ledger.jsonl"


def benchmark_dir(cfg: Config) -> Path:
    return cfg.root / "benchmark" / cfg.benchmark_version


def osm_sha(cfg: Config) -> str:
    return json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))["sources"]["osm"]["sha256"]
