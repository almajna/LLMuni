"""Local geocoder for San Francisco built from the pinned OSM extract: street addresses (exact house
number, else the nearest number on the same street) and street intersections ("Market St & 5th St")."""

from __future__ import annotations

import logging
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import osmium
import osmium.filter
import shapely.wkb
from rapidfuzz import fuzz, process

log = logging.getLogger(__name__)

SUFFIXES = {
    "st": "street", "str": "street", "ave": "avenue", "av": "avenue", "blvd": "boulevard", "dr": "drive",
    "rd": "road", "pl": "place", "ln": "lane", "ct": "court", "ter": "terrace", "terr": "terrace",
    "hwy": "highway", "pkwy": "parkway", "sq": "square", "aly": "alley", "cir": "circle", "wy": "way",
    "plz": "plaza", "bl": "boulevard",
}
ORDINAL_WORDS = {
    "first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th", "sixth": "6th",
    "seventh": "7th", "eighth": "8th", "ninth": "9th", "tenth": "10th", "eleventh": "11th", "twelfth": "12th",
}
UNIT = re.compile(r"(?:\b(?:suite|ste|unit|apt|fl|floor)\b\.?|#)\s*[\w-]+", re.IGNORECASE)
BARE_SUFFIXES = ("street", "avenue", "boulevard", "way", "drive", "place")  # tried when a name has none
CROSS = re.compile(r"\s+(?:&|and|at|@)\s+", re.IGNORECASE)
NUMBERED = re.compile(r"^\s*(\d+)[a-z]?(?:\s*-\s*\d+[a-z]?)?\s+(.+)$", re.IGNORECASE)
MAX_NUMBER_GAP = 60  # accept the nearest house number on the street if it is this close


def normalize_street(street: str) -> str:
    """'Mission St.' -> 'mission street'; 'Third Ave' -> '3rd avenue'; 'The Embarcadero' -> 'the embarcadero'."""
    tokens = re.sub(r"[.,]", " ", street.lower()).split()
    tokens = [ORDINAL_WORDS.get(t, t) for t in tokens]
    if tokens and tokens[-1] in SUFFIXES:
        tokens[-1] = SUFFIXES[tokens[-1]]
    return " ".join(tokens)


def parse_address(text: str) -> tuple[int | None, str | None, str | None]:
    """(house number, street, cross street) from a free-text SF address; city/state/zip are dropped."""
    first = UNIT.sub(" ", text.split(",")[0]).strip()
    if not first:
        return None, None, None
    parts = CROSS.split(first)
    if len(parts) == 2 and not NUMBERED.match(parts[0]):
        return None, normalize_street(parts[0]), normalize_street(parts[1])
    m = NUMBERED.match(first)
    if m:
        return int(m.group(1)), normalize_street(m.group(2)), None
    return None, normalize_street(first), None


@dataclass
class Geocoder:
    addresses: dict[str, tuple[np.ndarray, np.ndarray]]  # street -> (house numbers, (lat, lon) rows)
    street_nodes: dict[str, set[int]]  # street -> OSM node ids along it
    node_coords: dict[int, tuple[float, float]]
    _names: list[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._names = sorted(set(self.addresses) | set(self.street_nodes))

    def geocode(self, text: str | None) -> tuple[float, float] | None:
        if not text:
            return None
        number, street, cross = parse_address(text)
        if street is None:
            return None
        if cross is not None:  # "A & B": the first spelling pair that actually intersects
            for a in self._streets(street):
                for b in self._streets(cross):
                    point = self.intersection(a, b)
                    if point:
                        return point
            return None
        if number is None:
            return None
        for name in self._streets(street):
            if name in self.addresses:
                numbers, coords = self.addresses[name]
                gaps = np.abs(numbers - number)
                best = int(np.argmin(gaps))
                if gaps[best] <= MAX_NUMBER_GAP:
                    return float(coords[best][0]), float(coords[best][1])
        return None

    def intersection(self, a: str, b: str) -> tuple[float, float] | None:
        shared = self.street_nodes.get(a, set()) & self.street_nodes.get(b, set())
        if not shared:
            return None
        lat, lon = np.mean([self.node_coords[n] for n in shared], axis=0)
        return float(lat), float(lon)

    def _streets(self, street: str) -> list[str]:
        """Known street names a normalized name may mean: itself, with a suffix added ('haight' ->
        'haight street'), else the closest fuzzy match."""
        known = [s for s in (street, *(f"{street} {suffix}" for suffix in BARE_SUFFIXES))
                 if s in self.addresses or s in self.street_nodes]
        if known:
            return known
        found = process.extractOne(street, self._names, scorer=fuzz.ratio, score_cutoff=90)
        return [found[0]] if found else []


def build_geocoder(pbf: Path, cache: Path) -> Geocoder:
    """Geocoder for the extract; `cache` should name the pbf's content (e.g. its sha256)."""
    if cache.exists():
        with cache.open("rb") as f:
            return pickle.load(f)
    addresses: dict[str, list[tuple[int, float, float]]] = {}
    street_nodes: dict[str, set[int]] = {}
    node_coords: dict[int, tuple[float, float]] = {}
    wkb = osmium.geom.WKBFactory()
    objects = (
        osmium.FileProcessor(str(pbf))
        .with_locations()
        .with_areas(osmium.filter.KeyFilter("addr:housenumber"))
        .with_filter(osmium.filter.KeyFilter("addr:housenumber", "highway"))
    )
    for obj in objects:
        tags = obj.tags
        if obj.is_way() and "highway" in tags and "name" in tags:
            name = normalize_street(tags["name"])
            for node in obj.nodes:
                try:
                    node_coords[node.ref] = (node.lat, node.lon)
                except osmium.InvalidLocationError:
                    continue
                street_nodes.setdefault(name, set()).add(node.ref)
            continue
        if "addr:housenumber" not in tags or "addr:street" not in tags:
            continue
        m = re.match(r"\d+", tags["addr:housenumber"])
        if not m:
            continue
        if obj.is_node():
            lat, lon = obj.location.lat, obj.location.lon
        elif obj.is_area():
            try:
                point = shapely.wkb.loads(wkb.create_multipolygon(obj), hex=True).representative_point()
            except Exception:
                continue
            lat, lon = point.y, point.x
        else:
            continue
        addresses.setdefault(normalize_street(tags["addr:street"]), []).append((int(m.group()), lat, lon))
    table = {
        street: (np.array([r[0] for r in rows]), np.array([(r[1], r[2]) for r in rows]))
        for street, rows in addresses.items()
    }
    geocoder = Geocoder(table, street_nodes, node_coords)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("wb") as f:
        pickle.dump(geocoder, f)
    log.info("geocoder: %d addresses on %d streets, %d named streets",
             sum(len(v[0]) for v in table.values()), len(table), len(street_nodes))
    return geocoder
