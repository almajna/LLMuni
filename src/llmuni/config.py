"""Typed access to config.yaml, the single home of every pipeline parameter."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class Paths(BaseModel):
    raw: Path
    processed: Path
    manifest: Path
    reports: Path
    cache: Path


class Source(BaseModel):
    url: str
    label: str | None = None


class BrandedTags(BaseModel):
    """Tags that qualify only for the listed brands (lowercase substrings of name/brand/operator)."""

    tags: dict[str, list[str]]
    brands: list[str]


class CategorySpec(BaseModel):
    """OSM tag rules for one errand category."""

    tags: dict[str, list[str]]
    branded_tags: BrandedTags | None = None
    hours_keys: list[str] = Field(default_factory=lambda: ["opening_hours"])
    brands: dict[str, list[str]] = Field(default_factory=dict)


class DataConfig(BaseModel):
    reference_week_start: date
    min_valid_pois_per_category: int
    dedup_radius_m: float
    gtfs: dict[str, Source]
    osm: Source
    boundary_query: str

    @field_validator("reference_week_start")
    @classmethod
    def _is_monday(cls, v: date) -> date:
        if v.weekday() != 0:
            raise ValueError(f"reference_week_start must be a Monday, got a {v:%A}")
        return v


class RouterConfig(BaseModel):
    java_home: Path | None = None  # relative to the repo root
    walk_speed_mps: float
    max_trip_minutes: int
    max_walk_minutes: int
    departure_step_min: int
    threads: int
    sanity_departure: datetime


class Config(BaseModel):
    project: str
    benchmark_version: str
    seed: int
    timezone: str
    root: Path
    paths: Paths
    data: DataConfig
    router: RouterConfig
    categories: dict[str, CategorySpec]

    def rel(self, path: Path) -> str:
        """Repo-relative POSIX path, for portable references in manifests."""
        return path.resolve().relative_to(self.root).as_posix()


def load_config(path: str | Path | None = None) -> Config:
    """Load config.yaml (default: the nearest one at or above the cwd); paths become absolute."""
    cfg_path = Path(path) if path else _find_config()
    root = cfg_path.resolve().parent
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    raw["paths"] = {k: root / v for k, v in raw["paths"].items()}
    return Config(root=root, **raw)


def _find_config() -> Path:
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / "config.yaml").is_file():
            return d / "config.yaml"
    raise FileNotFoundError("config.yaml not found in the working directory or any parent")
