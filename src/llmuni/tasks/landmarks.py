"""Task start/end points: named intersections (data/landmarks.yaml) resolved against the OSM extract."""

from __future__ import annotations

import pandas as pd
import yaml

from llmuni.config import Config
from llmuni.data.osm import intersection_points


def load_landmarks(cfg: Config) -> pd.DataFrame:
    """place_id, label, neighborhood, lat, lon; also written to data/processed/landmarks.csv."""
    specs = yaml.safe_load((cfg.root / cfg.tasks.landmarks).read_text(encoding="utf-8"))
    points = intersection_points(cfg.paths.raw / "sf.osm.pbf", [tuple(s["streets"]) for s in specs])
    rows = []
    for i, spec in enumerate(specs, 1):
        point = points[tuple(spec["streets"])]
        if point is None:
            raise ValueError(f"landmark {spec['label']!r}: {spec['streets']} do not meet in the OSM extract")
        rows.append({"place_id": f"L{i:02d}", "label": spec["label"], "neighborhood": spec["neighborhood"],
                     "lat": round(point[0], 6), "lon": round(point[1], 6)})
    landmarks = pd.DataFrame(rows)
    landmarks.to_csv(cfg.paths.processed / "landmarks.csv", index=False)
    return landmarks
