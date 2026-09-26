import threading
from datetime import date

import numpy as np
import pytest

from llmuni.eval import prompts
from llmuni.eval.aggregate import headline, summarize
from llmuni.eval.baselines import greedy
from llmuni.eval.client import BudgetExceeded, Ledger
from llmuni.eval.run import RoundGate, rounds_that_fit
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
    with pytest.raises(BudgetExceeded):
        ledger.reserve(1.10)  # cannot fit even with nothing in flight
    ledger.reserve(0.60)
    ledger.settle(0.60, {"cost_usd": 0.10})  # the call actually cost 0.10
    ledger.reserve(0.85)  # 0.10 spent + 0.85 fits
    ledger.release(0.85)
    with pytest.raises(BudgetExceeded):
        ledger.reserve(0.95)  # 0.10 spent + 0.95 > 1.00
    assert Ledger(tmp_path / "ledger.jsonl", budget=1.00).spent == pytest.approx(0.10)  # spend persists


def test_ledger_waits_for_calls_in_flight_instead_of_refusing(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl", budget=1.00)
    ledger.reserve(0.60)
    waiter = threading.Thread(target=ledger.reserve, args=(0.50,))  # 0.60 reserved + 0.50 > 1.00: wait
    waiter.start()
    waiter.join(0.2)
    assert waiter.is_alive() and ledger.in_flight == 1
    ledger.settle(0.60, {"cost_usd": 0.20})  # 0.20 spent + 0.50 fits
    waiter.join(2)
    assert not waiter.is_alive() and ledger.reserved == pytest.approx(0.50)


def test_a_waiting_call_is_refused_if_what_was_spent_leaves_no_room(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl", budget=1.00)
    ledger.reserve(0.60)
    errors = []
    waiter = threading.Thread(target=lambda: _capture(errors, ledger.reserve, 0.50))
    waiter.start()
    ledger.settle(0.60, {"cost_usd": 0.55})  # 0.55 spent + 0.50 > 1.00
    waiter.join(2)
    assert errors and isinstance(errors[0], BudgetExceeded)


def _capture(errors: list, fn, *args) -> None:
    try:
        fn(*args)
    except Exception as exc:  # noqa: BLE001 - the test inspects it
        errors.append(exc)


def test_round_gate_admits_whole_rounds_while_their_expected_cost_fits(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl", budget=10.0)
    ledger.reserve(4.0)
    ledger.settle(4.0, {"cost_usd": 4.0})  # $6 left
    rounds = {"e6": 6, "m6": 6, "e7": 7, "m7": 7, "e8": 8, "m8": 8}
    expected = {("a", "open_book", t): 1.0 for t in rounds}  # $2 per round
    gate = RoundGate(ledger, expected, rounds, margin=1.25)
    assert gate.admit(("a", "open_book", "e6"))  # 6 >= 1.25 x 2
    assert gate.admit(("a", "open_book", "m6"))  # same round
    assert gate.admit(("a", "open_book", "e7"))  # 6 - 2 outstanding = 4 >= 2.5
    assert not gate.admit(("a", "open_book", "e8"))  # 6 - 4 outstanding = 2 < 2.5
    for key in expected:
        gate.done(key)
    assert not gate.admit(("a", "open_book", "m8"))  # a refusal is final: tiers stay balanced


def test_rounds_that_fit_matches_the_gate():
    rounds = {"e6": 6, "m6": 6, "e7": 7, "m7": 7, "e8": 8, "m8": 8}
    calls = [{"key": ("a", "open_book", t), "expected": 1.0} for t in rounds]
    fit = rounds_that_fit(calls, rounds, left=6.0, margin=1.25)
    assert fit["rounds"] == [6, 7] and fit["tasks"] == 4 and fit["expected"] == pytest.approx(4.0)


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


def test_closed_book_headline_breaks_ties_on_impossible_plans_not_list_order():
    from llmuni.eval.aggregate import headline

    def s(feasible, impossible, invented):
        return {"closed_book": {"feasible_pct": feasible, "impossible_plan_pct": impossible, "hallucination_pct": invented,
                                "median_gap": None}}
    h = headline({"a": s(0.0, 48.1, 11.1), "b": s(0.0, 22.2, 37.5), "c": s(0.0, 22.2, 3.7)})
    assert h["best_model_closed_book"] == "c" and h["pct_impossible_best_model_closed_book"] == 22.2
