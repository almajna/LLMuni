"""Brute-force enumeration: every errand order x every place choice (small instances only)."""

from __future__ import annotations

import itertools

from llmuni.oracle.model import Instance, Outcome, simulate


def brute_force(inst: Instance) -> Outcome | None:
    best = None
    for order in itertools.permutations(range(len(inst.errands))):
        for places in itertools.product(*(inst.options[e] for e in order)):
            outcome = simulate(inst, [(e, int(p)) for e, p in zip(order, places)])
            if outcome.feasible and (best is None or outcome.finish < best.finish):
                best = outcome
    return best
