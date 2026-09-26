"""Phase 2: door-to-door walk + transit routing on Muni and BART with R5 (via r5py).

R5 computes travel times for exact departure minutes on a fixed grid (every
`departure_step_min` minutes). `TravelMatrix.arrival` turns them into an earliest-arrival
function that is FIFO -- leaving later never arrives earlier -- which is what makes the
oracle's label-setting DP exact (see docs/methods.md).
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import logging
import os
import shutil
import sys
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from llmuni.config import Config

log = logging.getLogger(__name__)

NO_TRIP = int(np.iinfo(np.uint16).max)  # sentinel in uint16 minute arrays
R5_NULL = int(np.iinfo(np.int32).max)  # R5's "not reached"


@dataclass(frozen=True)
class Place:
    id: str
    lat: float
    lon: float


@dataclass
class TravelMatrix:
    """Earliest arrivals between places on one service day, for departures on a fixed grid."""

    ids: list[str]
    day: date
    start: int  # first grid departure, minutes after midnight
    step: int  # grid spacing, minutes
    arrive: np.ndarray  # uint16 (n, n, k): earliest arrival minute when leaving at grid departure k
    walk: np.ndarray  # uint16 (n, n): walking-only minutes

    def __post_init__(self) -> None:
        self._index = {pid: i for i, pid in enumerate(self.ids)}

    def index(self, place_id: str) -> int:
        return self._index[place_id]

    def arrival(self, i: int, j: int, t: int) -> int | None:
        """Earliest arrival (minutes after midnight) at place j when ready to leave place i at t.

        Either walk now, or wait for the next grid departure s >= t and use its (already
        FIFO-adjusted) arrival. Both options are non-decreasing in t, so their minimum is FIFO.
        """
        if i == j:
            return t
        best = NO_TRIP if self.walk[i, j] == NO_TRIP else t + int(self.walk[i, j])
        k = max(0, -(-(t - self.start) // self.step))  # ceil to the next grid departure
        if k < self.arrive.shape[2]:
            best = min(best, int(self.arrive[i, j, k]))
        return None if best >= NO_TRIP else best

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        meta = json.dumps({"day": self.day.isoformat(), "start": self.start, "step": self.step})
        np.savez_compressed(path, ids=np.array(self.ids), arrive=self.arrive, walk=self.walk, meta=np.array(meta))

    @classmethod
    def load(cls, path: Path) -> TravelMatrix:
        """From a .npz file, or from a matrix directory (arrive.npy is memory-mapped, not read into RAM)."""
        if path.is_dir():
            meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
            return cls(meta["ids"], date.fromisoformat(meta["day"]), meta["start"], meta["step"],
                       np.load(path / "arrive.npy", mmap_mode="r"), np.load(path / "walk.npy"))
        with np.load(path) as z:
            meta = json.loads(str(z["meta"]))
            return cls(list(z["ids"]), date.fromisoformat(meta["day"]), meta["start"], meta["step"], z["arrive"], z["walk"])

    @staticmethod
    def assemble(path: Path, ids: list[str], day: date, start: int, step: int, blocks: list[Path], walk: Path) -> None:
        """Write a matrix directory by streaming origin blocks into a memory-mapped arrive.npy, so the
        full matrix never has to fit in memory at once. meta.json is written last and marks completion."""
        tmp = path.with_suffix(".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        first = np.load(blocks[0], mmap_mode="r")
        arrive = np.lib.format.open_memmap(tmp / "arrive.npy", mode="w+", dtype=np.uint16,
                                           shape=(len(ids), len(ids), first.shape[2]))
        row = 0
        for block in blocks:
            part = np.load(block)
            arrive[row : row + len(part)] = part
            row += len(part)
        arrive.flush()
        del arrive
        shutil.copyfile(walk, tmp / "walk.npy")
        meta = {"ids": ids, "day": day.isoformat(), "start": start, "step": step}
        (tmp / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        tmp.rename(path)


def fifo_arrivals(minutes: np.ndarray, start: int, step: int) -> np.ndarray:
    """Door-to-door minutes per grid departure (last axis) -> earliest arrival minutes, allowing
    the traveler to wait for a later grid departure: arrive[k] = min over k' >= k of dep[k'] +
    minutes[k']. The result is non-decreasing along the last axis."""
    departures = start + step * np.arange(minutes.shape[-1], dtype=np.int64)
    arrive = np.where(minutes == NO_TRIP, np.iinfo(np.int64).max, minutes.astype(np.int64) + departures)
    arrive = np.minimum.accumulate(arrive[..., ::-1], axis=-1)[..., ::-1]
    return np.where(arrive >= NO_TRIP, NO_TRIP, arrive).astype(np.uint16)


class Router:
    """R5 transport network for SF (OSM streets + Muni and BART timetables)."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.params = cfg.router
        _use_configured_java(cfg)
        import r5py  # starts the JVM, so JAVA_HOME must be set first

        self._r5py = r5py
        raw = cfg.paths.raw
        feeds = [raw / f"gtfs_{name}.zip" for name in cfg.data.gtfs]
        started = perf_counter()
        self.network = r5py.TransportNetwork(raw / "sf.osm.pbf", feeds)
        log.info("transport network ready in %.0f s", perf_counter() - started)
        self._routes = _route_names(feeds)

    def travel_time(self, a: Place, b: Place, depart: datetime) -> float | None:
        """Door-to-door minutes from a to b leaving at depart (walking + Muni/BART)."""
        minutes = int(self.travel_times([a], [b], [depart])[0, 0, 0])
        return None if minutes == NO_TRIP else float(minutes)

    def travel_times(
        self, origins: list[Place], destinations: list[Place], departures: list[datetime], *, transit: bool = True
    ) -> np.ndarray:
        """uint16 door-to-door minutes indexed (origin, destination, departure); NO_TRIP where
        nothing arrives within max_trip_minutes. Each (origin, departure) is one R5 search."""
        import com.conveyal.r5

        base = self._task(destinations, departures[0], transit)
        out = np.full((len(origins), len(destinations), len(departures)), NO_TRIP, dtype=np.uint16)
        total = len(origins) * len(departures)
        done, started = itertools.count(1), perf_counter()

        def search(job: tuple[int, int]) -> None:
            i, k = job
            task = copy.copy(base)
            task.origin = shapely.Point(origins[i].lon, origins[i].lat)
            task.departure = departures[k]
            result = com.conveyal.r5.analyst.TravelTimeComputer(task, self.network).computeTravelTimes()
            minutes = np.asarray(result.travelTimes.getValues()[0], dtype=np.int64)
            out[i, :, k] = np.where(minutes >= min(R5_NULL, NO_TRIP), NO_TRIP, minutes)
            n = next(done)
            if total >= 50_000 and n % (total // 20) == 0:
                log.info("  %3.0f%% of %d searches (%.0f/s)", 100 * n / total, total, n / (perf_counter() - started))

        with ThreadPoolExecutor(self.params.threads) as pool:
            for _ in pool.map(search, itertools.product(range(len(origins)), range(len(departures)))):
                pass
        for i, origin in enumerate(origins):  # R5 links places to the nearest street, so self-trips aren't 0
            for j, destination in enumerate(destinations):
                if origin.id == destination.id:
                    out[i, j, :] = 0
        return out

    def matrix(self, places: list[Place], day: date, first: int, last: int, block: int = 64) -> TravelMatrix:
        """TravelMatrix for grid departures from `first` to `last` (minutes after midnight), cached on disk.
        Resumable: each block of origins is saved as it finishes, so an interruption costs one block."""
        step = self.params.departure_step_min
        path = matrix_cache_path(self.cfg, places, day, first, last)
        if (path / "meta.json").exists():
            return TravelMatrix.load(path)
        parts = path.with_suffix(".parts")
        parts.mkdir(parents=True, exist_ok=True)
        midnight = datetime.combine(day, datetime.min.time())
        departures = [midnight + timedelta(minutes=m) for m in range(first, last + 1, step)]
        n_blocks = -(-len(places) // block)
        blocks = [parts / f"arrive_{b:04d}.npy" for b in range(n_blocks)]
        started = perf_counter()
        for b, (i, part) in enumerate(zip(range(0, len(places), block), blocks)):
            if part.exists():
                continue
            minutes = self.travel_times(places[i : i + block], places, departures)
            np.save(part, fifo_arrivals(minutes, first, step))
            log.info("%s: block %d/%d done (%.0f s so far)", day, b + 1, n_blocks, perf_counter() - started)
        walk = parts / "walk.npy"
        if not walk.exists():
            np.save(walk, self.travel_times(places, places, departures[:1], transit=False)[:, :, 0])
        TravelMatrix.assemble(path, [p.id for p in places], day, first, step, blocks, walk)
        shutil.rmtree(parts)  # the finished matrix supersedes its partial blocks
        return TravelMatrix.load(path)

    def itinerary(self, a: Place, b: Place, depart: datetime, window_min: int | None = None) -> list[dict]:
        """Legs of the earliest-arriving trip from a to b leaving at depart (for visualization), searching
        departures over `window_min` minutes (default: the matrix grid step)."""
        r5py = self._r5py
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            trips = r5py.DetailedItineraries(
                self.network,
                origins=_points([a]),
                destinations=_points([b]),
                departure=depart,
                departure_time_window=timedelta(minutes=window_min or self.params.departure_step_min),
                transport_modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
                speed_walking=self.params.walk_speed_mps * 3.6,
                max_time=timedelta(minutes=self.params.max_trip_minutes),
                max_time_walking=timedelta(minutes=self.params.max_walk_minutes),
            )
        trips = trips.dropna(subset=["travel_time"])
        if trips.empty:
            return []
        leave = trips["departure_time"].fillna(pd.Timestamp(depart))  # direct walks carry no departure time
        trips = trips.assign(leave=leave, arrive=leave + trips["travel_time"])
        options = trips.groupby("option").agg(arrive=("arrive", "max"), legs=("segment", "size"))
        best = options.sort_values(["arrive", "legs"]).index[0]
        legs = []
        for leg in trips[trips["option"] == best].itertuples():
            mode = str(leg.transport_mode).split(".")[-1]
            legs.append({
                "mode": mode,
                "route": self._routes.get((leg.feed, str(leg.route_id))) if mode != "WALK" else None,
                "depart": leg.leave.to_pydatetime(),
                "arrive": leg.arrive.to_pydatetime(),
                "wait_min": leg.wait_time.total_seconds() / 60 if pd.notna(leg.wait_time) else 0.0,
                "distance_m": float(leg.distance),
                "coords": _coords(leg.geometry),
            })
        return legs

    def _task(self, destinations: list[Place], departure: datetime, transit: bool):
        r5py = self._r5py
        modes = [r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK] if transit else [r5py.TransportMode.WALK]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # a one-minute window is intentional: exact departures
            return r5py.RegionalTask(
                self.network,
                destinations=_points(destinations),
                departure=departure,
                departure_time_window=timedelta(minutes=1),
                transport_modes=modes,
                access_modes=[r5py.TransportMode.WALK],
                max_time=timedelta(minutes=self.params.max_trip_minutes),
                max_time_walking=timedelta(minutes=self.params.max_walk_minutes),
                speed_walking=self.params.walk_speed_mps * 3.6,
            )

def matrix_cache_path(cfg: Config, places: list[Place], day: date, first: int, last: int) -> Path:
    """Where Router.matrix caches a matrix: keyed by input data, places, day, grid and routing params."""
    sources = json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))["sources"]
    params = cfg.router
    key = {
        "inputs": {name: src["sha256"] for name, src in sources.items()  # routing inputs only
                   if src.get("sha256") and (name.startswith("gtfs_") or name == "osm")},
        "places": [(p.id, round(p.lat, 6), round(p.lon, 6)) for p in places],
        "day": day.isoformat(),
        "grid": [first, last, params.departure_step_min],
        "walk_speed_mps": params.walk_speed_mps,
        "max_trip_minutes": params.max_trip_minutes,
        "max_walk_minutes": params.max_walk_minutes,
    }
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:20]
    return cfg.paths.cache / "router" / f"{day:%Y%m%d}_{digest}"  # a matrix directory (TravelMatrix.assemble)


def _coords(geometry) -> list[tuple[float, float]]:
    """(lon, lat) points of a leg's line; multi-part lines are joined in order."""
    if geometry is None or geometry.is_empty:
        return []
    parts = geometry.geoms if geometry.geom_type.startswith("Multi") else [geometry]
    return [(round(x, 6), round(y, 6)) for part in parts for x, y in part.coords]


def _points(places: list[Place]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"id": [p.id for p in places]},
        geometry=gpd.points_from_xy([p.lon for p in places], [p.lat for p in places]),
        crs="EPSG:4326",
    )


def _use_configured_java(cfg: Config) -> None:
    """Point JPype at the configured JDK (e.g. the portable one in .tools/) unless JAVA_HOME is set,
    and cap the JVM heap: r5py reads --max-memory from sys.argv when it starts the JVM."""
    if "--max-memory" not in sys.argv:
        sys.argv += ["--max-memory", cfg.router.max_memory]
    if os.environ.get("JAVA_HOME") or cfg.router.java_home is None:
        return
    home = cfg.root / cfg.router.java_home
    if home.is_dir():
        os.environ["JAVA_HOME"] = str(home)


def _route_names(feeds: list[Path]) -> dict[tuple[str, str], str]:
    """(feed, route_id) -> rider-facing name: 'N JUDAH' for Muni, 'BART Yellow-N' for BART.
    Route ids collide across feeds (Muni's 6 bus vs BART's route 6), so the feed is part of the key;
    r5py reports the feed as the GTFS file's stem."""
    names: dict[tuple[str, str], str] = {}
    for feed in feeds:
        with zipfile.ZipFile(feed) as z:
            member = next(n for n in z.namelist() if Path(n).name == "routes.txt")
            routes = pd.read_csv(z.open(member), dtype=str, keep_default_na=False)
        bart = "bart" in feed.stem
        for r in routes.itertuples():
            short, long = r.route_short_name.strip(), r.route_long_name.strip()
            name = f"BART {short or long}" if bart else " ".join(x for x in (short, long) if x)
            names[(feed.stem, r.route_id)] = name
    return names
