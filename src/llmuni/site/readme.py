"""`llmuni readme`: rewrite the README's generated blocks (headline and leaderboard) from the latest results.

Only the text between `<!-- <name>:start -->` and `<!-- <name>:end -->` markers is replaced, so the rest of the
README stays hand-written.
"""

from __future__ import annotations

import json
import re

from llmuni.config import Config
from llmuni.site.export import latest_run

NAMES = {
    "openai/gpt-6-astra": "GPT-6 Astra",
    "anthropic/claude-fable-5.1": "Claude Fable 5.1",
    "google/gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "x-ai/grok-4.7": "Grok 4.7",
    "deepseek/deepseek-v4-pro-0813": "DeepSeek V4 Pro",
    "qwen/qwen3.8-max-prime": "Qwen 3.8 Max Prime",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick",
    "baseline:greedy": "Greedy baseline",
    "baseline:random": "Random baseline",
}


def name(model: str) -> str:
    return NAMES.get(model, model)


def pct(v) -> str:
    return "—" if v is None else f"{v:.0f}%"


def gap(v) -> str:
    return "—" if v is None else f"+{100 * v:.1f}%"


def leaderboard_md(results: dict, board: list[dict]) -> str:
    n = results["n_tasks_by_tier"]
    lines = []
    for mode, title in (("open_book", "Open book (candidate stores listed)"), ("closed_book", "Closed book (the model names real stores)")):
        rows = [e for e in board if e["mode"] == mode]
        if not rows:
            continue
        lines += [f"**{title}**", "",
                  "| # | Model | Feasible | Vs optimal (median) | Impossible plans | No such store | Wrong address | Spots impossible | $ / task |",
                  "|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
        rank = 0
        for e in rows:
            baseline = e["model"].startswith("baseline:")
            rank += 0 if baseline else 1
            cost = "—" if baseline or e["cost_per_task_usd"] is None else f"${e['cost_per_task_usd']:.3f}"
            lines.append(f"| {'' if baseline else rank} | {name(e['model'])} | {pct(e['feasible_pct'])} | {gap(e['median_gap'])} | "
                         f"{pct(e['impossible_plan_pct'])} | {pct(e.get('hallucination_pct'))} | {pct(e.get('wrong_address_pct'))} | "
                         f"{pct(e['correct_infeasible_pct'])} | {cost} |")
        lines.append("")
    lines.append(f"{sum(n.values())} tasks ({', '.join(f'{v} {k}' for k, v in n.items())}); each model answered each task once. "
                 "Feasible: the plan replays on the timetable with every store open and every time met. Vs optimal: extra time "
                 "over the provably optimal plan among feasible plans. Definitions: [docs/methods.md](docs/methods.md).")
    return "\n".join(lines)


def headline_md(results: dict, meta: dict) -> str:
    per_model = results["per_model"]
    h = results["headline"]
    closed = {m: s["closed_book"] for m, s in per_model.items() if "closed_book" in s}
    open_ = {m: s["open_book"] for m, s in per_model.items() if "open_book" in s}
    best_open = max(open_.items(), key=lambda kv: ((kv[1]["feasible_pct"] or 0), -(kv[1]["median_gap"] or 9)))
    worked = sum(1 for s in closed.values() if (s["feasible_pct"] or 0) > 0)
    bullets = [
        f"- **Open book:** {name(best_open[0])} leads: {pct(best_open[1]['feasible_pct'])} of its plans work on the timetable, "
        f"a median {gap(best_open[1]['median_gap'])} slower than the provably optimal plan.",
        f"- **Closed book:** {worked} of {len(closed)} models produced any plan that works when they had to name real stores themselves; "
        f"the best model's impossible-plan rate was {pct(h['pct_impossible_best_model_closed_book'])}.",
        f"- **{results['benchmark_version']}**, {meta['run']} run: {sum(results['n_tasks_by_tier'].values())} tasks x "
        f"{len(per_model)} models x 2 modes, ${results.get('spend_usd_total', 0):.2f} of model calls in total.",
    ]
    return "\n".join(bullets)


def run_readme(cfg: Config) -> None:
    found = latest_run(cfg)
    if found is None:
        raise FileNotFoundError("no results to write into the README")
    run, folder = found
    results = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    board = json.loads((folder / "leaderboard.json").read_text(encoding="utf-8"))
    readme = cfg.root / "README.md"
    text = readme.read_text(encoding="utf-8")
    for block, body in (("headline", headline_md(results, {"run": run})), ("leaderboard", leaderboard_md(results, board))):
        pattern = re.compile(rf"(<!-- {block}:start -->)(.*?)(<!-- {block}:end -->)", re.S)
        if not pattern.search(text):
            raise ValueError(f"README.md has no <!-- {block}:start --> / <!-- {block}:end --> markers")
        text = pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)
    readme.write_text(text, encoding="utf-8")
