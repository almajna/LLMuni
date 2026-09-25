"""`make data`: fetch GTFS + OSM, pin their versions, build the POI table and the Phase 1 report."""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import shapely

from llmuni import hours
from llmuni.config import Config
from llmuni.data import boundary, gtfs, osm, report
from llmuni.data.download import fetch, sha256_file

log = logging.getLogger(__name__)


def run_data_stage(cfg: Config, refresh: bool = False) -> dict:
    paths, week_start = cfg.paths, cfg.data.reference_week_start
    previous = _read_json(paths.manifest).get("sources", {})
    sources: dict[str, dict] = {}

    for name, src in cfg.data.gtfs.items():
        key, dest = f"gtfs_{name}", paths.raw / f"gtfs_{name}.zip"
        entry = fetch(src.url, dest, previous.get(key), refresh)
        entry.update(label=src.label or name, file=cfg.rel(dest), **gtfs.summarize_feed(dest, week_start))
        _require_service_all_week(key, entry["reference_week_service"])
        sources[key] = entry

    pbf = paths.raw / "sf.osm.pbf"
    entry = fetch(cfg.data.osm.url, pbf, previous.get("osm"), refresh)
    entry.update(file=cfg.rel(pbf), snapshot_timestamp=osm.snapshot_timestamp(pbf) or entry["http_last_modified"])
    sources["osm"] = entry

    boundary_file = paths.processed / "sf_boundary.geojson"
    sf, meta = boundary.load_boundary(cfg.data.boundary_query, boundary_file)
    sources["sf_boundary"] = {**meta, "file": cfg.rel(boundary_file)}
    sf_geom = sf.geometry.union_all()
    shapely.prepare(sf_geom)

    pois = build_pois(cfg, pbf, sf_geom)
    pois_file = paths.processed / "pois.parquet"
    pois.to_parquet(pois_file, index=False)

    coverage = report.coverage_table(pois, cfg.data.min_valid_pois_per_category, list(cfg.categories))
    caption = _caption(sources, week_start)
    report.write_phase1(paths.reports / "phase1", pois, coverage, osm.extract_roads(pbf), sf_geom, caption)

    manifest = {
        "project": cfg.project,
        "benchmark_version": cfg.benchmark_version,
        "reference_week": {"start": week_start.isoformat(), "end": (week_start + timedelta(days=6)).isoformat()},
        "sources": sources,
        "pois": {
            "file": cfg.rel(pois_file),
            "sha256": sha256_file(pois_file),
            "rows": len(pois),
            "rows_with_valid_hours": int(pois["valid_hours"].sum()),
            "categories_kept": [c for c in coverage.index if coverage.at[c, "kept"]],
            "categories_dropped": [c for c in coverage.index if not coverage.at[c, "kept"]],
        },
    }
    _write_json(paths.manifest, manifest)
    log.info("POI coverage:\n%s", coverage.to_string())
    return manifest


def build_pois(cfg: Config, pbf: Path, sf_geom) -> pd.DataFrame:
    """Named, public, de-duplicated POIs inside SF, with hours evaluated over the reference week."""
    df = osm.extract_pois(pbf, cfg.categories)
    extracted = len(df)
    df = df[shapely.contains_xy(sf_geom, df["lon"].to_numpy(), df["lat"].to_numpy())]
    df = df[df["name"].notna() & ~df["access"].isin(["private", "no"])]
    kept = len(df)
    df = dedupe(df, cfg.data.dedup_radius_m)
    log.info("POI rows: %d extracted, %d named/public inside SF, %d after de-duplication", extracted, kept, len(df))
    return add_hours(df, datetime.combine(cfg.data.reference_week_start, time()))


def dedupe(df: pd.DataFrame, radius_m: float) -> pd.DataFrame:
    """Drop same-name copies within radius_m per category (e.g. a store mapped as node and building).
    Keeps the copy with opening hours, then with an address, then the node."""
    quality = df["opening_hours"].notna().astype(int) * 2 + df["address"].notna().astype(int)
    ranked = df.assign(_key=df["name"].map(_norm_name), _q=quality).sort_values(
        ["_q", "osm_type"], ascending=[False, True], kind="stable"
    )
    keep = []
    for _, group in ranked.groupby(["category", "_key"], sort=False):
        kept: list[tuple[float, float]] = []
        for idx, lat, lon in zip(group.index, group["lat"], group["lon"]):
            if all(_distance_m(lat, lon, la, lo) > radius_m for la, lo in kept):
                kept.append((lat, lon))
                keep.append(idx)
    return df.loc[sorted(keep)]


def add_hours(df: pd.DataFrame, week_start: datetime) -> pd.DataFrame:
    """Parse opening hours and summarize them over the reference week.
    valid_hours = parseable and open at least once during the week."""
    stats = []
    for expr, lat, lon in zip(df["opening_hours"], df["lat"], df["lon"]):
        oh = hours.parse_hours(expr, coords=(lat, lon))
        week = hours.weekly_summary(oh, week_start) if oh is not None else {"open_hours": 0.0, "unknown_hours": 0.0, "open_days": 0}
        stats.append({"hours_parsed": oh is not None, **{f"{k}_week": v for k, v in week.items()}})
    out = pd.concat([df.reset_index(drop=True), pd.DataFrame(stats)], axis=1)
    out["valid_hours"] = out["hours_parsed"] & (out["open_hours_week"] > 0)
    return out.sort_values(["category", "poi_id"]).reset_index(drop=True)


def _require_service_all_week(key: str, week: dict[str, dict]) -> None:
    missing = [day for day, service in week.items() if service["trips"] == 0]
    if missing:
        raise RuntimeError(f"{key} has no scheduled trips on {', '.join(missing)}; pick another data.reference_week_start")


def _caption(sources: dict[str, dict], week_start: date) -> str:
    osm_date = (sources["osm"].get("snapshot_timestamp") or "unknown")[:10]
    feeds = " · ".join(
        f"{src['label']} GTFS {'–'.join(src['service_date_range'] or ['?'])}"
        for key, src in sources.items()
        if key.startswith("gtfs_")
    )
    return f"OSM snapshot {osm_date} · {feeds} · reference week {_week_label(week_start)}"


def _week_label(start: date) -> str:
    end = start + timedelta(days=6)
    if start.month == end.month:
        return f"{start:%b} {start.day}–{end.day}, {end.year}"
    return f"{start:%b} {start.day}–{end:%b} {end.day}, {end.year}"


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6_371_000 * math.hypot(x, y)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
