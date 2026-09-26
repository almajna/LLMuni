"""Planning matrices: every valid-hours POI plus the task landmarks, one TravelMatrix per
GTFS service day of the reference week (Mon-Fri share one when their timetables match)."""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import date, timedelta

import pandas as pd

from llmuni.config import Config
from llmuni.data.gtfs import active_service_ids, read_table
from llmuni.router import Place, Router, TravelMatrix, matrix_cache_path

log = logging.getLogger(__name__)


def minutes(hhmm: str) -> int:
    hour, minute = map(int, hhmm.split(":"))
    return 60 * hour + minute


def hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def service_days(cfg: Config) -> dict[date, date]:
    """Each reference-week date -> the first week date with identical Muni + BART service."""
    feeds = []
    for name in cfg.data.gtfs:
        with zipfile.ZipFile(cfg.paths.raw / f"gtfs_{name}.zip") as z:
            feeds.append((read_table(z, "calendar.txt"), read_table(z, "calendar_dates.txt")))
    first_by_service: dict[tuple, date] = {}
    days = {}
    for offset in range(7):
        day = cfg.data.reference_week_start + timedelta(days=offset)
        service = tuple(frozenset(active_service_ids(cal, dates, day)) for cal, dates in feeds)
        days[day] = first_by_service.setdefault(service, day)
    return days


def planning_pois(cfg: Config) -> pd.DataFrame:
    """POI rows of the categories kept after Phase 1 (see MANIFEST.json), all hours statuses."""
    manifest = json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))
    pois = pd.read_parquet(cfg.paths.processed / "pois.parquet")
    return pois[pois["category"].isin(manifest["pois"]["categories_kept"])].reset_index(drop=True)


def routable_places(landmarks: pd.DataFrame, pois: pd.DataFrame) -> list[Place]:
    """Landmarks, then every distinct POI with valid hours, in a fixed order."""
    valid = pois[pois["valid_hours"]].drop_duplicates("poi_id").sort_values("poi_id")
    return [Place(r.place_id, r.lat, r.lon) for r in landmarks.itertuples()] + [
        Place(r.poi_id, r.lat, r.lon) for r in valid.itertuples()
    ]


class Matrices:
    """TravelMatrix per task date, loaded from the router cache (computed with R5 when missing)."""

    def __init__(self, cfg: Config, places: list[Place]) -> None:
        self.cfg, self.places = cfg, places
        self.days = service_days(cfg)
        self.first, self.last = (minutes(t) for t in cfg.tasks.matrix_window)
        self._router: Router | None = None
        self._loaded: dict[date, TravelMatrix] = {}

    def for_day(self, day: date) -> TravelMatrix:
        service_day = self.days[day]
        if service_day not in self._loaded:
            path = matrix_cache_path(self.cfg, self.places, service_day, self.first, self.last)
            if (path / "meta.json").exists():
                self._loaded[service_day] = TravelMatrix.load(path)
            else:
                log.info("computing the %s matrix: %d places x %d departures (R5)", service_day,
                         len(self.places), (self.last - self.first) // self.cfg.router.departure_step_min + 1)
                self._router = self._router or Router(self.cfg)
                self._loaded[service_day] = self._router.matrix(self.places, service_day, self.first, self.last)
        return self._loaded[service_day]

    def precompute(self) -> None:
        for service_day in sorted(set(self.days.values())):
            self.for_day(service_day)
