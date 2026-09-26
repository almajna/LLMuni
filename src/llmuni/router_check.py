"""`make router-check`: door-to-door times on well-known SF trips, plus matrix throughput."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from time import perf_counter

import numpy as np
import pandas as pd

from llmuni.config import Config
from llmuni.router import NO_TRIP, Place, Router

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SanityTrip:
    label: str
    origin: tuple[float, float]  # (lat, lon)
    destination: tuple[float, float]
    plausible: tuple[int, int]  # door-to-door minutes, inclusive


TRIPS = [
    SanityTrip("Powell St BART → Civic Center BART", (37.7844, -122.4079), (37.7797, -122.4138), (4, 14)),
    SanityTrip("Mission & 16th → Ferry Building", (37.7650, -122.4196), (37.7955, -122.3937), (10, 30)),
    SanityTrip("Castro & Market → Montgomery St", (37.7626, -122.4351), (37.7893, -122.4012), (10, 35)),
    SanityTrip("Inner Sunset (9th Ave & Irving) → Union Square", (37.7641, -122.4665), (37.7876, -122.4079), (20, 50)),
    SanityTrip("Outer Richmond (Geary & 25th) → Chinatown", (37.7801, -122.4846), (37.7937, -122.4078), (25, 65)),
    SanityTrip("Dolores Park → Mission & 19th (walk)", (37.7596, -122.4269), (37.7601, -122.4190), (5, 14)),
]


def run_router_check(cfg: Config) -> pd.DataFrame:
    router = Router(cfg)
    depart = cfg.router.sanity_departure
    rows = []
    for trip in TRIPS:
        a, b = Place("origin", *trip.origin), Place("destination", *trip.destination)
        minutes = router.travel_time(a, b, depart)
        legs = router.itinerary(a, b, depart)
        low, high = trip.plausible
        rows.append({
            "trip": trip.label,
            "minutes": minutes,
            "plausible": f"{low}–{high}",
            "ok": minutes is not None and low <= minutes <= high,
            "itinerary": describe(legs),
        })
    result = pd.DataFrame(rows)
    throughput = measure_throughput(router, cfg)
    _write_report(cfg, result, throughput)
    log.info("sanity trips:\n%s", result.drop(columns="itinerary").to_string(index=False))
    return result


def describe(legs: list[dict]) -> str:
    """'Walk 4 → BART Yellow-N 6 → Walk 3' (minutes moving per leg; waits are not shown)."""
    parts = []
    for leg in legs:
        minutes = round((leg["arrive"] - leg["depart"]).total_seconds() / 60)
        name = "Walk" if leg["mode"] == "WALK" else (leg["route"] or leg["mode"].title())
        parts.append(f"{name} {minutes}")
    return " → ".join(parts) or "—"


def measure_throughput(router: Router, cfg: Config, n_places: int = 40, n_departures: int = 12) -> dict:
    """Time an n_places x n_places matrix over n_departures grid departures."""
    pois = pd.read_parquet(cfg.paths.processed / "pois.parquet")
    pois = pois[pois["valid_hours"]].drop_duplicates("poi_id").sample(n_places, random_state=cfg.seed)
    places = [Place(r.poi_id, r.lat, r.lon) for r in pois.itertuples()]
    start = cfg.router.sanity_departure
    departures = [start + timedelta(minutes=cfg.router.departure_step_min * k) for k in range(n_departures)]
    started = perf_counter()
    minutes = router.travel_times(places, places, departures)
    seconds = perf_counter() - started
    searches = n_places * n_departures
    return {
        "places": n_places,
        "departures": n_departures,
        "seconds": round(seconds, 1),
        "searches_per_s": round(searches / seconds, 1),
        "reachable_pct": round(100 * float(np.mean(minutes != NO_TRIP)), 1),
    }


def _write_report(cfg: Config, result: pd.DataFrame, throughput: dict) -> None:
    out = cfg.paths.reports / "phase2"
    out.mkdir(parents=True, exist_ok=True)
    depart = cfg.router.sanity_departure
    lines = [
        "# Phase 2: router sanity trips",
        "",
        f"Door-to-door minutes leaving {depart:%a %b %d, %Y %H:%M} (walk {cfg.router.walk_speed_mps} m/s + Muni + BART, R5).",
        "",
        "| Trip | Minutes | Plausible | OK | Fastest itinerary (minutes per leg) |",
        "|---|---:|---:|:---:|---|",
    ]
    for r in result.itertuples():
        minutes = "—" if r.minutes is None or pd.isna(r.minutes) else f"{r.minutes:.0f}"
        lines.append(f"| {r.trip} | {minutes} | {r.plausible} | {'yes' if r.ok else '**no**'} | {r.itinerary} |")
    t = throughput
    lines += [
        "",
        f"Throughput: {t['places']}×{t['places']} matrix over {t['departures']} departures in {t['seconds']} s "
        f"({t['searches_per_s']} R5 searches/s, {cfg.router.threads} threads); {t['reachable_pct']}% of pairs reachable.",
    ]
    (out / "sanity_trips.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
