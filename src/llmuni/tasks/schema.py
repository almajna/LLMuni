"""Task schema (one JSON object per line in benchmark/<version>/tasks.jsonl). Times are "HH:MM" local."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Start(BaseModel):
    place_id: str
    label: str
    neighborhood: str
    lat: float
    lon: float
    depart_time: str


class End(BaseModel):
    place_id: str
    label: str
    neighborhood: str
    lat: float
    lon: float
    arrive_by: str | None


class ErrandSpec(BaseModel):
    category: str
    brand: str | None = None
    service_min: int
    deadline: str | None = None  # the errand must be finished by then


class Candidate(BaseModel):
    poi_id: str
    name: str
    address: str | None
    lat: float
    lon: float
    opening_hours: str


class Design(BaseModel):
    """How the task was built; never shown to models."""

    infeasible: bool = False
    infeasible_mode: Literal["end_too_early", "deadline_too_early", "closed"] | None = None
    reason: str | None = None
    closing_soon: str | None = None  # category whose stores close soon after departure (medium tier)


class Task(BaseModel):
    task_id: str
    benchmark_version: str
    tier: Literal["easy", "medium", "hard"]
    weekday: str
    date: str
    start: Start
    errands: list[ErrandSpec]
    end: End | None
    objective: Literal["min_finish_time"] = "min_finish_time"
    candidates: dict[str, list[Candidate]]
    prompt: str
    design: Design
