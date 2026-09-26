"""Street- and rail-following paths for the site's route replay.

Every hop the site draws (start -> stop -> ... -> end, for the optimal plans and every graded model plan) gets
the R5 itinerary for that origin, destination and departure minute, cached per hop in cache/site_routes.json.
The itinerary is then stretched onto the plan's own replayed times (leave when the previous errand is done,
arrive when the grader's replay arrives), so the map and the clocks never disagree. Without a cached itinerary
a hop is drawn as a shallow arc on the same times: schematic on purpose, so it is never mistaken for the street
or line actually taken. (R5 itineraries need more than a 4 GB heap on this network; `--routes` is optional.)
"""

from __future__ import annotations

import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

from llmuni.config import Config

log = logging.getLogger(__name__)

XY = tuple[float, float]


def cache_path(cfg: Config) -> Path:
    return cfg.paths.cache / "site_routes.json"


def hop_key(day: str, a: XY, b: XY, leave: int) -> str:
    return f"{day}|{a[0]:.5f},{a[1]:.5f}|{b[0]:.5f},{b[1]:.5f}|{leave}"


def plan_hops(start: XY, depart: int, stops: list[dict], end: XY | None, end_arrive: int | None) -> list[tuple]:
    """(from, to, leave, arrive) for each travel hop of a replayed plan; stops carry at/arrive/done and the
    plan stops at the first stop it could not reach or be served at."""
    hops, here, t = [], start, depart
    for stop in stops:
        if stop.get("at") is None or stop.get("arrive") is None:
            return hops
        hops.append((here, tuple(stop["at"]), t, stop["arrive"]))
        if stop.get("done") is None:
            return hops
        here, t = tuple(stop["at"]), stop["done"]
    if end is not None and end_arrive is not None:
        hops.append((here, end, t, end_arrive))
    return hops


def timed_path(hops: list[tuple], legs_by_hop: dict[str, list[dict]], day: str) -> list[list[float]]:
    """[lon, lat, minute] points: each hop's itinerary (or a straight line) on the plan's own times, with the
    waits at stops in between."""
    points: list[list[float]] = []
    for a, b, leave, arrive in hops:
        legs = legs_by_hop.get(hop_key(day, a, b, leave)) or []
        for lon, lat, t in _hop_points(a, b, leave, arrive, legs):
            if points and points[-1][:2] == [lon, lat] and points[-1][2] >= t:
                continue
            points.append([lon, lat, t])
    return points


ARC_BEND = 0.14  # an un-routed hop is drawn as a shallow arc (clearly schematic, not a street path)
ARC_POINTS = 16


def _arc(a: XY, b: XY, leave: int, arrive: int) -> list[tuple[float, float, float]]:
    """A quadratic arc from a to b bending to the right of travel, timed evenly along its length."""
    kx = math.cos(math.radians((a[1] + b[1]) / 2))  # metres per degree of longitude shrink with latitude
    dx, dy = (b[0] - a[0]) * kx, b[1] - a[1]
    mid = ((a[0] + b[0]) / 2 + dy * ARC_BEND / kx, (a[1] + b[1]) / 2 - dx * ARC_BEND)
    pts = []
    for k in range(ARC_POINTS + 1):
        u = k / ARC_POINTS
        x = (1 - u) ** 2 * a[0] + 2 * (1 - u) * u * mid[0] + u ** 2 * b[0]
        y = (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * mid[1] + u ** 2 * b[1]
        pts.append((x, y))
    lengths = [0.0]
    for p, q in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + _meters(p, q))
    total = lengths[-1] or 1.0
    return [(x, y, round(leave + (arrive - leave) * d / total, 3)) for (x, y), d in zip(pts, lengths)]


def _hop_points(a: XY, b: XY, leave: int, arrive: int, legs: list[dict]) -> list[tuple[float, float, float]]:
    coords = [(leg["coords"], leg["t0"], leg["t1"]) for leg in legs if leg["coords"]]
    if not coords:
        return _arc(a, b, leave, arrive) if a != b else [(a[0], a[1], float(leave)), (b[0], b[1], float(arrive))]
    t_first, t_last = coords[0][1], coords[-1][2]
    scale = (arrive - leave) / (t_last - t_first) if t_last > t_first else 0.0
    out = [(a[0], a[1], float(leave))]
    for line, t0, t1 in coords:
        s0, s1 = leave + (t0 - t_first) * scale, leave + (t1 - t_first) * scale
        lengths = [0.0]
        for p, q in zip(line, line[1:]):
            lengths.append(lengths[-1] + _meters(p, q))
        total = lengths[-1] or 1.0
        out += [(p[0], p[1], round(s0 + (s1 - s0) * d / total, 3)) for p, d in zip(line, lengths)]
    out.append((b[0], b[1], float(arrive)))
    return out


def compute_routes(cfg: Config, wanted: dict[str, tuple[str, XY, XY, int]], threads: int = 2) -> dict[str, list[dict]]:
    """R5 itineraries for the hops not cached yet (key -> (day, from, to, leave)); saves as it goes."""
    path = cache_path(cfg)
    cache: dict[str, list[dict]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = {k: v for k, v in wanted.items() if k not in cache}
    if not todo:
        return cache
    from llmuni.router import Place, Router

    log.info("site routes: %d hops cached, %d to route with R5", len(wanted) - len(todo), len(todo))
    router = Router(cfg)

    def route(item):
        key, (day, a, b, leave) = item
        depart = datetime.combine(date.fromisoformat(day), datetime.min.time()) + timedelta(minutes=leave)
        legs = router.itinerary(Place("a", a[1], a[0]), Place("b", b[1], b[0]), depart, window_min=1)
        midnight = datetime.combine(date.fromisoformat(day), datetime.min.time())
        return key, [{"mode": leg["mode"], "route": leg["route"], "coords": [list(c) for c in leg["coords"]],
                      "t0": (leg["depart"].replace(tzinfo=None) - midnight).total_seconds() / 60,
                      "t1": (leg["arrive"].replace(tzinfo=None) - midnight).total_seconds() / 60} for leg in legs]

    done = 0
    with ThreadPoolExecutor(threads) as pool:
        for future in as_completed([pool.submit(route, item) for item in todo.items()]):
            try:
                key, legs = future.result()
            except Exception as exc:  # a hop R5 cannot route is drawn straight
                log.warning("site route failed: %s", exc)
                continue
            cache[key] = legs
            done += 1
            if done % 25 == 0:
                _save(path, cache)
                log.info("site routes: %d/%d", done, len(todo))
    _save(path, cache)
    return cache


def _save(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def _meters(p: tuple[float, float], q: tuple[float, float]) -> float:
    x = math.radians(q[0] - p[0]) * math.cos(math.radians((p[1] + q[1]) / 2))
    return 6_371_000 * math.hypot(x, math.radians(q[1] - p[1]))
