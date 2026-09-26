"""`make tasks`: seeded errand-day tasks with candidate stores, tier constraints and oracle-verified
(in)feasibility. Writes benchmark/<version>/tasks.jsonl, pilot_ids.json and reports/phase3/."""

from __future__ import annotations

import itertools
import json
import logging
import random
from collections import Counter
from datetime import date, timedelta

import numpy as np
import pandas as pd

from llmuni.config import Config, TierConfig
from llmuni.oracle.build import UNIVERSES, InstanceBuilder
from llmuni.oracle.dp import earliest_completion, solve
from llmuni.oracle.model import INF, Outcome
from llmuni.tasks.landmarks import load_landmarks
from llmuni.tasks.prompts import clock, noun, render_prompt
from llmuni.tasks.schema import Candidate, Design, End, ErrandSpec, Start, Task
from llmuni.travel import Matrices, hhmm, minutes, planning_pois, routable_places

log = logging.getLogger(__name__)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
INFEASIBLE_MODES = ("end_too_early", "deadline_too_early", "closed")
EARLIEST, LATEST = minutes("08:00"), minutes("17:30")  # sensible departure times
CLOSED_LATEST = minutes("20:30")  # "closed" tasks may leave after work, once a category has closed citywide


def run_tasks_stage(cfg: Config) -> list[Task]:
    landmarks = load_landmarks(cfg)
    pois = planning_pois(cfg)
    builder = InstanceBuilder(cfg, Matrices(cfg, routable_places(landmarks, pois)), pois)
    generator = Generator(cfg, landmarks, builder)
    tasks = [task for tier in cfg.tasks.tiers for task in generator.tier(tier)]
    subsets = pick_subsets(cfg, tasks)
    out = cfg.root / "benchmark" / cfg.benchmark_version
    out.mkdir(parents=True, exist_ok=True)
    (out / "tasks.jsonl").write_text("".join(t.model_dump_json() + "\n" for t in tasks), encoding="utf-8")
    for name, ids in subsets.items():
        (out / f"{name}_ids.json").write_text(json.dumps(ids, indent=2) + "\n", encoding="utf-8")
    write_summary(cfg, tasks, subsets["pilot"])
    return tasks


class Generator:
    def __init__(self, cfg: Config, landmarks: pd.DataFrame, builder: InstanceBuilder) -> None:
        self.cfg, self.tc, self.builder = cfg, cfg.tasks, builder
        self.landmarks = landmarks.reset_index(drop=True)
        self.week = [cfg.data.reference_week_start + timedelta(days=d) for d in range(7)]
        self.categories = [c for c in cfg.categories if c in builder.by_category]  # kept, in config order

    def tier(self, tier: str) -> list[Task]:
        n = self.tc.n_per_tier
        rng = random.Random(f"{self.cfg.seed}:{self.cfg.benchmark_version}:{tier}")
        slots = sorted(rng.sample(range(n), round(n * self.tc.infeasible_share)))
        modes = dict(zip(slots, itertools.cycle(INFEASIBLE_MODES)))
        tasks = []
        for i in range(n):
            tasks.append(self.task(tier, i, modes.get(i)))
            if (i + 1) % 10 == 0:
                log.info("%s: %d/%d tasks", tier, i + 1, n)
        return tasks

    def task(self, tier: str, i: int, mode: str | None) -> Task:
        rng = random.Random(f"{self.cfg.seed}:{self.cfg.benchmark_version}:{tier}:{i}")
        for _ in range(500):
            task = self._attempt(tier, i, rng, mode)
            if task is not None:
                return task
        raise RuntimeError(f"no valid {tier} task #{i} (mode {mode}) after 500 attempts")

    def _attempt(self, tier: str, i: int, rng: random.Random, mode: str | None) -> Task | None:
        tier_cfg = self.tc.tiers[tier]
        day = rng.choice(self.week)
        start = self.landmarks.iloc[rng.randrange(len(self.landmarks))]
        categories = self._pick_categories(rng, tier_cfg)
        brand = rng.choice(self.tc.brands) if "supermarket" in categories and rng.random() < tier_cfg.brand_share else None
        specs = [
            ErrandSpec(category=c, brand=brand if c == "supermarket" else None, service_min=self.tc.service_min[c])
            for c in categories
        ]
        end = self._pick_end(rng, tier_cfg, start, force=mode == "end_too_early")
        design = Design()
        if mode == "closed":
            setup = self._closed_setup(rng, specs)
            if setup is None:
                return None
            day, depart, closed, last = setup
            reason = (
                f"Every {noun(closed)} in San Francisco is closed all day on {WEEKDAYS[day.weekday()]}."
                if last is None
                else f"No {noun(closed)} in San Francisco is still open when you leave at {clock(hhmm(depart))} "
                f"on {WEEKDAYS[day.weekday()]}."
            )
            design = Design(infeasible=True, infeasible_mode="closed", reason=reason)
        elif tier_cfg.closing_soon_lead_min:
            soon = next(s for s in specs if s.category in self.tc.closing_soon_categories)
            depart = self._closing_soon_depart(rng, tier_cfg, soon, day, start, end)
            if depart is None:
                return None
            design.closing_soon = soon.category
        else:
            depart = self._random_time(rng, *tier_cfg.depart)

        task = self._assemble(tier, i, day, start, end, depart, specs, design, allow_closed=mode == "closed")
        if task is None:
            return None
        if mode == "closed":
            return self._finish(task, rng) if self._infeasible_everywhere(task) else None
        plan = solve(self.builder.instance(task, constraints=False))
        if plan is None:
            return None
        self._tighten(task, plan, tier_cfg, rng)
        if mode is None:
            ok = all(solve(self.builder.instance(task, universe)) is not None for universe in UNIVERSES)
        else:
            ok = self._break(task, mode, rng) and self._infeasible_everywhere(task)
        return self._finish(task, rng) if ok else None

    def _pick_categories(self, rng: random.Random, tier_cfg: TierConfig) -> list[str]:
        n = rng.randint(*tier_cfg.errands)
        rare = [c for c in self.tc.rare_categories if c in self.categories]
        chosen = rng.sample(rare, tier_cfg.min_rare)
        if tier_cfg.closing_soon_lead_min:
            soon = [c for c in self.tc.closing_soon_categories if c in self.categories and c not in chosen]
            chosen.append(rng.choice(soon))
        pool = [c for c in self.categories if c not in chosen]
        weights = [1 if c in rare else 2 for c in pool]  # everyday errands are more common
        while len(chosen) < n:
            k = rng.choices(range(len(pool)), weights)[0]
            chosen.append(pool.pop(k))
            weights.pop(k)
        rng.shuffle(chosen)
        return chosen

    def _pick_end(self, rng: random.Random, tier_cfg: TierConfig, start: pd.Series, force: bool) -> pd.Series | None:
        if not force and rng.random() >= tier_cfg.end_share:
            return None
        others = self.landmarks[self.landmarks["place_id"] != start["place_id"]]
        if tier_cfg.cross_city:
            far = _km(start["lat"], start["lon"], others["lat"].to_numpy(), others["lon"].to_numpy()) >= self.tc.cross_city_km
            others = others[far & (others["neighborhood"] != start["neighborhood"]).to_numpy()]
        return others.iloc[rng.randrange(len(others))]

    @staticmethod
    def _random_time(rng: random.Random, lo: str, hi: str) -> int:
        a, b = minutes(lo), minutes(hi)
        return a + 5 * rng.randint(0, (b - a) // 5)

    def _closing_soon_depart(self, rng, tier_cfg, spec, day, start, end) -> int | None:
        """Leave 60-150 min before the median closing time of the stores nearest the route."""
        stores = self.builder.pool(spec.category, spec.brand)
        near = stores.iloc[np.argsort(_route_km(stores, start, end), kind="stable")[: self.tc.candidates_k]]
        closings = [iv[-1][1] for iv in (self.builder.intervals(p, day) for p in near["poi_id"]) if iv]
        if not closings:
            return None
        close = sorted(closings)[len(closings) // 2]
        depart = (close - rng.randint(*tier_cfg.closing_soon_lead_min)) // 5 * 5
        return depart if EARLIEST <= depart <= LATEST else None

    def _assemble(self, tier, i, day, start, end, depart, specs, design, allow_closed) -> Task | None:
        """The task with the K servable stores nearest the route per errand (nearest stores of any
        hours when none is servable and allow_closed)."""
        candidates = {}
        for spec in specs:
            stores = self.builder.servable(spec.category, spec.brand, day, depart, spec.service_min)
            if stores.empty:
                if not allow_closed:
                    return None
                stores = self.builder.pool(spec.category, spec.brand)
            nearest = stores.iloc[np.argsort(_route_km(stores, start, end), kind="stable")[: self.tc.candidates_k]]
            candidates[spec.category] = [
                Candidate(poi_id=r.poi_id, name=r.name, address=r.address if isinstance(r.address, str) else None,
                          lat=r.lat, lon=r.lon, opening_hours=r.opening_hours)
                for r in nearest.itertuples()
            ]
        return Task(
            task_id=f"{self.cfg.benchmark_version}-{tier}-{i:03d}",
            benchmark_version=self.cfg.benchmark_version,
            tier=tier,
            weekday=WEEKDAYS[day.weekday()],
            date=day.isoformat(),
            start=Start(place_id=start["place_id"], label=start["label"], neighborhood=start["neighborhood"],
                        lat=start["lat"], lon=start["lon"], depart_time=hhmm(depart)),
            errands=specs,
            end=None if end is None else End(place_id=end["place_id"], label=end["label"],
                                             neighborhood=end["neighborhood"], lat=end["lat"], lon=end["lon"],
                                             arrive_by=None),
            candidates=candidates,
            prompt="",
            design=design,
        )

    def _tighten(self, task: Task, plan: Outcome, tier_cfg: TierConfig, rng: random.Random) -> None:
        """Deadlines and arrive_by at the unconstrained optimum's own times plus slack, so the
        optimum stays feasible while the constraints bind."""
        horizon = self.builder.horizon
        for e in rng.sample(range(len(task.errands)), rng.randint(*tier_cfg.deadlines)):
            done = next(s.done for s in plan.stops if s.errand == e)
            task.errands[e].deadline = hhmm(min(horizon, _ceil5(done + rng.randint(*tier_cfg.deadline_slack_min))))
        if task.end is not None:
            task.end.arrive_by = hhmm(min(horizon, _ceil5(plan.finish + rng.randint(*tier_cfg.end_slack_min))))

    def _break(self, task: Task, mode: str, rng: random.Random) -> bool:
        """Make a feasible task impossible in an explainable way; False if this draft can't be."""
        depart = minutes(task.start.depart_time)
        if mode == "end_too_early":
            best = solve(self.builder.instance(task, "global", constraints=False))
            if best is None:
                return False
            by = (best.finish - rng.randint(10, 30)) // 5 * 5
            if by <= depart + 30:
                return False
            task.end.arrive_by = hhmm(by)
            task.design = Design(infeasible=True, infeasible_mode=mode, closing_soon=task.design.closing_soon, reason=(
                f"Even the fastest plan reaches {task.end.label} at {clock(hhmm(best.finish))}, "
                f"after the {clock(task.end.arrive_by)} meeting."))
            return True
        if mode == "deadline_too_early":
            e = rng.randrange(len(task.errands))
            earliest = self._earliest_done(task, e)
            if earliest is None:
                return False
            deadline = (earliest - rng.randint(5, 15)) // 5 * 5
            if deadline <= depart:
                return False
            spec = task.errands[e]
            spec.deadline = hhmm(deadline)
            task.design = Design(infeasible=True, infeasible_mode=mode, closing_soon=task.design.closing_soon, reason=(
                f"No {noun(spec)} can be finished by {clock(spec.deadline)}; "
                f"the earliest any plan can finish it is {clock(hhmm(earliest))}."))
            return True
        raise ValueError(f"unknown infeasible mode {mode}")

    def _earliest_done(self, task: Task, e: int) -> int | None:
        """Earliest time any plan can finish errand e at any store in SF (exact: DP labels, so
        detours through other errands' stores count too)."""
        return earliest_completion(self.builder.instance(task, "global", constraints=False), e)

    def _closed_setup(self, rng: random.Random, specs: list[ErrandSpec]):
        """(day, depart, errand, last) such that no store in SF can serve the errand after depart that
        day (last = latest possible arrival, None if closed all day) while every other errand still can."""
        for spec in rng.sample(specs, len(specs)):
            for day in rng.sample(self.week, len(self.week)):
                last = self._last_arrival(spec, day)
                if last is None:
                    depart = self._random_time(rng, "09:00", "13:00")
                else:
                    depart = _ceil5(last + rng.randint(15, 60))
                    if depart < EARLIEST or depart > CLOSED_LATEST:
                        continue
                if all(len(self.builder.servable(s.category, s.brand, day, depart, s.service_min))
                       for s in specs if s is not spec):
                    return day, depart, spec, last
        return None

    def _last_arrival(self, spec: ErrandSpec, day: date) -> int | None:
        latest = None
        for poi in self.builder.pool(spec.category, spec.brand)["poi_id"]:
            ok = np.flatnonzero(self.builder.table(poi, day, spec.service_min) < INF)
            if ok.size:
                latest = max(latest or 0, int(ok[-1]))
        return latest

    def _infeasible_everywhere(self, task: Task) -> bool:
        return all(solve(self.builder.instance(task, universe)) is None for universe in UNIVERSES)

    @staticmethod
    def _finish(task: Task, rng: random.Random) -> Task:
        task.prompt = render_prompt(task, rng)
        return task


def _tier_orders(cfg: Config, tasks: list[Task]) -> dict[str, tuple[list[str], list[str]]]:
    """One fixed shuffled order per tier and kind (feasible, infeasible); subsets take prefixes of it."""
    rng = random.Random(f"{cfg.seed}:{cfg.benchmark_version}:subsets")
    order = {}
    for tier in cfg.tasks.tiers:
        pool = [t for t in tasks if t.tier == tier]
        order[tier] = ([t.task_id for t in rng.sample(pool, len(pool)) if not t.design.infeasible],
                       [t.task_id for t in rng.sample(pool, len(pool)) if t.design.infeasible])
    return order


def _per_tier(cfg: Config, order: dict, quota: int) -> dict[str, list[str]]:
    """`quota` tasks per tier, at least one of them infeasible. Prefixes are nested as the quota grows."""
    n_infeasible = max(1, round(quota * cfg.tasks.infeasible_share))
    return {tier: order[tier][0][: quota - n_infeasible] + order[tier][1][:n_infeasible] for tier in cfg.tasks.tiers}


def final_rounds(cfg: Config, tasks: list[Task]) -> list[list[str]]:
    """The final subset as rounds of one task per tier: round k holds what each tier adds when its quota
    grows from k-1 to k. The first pilot_size/3 rounds are the pilot, so a run that stops after any round
    covers every tier equally."""
    order, tiers = _tier_orders(cfg, tasks), list(cfg.tasks.tiers)
    rounds, before = [], {tier: [] for tier in tiers}
    for quota in range(1, cfg.tasks.final_size // len(tiers) + 1):
        now = _per_tier(cfg, order, quota)
        rounds.append([next(t for t in now[tier] if t not in before[tier]) for tier in tiers])
        before = now
    return rounds


def pick_subsets(cfg: Config, tasks: list[Task]) -> dict[str, list[str]]:
    """Nested, stratified subsets: pilot (equal per tier, at least one infeasible task per tier) inside
    final (same rule, larger); calibration is feasible pilot tasks taken round-robin across tiers.
    Nesting means every answer bought for a smaller subset is reused by the larger one."""
    order, tiers = _tier_orders(cfg, tasks), list(cfg.tasks.tiers)

    def take(size: int) -> dict[str, list[str]]:
        return _per_tier(cfg, order, size // len(tiers))

    pilot, final = take(cfg.tasks.pilot_size), take(cfg.tasks.final_size)
    feasible_ids = {t.task_id for t in tasks if not t.design.infeasible}
    feasible_pilot = [[tid for tid in pilot[tier] if tid in feasible_ids] for tier in tiers]
    calibration = [tid for group in itertools.zip_longest(*feasible_pilot) for tid in group if tid]
    return {
        "calibration": sorted(calibration[: cfg.tasks.calibration_size]),
        "pilot": sorted(tid for ids in pilot.values() for tid in ids),
        "final": sorted(tid for ids in final.values() for tid in ids),
    }


def write_summary(cfg: Config, tasks: list[Task], pilot: list[str]) -> None:
    rows = []
    for tier in cfg.tasks.tiers:
        group = [t for t in tasks if t.tier == tier]
        modes = Counter(t.design.infeasible_mode for t in group if t.design.infeasible)
        rows.append({
            "tier": tier,
            "tasks": len(group),
            "infeasible": sum(t.design.infeasible for t in group),
            "by mode": ", ".join(f"{m} {n}" for m, n in sorted(modes.items())),
            "errands (mean)": round(np.mean([len(t.errands) for t in group]), 1),
            "with end": sum(t.end is not None for t in group),
            "with deadlines": sum(any(e.deadline for e in t.errands) for t in group),
            "branded": sum(any(e.brand for e in t.errands) for t in group),
            "closing soon": sum(t.design.closing_soon is not None for t in group),
        })
    table = pd.DataFrame(rows)
    categories = Counter(e.category for t in tasks for e in t.errands)
    days = Counter(t.weekday for t in tasks)
    lines = [
        f"# Phase 3: task set {cfg.benchmark_version}",
        "",
        f"{len(tasks)} tasks, pilot subset of {len(pilot)} (benchmark/{cfg.benchmark_version}/pilot_ids.json).",
        "",
        _markdown(table),
        "",
        "Errands per category: " + ", ".join(f"{c} {n}" for c, n in categories.most_common()) + ".",
        "",
        "Weekdays: " + ", ".join(f"{d} {days[d]}" for d in WEEKDAYS) + ".",
        "",
        "## Example prompts",
    ]
    for tier in cfg.tasks.tiers:
        example = next(t for t in tasks if t.tier == tier and not t.design.infeasible)
        lines += ["", f"**{example.task_id}**", "", f"> {example.prompt}"]
    out = cfg.paths.reports / "phase3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "tasks_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _markdown(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns) + " |"
    rule = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, rule, *body])


def _km(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lat1, lat2 = np.radians(lat), np.radians(lats)
    dlat, dlon = lat2 - lat1, np.radians(lons - lon)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _route_km(stores: pd.DataFrame, start: pd.Series, end: pd.Series | None) -> np.ndarray:
    """Distance from each store to the nearer of the task's start and end."""
    lats, lons = stores["lat"].to_numpy(), stores["lon"].to_numpy()
    d = _km(start["lat"], start["lon"], lats, lons)
    return d if end is None else np.minimum(d, _km(end["lat"], end["lon"], lats, lons))


def _ceil5(t: int) -> int:
    return -(-t // 5) * 5
