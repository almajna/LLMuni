"""`llmuni video-basemap`: the video's map plate, drawn from the pinned data in the site's slate palette.

Every OSM street of San Francisco (minor streets as hairlines, arterials heavier) and the rail network from
the GTFS shapes (Muni Metro, streetcars, cable cars, BART), in Web Mercator. The video projects routes with
the same bounds (video/src/data/basemap.json), so the plate and the routes line up exactly.
"""

from __future__ import annotations

import io
import json
import math
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402

from llmuni.config import Config  # noqa: E402
from llmuni.data import osm  # noqa: E402

BOUNDS = (-122.5170, 37.7040, -122.3540, 37.8120)  # lon0, lat0, lon1, lat1: the city, water trimmed
WIDTH = 4000
GROUND, MINOR, MAJOR, RAIL = "#0b1110", "#243330", "#35463f", "#5d716b"
MAJOR_CLASSES = {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link"}
RAIL_TYPES = {0, 1, 2, 5, 7}  # tram/light rail, subway, rail, cable car, funicular


def merc(lon: float, lat: float) -> tuple[float, float]:
    return math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def run_basemap(cfg: Config) -> dict:
    lon0, lat0, lon1, lat1 = BOUNDS
    (x0, y0), (x1, y1) = merc(lon0, lat0), merc(lon1, lat1)
    height = round(WIDTH * (y1 - y0) / (x1 - x0))
    fig = plt.figure(figsize=(WIDTH / 100, height / 100), dpi=100, facecolor=GROUND)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_facecolor(GROUND)

    minor, major = [], []
    for highway, coords in osm.extract_roads(cfg.paths.raw / "sf.osm.pbf"):
        line = [merc(lon, lat) for lon, lat in coords]
        (major if highway in MAJOR_CLASSES else minor).append(line)
    ax.add_collection(LineCollection(minor, colors=MINOR, linewidths=0.9, capstyle="round"))
    ax.add_collection(LineCollection(major, colors=MAJOR, linewidths=2.2, capstyle="round"))
    ax.add_collection(LineCollection(rail_lines(cfg), colors=RAIL, linewidths=1.8, linestyles=(0, (4, 3))))

    out = cfg.root / "video" / "public" / "basemap.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100, facecolor=GROUND)
    plt.close(fig)
    meta = {"lon0": lon0, "lat0": lat0, "lon1": lon1, "lat1": lat1, "width": WIDTH, "height": height,
            "source": "OpenStreetMap streets and Muni/BART GTFS shapes from data/MANIFEST.json"}
    data = cfg.root / "video" / "src" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "basemap.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return meta


def rail_lines(cfg: Config) -> list[list[tuple[float, float]]]:
    """One polyline per distinct GTFS shape of a rail route (Muni Metro, streetcars, cable cars, BART)."""
    lines = []
    for feed in sorted(cfg.paths.raw.glob("gtfs_*.zip")):
        with zipfile.ZipFile(feed) as z:
            read = lambda name: pd.read_csv(io.BytesIO(z.read(name)), dtype=str)  # noqa: E731
            routes, trips, shapes = read("routes.txt"), read("trips.txt"), read("shapes.txt")
        rail = routes[routes["route_type"].astype(int).isin(RAIL_TYPES)]["route_id"]
        shape_ids = set(trips[trips["route_id"].isin(rail)]["shape_id"].dropna())
        shapes = shapes[shapes["shape_id"].isin(shape_ids)].copy()
        shapes["seq"] = shapes["shape_pt_sequence"].astype(int)
        for _, pts in shapes.sort_values(["shape_id", "seq"]).groupby("shape_id"):
            lines.append([merc(float(lon), float(lat)) for lon, lat in zip(pts["shape_pt_lon"], pts["shape_pt_lat"])])
    return lines


def main(cfg: Config) -> Path:
    run_basemap(cfg)
    return cfg.root / "video" / "public" / "basemap.png"
