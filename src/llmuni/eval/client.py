"""OpenRouter chat client with retries and a hard budget.

Before every call the ledger reserves that call's worst case (estimated prompt tokens x 1.25 at the input
price, plus at the output price the larger of max_tokens and 1.5x the model's largest observed completion:
some providers let reasoning run past max_tokens). The call is refused unless spent + reserved + worst
case stays within the budget; afterwards the reservation is replaced by the cost OpenRouter reports.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from llmuni.config import Config

log = logging.getLogger(__name__)

API = "https://openrouter.ai/api/v1"
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


class BudgetExceeded(RuntimeError):
    pass


def fetch_models(models: list[str]) -> dict[str, dict]:
    """Per model: USD per prompt/completion token and whether it accepts `reasoning`, from OpenRouter's
    public model list (free)."""
    data = httpx.get(f"{API}/models", timeout=60).raise_for_status().json()["data"]
    info = {m["id"]: {"price_in": float(m["pricing"]["prompt"]), "price_out": float(m["pricing"]["completion"]),
                      "reasoning": "reasoning" in (m.get("supported_parameters") or [])} for m in data}
    missing = [m for m in models if m not in info]
    if missing:
        raise ValueError(f"not available on OpenRouter: {', '.join(missing)}")
    return {m: info[m] for m in models}


def estimate_tokens(messages: list[dict], tools: list[dict] | None = None) -> int:
    """Generous prompt-token estimate (~3.5 characters per token)."""
    chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) + len(json.dumps(tools or []))
    return int(chars / 3.5) + 50


class Ledger:
    """Actual spend (OpenRouter's reported cost) plus worst-case reservations for calls in flight."""

    def __init__(self, path: Path, budget: float) -> None:
        self.path, self.budget, self._lock = path, budget, threading.Lock()
        records = [json.loads(line) for line in (path.read_text(encoding="utf-8").splitlines() if path.exists() else []) if line]
        self.spent = sum(r["cost_usd"] for r in records)
        self.reserved = 0.0
        self.max_completion: dict[str, int] = {}  # largest completion seen per model (some exceed max_tokens)
        for r in records:
            self._observe(r)

    def _observe(self, record: dict) -> None:
        model, tokens = record.get("model"), record.get("completion_tokens") or 0
        if model:
            self.max_completion[model] = max(self.max_completion.get(model, 0), tokens)

    def reserve(self, amount: float) -> None:
        with self._lock:
            if self.spent + self.reserved + amount > self.budget:
                raise BudgetExceeded(
                    f"the next call could cost up to ${amount:.2f}: ${self.spent:.2f} spent and "
                    f"${self.reserved:.2f} reserved of the ${self.budget:.2f} budget")
            self.reserved += amount

    def release(self, amount: float) -> None:
        with self._lock:
            self.reserved -= amount

    def settle(self, amount: float, record: dict) -> None:
        with self._lock:
            self.reserved -= amount
            self.spent += record["cost_usd"]
            self._observe(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")


def _transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, json.JSONDecodeError)):  # incl. keep-alive-only bodies on timeouts
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in TRANSIENT_STATUS


class OpenRouter:
    def __init__(self, cfg: Config, ledger: Ledger, models: dict[str, dict]) -> None:
        load_dotenv(cfg.root / ".env")
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (expected in .env)")
        self.cfg, self.ledger, self.models = cfg, ledger, models
        self.http = httpx.Client(base_url=API, timeout=cfg.eval.request_timeout_s,
                                 headers={"Authorization": f"Bearer {key}", "X-Title": "LLMuni benchmark"})

    def worst_case(self, model: str, messages: list[dict], tools: list[dict] | None = None) -> float:
        """Worst-case cost of one call. Some providers let reasoning run past max_tokens, so the output
        bound is the larger of max_tokens and 1.5x the largest completion this model has returned."""
        info = self.models[model]
        output_cap = max(self.cfg.eval.max_output_tokens, int(1.5 * self.ledger.max_completion.get(model, 0)))
        return 1.25 * estimate_tokens(messages, tools) * info["price_in"] + output_cap * info["price_out"]

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None) -> dict:
        worst = self.worst_case(model, messages, tools)
        self.ledger.reserve(worst)
        body = {"model": model, "messages": messages, "max_tokens": self.cfg.eval.max_output_tokens,
                "usage": {"include": True}}
        if self.cfg.eval.reasoning_effort and self.models[model]["reasoning"]:
            body["reasoning"] = {"effort": self.cfg.eval.reasoning_effort}
        if tools:
            body["tools"] = tools
        started = perf_counter()
        try:
            data = self._post(body)
        except BaseException:
            self.ledger.release(worst)
            raise
        latency = perf_counter() - started
        usage = data.get("usage") or {}
        cost = usage.get("cost")
        if cost is None:  # fall back to list prices if the cost field is missing
            info = self.models[model]
            cost = usage.get("prompt_tokens", 0) * info["price_in"] + usage.get("completion_tokens", 0) * info["price_out"]
        self.ledger.settle(worst, {"model": model, "cost_usd": cost, "prompt_tokens": usage.get("prompt_tokens"),
                                   "completion_tokens": usage.get("completion_tokens"), "latency_s": round(latency, 2)})
        choice = data["choices"][0]
        return {"message": choice["message"], "finish_reason": choice.get("finish_reason"), "usage": usage,
                "cost_usd": cost, "latency_s": latency}

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=4, max=60),
           retry=retry_if_exception(_transient), reraise=True)
    def _post(self, body: dict) -> dict:
        response = self.http.post("/chat/completions", json=body)
        response.raise_for_status()
        data = response.json()
        if "error" in data and not data.get("choices"):
            raise RuntimeError(f"OpenRouter error: {data['error']}")
        return data
