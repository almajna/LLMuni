from datetime import date

import numpy as np
import pytest

from llmuni.eval import prompts
from llmuni.eval.aggregate import headline, summarize
from llmuni.eval.baselines import greedy
from llmuni.eval.client import BudgetExceeded, Ledger
from llmuni.eval.tools import TravelTool
from llmuni.oracle.model import Errand, Instance, service_table
from llmuni.router import TravelMatrix, fifo_arrivals
from llmuni.tasks.schema import Candidate, Design, End, ErrandSpec, Start, Task


def _task() -> Task:
    return Task(
        task_id="t1", benchmark_version="test", tier="easy", weekday="Wednesday", date="2026-10-07",
        start=Start(place_id="L01", label="16th & Mission", neighborhood="Mission", lat=37.765, lon=-122.42, depart_time="09:00"),
        errands=[ErrandSpec(category="pharmacy", service_min=10), ErrandSpec(category="bank_atm", service_min=5)],
        end=End(place_id="L02", label="Ferry Building", neighborhood="Downtown", lat=37.795, lon=-122.39, arrive_by="11:00"),
        candidates={
            "pharmacy": [Candidate(poi_id="p1", name="Walgreens", address="100 Market Street", lat=37.79, lon=-122.40,
                                   opening_hours="Mo-Su 08:00-22:00")],
            "bank_atm": [Candidate(poi_id="p2", name="Chase", address=None, lat=37.77, lon=-122.41,
                                   opening_hours="Mo-Fr 09:00-17:00")],
        },
        prompt="Plan my errands.", design=Design(),
    )


def _matrix() -> TravelMatrix:
    ids = ["L01", "L02", "p1", "p2"]
    minutes = np.array([[[0, 20, 10, 5], [20, 0, 10, 15], [10, 10, 0, 12], [5, 15, 12, 0]]] * 1, dtype=np.uint16)
    minutes = np.repeat(minutes.reshape(4, 4, 1), 60, axis=2)
    walk = np.full((4, 4), 60, dtype=np.uint16)
    np.fill_diagonal(walk, 0)
    return TravelMatrix(ids, date(2026, 10, 7), 540, 5, fifo_arrivals(minutes, 540, 5), walk)


def test_ledger_refuses_a_call_whose_worst_case_would_cross_the_budget(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl", budget=1.00)
    ledger.reserve(0.60)
    with pytest.raises(BudgetExceeded):
        ledger.reserve(0.50)  # 0.60 reserved + 0.50 > 1.00
    ledger.settle(0.60, {"cost_usd": 0.10})  # the call actually cost 0.10
    ledger.reserve(0.85)  # 0.10 spent + 0.85 fits
    assert Ledger(tmp_path / "ledger.jsonl", budget=1.00).spent == pytest.approx(0.10)  # spend persists


def test_ledger_remembers_each_models_largest_completion(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl", budget=10.0)
    ledger.reserve(1.0)
    ledger.settle(1.0, {"model": "x-ai/grok", "cost_usd": 0.2, "completion_tokens": 39000})
    assert Ledger(tmp_path / "ledger.jsonl", budget=10.0).max_completion["x-ai/grok"] == 39000


def test_travel_tool_answers_with_the_router_clock_and_enforces_the_call_limit():
    tool = TravelTool(_task(), _matrix(), max_calls=2)
    assert tool({"from_id": "start", "to_id": "p1", "depart_time": "09:02"}) == {
        "from_id": "start", "to_id": "p1", "depart_time": "09:02", "arrive_time": "09:15", "travel_minutes": 13}
    assert "error" in tool({"from_id": "start", "to_id": "nowhere", "depart_time": "09:00"})
    assert "limit" in tool({"from_id": "start", "to_id": "p1", "depart_time": "09:00"})["error"]


def test_greedy_takes_the_errand_it_can_finish_first():
    task, tm = _task(), _matrix()
    tables = [service_table([(480, 1320)], 10, 1380)[None], service_table([(540, 1020)], 5, 1380)[None]]
    inst = Instance(tm, 0, 540, [Errand("pharmacy", 10), Errand("bank_atm", 5)], [np.array([2]), np.array([3])],
                    tables, end=1, arrive_by=660, horizon=1380)
    answer = greedy(task, inst)
    assert [s.category for s in answer.stops] == ["bank_atm", "pharmacy"]  # bank is 5 min away, pharmacy 10


def test_prompts_list_stores_only_in_open_book_and_tools_only_in_tool_mode():
    task = _task()
    closed = prompts.messages(task, "closed_book", 40)
    open_ = prompts.messages(task, "open_book", 40)[1]["content"]
    tools = prompts.messages(task, "tool_use", 40)[1]["content"]
    assert "Walgreens" not in closed[1]["content"] and '"bank_atm" (bank or ATM)' in closed[0]["content"]
    assert "id p1: Walgreens, 100 Market Street" in open_ and "get_travel_time" not in open_
    assert "up to 40 times" in tools and "'start' for 16th & Mission" in tools


def test_summary_and_headline():
    rows = [
        {"task_feasible": True, "tier": "easy", "status": "feasible", "optimality_gap": 0.1, "claimed_feasible": True,
         "hallucinated_store": False, "correct_infeasible_call": None, "false_infeasible_call": False,
         "cost_usd": 0.2, "prompt_tokens": 100, "completion_tokens": 50},
        {"task_feasible": True, "tier": "easy", "status": "hallucinated", "optimality_gap": None, "claimed_feasible": True,
         "hallucinated_store": True, "correct_infeasible_call": None, "false_infeasible_call": False,
         "cost_usd": 0.2, "prompt_tokens": 100, "completion_tokens": 50},
        {"task_feasible": False, "tier": "hard", "status": "declined", "optimality_gap": None, "claimed_feasible": False,
         "hallucinated_store": False, "correct_infeasible_call": True, "false_infeasible_call": False,
         "cost_usd": 0.1, "prompt_tokens": 100, "completion_tokens": 50},
    ]
    s = summarize(rows)
    assert s["feasible_pct"] == 50.0 and s["impossible_plan_pct"] == 50.0 and s["hallucination_pct"] == 50.0
    assert s["correct_infeasible_pct"] == 100.0 and s["median_gap"] == 0.1 and s["cost_usd"] == 0.5
    h = headline({"m": {"closed_book": s, "open_book": s | {"median_gap": 0.2}, "tool_use": s | {"median_gap": 0.05}}})
    assert h["pct_impossible_best_model_closed_book"] == 50.0 and h["tool_mode_improvement_pct"] == 75.0
