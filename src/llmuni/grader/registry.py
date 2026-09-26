"""San Francisco's Registered Business Locations (DataSF g8m3-pdis, active locations only): a second source,
independent of OpenStreetMap, that the grader consults only for stores it cannot find in OSM.

A business registered under the model's store name at (or within 150 m of) the model's address is a real
store OSM lacks: "not in OSM", scored unverifiable like a store with unknown hours. A name that is mapped
or registered only elsewhere in San Francisco is a wrong address. A name found in neither source is a store
that does not exist, as far as either source knows.
"""

from __future__ import annotations

import json
import logging
import pickle
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from llmuni.config import Config
from llmuni.data.download import fetch
from llmuni.grader.geocode import parse_address

log = logging.getLogger(__name__)

NAME_MIN = 85  # name similarity (token set ratio of normalized names), as for name-only OSM matches
POINT = re.compile(r"POINT \((-?[\d.]+) (-?[\d.]+)\)")
STORE_NUMBER = re.compile(r"\b\d{3,}\b")  # "Walgreens #04529" -> "walgreens"
NOISE = re.compile(r"\b(?:the|inc|incorporated|llc|llp|lp|ltd|co|corp|corporation|company|n a|na|dba|store|shop|"
                   r"san francisco|sf)\b")
# Category words: a name made only of these ("Post Office", "Cafe") says nothing about which business it is.
GENERIC = frozenset(
    "a and of at on in bank banks atm pharmacy pharmacies drug drugs drugstore rx cafe caffe coffee espresso tea "
    "bakery bakeries bread cleaner cleaners cleaning dry laundry florist florists flower flowers market markets "
    "supermarket grocery groceries foods food hardware library branch post office station postal usps bike bikes "
    "bicycle bicycles cycle cycles books book bookstore bookshop".split())


def core_name(name: str) -> str:
    text = name.lower().replace("&", " and ").replace("’", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return " ".join(NOISE.sub(" ", STORE_NUMBER.sub(" ", text)).split())


def distinctive(core: str) -> bool:
    return any(token not in GENERIC for token in core.split())


@dataclass
class Registry:
    names: list[str]      # distinct core names (DBA and owner), distinctive ones only
    record_names: list[tuple[int, ...]]  # per record: indices of its names
    number: np.ndarray    # per record: house number, or -1
    street: np.ndarray    # per record: normalized street, or ""
    lat: np.ndarray       # per record; NaN where the city has no point
    lon: np.ndarray

    def near(self, name: str, point: tuple[float, float] | None, number: int | None, street: str | None,
             radius_m: float) -> bool:
        """A business registered under this name at this address or within radius_m of the point."""
        query = core_name(name)
        if not distinctive(query):
            return False
        here = np.zeros(len(self.number), dtype=bool)
        if point is not None:
            here |= _meters(point, self.lat, self.lon) <= radius_m
        if number is not None and street:
            here |= (self.number == number) & (self.street == street)
        candidates = sorted({self.names[j] for i in np.flatnonzero(here) for j in self.record_names[i]})
        return bool(candidates) and process.extractOne(query, candidates, scorer=fuzz.token_set_ratio, processor=None,
                                                       score_cutoff=NAME_MIN) is not None

    def anywhere(self, name: str) -> bool:
        """A business registered under this name anywhere in San Francisco."""
        query = core_name(name)
        return distinctive(query) and process.extractOne(
            query, self.names, scorer=fuzz.token_set_ratio, processor=None, score_cutoff=NAME_MIN) is not None


def registry_source(cfg: Config, previous: dict | None, refresh: bool = False) -> dict:
    """Download the registry unless the manifest already pins this file; its manifest entry."""
    dest = cfg.paths.raw / "sf_businesses.csv"
    entry = fetch(cfg.data.registry.url, dest, previous, refresh)
    rows = previous["rows"] if previous and previous.get("sha256") == entry["sha256"] else _count_rows(dest)
    return {**entry, "label": cfg.data.registry.label, "file": cfg.rel(dest), "rows": rows}


def fetch_registry(cfg: Config) -> Path:
    """The registry file, pinned in data/MANIFEST.json (sources.registry); `make data` pins it too."""
    manifest = json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))
    previous = manifest["sources"].get("registry")
    entry = registry_source(cfg, previous)
    if entry != previous:
        manifest["sources"]["registry"] = entry
        tmp = cfg.paths.manifest.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        tmp.replace(cfg.paths.manifest)
    return cfg.root / entry["file"]


def _count_rows(path: Path) -> int:
    return len(pd.read_csv(path, usecols=[0], dtype=str))


def load_registry(cfg: Config) -> Registry:
    csv = fetch_registry(cfg)
    sha = json.loads(cfg.paths.manifest.read_text(encoding="utf-8"))["sources"]["registry"]["sha256"]
    cache = cfg.paths.cache / f"registry_{sha[:16]}.pkl"
    if cache.exists():
        with cache.open("rb") as f:
            return pickle.load(f)
    registry = build_registry(pd.read_csv(csv, dtype=str, keep_default_na=False))
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("wb") as f:
        pickle.dump(registry, f)
    return registry


def build_registry(df: pd.DataFrame) -> Registry:
    """df: registry rows with dba_name, ownership_name, full_business_address and location (WKT point)."""
    parsed = [parse_address(a) if a else (None, None, None) for a in df["full_business_address"]]
    points = [POINT.match(p or "") for p in df["location"]]
    index: dict[str, int] = {}
    record_names = []
    for dba, owner in zip(df["dba_name"], df["ownership_name"]):
        cores = {core_name(dba or ""), core_name(owner or "")}
        record_names.append(tuple(index.setdefault(c, len(index)) for c in sorted(cores) if c and distinctive(c)))
    log.info("registry: %d active locations, %d distinct names", len(df), len(index))
    return Registry(
        names=list(index),
        record_names=record_names,
        number=np.array([p[0] if p[0] is not None else -1 for p in parsed]),
        street=np.array([p[1] or "" for p in parsed], dtype=object),
        lat=np.array([float(m.group(2)) if m else np.nan for m in points]),
        lon=np.array([float(m.group(1)) if m else np.nan for m in points]),
    )


def _meters(point: tuple[float, float], lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lat, lon = point
    x = np.radians(lons - lon) * np.cos(np.radians((lats + lat) / 2))
    with np.errstate(invalid="ignore"):
        return 6_371_000 * np.hypot(x, np.radians(lats - lat))
