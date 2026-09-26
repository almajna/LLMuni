"""Grade one answer: check it covers the errands, match its stores, replay it on the timetable.

The replay is the oracle's own `simulate` (same FIFO travel, same waiting-for-opening policy, same
closing times, deadlines and arrive-by), so a model's plan and the optimal plan share one clock.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from llmuni.grader.answer import Answer
from llmuni.grader.match import Match, StoreMatcher
from llmuni.hours import CLOSED_ALL_WEEK
from llmuni.oracle.build import InstanceBuilder
from llmuni.oracle.model import simulate
from llmuni.tasks.schema import Task
from llmuni.travel import hhmm, minutes

REFERENCE = {"closed_book": "global_optimum", "open_book": "optimum", "tool_use": "optimum"}


@dataclass
class Grade:
    # feasible | infeasible | hallucinated (a store that does not exist) | wrong_address (a real store, not
    # where the plan goes) | unverifiable | invalid_plan | invalid_json | declined
    status: str
    valid_json: bool
    claimed_feasible: bool | None = None
    failure: str | None = None
    finish: str | None = None
    end_arrive: str | None = None  # replayed arrival at the end place, also when late
    optimality_gap: float | None = None
    hallucinated_store: bool = False  # names a store found in neither OSM nor the city's business registry
    wrong_address: bool = False  # names a real store at an address where it is not
    not_in_osm_stops: int = 0  # real stores (registered at that address) that OSM lacks; also unverifiable
    unverifiable_stops: int = 0
    correct_infeasible_call: bool | None = None  # infeasible tasks only: did the model say so?
    false_infeasible_call: bool = False  # feasible task declined as impossible
    stops: list[dict] = field(default_factory=list)

    @property
    def feasible_replay(self) -> bool:
        return self.status == "feasible"

    def as_dict(self) -> dict:
        return asdict(self) | {"feasible_replay": self.feasible_replay}


class Grader:
    def __init__(self, builder: InstanceBuilder, matcher: StoreMatcher, oracle: dict[str, dict]) -> None:
        self.builder, self.matcher, self.oracle = builder, matcher, oracle

    def grade(self, task: Task, answer: Answer | None, mode: str) -> Grade:
        impossible = task.design.infeasible
        if answer is None:
            return Grade("invalid_json", valid_json=False)
        if not answer.feasible:
            return Grade("declined", True, False, correct_infeasible_call=True if impossible else None,
                         false_infeasible_call=not impossible)
        verdict = self._coverage(task, answer)
        if verdict:
            return Grade("invalid_plan", True, True, failure=verdict, correct_infeasible_call=False if impossible else None)

        errand_of = {spec.category: e for e, spec in enumerate(task.errands)}
        matches: list[Match] = []
        near = (task.start.lat, task.start.lon)
        for stop in answer.stops:
            match = self.matcher.match(stop.category, stop.store_name, stop.address, stop.poi_id, near)
            matches.append(match)
            if match.lat is not None:
                near = (match.lat, match.lon)

        # The replay runs up to the first stop it cannot check. A stop that cannot be visited as planned (a store
        # that does not exist, a wrong address, a store closed all week) makes the plan impossible wherever it
        # is, so it outranks an earlier stop that is merely unverifiable.
        chosen, sequence, blocked, definite = {}, [], None, None
        for stop, match in zip(answer.stops, matches):
            e = errand_of[stop.category]
            fatal = None
            if match.status == "hallucinated" and match.reason == "wrong_address":
                fatal = ("wrong_address", f"no {stop.category} called {stop.store_name!r} at that address")
            elif match.status == "hallucinated":
                fatal = ("hallucinated", f"no {stop.category} called {stop.store_name!r} in San Francisco")
            elif match.status == "matched" and match.hours_status == CLOSED_ALL_WEEK:
                fatal = ("infeasible", f"closed: {stop.store_name} is closed all week")
            definite = definite or fatal
            if blocked:
                continue
            if fatal:
                blocked = fatal
            elif match.status == "unverifiable":
                blocked = ("unverifiable", f"{stop.store_name}: {match.reason}")
            elif not self.builder.routable(match.poi_id):
                blocked = ("unverifiable", f"{stop.store_name}: not routable")
            else:
                chosen[e] = match.poi_id
                sequence.append(e)

        inst = self.builder.plan_instance(task, chosen)
        outcome = simulate(inst, [(e, int(inst.options[e][0])) for e in sequence])
        grade = Grade("feasible", True, True,
                      hallucinated_store=any(m.status == "hallucinated" and m.reason != "wrong_address" for m in matches),
                      wrong_address=any(m.reason == "wrong_address" for m in matches),
                      not_in_osm_stops=sum(m.reason == "not_in_osm" for m in matches),
                      unverifiable_stops=sum(m.status == "unverifiable" for m in matches),
                      correct_infeasible_call=False if impossible else None)
        grade.stops = self._stop_log(answer, matches, outcome)
        grade.end_arrive = hhmm(outcome.end_arrive) if outcome.end_arrive is not None else None
        if outcome.failure_kind not in (None, "incomplete"):
            grade.status, grade.failure = "infeasible", outcome.failure  # broke before any blocked stop
        elif definite:
            grade.status, grade.failure = definite
        elif blocked:
            grade.status, grade.failure = blocked
        elif not outcome.feasible:
            grade.status, grade.failure = "infeasible", outcome.failure
        else:
            grade.finish = hhmm(outcome.finish)
            grade.optimality_gap = self._gap(task, outcome.finish, mode)
        return grade

    @staticmethod
    def _coverage(task: Task, answer: Answer) -> str | None:
        wanted = {spec.category for spec in task.errands}
        counts = Counter(stop.category for stop in answer.stops)
        unknown = sorted(set(counts) - wanted)
        if unknown:
            return f"stops for errands not asked for: {', '.join(unknown)}"
        missing = sorted(wanted - set(counts))
        if missing:
            return f"missing errands: {', '.join(missing)}"
        repeated = sorted(c for c, n in counts.items() if n > 1)
        return f"errands repeated: {', '.join(repeated)}" if repeated else None

    def _gap(self, task: Task, finish: int, mode: str) -> float | None:
        best = self.oracle.get(task.task_id, {}).get(REFERENCE[mode])
        if not best:
            return None
        depart, optimum = minutes(task.start.depart_time), minutes(best["finish"])
        return (finish - optimum) / max(optimum - depart, 1)

    @staticmethod
    def _stop_log(answer: Answer, matches: list[Match], outcome) -> list[dict]:
        """Per stop: what the model named, what it matched, and replayed times where known."""
        failed = None
        if outcome.failed_at is not None:  # a deadline miss still records the stop; closed/unreachable don't
            failed = len(outcome.stops) - 1 if outcome.failure_kind == "deadline" else len(outcome.stops)
        log = []
        for k, (stop, match) in enumerate(zip(answer.stops, matches)):
            entry = {"category": stop.category, "store_name": stop.store_name, "match": match.status,
                     "method": match.method, "poi_id": match.poi_id, "reason": match.reason}
            if k < len(outcome.stops):
                s = outcome.stops[k]
                entry |= {"arrive": hhmm(s.arrive), "start": hhmm(s.start), "done": hhmm(s.done)}
            elif k == failed and outcome.failed_at[2] >= 0:
                entry["arrive"] = hhmm(outcome.failed_at[2])
            if k == failed:
                entry["failed"] = outcome.failure_kind
            log.append(entry)
        return log
