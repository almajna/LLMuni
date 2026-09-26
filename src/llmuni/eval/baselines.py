"""Non-LLM baselines over the listed stores: greedy (always finish the next errand as early as possible)
and random (random order, random listed store). Both are graded exactly like models in open-book mode."""

from __future__ import annotations

import random

from llmuni.grader.answer import Answer, AnswerStop
from llmuni.oracle.model import INF, Instance
from llmuni.tasks.schema import Task

BASELINES = ("greedy", "random")


def greedy(task: Task, inst: Instance) -> Answer:
    """From where you are, go to the (errand, store) you can finish earliest; repeat. Ignores deadlines
    and the end, which is exactly what makes it a baseline."""
    t, here, remaining, stops = inst.depart, inst.start, set(range(len(task.errands))), []
    while remaining:
        best = None
        for e in sorted(remaining):
            for q in inst.options[e]:
                arrive = inst.matrix.arrival(here, int(q), t)
                if arrive is None:
                    continue
                start = inst.service_start_at(e, int(q), arrive)
                if start < INF and (best is None or start + inst.errands[e].service_min < best[0]):
                    best = (start + inst.errands[e].service_min, e, int(q))
        if best is None:
            return Answer(feasible=False, reason="no listed store can serve the remaining errands")
        t, e, here = best
        stops.append(_stop(task, e, inst.matrix.ids[here]))
        remaining.remove(e)
    return Answer(feasible=True, stops=stops)


def random_plan(task: Task, seed: str) -> Answer:
    rng = random.Random(seed)
    order = rng.sample(range(len(task.errands)), len(task.errands))
    return Answer(feasible=True, stops=[
        _stop(task, e, rng.choice(task.candidates[task.errands[e].category]).poi_id) for e in order
    ])


def _stop(task: Task, e: int, poi_id: str) -> AnswerStop:
    category = task.errands[e].category
    store = next(c for c in task.candidates[category] if c.poi_id == poi_id)
    return AnswerStop(category=category, store_name=store.name, address=store.address, poi_id=poi_id)
