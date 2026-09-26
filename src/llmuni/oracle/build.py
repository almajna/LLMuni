"""Oracle instances from tasks, over one of two store universes:

- "candidates": the K stores listed per errand (what open-book and tool-use models choose from);
- "global": every store in SF with valid hours that can still serve the errand that day
  (what a closed-book model may name).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from llmuni import hours
from llmuni.config import Config
from llmuni.oracle.model import INF, Errand, Instance, service_table
from llmuni.tasks.schema import Task
from llmuni.travel import Matrices, minutes

UNIVERSES = ("candidates", "global")


class InstanceBuilder:
    def __init__(self, cfg: Config, matrices: Matrices, pois: pd.DataFrame) -> None:
        self.cfg, self.matrices = cfg, matrices
        self.horizon = minutes(cfg.tasks.horizon)
        valid = pois[pois["valid_hours"]]
        self.by_category = {category: rows.reset_index(drop=True) for category, rows in valid.groupby("category")}
        self._hours = {row.poi_id: (row.opening_hours, row.lat, row.lon) for row in valid.itertuples()}
        self._intervals: dict[tuple[str, date], list[tuple[int, int]]] = {}
        self._tables: dict[tuple[str, date, int], np.ndarray] = {}

    def intervals(self, poi_id: str, day: date) -> list[tuple[int, int]]:
        key = (poi_id, day)
        if key not in self._intervals:
            expr, lat, lon = self._hours[poi_id]
            self._intervals[key] = hours.day_intervals(hours.parse_hours(expr, coords=(lat, lon)), day)
        return self._intervals[key]

    def table(self, poi_id: str, day: date, service: int) -> np.ndarray:
        key = (poi_id, day, service)
        if key not in self._tables:
            self._tables[key] = service_table(self.intervals(poi_id, day), service, self.horizon)
        return self._tables[key]

    def pool(self, category: str, brand: str | None = None) -> pd.DataFrame:
        """Every store of the category (and brand) with valid hours."""
        stores = self.by_category.get(category, pd.DataFrame(columns=["poi_id"]))
        return stores[stores["brand"] == brand] if brand else stores

    def servable(self, category: str, brand: str | None, day: date, depart: int, service: int) -> pd.DataFrame:
        """Stores of the category that can still serve the errand on `day` at or after `depart`."""
        stores = self.pool(category, brand)
        mask = [self.table(p, day, service)[min(depart, self.horizon + 1)] < INF for p in stores["poi_id"]]
        return stores[np.array(mask, dtype=bool)] if len(stores) else stores

    def instance(self, task: Task, universe: str = "candidates", constraints: bool = True) -> Instance:
        """Oracle problem for a task; constraints=False drops deadlines and arrive_by."""
        day = date.fromisoformat(task.date)
        tm = self.matrices.for_day(day)
        depart = minutes(task.start.depart_time)
        errands, options, tables = [], [], []
        for spec in task.errands:
            if universe == "candidates":
                ids = [c.poi_id for c in task.candidates[spec.category]]
            else:
                ids = list(self.servable(spec.category, spec.brand, day, depart, spec.service_min)["poi_id"])
            deadline = minutes(spec.deadline) if constraints and spec.deadline else None
            errands.append(Errand(spec.category, spec.service_min, deadline))
            options.append(np.array([tm.index(i) for i in ids], dtype=np.int64))
            rows = [self.table(i, day, spec.service_min) for i in ids]
            tables.append(np.stack(rows) if rows else np.empty((0, self.horizon + 2), dtype=np.int64))
        end = tm.index(task.end.place_id) if task.end else None
        arrive_by = minutes(task.end.arrive_by) if constraints and task.end and task.end.arrive_by else None
        return Instance(tm, tm.index(task.start.place_id), depart, errands, options, tables, end, arrive_by, self.horizon)

    def routable(self, poi_id: str) -> bool:
        """Whether the store is in the travel matrices (every store with valid hours is)."""
        return poi_id in self._hours

    def plan_instance(self, task: Task, chosen: dict[int, str]) -> Instance:
        """Instance whose only option per errand is the store a plan chose ({errand index: poi_id});
        errands without a choice get no options. For replaying a model's plan with `simulate`."""
        day = date.fromisoformat(task.date)
        tm = self.matrices.for_day(day)
        errands, options, tables = [], [], []
        for e, spec in enumerate(task.errands):
            deadline = minutes(spec.deadline) if spec.deadline else None
            errands.append(Errand(spec.category, spec.service_min, deadline))
            poi = chosen.get(e)
            options.append(np.array([tm.index(poi)] if poi else [], dtype=np.int64))
            tables.append(self.table(poi, day, spec.service_min)[None] if poi
                          else np.empty((0, self.horizon + 2), dtype=np.int64))
        end = tm.index(task.end.place_id) if task.end else None
        arrive_by = minutes(task.end.arrive_by) if task.end and task.end.arrive_by else None
        return Instance(tm, tm.index(task.start.place_id), minutes(task.start.depart_time), errands, options,
                        tables, end, arrive_by, self.horizon)
